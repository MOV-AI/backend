"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from .callbackeditor import CallbcakEditor
from .datavalidation import DataValidation
from .flowtopbar import FlowTopBar
from .getportsdata import get_ports_data
from .startsystemwidget import start_system_widget
from .viewer import Viewer


ide_action_map = {
    # callbackeditor
    "init": CallbcakEditor.init,
    "get_libraries": CallbcakEditor.get_libraries,
    "get_all_libraries": CallbcakEditor.get_all_libraries,
    "get_messages": CallbcakEditor.get_messages,
    "get_msg_struct": CallbcakEditor.get_msg_struct,
    "library": CallbcakEditor.describe_module,
    # datavalidation
    "validateConfiguration": DataValidation.validate_configuration,
    "validateConfigurationRaw": DataValidation.validate_configuration_raw,
    # flowtopbar
    "getDefaultRobot": FlowTopBar.get_default_robot,
    "sendToRobot": FlowTopBar.send_to_robot,
    "commandNode": FlowTopBar.command_node,
    # getportsdata
    "getPortsData": get_ports_data,
    # statesystemwidget
    "startSystemWidget": start_system_widget,
    # viewer
    "save": Viewer.on_save,
    "addNodeItem": Viewer.on_add_node_item,
    "deleteNodeByName": Viewer.on_delete_node_by_name,
    "updateNode": Viewer.on_update_node,
    "retrieveScene": Viewer.on_retrieve_scene,
    "deleteMap": Viewer.on_delete_map,
    "deleteMesh": Viewer.on_delete_mesh,
    "deletePointCloud": Viewer.on_delete_point_cloud,
    "getComputedAnnotations": Viewer.get_computed_annotations,
    "setRobotMesh": Viewer.set_robot_mesh,
    "setRobotPoseEstimation": Viewer.set_robot_pose_estimation,
    "setRobotPoseGoal": Viewer.set_robot_pose_goal,
}


ide_enterprise_map = {
    # viewer
    "save": Viewer.on_save,
    "addNodeItem": Viewer.on_add_node_item,
    "deleteNodeByName": Viewer.on_delete_node_by_name,
    "updateNode": Viewer.on_update_node,
    "retrieveScene": Viewer.on_retrieve_scene,
    "deleteMap": Viewer.on_delete_map,
    "deleteMesh": Viewer.on_delete_mesh,
    "deletePointCloud": Viewer.on_delete_point_cloud,
    "getComputedAnnotations": Viewer.get_computed_annotations,
    "setRobotMesh": Viewer.set_robot_mesh,
    "setRobotPoseEstimation": Viewer.set_robot_pose_estimation,
    "setRobotPoseGoal": Viewer.set_robot_pose_goal,
}