#!/usr/bin/env python

# WS proxy server

import logging
import asyncio
import websockets
import time
import traceback
import sys
import pathlib
import ssl
from quart import json

logging.basicConfig (level=logging.DEBUG, filename="ws-proxy.log", 
                     format='%(asctime)s %(name)s: %(levelname)s %(message)s')
logger = logging.getLogger ('micronets-ws-proxy')

proxy_service_prefix = "/micronets/v1/ws-proxy/"

meetup_table = {}

class WSClient:
    def __init__ (self, meetup_id, websocket, hello_message=None):
        self.peer_arrival_future = asyncio.get_event_loop ().create_future ()
        self.meetup_id = meetup_id
        self.websocket = websocket
        self.hello_message = hello_message
        self.peer_arrival_future = asyncio.get_event_loop ().create_future ()

async def ws_connected (websocket, path):
    try:
        remote_address = websocket.remote_address
        logger.info (f"ws_connected: from {websocket.remote_address}, {path}")
        if (not path.startswith (proxy_service_prefix)):
            logger.warn (f"ws_connected: Unsupported path: {proxy_service_prefix} - CLOSING!")
            return
        meetup_id = path [len (proxy_service_prefix):]
        new_client = WSClient (meetup_id, websocket)
        logger.debug (f"ws_connected: client {id (new_client)}: (meetup_id: {meetup_id})")
        logger.debug (f"ws_connected: client {id (new_client)}: Waiting for HELLO message...")
        hello_message = await get_hello_message (websocket)
        logger.info (f"ws_connected: client {id (new_client)}: Received HELLO message:")
        logger.info (json.dumps (hello_message, indent=2))
        new_client.hello_message = hello_message
    except ConnectionClosed as cce:
        logger.info (f"ws_connected: client {id (new_client)} disconnected")
    except Exception as ex:
        logger.warn (f"ws_connected: client {id (new_client)}: Caught an exception processing hello message: {ex}")

    if (not meetup_id in meetup_table):
        client_list = []
        meetup_table [meetup_id] = client_list
    else:
        client_list = meetup_table [meetup_id]

    initial_message = None
    if (len (client_list) == 0):
        logger.debug (f"ws_connected: client {id (new_client)} is the first connected to {path}")
        client_list.append (new_client)
        logger.info (f"ws_connected: client {id (new_client)} - waiting for peer on {path}...")
        recv_task = asyncio.get_event_loop ().create_task (websocket.recv ())
        # We need to have a call to recv() in order to know if the socket closes while we're waiting
        done, pending = await asyncio.wait( [new_client.peer_arrival_future, recv_task],
                                            return_when=asyncio.FIRST_COMPLETED)
        if (not new_client.peer_arrival_future in done):
            raise Exception (f"Client {id (new_client)} failed/recved data before peer could attach to {path}")
        if (recv_task.done ()):
            # A message slipped through
            initial_message = recv_task.result ()
        else:
            recv_task.cancel ()
        peer_client = new_client.peer_arrival_future.result ()
        logger.info (f"ws_connected: client {id (new_client)}: peer {id (peer_client)} connected via {path}")
    else:
        if (len (client_list) > 1):
            logger.warn (f"ws_connected: client {id (new_client)}: meetup ID {meetup_id} "
                         f"already has {len (client_list)} clients - CLOSING!")
            return
        client_list.append (new_client)
        peer_client = client_list [0]
        logger.debug (f"ws_connected: client {id (new_client)}: signalling waiting peer {id (peer_client)}")
        peer_client.peer_arrival_future.set_result (new_client)

    logger.debug (f"ws_connected: client {id (new_client)}: Starting ws_reader()...")
    try:
        await ws_reader (new_client, peer_client, initial_message)
    except websockets.ConnectionClosed as cce:
        logger.info (f"ws_connected: client {id (new_client)} disconnected")
    except Exception as Ex:
        logger.warn (f"ws_connected: client {id (new_client)}: Caught an exception from ws_reader: {Ex}")
        traceback.print_exc (file=sys.stdout)
    finally:
        logger.info (f"ws_connected: client {id (new_client)}: Cleaning up...")
        client_list.remove (new_client)
        if (peer_client.websocket.open):
            await peer_client.websocket.close (reason=f"The peer connection from {remote_address} closed")
    # When this function returns, the websocket is closed

async def get_hello_message (websocket):
    raw_message = await websocket.recv ()
    message = json.loads (raw_message)
    if (not message):
        raise Exception (f"message does not appear to be json")
    hello_message = check_json_field (message, 'message', dict, True)
    message_id = check_json_field (hello_message, 'messageId', int, True)
    message_type = hello_message ['messageType']
    requires_response = check_json_field (hello_message, 'requiresResponse', bool, True)
    if (not message_type == "CONN:HELLO"):
        raise Exception (f"message does not appear to be a CONN:HELLO message (found {message_type})")
    return message

async def ws_reader (source_client, dest_client, initial_message):
    logger.debug (f"ws_reader: client {id (source_client)}: sending cached hello to client {id (dest_client)}")
    logger.debug ("        ", source_client.hello_message)
    await dest_client.websocket.send (json.dumps (source_client.hello_message))
    logger.info (f"ws_reader: client {id (source_client)}: Routing all messages to {id (dest_client)}")
    while True:
        if (initial_message):
            message = initial_message
            initial_message = None
        else:
            message = await source_client.websocket.recv ()
        logger.info (f"ws_reader: client {id (source_client)}: Copying message to client {id (dest_client)}")
        logger.debug (message)
        await dest_client.websocket.send (message)

def check_json_field (json_obj, field, field_type, required):
    '''Thrown an Exception of json_obj doesn't contain field and/or it isn't of type field_type'''
    if field not in json_obj:
        if required:
            raise Exception (f"message doesn't contain a '{field}' field")
        else:
            return None
    field_val = json_obj [field]
    if not isinstance (field_val, field_type):
        raise Exception (f"Field type for '{field}' field is not a {field_type}")
    return field_val

pending_requests = {}

proxy_port = 8765
ssl_context = ssl.SSLContext (ssl.PROTOCOL_TLS_SERVER)

# Setup the proxy's cert
proxy_cert_path = pathlib.Path (__file__).parent.parent.joinpath ('lib/micronets-ws-proxy.pkeycert.pem')
logger.info ("Loading proxy certificate from %s", proxy_cert_path)
ssl_context.load_cert_chain (proxy_cert_path)

# Enable client cert verification
root_cert_path = pathlib.Path (__file__).parent.parent.joinpath ('lib/micronets-ws-root.cert.pem')
logger.info ("Loading CA certificate from %s", root_cert_path)
ssl_context.load_verify_locations (cafile = root_cert_path)
ssl_context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
ssl_context.check_hostname = False

websocket = websockets.serve (ws_connected, 'localhost', proxy_port, ssl=ssl_context)

logger.info (f"Starting micronets websocket proxy on port {proxy_port}...")
asyncio.get_event_loop ().run_until_complete (websocket)
asyncio.get_event_loop ().run_forever ()
