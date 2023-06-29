

'''

    Tasks api

    @params {dict} msg - Receives a function name and function arguments

    msg format - {func:<func_to_call>, args:{<args_to_forward>}


    Use:

    POST 

    url:     http://<robot_ip>/api/v1/function/fleetDashboard.tasks/

    payload: {func: <function_name>, args:{<var_name>: <var_value>}}

    
    v.2.0.0
'''
import uuid

from movai_core_shared.logger import Log
from movai_core_shared.common.utils import is_enterprise

from dal.models.scopestree import ScopesTree

if is_enterprise:
    from movai_core_enterprise.scopes.shareddataentry import SharedDataEntry
    from movai_core_enterprise.scopes.shareddatatemplate import SharedDataTemplate
    from movai_core_enterprise.models.taskentry import TaskEntry


LOGGER = Log.get_logger(__name__)

class Tasks:
    @staticmethod
    def getTasks():
        """ returns all tasks """
        RESULT = "result"
        TASK_ENTRY = "TaskEntry"
        REF = "ref"
        response = {"success": False}
        try:
            response[RESULT] = []
            # get all SharedDataEntry objects
            entries = ScopesTree()().list_scopes(scope=TASK_ENTRY)
            for entry in entries:
                obj_dict = ScopesTree()().TaskEntry[entry[REF]]
                # get relevant information from main properties
                output = {"id": obj_dict.ref, "Status": obj_dict.Status, "Label": obj_dict.ref, "Description": obj_dict.Description,
                          "TemplateID": obj_dict.TemplateID,  "Priority": obj_dict.Priority}
                response[RESULT].append(output)
            response["success"] = True
        except Exception as e:
            LOGGER.warning("Caught exception in getTasks", e)
            raise e
        return response

    @staticmethod
    def saveTask(data):
        """ Add or update Task """
        response = {"success": False}
        try:
            _id = data.get("id", None)
            if not _id:
                raise Exception("Task entry is required")
            task_entry = TaskEntry(_id)
            for key in data:
                try:
                    if(key in task_entry):
                        task_entry[key].value = data[key]
                except Exception as error:
                    LOGGER.error(error)
            task_entry.write()
            response["success"] = True
        except Exception as error:
            LOGGER.error("Caught exception while saving task", error)
        return response

    @staticmethod
    def deleteTask(data):
        """ Delete a task """
        print("debug FLEET TASKS deleteTask", data)
        response = {"success": False}
        try:
            task = ScopesTree()().TaskEntry[data["id"]]
            task.delete()
            response["success"] = True
        except Exception as error:
            LOGGER.error("Caught exception while delete task", error)
            raise error
        return response

