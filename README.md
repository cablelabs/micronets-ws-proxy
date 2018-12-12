# Micronets Infrastructure Components

This repository is for managing tools, data, and other cross-component Micronets elements. 

## 1. The websocket proxy

The websocket proxy allows 2 websocket clients to connect to each other using
outbound connections to a common URI.

### 1.1 Quick Start

#### 1.1.0 Checkout out the Micronets infrastructure project

From a directory containing your micronets repositories (e.g. "~/projects/micronets")

```
git clone git@github.com:cablelabs/micronets-infrastructure.git
```

This will create a "micronets-infrastructure" containing the websocket proxy.

#### 1.1.1 Setting the proxy parameters

For now, the websocket proxy's parameters are stored in the bin/websocket-test-client.py source.
If you're running the proxy on your local machine (for testing), you don't need to change the
defaults - which should be something like this:

```
proxy_bind_address = "localhost"
proxy_port = 5050
proxy_service_prefix = "/micronets/v1/ws-proxy/"
proxy_cert_path = bin_path.parent.joinpath ('lib/micronets-ws-proxy.pkeycert.pem')
root_cert_path = bin_path.parent.joinpath ('lib/micronets-ws-root.cert.pem')
```

If you have a test server to run the proxy on, most likely the only param you would want
to change is the `proxy_bind_address` - which you can set to `0.0.0.0` to listen on all
interfaces, or set to the IP address of the interface you want to expose the proxy on.

#### 1.1.2 Setting up the websocket proxy environment

Note that the Python websocket proxy requires python 3.6, pip, and the "virtualenv" package. 
All other dependancies are installed into the virtualenv for the websocket proxy.

The python virtualenv with the library dependancies is setup by performing the following steps:

From the python-infrastructure directory:

```
virtualenv --clear -p $(which python3.6) $PWD/virtualenv
source virtualenv/bin/activate
pip install -r requirements.txt 
```

#### 1.1.3 Running the websocket proxy manually

From the python-infrastructure directory, perform the following steps:

Setup the virtualenv:
```
bin/setup-virtualenv.sh
```

Start the proxy:
```
virtualenv/bin/python bin/websocket-proxy.py
```

You should see output similar to the following:

```
2018-12-10 12:56:07,310 micronets-ws-proxy: INFO Loading proxy certificate from lib/micronets-ws-proxy.pkeycert.pem
2018-12-10 12:56:07,312 micronets-ws-proxy: INFO Loading CA certificate from lib/micronets-ws-root.cert.pem
2018-12-10 12:56:07,313 micronets-ws-proxy: INFO Starting micronets websocket proxy on 0.0.0.0 port 5050...
```

The websocket proxy can be stopped via Control-C. But it will also be stopped if/when the terminal session 
the proxy is started from terminates. It can also be run via "nohup". But running it via systemd is the
preferred method (see below).

#### 1.1.4 Running the websocket proxy using systemd

From the python-infrastructure directory, perform the following steps to setup the virtualenv:

Setup the virtualenv:
```
bin/setup-virtualenv.sh
```

An example systemd service control file `micronets-ws-proxy.service` is provided in the source 
distribution. The "WorkingDirectory" and "ExecStart" entries need to be modified to match the
location of the websocket proxy virtualenv and python program. And the "User" and "Group" settings
should be set to the "micronets" user (or commented out to run as "root") E.g.

```
WorkingDirectory=/home/micronets-dev/Projects/micronets/micronets-infrastructure
ExecStart=/home/micronets-dev/Projects/micronets/micronets-infrastructure/virtualenv/bin/python bin/websocket-proxy.py
User=micronets-dev
Group=micronets-dev
```

The systemctl service unit file can be installed for the systemd service using:

```
sudo systemctl enable $PWD/micronets-ws-proxy.service
sudo systemctl daemon-reload
```

Once the micronets-ws-proxy service is installed, it can be run using:

```
sudo systemctl start micronets-ws-proxy.service
```

Where the logging will be stored is system-dependent. On Ubuntu 16.04 systems
logging will be written to `/var/log/syslog`.

The status of the proxy can be checked using:

```
sudo systemctl status micronets-ws-proxy
```

and the proxy stopped using:

```
sudo systemctl stop micronets-ws-proxy
```

### 1.2 Setting up proxy authorization using certificates

This repository contains pre-generated certificates for testing/prototyping. 
For a discreet/production installation, new certificates should be generated
and deployed. The instructions below detail a basic prodedure for generating
new certificates.

#### 1.2.1 Generating the shared root certificate used for websocket communication:

This will produce the root certificate and key for validating/generating
leaf certificates used by peers of the websocket proxy:

```
bin/gen-root-cert --cert-basename lib/micronets-ws-root \
    --subject-org-name "Micronets Websocket Root Cert" \
    --expiration-in-days 3650
```

The shared root cert will be the basis for trust for all the entities
communicating via the websocket proxy. The websocket proxy will only 
trust peers that present a cert (and can accept a challenge from) the
proxy.

The `micronets-ws-root.key.pem` file generated by this script should
only be retained for the purposes of generating new leaf certs for the
websocket peers.

#### 1.2.2 To generate the cert to be used for the Websocket Proxy:

```
bin/gen-leaf-cert --cert-basename lib/micronets-ws-proxy \
    --subject-org-name "Micronets Websocket Proxy Cert" \
    --expiration-in-days 3650 \
    --ca-certfile lib/micronets-ws-root.cert.pem \
    --ca-keyfile lib/micronets-ws-root.key.pem

cat lib/micronets-ws-proxy.cert.pem lib/micronets-ws-proxy.key.pem > lib/micronets-ws-proxy.pkeycert.pem
```

The `lib/micronets-ws-proxy.pkeycert.pem` file must be deployed with the 
Micronets websocket proxy and well-protected. The `lib/micronets-ws-root.cert.pem`
must be added to the Proxy's list of trusted CAs. (and should really be the only
CA enabled for the proxy)

#### 1.2.3 Generating the cert to be used for the Micronets Manager:

```
bin/gen-leaf-cert --cert-basename lib/micronets-manager \
    --subject-org-name "Micronets Manager Websocket Client Cert" \
    --expiration-in-days 3650 \
    --ca-certfile lib/micronets-ws-root.cert.pem \
    --ca-keyfile lib/micronets-ws-root.key.pem

cat lib/micronets-manager.cert.pem lib/micronets-manager.key.pem > lib/micronets-manager.pkeycert.pem
```

The `lib/micronets-manager.pkeycert.pem` file must be deployed with the 
Micronets Manager to connect to the websocket proxy and `lib/micronets-ws-root.cert.pem` 
must be added to the Micronet's Manager CA list.

#### 1.2.4 To generate the cert to be used for the Micronets Gateway Service:

```
bin/gen-leaf-cert --cert-basename lib/micronets-gateway-service \
    --subject-org-name "Micronets Gateway Service Websocket Client Cert" \
    --expiration-in-days 3650 \
    --ca-certfile lib/micronets-ws-root.cert.pem \
    --ca-keyfile lib/micronets-ws-root.key.pem

cat lib/micronets-dhcp-manager.cert.pem lib/micronets-dhcp-manager.key.pem > lib/micronets-dhcp-manager.pkeycert.pem
```

The `lib/micronets-manager.pkeycert.pem` file must be deployed with the 
Micronets Manager to connect to the websocket proxy and `lib/micronets-ws-root.cert.pem` 
must be added to the Micronet's Manager CA list.

#### 1.2.5 To generate the cert to be used by the test client:

```
bin/gen-leaf-cert --cert-basename lib/micronets-ws-test-client \
    --subject-org-name "Micronets Websocket Test Client Cert" \
    --expiration-in-days 3650 \
    --ca-certfile lib/micronets-ws-root.cert.pem \
    --ca-keyfile lib/micronets-ws-root.key.pem

cat lib/micronets-ws-test-client.cert.pem lib/micronets-ws-test-client.key.pem > lib/micronets-ws-test-client.pkeycert.pem
```

### 1.3 Testing the micronets websocket proxy

#### 1.3.1 Downloading the micronets infrastructure source (containing the test client)

```
mkdir -p ~/projects/micronets
cd ~/projects/micronets
git clone git@github.com:cablelabs/micronets-infrastructure.git
cd micronets-infrastructure
mkvirtualenv -r requirements.txt -a $PWD -p $(which python3) micronets-websocket-proxy
```

#### 1.3.2 Connecting the websocket test client to the proxy (using the same URI as a connected micronets gateway)

The websocket test client takes all its parameters via arguments. Use "-h" to see the options. A typical test session would look like this:

```
workon micronets-websocket-proxy
bin/websocket-test-client.py --client-cert lib/micronets-manager.pkeycert.pem --ca-cert lib/micronets-ws-root.cert.pem  wss://74.207.229.106:5050/micronets/v1/ws-proxy/micronets-dhcp-0001
```

The test client should startup with log messages similar to:

```
Loading test client certificate from lib/micronets-manager.pkeycert.pem
Loading CA certificate from lib/micronets-ws-root.cert.pem
ws-test-client: Starting stdin reader...
ws-test-client: Opening websocket to wss://74.207.229.106:5050/micronets/v1/ws-proxy/micronets-dhcp-0001...
ws-test-client: Connected to wss://74.207.229.106:5050/micronets/v1/ws-proxy/micronets-dhcp-0001.
ws-test-client: Sending HELLO message...
ws-test-client: > sending hello message:  {"message": {"messageId": 0, "messageType": "CONN:HELLO", "requiresResponse": false, "peerClass": "micronets-ws-test-client", "peerId": "12345678"}}
ws-test-client: Waiting for HELLO message...
ws-test-client: process_hello_messages: Received message: {'message': {'messageId': 0, 'messageType': 'CONN:HELLO', 'peerClass': 'micronets-dhcp-service', 'peerId': '12345678', 'requiresResponse': False}}
ws-test-client: process_hello_messages: Received HELLO message
ws-test-client: HELLO handshake complete.
MyHTTPServerThread.__init__(): state: ready
ws-test-client: Starting event loop...
ws-test-client: receive: starting...
MyHTTPServerThread: Starting HTTP server on localhost port 5001...
```

#### 1.3.3 Using the websocket test client's built-in HTTP proxy to test the websocket

To use the websocket-test-client’s built-in server to test the proxying of an HTTP REST request and response to the Micronet’s DHCP server running on the gateway, requests can be sent to the port specified using the "--http-proxy-port" argument (or port "5001" if not specified).

e.g.

```
curl -H "Content-Type: application/json" http://localhost:5001/micronets/v1/dhcp/subnets
```

When sending a request via the built-in http test server, the websocket-test-client program will encapsulate the HTTP request sent by curl into a “REST:REQUEST” websocket message and send it to the proxy - which will send it to the gateway. After processing the request, the micronets-dhcp server will send a response, encapsulate it in a “REST:RESPONSE” websocket message, send it to the proxy - which will send it to the websocket-test-client program. The websocket-test-client program will then take the contents out of the websocket message and send the response to curl.

See below for details on the micronets websocket proxy message format.

## 2. The MUD Manager

### 2.1 Quick Start

#### 2.1.1 Running the MUD Manager manually

From the python-infrastructure directory, perform the following steps:

Setup the virtualenv:
```
bin/setup-virtualenv-mudmanager.sh
```

Start the MUD manger:
```
micronets-mud-manager.virtualenv/bin/python bin/mudWS.py
```
(or if you plan to run the MUD Manager repeatedly, for debug/development)
```
source micronets-mud-manager.virtualenv/bin/activate
python bin/mudWS.py
```

You should see output similar to the following:
```
12/Dec/2018:22:53:57] ENGINE Bus STARTING
CherryPy Checker:
The Application mounted at '' has an empty config.

[12/Dec/2018:22:53:57] ENGINE Started monitor thread 'Autoreloader'.
[12/Dec/2018:22:53:57] ENGINE Serving on http://0.0.0.0:8888
[12/Dec/2018:22:53:57] ENGINE Bus STARTED
```

The MUD Manager can be stopped via Control-C. But it will also be stopped if/when the terminal session 
the proxy is started from terminates. It can also be run via "nohup". But running it via systemd is the
preferred method (see below).

#### 2.1.2 Running the MUD Manager using systemd

From the python-infrastructure directory, perform the following steps to setup the virtualenv:

Setup the virtualenv:
```
bin/setup-virtualenv-mudmanager.sh
```

An example systemd service control file `micronets-mud-manager.service` is provided in the source 
distribution. The "WorkingDirectory" and "ExecStart" entries need to be modified to match the
location of the MUD Manager virtualenv and python program. And the "User" and "Group" settings
should be set to the "micronets" user (or commented out to run as "root") E.g.

```
WorkingDirectory=/home/micronets-dev/Projects/micronets/micronets-infrastructure
ExecStart=/home/micronets-dev/Projects/micronets/micronets-infrastructure/virtualenv/bin/python bin/websocket-proxy.py
User=micronets-dev
Group=micronets-dev
```

The systemctl service unit file can be installed for the systemd service using:

```
sudo systemctl enable $PWD/micronets-mud-manager.service
sudo systemctl daemon-reload
```

Once the micronets-mud-manager service is installed, it can be run using:

```
sudo systemctl start micronets-mud-manager.service
```

Where the logging will be stored is system-dependent. On Ubuntu 16.04 systems
logging will be written to `/var/log/syslog`.

The status of the proxy can be checked using:

```
sudo systemctl status micronets-mud-manager.service
```

and the proxy stopped using:

```
sudo systemctl stop micronets-mud-manager.service
```

## 3. API Client Certs

### 3.1 Generating the shared root certificate used for micronets API component communication:

This will produce the root certificate and key for validating/generating
leaf certificates used by certain micronets API:

```
bin/gen-root-cert --cert-basename lib/micronets-api-root \
    --subject-org-name "Micronets API Root Cert" \
    --expiration-in-days 3650
```

This root cert is be the basis for trust for all the clients
communicating via select Micronets APIs. APIs will only 
trust peers that present a cert signed by this root cert. 
The API server must have client cert verification enabled/required 
and `lib/micronets-api-root.cert.pem` must be added to the API 
endpoint's list of trusted CAs (and should really be the only
CA enabled).

The `micronets-ws-root.key.pem` file generated by this script should
only be retained for the purposes of generating new leaf certs for the
websocket peers. It should not be deployed with any software 
components.

### 3.2 Generating API client certificates:

```
bin/gen-leaf-cert --cert-basename lib/micronets-api-client \
    --subject-org-name "Micronets API Client Cert" \
    --expiration-in-days 3650 \
    --ca-certfile lib/micronets-api-root.cert.pem \
    --ca-keyfile lib/micronets-api-root.key.pem

cat lib/micronets-api-client.cert.pem lib/micronets-api-client.key.pem > lib/micronets-api-client.pkeycert.pem
```

The `lib/micronets-api-client.pkeycert.pem` file must be deployed with any
micronet software component that needs to access a cert-controlleed micronets API.


## 4. Websocket message format

### 4.1 Base message definition

All messages exchanged via the websocket channel must have these fields:

```
{
   “message”: {
      “messageId”: <client-supplied session-unique string>,
      “messageType”: <string identifying the message type>,
      “requiresResponse”: <boolean>
      “inResponseTo”: <id string of the originating message> (optional)
   }
}
```

### 4.2 HELLO message definition

```
{
    "message": {
        "messageId": 0,
        "messageType": "CONN:HELLO",
        "peerClass": <string identifying the type of peer connecting to the websocket>,
        "peerId": <string uniquely identifying the peer in the peer class>,
        "requiresResponse": false
    }
}
```

Example:

```
{
    "message": {
        "messageId": 0,
        "messageType": "CONN:HELLO",
        "requiresResponse": false,
        "peerClass": "micronets-ws-test-client",
        "peerId": "12345678"
    }
}
```

### 4.3 REST Request definition

This defines a REST Request message:

```
“message”: {
   “messageType”: “REST:REQUEST”,
   “requiresResponse”: true,
   “method”: <HEAD|GET|POST|PUT|DELETE|…>,
   “path”: <URI path>,
   “queryStrings”: [{“name”: <name string>, “value”: <val string>}, …],
   “headers”: [{“name”: <name string>, “value”: <val string>}, …],
   “dataFormat”: <mime data format for the messageBody>
   “messageBody”: <either a string encoded according to the mime type, base64 string if dataFormat is “application/octet-stream”, or JSON object if dataFormat is “application/json”>
```

Note that Content-Length, Content-Type, and Content-Encoding should not be communicated via the "headers" element as they are conveyed via the dataFormat and messageBody elements. If the request is handled by a HTTP processing system, these header elements may need to be derived from dataFormat and messageBody.

Example GET request:

```
{
  "message": {
    "messageId": 3,
    "messageType": "REST:REQUEST",
    "requiresResponse": true,
    "method": "GET",
    "path": "/micronets/v1/dhcp/subnets",
    "headers": [
      {
        "name": "Host",
        "value": "localhost:5001"
      },
      {
        "name": "User-Agent",
        "value": "curl/7.54.0"
      },
      {
        "name": "Accept",
        "value": "*/*"
      }
    ]
  }
}
```

Example POST request:

```
{
  "message": {
    "messageId": 1,
    "messageType": "REST:REQUEST",
    "requiresResponse": true,
    "method": "POST",
    "path": "/micronets/v1/dhcp/subnets",
    "headers": [
      {
        "name": "Host",
        "value": "localhost:5001"
      },
      {
        "name": "User-Agent",
        "value": "curl/7.54.0"
      },
      {
        "name": "Accept",
        "value": "*/*"
      }
    ],
    "dataFormat": "application/json",
    "messageBody": {
      "subnetId": "mocksubnet007",
      "ipv4Network": {
        "network": "192.168.1.0",
        "mask": "255.255.255.0",
        "gateway": "192.168.1.1"
      },
      "nameservers": [
        "1.2.3.4",
        "1.2.3.5"
      ]
    }
  }
}
```

Example PUT request:

```
{
    "message": {
        "messageId": 3,
        "messageType": "REST:REQUEST",
        "requiresResponse": true,
        "method": "PUT",
        "path": "/micronets/v1/dhcp/subnets/mocksubnet007",
        "dataFormat": "application/json",
        "headers": [
           {"name": "Host", "value": "localhost:5001"},
           {"name": "User-Agent", "value": "curl/7.54.0"},
           {"name": "Accept", "value": "*/*"}
        ],
        "messageBody": {
            "ipv4Network": {
                "gateway": "192.168.1.3"
            }
        }
    }
}
```

### 4.4 REST Response definition

This defines a REST Response message:

```
{
    “message”: {
        “messageType”: “REST:RESPONSE”,
        "inResponseTo": <integer message ID of the REST:REQUEST that generated the response>
        “requiresResponse”: false,
        “statusCode”: <HTTP integer status code>,
        “reasonPhrase”: <HTTP reason phrase string>,
        “headers”: [{“name”: <name string>, “value”: <val string>}, ],
        “dataFormat”: <mime data format for the messageBody>,
        “messageBody”: <either a string encoded according to the dataFormat, base64 string if dataFormat is         “application/octet-stream”, or JSON object if dataFormat is “application/json”>
 “application/octet-stream”, or JSON object if dataFormat is “application/json”>
    }
}
```

Note that Content-Length, Content-Type, and Content-Encoding should not be communicated via the "headers" element as they are conveyed via the dataFormat and messageBody elements. If the request is handled by a HTTP processing system, these header elements may need to be derived from dataFormat and messageBody.

Example GET response:
```
{
    "message": { 
        "messageId": 2,
        "inResponseTo": 3,
        "messageType": "REST:RESPONSE",
        "reasonPhrase": null,
        "requiresResponse": false, 
        "statusCode": 200,
        "dataFormat": "application/json", 
        "messageBody": {
            "subnets": [
                {
                    "ipv4Network": {
                        "gateway": "192.168.30.2",
                        "mask": "255.255.255.0",
                        "network": "192.168.30.0"
                    }, 
                    "subnetId": "wireless-network-1"
                }, 
                {
                    "ipv4Network": {
                        "gateway": "192.168.40.1",
                        "mask": "255.255.255.0",
                        "network": "192.168.40.0"
                    }, 
                    "subnetId": "wired-network-3"
                },
                {
                    "ipv4Network": {
                        "gateway": "10.40.0.1",
                        "mask": "255.255.255.0",
                        "network": "10.40.0.0"
                    }, 
                    "nameservers": ["10.40.0.1"],
                    "subnetId": "testsubnet001"
                }
            ]
        }
    }
}
```

Example POST response:

```
{
    "message": {
        "messageId": 2,
        "inResponseTo": 1,
        "messageType": "REST:RESPONSE",
        "requiresResponse": false,
        "statusCode": 201
        "dataFormat": "application/json",
        "messageBody": {
            "subnet": {
                "subnetId": "mocksubnet007",
                "ipv4Network": {
                    "gateway": "192.168.1.1",
                    "mask": "255.255.255.0",
                    "network": "192.168.1.0"
                }, 
                "nameservers": ["1.2.3.4", "1.2.3.5"]
            }
        }
    }
}
```

Example PUT response:
```
 {
     "message": {
         "messageId": 2,
         "inResponseTo": 3,
         "messageType": "REST:RESPONSE",
         "requiresResponse": false,
         "statusCode": 200,
         "dataFormat": "application/json",
         "messageBody": {
             "subnet": {
                 "ipv4Network": {
                     "gateway": "192.168.1.3",
                     "mask": "255.255.255.0",
                     "network": "192.168.1.0"
                 },
                 "nameservers": ["1.2.3.4", "1.2.3.5"],
                 "subnetId": "mocksubnet007"
             }
         }
     }
 }
```

Example DELETE response:
```
{
    "message": {
        "messageId": 3,
        "inResponseTo": 5,
        "messageType": "REST:RESPONSE",
        "requiresResponse": false,
        "statusCode": 200
    }
}
```

### 4.5 Event Message definition

```
{
    “message”: {
        “messageType”: “EVENT:<client-supplied event name>”,
        “requiresResponse”: False,
        “dataFormat”: <mime data format for the messageBody>,
        “messageBody”: <either a string encoded according to the mime type, base64 string if dataFormat is “application/octet-stream”, or JSON object if dataFormat is “application/json”>
    }
}
```
