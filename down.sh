#!/bin/bash

set -a
source tests/docker.env
set +a

docker-compose -f docker-compose.yml down
