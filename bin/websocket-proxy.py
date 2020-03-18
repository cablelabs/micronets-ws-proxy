#!/usr/bin/env python

# WS proxy server

import logging
import asyncio
import websockets
import pathlib
import ssl
import argparse
import os

from quart import json

logging.basicConfig (level='INFO',format='%(asctime)s %(name)s: %(levelname)s %(message)s')
logger = logging.getLogger ('micronets-ws-proxy')

bin_path = pathlib.Path (__file__).parent

# Change these if/when necessary (TODO: integrate argparse support)

arg_parser = argparse.ArgumentParser(description='The micronets websocket proxy service',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

arg_parser.add_argument ('--ca-certs', "-cac", required=False, action='store', type=open,
                         default = os.environ.get('MICRONETS_WSPROXY_CA_CERT'),
                         help="add the given CA cert to the list of trusted root certs (or MICRONETS_WSPROXY_CA_CERT)")
arg_parser.add_argument ('--ca-path', "-cap", required=False, action='store', type=str,
                         default = os.environ.get('MICRONETS_WSPROXY_CA_PATH'),
                         help="add the given CA cert to the list of trusted root certs (or MICRONETS_WSPROXY_CA_PATH)")
arg_parser.add_argument ('--server-cert', "-sc", required=True, action='store', type=str,
                         default = os.environ.get('MICRONETS_WSPROXY_SERVER_CERT'),
                         help="use the given cert and private key file for the WSS server (or MICRONETS_WSPROXY_SERVER_CERT)")
arg_parser.add_argument ('--bind-address', "-a", required=False, action='store', type=str,
                         default=os.environ.get('MICRONETS_WSPROXY_BIND_ADDRESS') or "0.0.0.0",
                         help="specify the address to bind the MUD manager to (or MICRONETS_WSPROXY_BIND_ADDRESS)")
arg_parser.add_argument ('--bind-port', "-p", required=False, action='store', type=int,
                         default = os.environ.get('MICRONETS_WSPROXY_BIND_PORT') or 5050,
                         help="specify the port to bind the MUD manager to (or MICRONETS_WSPROXY_BIND_PORT)")
arg_parser.add_argument ('--url-path-prefix', "-sp", required=False, action='store', type=str,
                         default = os.environ.get('MICRONETS_WSPROXY_URL_PATH_PREFIX') or "/micronets/v1/ws-proxy/",
                         help="the URL prefix required for any clients to connect (or MICRONETS_WSPROXY_URL_PATH_PREFIX)")
arg_parser.add_argument ('--report-interval', "-ri", required=False, action='store', type=int,
                         default = os.environ.get('MICRONETS_WSPROXY_REPORT_INTERVAL') or 0,
                         help="the amount of time to wait between generating reports (or MICRONETS_WSPROXY_PATH_PREFIX)"
                              " (0: disabled)")
args = arg_parser.parse_args ()

logger.info(f"Bind address: {args.bind_address}")
logger.info(f"Bind port: {args.bind_port}")
logger.info(f"Server cert/key: {args.server_cert}")
logger.info(f"CA path: {args.ca_path}")
logger.info(f"Additional CA certs: {args.ca_certs.name if args.ca_certs else None}")
logger.info(f"URL Path Prefix: {args.url_path_prefix}")
logger.info(f"Report Interval: {args.report_interval}")

meetup_table = {}


class WSClient:
    def __init__ (self, meetup_id, websocket, hello_message=None, peer_client=None, 
                        ping_interval_s = 10, ping_timeout_s=10):
        self.meetup_id = meetup_id
        self.websocket = websocket
        self.peer_arrival_future = asyncio.Future ()
        self.ping_timeout_future = asyncio.Future ()
        self.ping_task = None
        self.ping_interval_s = ping_interval_s
        self.ping_timeout_s = ping_timeout_s
        self.hello_message = hello_message
        self.peer_client = peer_client
        self.start_pings ()

    def __str__ (self):
        if self.hello_message and 'message' in self.hello_message and 'peerId' in self.hello_message['message']:
            # TODO: REMOVE ME
            logger.info (f"message: {self.hello_message}")
            peer_id = self.hello_message ['message']['peerId']
        else:
            peer_id = "none"
        return f"Client {id (self)} (peer: {peer_id}) @ {self.websocket.remote_address})"

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
        recv_task = asyncio.get_event_loop ().create_task (self.websocket.recv ())
        logger.info (f"ws_client {id (self)}: wait_for_peer: waiting for peer on {self.meetup_id}...")
        # We need to have a call to recv() in order to know if the socket closes while we're waiting
        done, pending = await asyncio.wait( [self.peer_arrival_future, recv_task, self.ping_timeout_future],
                                            return_when=asyncio.FIRST_COMPLETED)
        if (recv_task.done ()):
            message = recv_task.result()  # This will throw an exception if the task raised one
            if (message):
                # A message slipped through
                logger.warning (f"ws_client {id (self)}: wait_for_peer: A message was received while waiting for a peer - DROPPING: {message}")
        else:
            recv_task.cancel ()
        if (not self.peer_arrival_future in done):
            raise Exception (f"Client {id (self)} failed/recv-ed data before a peer could attach to {self.meetup_id}")
        self.peer_client = self.peer_arrival_future.result ()
        self.peer_arrival_future = None
        return self.peer_client

    def set_peer (self, peer):
        if (self.peer_arrival_future):
            self.peer_arrival_future.set_result (peer)
        self.peer_client = peer

    def start_pings (self):
        logger.debug (f"ws_client {id (self)}: Starting pings every {self.ping_interval_s} seconds ({self.ping_timeout_s} timout)")
        self.stop_pings ()
        self.ping_task = asyncio.get_event_loop ().create_task (self.ping_peer ())

    def stop_pings (self):
        if (self.ping_task):
            logger.debug (f"ws_client {id (self)}: Stopping pings")
            self.ping_task.cancel ()
            self.ping_task = None

    async def ping_peer (self):
        while (self.ping_interval_s and self.ping_interval_s > 0):
            ping_send_time = asyncio.get_event_loop ().time ()
            logger.debug (f"ws_client {id (self)}: ping_peer: Sending ping...")
            pong_waiter = await (self.websocket.ping ())
            logger.debug (f"ws_client {id (self)}: ping_peer: Waiting for pong...")
            done, pending = await asyncio.wait ([pong_waiter], timeout=self.ping_timeout_s)
            if (not pong_waiter in done):
                logger.warning (f"ws_client {id (self)}: ping_peer: ping timeout - DISCONNECTING")
                pong_waiter.cancel ()
                close_reason = f"Ping timed out ({self.ping_timeout_s} seconds)"
                if self.ping_timeout_future:
                    self.ping_timeout_future.set_result (close_reason)
                await self.close_websocket (1002, close_reason)
                return
            pong_received_time = asyncio.get_event_loop ().time ()
            logger.debug (f"ws_client {id (self)}: ping_peer: pong received after {pong_received_time-ping_send_time}")
            wait_time = ping_send_time + self.ping_interval_s - pong_received_time
            logger.debug (f"ws_client {id (self)}: ping_peer: Sending next ping in {wait_time} seconds...")
            await asyncio.sleep (wait_time)

    async def communicate_with_peer (self):
        relay_task = self.relay_messages_to_peer ()
        done, pending = await asyncio.wait ([self.ping_timeout_future, relay_task],
                                            return_when=asyncio.FIRST_COMPLETED)
        if relay_task in done:
            logger.info (f"ws_client {id (self)}: communicate_with_peer: "
                         f"relay_messages_to_peer completed/terminated")
            self.ping_timeout_future.cancel()
            self.ping_timeout_future = None
            # Note: result should throw the exception returned via the Future if there's one
            #       See https://docs.python.org/3.6/library/asyncio-task.html#asyncio.Future
            return relay_task.result ()

        if self.ping_timeout_future in done:
            relay_task.cancel ()
            temp_future = self.ping_timeout_future
            self.ping_timeout_future = None
            result = temp_future.result ()
            logger.info (f"ws_client {id (self)}: communicate_with_peer: "
                         f"communication terminated with reason: {result}")
            raise Exception (f"communication was cancelled: {result}")

    async def relay_messages_to_peer (self):
        try:
            logger.debug (f"ws_client {id (self)}: relay_messages_to_peer: sending cached hello to client {id (self.peer_client)}")
            logger.debug ("        %s", self.hello_message)
            await self.peer_client.send_message (json.dumps (self.hello_message))
            logger.info (f"ws_client {id (self)}: relay_messages_to_peer: Routing all messages to {id (self.peer_client)}")
            while True:
                message = await self.websocket.recv ()
                logger.info (f"ws_client {id (self)}: relay_messages_to_peer: Copying message to client {id (self.peer_client)}")
                logger.debug (message)
                await self.peer_client.send_message (message)
        finally:
            logger.info(f"ws_client {id (self)}: relay_messages_to_peer: terminating")

    def cleanup_before_close (self):
        self.stop_pings ()

    async def close_websocket (self, reasonCode, reasonPhrase):
        try:
            self.cleanup_before_close ()
            logger.debug (f"ws_client {id (self)}: close_websocket: closing websocket")
            await self.websocket.close (code = reasonCode, reason = reasonPhrase)
        except Exception as ex:
            logger.debug (f"ws_client {id (self)}: close_websocket: Exception on closing connection: {ex}")

    async def send_message (self, message):
        return await self.websocket.send (message)

    async def peer_disconnected (self, peer):
        await self.close_websocket (reasonCode=1002, reasonPhrase=f"the peer websocket disconnected")

async def ws_connected (websocket, path):
    try:
        new_client = None
        peer_client = None
        client_list = None
        remote_address = websocket.remote_address
        logger.info (f"ws_connected: from {remote_address}, {path}")
        if (not path.startswith (args.url_path_prefix)):
            logger.warning (f"ws_connected: Error: {path} doesn't start with {args.url_path_prefix} - CLOSING!")
            return
        meetup_id = path [len (args.url_path_prefix):]
        if (not meetup_id in meetup_table):
            client_list = []
            meetup_table [meetup_id] = client_list
        else:
            client_list = meetup_table [meetup_id]
        if (len (client_list) >= 2):
            logger.warning (f"ws_connected: client {id (new_client)}: meetup ID {meetup_id} "
                            f"already has {len (client_list)} clients - CLOSING connection from {remote_address}.")
            return

        new_client = WSClient (meetup_id, websocket)
        client_list.append (new_client)

        perform_connection_report ()

        logger.debug (f"ws_connected: client {id (new_client)}: (meetup_id: {meetup_id})")
        logger.debug (f"ws_connected: client {id (new_client)}: Waiting for HELLO message...")
        hello_message = await new_client.recv_hello_message ()
        logger.info (f"ws_connected: client {id (new_client)}: Received HELLO message:")
        logger.info (json.dumps (hello_message, indent=2))

        # Here's where we'd add any accept criteria based on the HELLO message

        if (len (client_list) == 1):
            logger.info (f"ws_connected: client {id (new_client)} is the first connected to {path}")
            perform_connection_report ()
            peer_client = await new_client.wait_for_peer ()
        else:
            logger.info (f"ws_connected: client {id (new_client)} is the second connected to {path}")
            peer_client = client_list [0]
            new_client.set_peer (peer_client)
            peer_client.set_peer (new_client)
            perform_connection_report ()

        # Will just relay data between the clients until someone disconnects...
        await new_client.communicate_with_peer ()
        logger.info (f"ws_connected: client {id (new_client)} relay_messages_to_peer() returned")
    except websockets.ConnectionClosed as cce:
        logger.info (f"ws_connected: client {id (new_client)} disconnected normally")
    except Exception as Ex:
        logger.info (f"ws_connected: client {id (new_client)}: Caught an exception from ws_reader: {Ex}")
    finally:
        logger.info (f"ws_connected: client {id (new_client)}: Cleaning up...")
        if (new_client in client_list):
            client_list.remove (new_client)
            if len(client_list) == 0:
                meetup_table.pop (meetup_id)
            perform_connection_report()
        if (new_client):
            new_client.cleanup_before_close ()
        if (peer_client):
            await peer_client.peer_disconnected (new_client)

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

def start_websocket_reporting (report_interval_s):
    report_task = asyncio.get_event_loop ().create_task (perform_periodic_connection_reports (report_interval_s))

def perform_connection_report ():
        report = f"\n---------------------------------------------------------------------------------------\n"
        report += "WEBSOCKET MEETUP TABLE REPORT FOR {}:{}/{}\n"\
                  .format (args.bind_address, args.bind_port, args.url_path_prefix)
        for meetup_id, meetup_list in meetup_table.items():
            report += "\n  MEETUP ID: {}\n".format (meetup_id)
            if len(meetup_list) > 0:
                client_1 = str (meetup_list[0])
            else:
                client_1 = "Not connected"
            if len(meetup_list) > 1:
                client_2 = str (meetup_list[1])
            else:
                client_2 = "Not connected"
            report += "    Client 1: {}\n".format (client_1)
            report += "    Client 2: {}\n".format (client_2)
        report += f"----------------------------------------------------------------------------------------\n"
        logger.info (report)

async def perform_periodic_connection_reports (report_interval_s):
    logger.info("Performing websocket connection reports every %s seconds", report_interval_s)
    while True:
        await asyncio.sleep (report_interval_s)
        perform_connection_report ()

ssl_context = ssl.SSLContext (ssl.PROTOCOL_TLS_SERVER)

# Setup the proxy's cert
logger.info ("Loading proxy certificate/key from %s", args.server_cert)
ssl_context.load_cert_chain(args.server_cert)

# Enable client cert verification
ssl_context.load_verify_locations (cafile = args.ca_certs.name if args.ca_certs else None, capath=args.ca_path)

ssl_context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
ssl_context.check_hostname = False

websocket = websockets.serve (ws_connected, args.bind_address, args.bind_port, ssl=ssl_context)

if args.report_interval > 0:
    start_websocket_reporting (args.report_interval)

logger.info (f"Starting micronets websocket proxy on {args.bind_address} port {args.bind_port}...")
logger.info (f"Clients may connect to wss://{args.bind_address}:{args.bind_port}{args.url_path_prefix}*")
asyncio.get_event_loop ().run_until_complete (websocket)
asyncio.get_event_loop ().run_forever ()
