"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Vicente Queiroz (vicente.queiroz@mov.ai) - 2020
"""
from movai_core_shared.logger import Log

from dal.scopes.robot import Robot
from dal.scopes.fleetrobot import FleetRobot


LOGGER = Log.get_logger(__name__)


class FlowTopBar:
    @staticmethod
    def get_default_robot(msg):
        robot = Robot()
        return {"robotName": robot.RobotName, "robotIP": Robot().IP}

    @staticmethod
    def send_to_robot(msg):
        action_name = msg[0]
        flow_name = msg[1]
        robot_name = msg[2]

        if robot_name == "Default":
            robot = Robot
        else:
            robot = FleetRobot(robot_name)
        robot.send_cmd(command=action_name, flow=flow_name)
        return True

    @staticmethod
    def command_node(**msg):
        if msg["robotName"] == "Default":
            robot = Robot
        else:
            robot = FleetRobot(msg["robotName"])
        robot.send_cmd(command=msg["command"], node=msg["nodeName"])
