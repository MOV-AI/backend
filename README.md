# backend


## Usage

The python module named `backend` should launch a web server on port 5004 serving all necessary API endpoints for MOV.AI core webservices.

    python3 -m backend

> Prerequisites : 2 running redis servers

Parameters list that can be set through environment variables:

    REDIS_LOCAL_PORT=6379
    REDIS_MASTER_PORT=6379
    REDIS_MASTER_HOST=redis-master
    REDIS_LOCAL_HOST=redis-local



## Build

The complete build process requires 2 steps :
- a python module building step which will create a `.whl` file
- a docker image building step which will create a container image and install the previously built `.whl` file

## build pip module

    python3 -m build .

## install pip module locally

    python3 -m venv .testenv
    source .testenv/bin/activate
    python3 -m pip install --no-cache-dir \
    --index-url="https://artifacts.cloud.mov.ai/repository/pypi-experimental/simple" \
    --extra-index-url https://pypi.org/simple \
    ./dist/*.whl

## build docker images

For ROS melodic distribution :

    docker build -t backend:melodic -f docker/melodic/Dockerfile .


For ROS noetic distribution :

    docker build -t backend:noetic -f docker/noetic/Dockerfile .


## Basic Run

For ROS melodic distribution :

    docker run -t backend:noetic

For ROS noetic distribution :

    docker run -t backend:noetic

## Development stack

    docker-compose -f tests/docker-compose.yml up -d

