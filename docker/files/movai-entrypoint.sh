#!/bin/bash
#
# Copyright 2021 MOV.AI
#
#    Licensed under the Mov.AI License version 1.0;
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        https://www.mov.ai/flow-license/
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# File: movai-entrypoint.sh
set -em
printf "Mov.ai Backend - %s Edition\n" "$MOVAI_ENV"
printf "Redis Master: %s:%d\n" ${REDIS_MASTER_HOST} ${REDIS_MASTER_PORT}
printf "Redis Local: %s:%d\n" ${REDIS_LOCAL_HOST} ${REDIS_LOCAL_PORT}

source "/opt/ros/$ROS_DISTRO/setup.bash"
export PYTHONPATH=${APP_PATH}:${PYTHONPATH}

# if commands passed
[ $# -gt 0 ] && exec "$@"

# else
if [ ! -f ${MOVAI_HOME}/.first_run ]; then
    /usr/local/bin/deploy.sh && touch ${MOVAI_HOME}/.first_run
fi

# start the backend
python3 -m backend &

# default launch nodes
if [ -n "${START_NODES}" ]; then
    # START_NODES="template1,instance1;template2,instance2;..."
    for NODE_PAIR in $(echo $START_NODES | grep -oP '[^;]+'); do
        PARAMS="$(echo $NODE_PAIR | sed -E 's/^(.+),(.+)/-n \1 -i \2/')"
        /usr/bin/python3 ${APP_PATH}/GD_Node.py ${PARAMS} -v &
    done
fi
# Hold until user stops container
tail -f /dev/null
fg %1

