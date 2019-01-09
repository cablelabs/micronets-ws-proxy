#!/usr/bin/env python

# WS server example

import asyncio
import websockets
import threading
import time
from quart import json
from http.server import BaseHTTPRequestHandler, HTTPServer

async def ws_connected (websocket, path):
    reader_task = asyncio.ensure_future (ws_reader (websocket, path))
    writer_task = asyncio.ensure_future (ws_writer (websocket, path))
    done, pending = await asyncio.wait( [reader_task, writer_task],
                                        return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel ()

async def ws_reader (websocket, path):
    print ("ws-test-server: ws_reader: started")
    global pending_requests
    while True:
        message = await websocket.recv ()
        print ("ws-test-server: ws_reader: < received: ", message)
        message_json = json.loads (message) ['message']
        if ('inResponseTo' in message_json):
            in_response_to_id = message_json ['inResponseTo']
            print (f"ws-test-server: ws_reader: Message {message_json['messageId']} "
                   f"is a response to {in_response_to_id} - signaling future #{in_response_to_id}")
            response_future = pending_requests.pop (in_response_to_id)
            if (not response_future):
                print (f"ws-test-server: ws_reader: No future found for message {in_response_to_id}!")
            else:
                response_future.set_result (message)
        if (message_json ['messageType'] == 'REST:REQUEST'):
            print (f"ws-test-server: ws_reader: Found rest {message_json ['method']} request for {message_json ['path']}")
            await handle_rest_request (websocket, message_json)
        # await consumer(message)

message_id = 1

async def handle_rest_request (websocket, message_json):
    global message_id
    print (f"handle_rest_request: {message_json ['method']} for {message_json ['path']}")
    if ('dataFormat' in message_json):
        print (f"handle_rest_request: message_body ({message_json [dataFormat]}):\n{message_json [messageBody]}")
    response = json.dumps ( {'message': {'messageId': message_id,
                                         'messageType': 'REST:RESPONSE',
                                         'requiresResponse': False,
                                         'inResponseTo': message_json ['messageId'],
                                         'statusCode': 200,
                                         'reasonPhrase': "OK"} } )
    message_id = message_id + 1
    print (f"handle_rest_request: sending response:", response)
    await websocket.send (response)

async def ws_writer (websocket, path):
    print ("ws-test-server: ws_writer: started")
    global pending_requests
    i = 1
    while True:
        # message = await producer()

        ##
        ## THIS IS JUST FOR TESTING - SEND A GET REQUEST...
        ##
        message = json.dumps ( {'message': {'messageId': i, 
                                            'messageType': 'REST:REQUEST',
                                            'requiresResponse': True,
                                            'method': 'GET',
                                            'path': '/micronets/v1/dhcp/subnets' }} )
        print ("ws-test-client: > sending client message: ", message)
        await websocket.send (message)
        print ("ws-test-client: > sent client message #", i)
        message_future = asyncio.get_event_loop ().create_future ()
        pending_requests [i] = message_future
        print ("ws-test-client: Waiting for future #", i)
        response = await message_future
        message = json.loads (response)
        print (f"ws-test-client: Got a response from future #{i}: ", json.dumps (message, indent=2))
        print (f"ws-test-client: Sleeping...")
        await asyncio.sleep (30)
        i += 1

class MyHTTPHandler (BaseHTTPRequestHandler):
    def do_HEAD (self):
        print ("Got HEAD request for", self.path)

class MyThread (threading.Thread):
    def __init__ (self):
        threading.Thread.__init__ (self)

    def run (self):
        print ("Starting HTTP server on port 5001...")
        server_address = ('', 5001)
        httpd = HTTPServer (server_address, MyHTTPHandler)
        httpd.serve_forever ()

pending_requests = {}

print ("Starting websocket-test-server...")
my_thread = MyThread ()
my_thread.start ()

websocket = websockets.serve (ws_connected, 'localhost', 8765)
asyncio.get_event_loop ().run_until_complete (websocket)
asyncio.get_event_loop ().run_forever ()
