from aiohttp import web
from typing import List

from dal.models.message import Message

from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager

from .callbackeditor import CallbcakEditor
from .datavalidation import DataValidation
from .flowtopbar import FlowTopBar
from .startsystemwidget import start_system_widget
from .viewer import Viewer


ide_action_map = {
    #callbackeditor
    "init": CallbcakEditor.init,
    "get_libraries": CallbcakEditor.get_libraries,
    "get_all_libraries": CallbcakEditor.get_all_libraries,
    "get_messages": CallbcakEditor.get_messages,
    "get_msg_struct": CallbcakEditor.get_msg_struct,
    "library": CallbcakEditor.describe_module,
    #datavalidation
    "validateConfiguration": DataValidation.validate_configuration,
    "validateConfigurationRaw": DataValidation.validate_configuration_raw,
    #flowtopbar
    "getDefaultRobot": FlowTopBar.getDefaultRobot,
    "sendToRobot": FlowTopBar.sendToRobot,
    "commandNode": FlowTopBar.commandNode,
    #getportsdata
    "getPortsData": Message.fetch_portdata_api,
    #statesystemwidget
    "startSystemWidget": start_system_widget,
    #viewer
    "save": Viewer.on_save,
    "addNodeItem": Viewer.on_addNodeItem,
    "deleteNodeByName": Viewer.on_deleteNodeByName,
    "updateNode": Viewer.on_updateNode,
    "retrieveScene": Viewer.on_retrieveScene,
    "deleteMap": Viewer.on_delete_map,
    "deleteMesh": Viewer.on_delete_mesh,
    "deletePointCloud": Viewer.on_delete_point_cloud,
    "getComputedAnnotations": Viewer.get_computed_annotations,
    "setRobotMesh": Viewer.set_robot_mesh,
    "setRobotPoseEstimation": Viewer.set_robot_pose_estimation,
    "setRobotPoseGoal": Viewer.set_robot_pose_goal 
}

ide_cb = (
"backend.CallbackEditor",
"backend.DataValidation",
"backend.FlowTopBar",
"backend.getPortsData",
"backend.StartSystemWidget",
"backend.viewer",
)

