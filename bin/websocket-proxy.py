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
import configparser

from threading import Timer
from quart import json

bin_path = pathlib.Path (__file__).parent

# Change these if/when necessary

logfile_path = bin_path.parent.joinpath ('ws-proxy.log')
logfile_mode = 'w'  # 'w' clears the log at startup, 'a' appends to the existing log file
proxy_bind_address = "localhost"
proxy_port = 5050
proxy_service_prefix = "/micronets/v1/ws-proxy/"
proxy_cert_path = bin_path.parent.joinpath ('lib/micronets-ws-proxy.pkeycert.pem')
root_cert_path = bin_path.parent.joinpath ('lib/micronets-ws-root.cert.pem')

meetup_table = {}

class WSClient:
    def __init__ (self, meetup_id, websocket, hello_message=None, peer_client=None, ping_timeout_limit=10):
        self.meetup_id = meetup_id
        self.websocket = websocket
        self.hello_message = hello_message
        self.peer_arrival_future = None
        self.ping_timeout_limit_s = ping_timeout_limit
        self.ping_timeout_timer = None
        self.hello_message = hello_message
        self.peer_client = peer_client
        self.start_ping_timer ()

    async def recv_hello_message (self):
        raw_message = await self.websocket.recv ()
        message = json.loads (raw_message)
        if (not message):
            raise Exception (f"message does not appear to be json")
        hello_message = check_json_field (message, 'message', dict, True)
        message_id = check_json_field (hello_message, 'messageId', int, True)
        message_type = hello_message ['messageType']
        requires_response = check_json_field (hello_message, 'requiresResponse', bool, True)
        if (not message_type == "CONN:HELLO"):
            raise Exception (f"message does not appear to be a CONN:HELLO message (found {message_type})")
        self.hello_message = message
        return self.hello_message

    async def get_hello_message (self):
        return self.hello_message
    
    async def wait_for_peer (self):
        self.peer_arrival_future = asyncio.get_event_loop ().create_future ()
        recv_task = asyncio.get_event_loop ().create_task (self.websocket.recv ())
        logger.info (f"ws_client {id (self)}: wait_for_peer: waiting for peer on {self.meetup_id}...")
        # We need to have a call to recv() in order to know if the socket closes while we're waiting
        done, pending = await asyncio.wait( [self.peer_arrival_future, recv_task],
                                            return_when=asyncio.FIRST_COMPLETED)
        if (not self.peer_arrival_future in done):
            raise Exception (f"Client {id (self)} failed/recv-ed data before peer could attach to {path}")
        if (recv_task.done ()):
            initial_message = recv_task.result ()
            if (initial_message):
                # A message slipped through
                logger.warn (f"ws_client {id (self)}: wait_for_peer: A message was received while waiting for a peer - DROPPING: {message}")
        else:
            recv_task.cancel ()
        self.peer_client = self.peer_arrival_future.result ()
        self.peer_arrival_future = None
        return self.peer_client

    def set_peer (self, peer):
        if (self.peer_arrival_future):
            self.peer_arrival_future.set_result (peer)
        self.peer_client = peer

    def start_ping_timer (self):
        if (self.ping_timeout_limit_s and self.ping_timeout_limit_s > 0):
            if self.ping_timeout_timer:
                self.ping_timeout_timer.cancel ()
            self.ping_timeout_timer = Timer (self.ping_timeout_limit_s, self.ping_timeout)
            self.ping_timeout_timer.start ()

    def ping_timeout (self):
        logger.warn (f"ws_client {id (self)}: ping timeout")

    async def clean_up (self):
        if (self.websocket.open):
            await self.websocket.close (reason=f"The peer connection from {self.websocket.remote_address} closed")

    async def send_message (self, message):
        return await self.websocket.send (message)

    async def relay_messages_to_peer (self):
        logger.debug (f"ws_client {id (self)}: relay_messages_to_peer: sending cached hello to client {id (self.peer_client)}")
        logger.debug ("        ", self.hello_message)
        await self.peer_client.send_message (json.dumps (self.hello_message))
        logger.info (f"ws_client {id (self)}: relay_messages_to_peer: Routing all messages to {id (self.peer_client)}")
        while True:
            message = await self.websocket.recv ()
            logger.info (f"ws_client {id (self)}: relay_messages_to_peer: Copying message to client {id (self.peer_client)}")
            logger.debug (message)
            await self.peer_client.send_message (message)
        
async def ws_connected (websocket, path):
    try:
        remote_address = websocket.remote_address
        logger.info (f"ws_connected: from {remote_address}, {path}")
        if (not path.startswith (proxy_service_prefix)):
            logger.warn (f"ws_connected: Unsupported path: {proxy_service_prefix} - CLOSING!")
            return
        meetup_id = path [len (proxy_service_prefix):]
        if (not meetup_id in meetup_table):
            client_list = []
            meetup_table [meetup_id] = client_list
        else:
            client_list = meetup_table [meetup_id]
        if (len (client_list) >= 2):
            logger.warn (f"ws_connected: client {id (new_client)}: meetup ID {meetup_id} "
                         f"already has {len (client_list)} clients - CLOSING connection from {remote_address}.")
            return

        new_client = WSClient (meetup_id, websocket)
        client_list.append (new_client)

        logger.debug (f"ws_connected: client {id (new_client)}: (meetup_id: {meetup_id})")
        logger.debug (f"ws_connected: client {id (new_client)}: Waiting for HELLO message...")
        hello_message = await new_client.recv_hello_message ()
        logger.info (f"ws_connected: client {id (new_client)}: Received HELLO message:")
        logger.info (json.dumps (hello_message, indent=2))

        # Here's where we'd add any accept criteria based on the HELLO message

        if (len (client_list) == 1):
            logger.debug (f"ws_connected: client {id (new_client)} is the first connected to {path}")
            await new_client.wait_for_peer ()
        else:
            logger.debug (f"ws_connected: client {id (new_client)} is the second connected to {path}")
            peer_client = client_list [0]
            new_client.set_peer (peer_client)
            peer_client.set_peer (new_client)

        # Will just relay until someone disconnects...
        await new_client.relay_messages_to_peer ()
        logger.info (f"ws_connected: client {id (new_client)} relay_messages_to_peer() returned")
    except websockets.ConnectionClosed as cce:
        logger.info (f"ws_connected: client {id (new_client)} disconnected")
    except Exception as Ex:
        logger.warn (f"ws_connected: client {id (new_client)}: Caught an exception from ws_reader: {Ex}")
        traceback.print_exc (file=sys.stdout)
    finally:
        logger.info (f"ws_connected: client {id (new_client)}: Cleaning up...")
        client_list.remove (new_client)
        await new_client.clean_up ()
    # When this function returns, the websocket is closed

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

logging.basicConfig (level=logging.DEBUG, filename=logfile_path, filemode=logfile_mode,
                     format='%(asctime)s %(name)s: %(levelname)s %(message)s')

logger = logging.getLogger ('micronets-ws-proxy')

ssl_context = ssl.SSLContext (ssl.PROTOCOL_TLS_SERVER)

# Setup the proxy's cert
logger.info ("Loading proxy certificate from %s", proxy_cert_path)
ssl_context.load_cert_chain (proxy_cert_path)

# Enable client cert verification
logger.info ("Loading CA certificate from %s", root_cert_path)
ssl_context.load_verify_locations (cafile = root_cert_path)
ssl_context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
ssl_context.check_hostname = False

websocket = websockets.serve (ws_connected, proxy_bind_address, proxy_port, ssl=ssl_context)

logger.info (f"Starting micronets websocket proxy on {proxy_bind_address} port {proxy_port}...")
asyncio.get_event_loop ().run_until_complete (websocket)
asyncio.get_event_loop ().run_forever ()
