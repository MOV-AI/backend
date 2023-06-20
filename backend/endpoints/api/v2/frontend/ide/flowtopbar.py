"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Vicente Queiroz (vicente.queiroz@mov.ai) - 2020

"""
from aiohttp import web

from movai_core_shared.logger import Log

from dal.scopes.robot import Robot
from dal.scopes.fleetrobot import FleetRobot


LOGGER = Log.get_logger(__name__)

def getDefaultRobot(msg):
    robot = Robot()
    return {"robotName": robot.RobotName, "robotIP": Robot().IP}


def sendToRobot(msg):
    action_name = msg[0]
    flow_name = msg[1]
    robot_name = msg[2]

    if robot_name == "Default":
        robot = Robot
    else:
        robot = FleetRobot(robot_name)
    robot.send_cmd(command=action_name, flow=flow_name)
    return True


def commandNode(msg):
    if msg["robotName"] == "Default":
        robot = Robot
    else:
        robot = FleetRobot(msg["robotName"])
    robot.send_cmd(command=msg["command"], node=msg["nodeName"])


key2action_map = {
    "getDefaultRobot": getDefaultRobot,
    "sendToRobot": sendToRobot,
    "commandNode": commandNode,
}

async def flow_top_bar(request: web.Request):
    try:
        response = {"success": True}
        data = await request.json()
        func = data.get("func")
        if func is None:
            raise ValueError("the 'func' argument is missing in request's body!")
        args = data.get("args")
        response["result"] = key2action_map[func](args)
    except Exception as exc:
        response = {"success": False, "error": str(exc)}
    finally:
        return web.json_response(response)