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

export PATH=${MOVAI_HOME}/.local/bin:${PATH}
export PYTHONPATH=${APP_PATH}:${PYTHONPATH}

# if commands passed
[ $# -gt 0 ] && exec "$@"

# else
if [ ! -f ${MOVAI_HOME}/.first_run ]; then
    touch ${MOVAI_HOME}/.first_run
fi

# start the backend
backend &

while ! timeout 1 bash -c "echo > /dev/tcp/localhost/$HTTP_PORT"; do
    printf "Waiting backend to launch on localhost:%s...\n" "$HTTP_PORT"
    sleep 5
done

if [ ! -f ${MOVAI_HOME}/.default_user ]; then
    if [ -n "${DEFAULT_USERNAME}" ] && [ -n "${DEFAULT_PASSWORD}" ]; then
        printf "Adding default user %s\n" "${DEFAULT_USERNAME}"
        user_tool create -u "${DEFAULT_USERNAME}" -p "${DEFAULT_PASSWORD}" -s
        echo "${DEFAULT_USERNAME}" > ${MOVAI_HOME}/.default_user
    else
        echo "not set" > ${MOVAI_HOME}/.default_user
    fi
fi

# default launch nodes
if [ -n "${START_NODES}" ]; then
    # START_NODES="template1,instance1;template2,instance2;..."
    for NODE_PAIR in $(echo $START_NODES | grep -oP '[^;]+'); do
        printf "launching $NODE_PAIR\n"
        PARAMS="$(echo $NODE_PAIR | sed -E 's/^(.+),(.+)/-n \1 -i \2/')"
        gd_node ${PARAMS} -v &
    done
fi
printf "Ready to serve\n"
fg %1
