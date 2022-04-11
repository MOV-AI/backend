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
# File: create-user.sh
set -e

printf "Mov.ai Install Create User\n"

if [ $# -eq 0 ]; then
    printf "mov.ai Create User\n"
    printf "usage: %s <username> <password>\n" "$(basename ${0})"
    exit 0
fi

source "/opt/ros/$ROS_DISTRO/setup.bash"
PYTHONPATH="${APP_PATH}:${PYTHONPATH}"
/usr/bin/python3 -m tools.new_user -u "${1}" -p "${2}"
