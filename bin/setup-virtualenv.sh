#!/bin/bash

# Enable tracing of command invocations
set -x

if [ "$#" -lt 1 ]; then
  WS_PROXY_DIR="$( cd "$(dirname "$0/..")" ; pwd -P )"
else
  WS_PROXY_DIR="$1"
fi

echo "WS_PROXY_DIR: $WS_PROXY_DIR"

WS_PROXY_VIRTENV_NAME=virtualenv

# This requires the "virtualenv" package to be installed

cd "$WS_PROXY_DIR"

echo "Creating virtualenv $WS_PROXY_VIRTENV_NAME (in $WS_PROXY_DIR/$WS_PROXY_VIRTENV_NAME)"
virtualenv --clear -p $(which python3.6) $WS_PROXY_DIR/$WS_PROXY_VIRTENV_NAME

source $WS_PROXY_VIRTENV_NAME/bin/activate

pip install -r requirements.txt
