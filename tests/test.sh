#!/bin/bash

set -a
source tests/docker.env
set +a

docker-compose -f docker-compose.yml -f tests/docker-compose.yml up --build -V --exit-code-from pdspi-mapper-parallex-example-test
