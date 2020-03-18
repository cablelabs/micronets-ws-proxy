#!/bin/bash

set -e

shortname="${0##*/}"
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

DOCKER_CMD="docker"
# https://community.cablelabs.com/mvn/micronets-docker/micronets-ws-proxy
DEF_IMAGE_LOCATION="community.cablelabs.com:4567/micronets-docker/micronets-ws-proxy:latest"
DEF_CONTAINER_NAME=micronets-ws-proxy-service
DEF_LIB_PATH=/etc/micronets/micronets-ws-proxy/lib
DEF_BIND_PORT=5050
DEF_BIND_ADDRESS=0.0.0.0

function bailout()
{
    local message="$1"
    echo "$shortname: error: ${message}" >&2
    exit 1;
}

function bailout_with_usage()
{
    local message="$1"
    echo "$shortname: error: ${message}" >&2
    print_usage
    exit 1;
}

function print_usage()
{
    echo " "
    echo "Usage: ${shortname} <operation>"
    echo ""
    echo "   operation can be one of:"
    echo ""
    echo "     docker-pull: Download the $shortname docker image"
    echo "     docker-run: Create and start the $shortname docker container"
    echo "     docker-status: Show the status of the $shortname docker container"
    echo "     docker-kill: Kill the $shortname docker container"
    echo "     docker-restart: Restart the $shortname docker container"
    echo "     docker-logs: Show the logs for $shortname docker container"
    echo "     docker-trace: Watch the logs for the $shortname docker container"
    echo "     docker-address|addr: Print the IP addresses for the $shortname docker container"
    echo "     docker-env: List the environment variables for the $shortname docker container"
    echo ""
    echo "   [--docker-image <docker image ID>"
    echo "       (default \"$DEF_IMAGE_LOCATION\")"
    echo "   [--docker-name <docker name to assign>"
    echo "       (default \"$DEF_CONTAINER_NAME\")"
    echo "   [--library-bind-path <lib directory to mount in container>"
    echo "       (default \"$DEF_LIB_PATH\")"
    echo "   [--bind-address <addresd to bind ${shortname} to>"
    echo "       (default \"$DEF_BIND_ADDRESS\")"
    echo "   [--bind-port <port to bind ${shortname} to>"
    echo "       (default \"$DEF_BIND_PORT\")"
}

function process_arguments()
{
    shopt -s nullglob
    shopt -s shift_verbose

    operation=""
    docker_image_id="$DEF_IMAGE_LOCATION"
    container_name=$DEF_CONTAINER_NAME
    lib_bind_path=$DEF_LIB_PATH
    bind_address=$DEF_BIND_ADDRESS
    bind_port=$DEF_BIND_PORT

    while [[ $1 == --* ]]; do
        if [ "$1" == "--docker-image" ]; then
            shift
            docker_image_id="$1"
            shift || bailout_with_usage "missing parameter to --docker-image"
        elif [ "$1" == "--docker-name" ]; then
            shift
            container_name="$1"
            shift || bailout_with_usage "missing parameter to --docker-name"
        elif [ "$1" == "--library-bind-path" ]; then
            shift
            lib_bind_path="$1"
            shift || bailout_with_usage "missing parameter to --library-bind-path"
        elif [ "$1" == "--bind-address" ]; then
            shift
            bind_address="$1"
            shift || bailout_with_usage "missing parameter to --bind-address"
        elif [ "$1" == "--bind-port" ]; then
            shift
            bind_port="$1"
            shift || bailout_with_usage "missing parameter to --bind-port"
        else
            bailout_with_usage "Unrecognized option: $1"
        fi
    done

    if [ $# -lt 1 ]; then
        bailout_with_usage "Missing operation"
    fi

    operation=$1
    shift
}

function docker-pull()
{
    echo "Pulling docker image from $docker_image_id"
	$DOCKER_CMD pull $docker_image_id
}

function docker-run()
{
    echo "Starting container \"$container_name\" from $docker_image_id (on $bind_address:$bind_port)"
    docker-rm
    $DOCKER_CMD run --read-only -d --restart unless-stopped \
        --name $container_name \
        -v $lib_bind_path:/app/lib/ \
        -p $bind_address:$bind_port:$bind_port \
        $docker_image_id --bind-port $bind_port \
                         --server-cert /app/lib/micronets-ws-proxy.pkeycert.pem \
                         --ca-certs /app/lib/micronets-ws-root.cert.pem
    # Note that the
}

function docker-rm()
{
    echo "Attempting to remove container \"$container_name\""
    $DOCKER_CMD container rm $container_name
}

#
# main logic
#

process_arguments "$@"

$operation
