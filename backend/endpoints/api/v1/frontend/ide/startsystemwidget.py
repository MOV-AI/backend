"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Vicente Queiroz (vicente.queiroz@mov.ai) - 2020
"""
from dal.scopes.robot import Robot
from dal.scopes.fleetrobot import FleetRobot


def check_args(**kwargs):
    args = ["action_name", "flow_name", "robot_name"]
    for arg in args:
        if arg not in kwargs:
            raise ValueError(f"The argument '{arg}' is missing")


def start_system_widget(**kwargs):
    check_args(**kwargs)
    action_name = kwargs["action_name"]
    flow_name = kwargs["flow_name"]
    robot_name = kwargs["robot_name"]

    if flow_name is not None:
        if robot_name == "":
            robot = Robot()
        else:
            robot = FleetRobot(robot_name)

        robot.send_cmd(command=action_name, flow=flow_name)
