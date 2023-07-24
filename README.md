# MOV.AI Backend Server


<p align="center">
  <a href="https://github.com/MOV-AI/backend/releases/latest"><img alt="CircleCI" src="https://img.shields.io/github/release/MOV-AI/movai-flow.svg?label=current+release"></a>
  <a href="https://github.com/MOV-AI/backend/actions/workflows/DeployOnGitRelease.yml"><img alt="Official Release" src="https://github.com/MOV-AI/backend/actions/workflows/DeployOnGitRelease.yml/badge.svg"></a>
  <a href="https://github.com/MOV-AI/backend/actions/workflows/DeployOnMergeMain.yml"><img alt="Pre Release" src="https://github.com/MOV-AI/backend/actions/workflows/DeployOnMergeMain.yml/badge.svg"></a>
  <a href="https://github.com/MOV-AI/backend/actions/workflows/TestOnPR.yml"><img alt="PR Checks" src="https://github.com/MOV-AI/backend/actions/workflows/TestOnPR.yml/badge.svg"></a>
  <a href="https://twitter.com/MovAIRobots"><img alt="Twitter" src="https://img.shields.io/twitter/url/http/shields.io.svg?style=social"></a>
</p>

## Description

The Backend is the REST API server of the MOV.AI platform
All the REST API request end points are contained in the Backend server
The Backend is activating the internal platform APIs for serving the received requests
Additionally the Backend is managing the users Login process

## Usage

The python module named `backend` should launch a web server on port 5004 serving all necessary API endpoints for MOV.AI core webservices.

    python3 -m backend

> Prerequisites : 2 running redis servers

Parameters list that can be set through environment variables:

    HTTP_PORT=5004
    REDIS_LOCAL_PORT=6379
    REDIS_MASTER_PORT=6379
    REDIS_MASTER_HOST=redis-master
    REDIS_LOCAL_HOST=redis-local


## Build

The complete build process requires 2 steps :
- a python module building step which will create a `.whl` file
- a docker image building step which will create a container image and install the previously built `.whl` file

## build pip module

    rm dist/*
    python3 -m build .

## install pip module locally

    python3 -m venv .testenv
    source .testenv/bin/activate
    python3 -m pip install --no-cache-dir \
    --index-url="https://artifacts.cloud.mov.ai/repository/pypi-experimental/simple" \
    --extra-index-url https://pypi.org/simple \
    ./dist/*.whl

## build docker images

For ROS noetic distribution :

    docker build -t backend:noetic -f docker/noetic/Dockerfile .


## Basic Run

For ROS noetic distribution :

    docker run -t backend:noetic

## Development stack


For ROS noetic distribution :

    rm dist/*
    python3 -m build .
    export BACKEND_DISTRO=noetic
    docker-compose -f tests/docker-compose.yml up -d

