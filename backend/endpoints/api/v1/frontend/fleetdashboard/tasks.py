"""
    Copyright (C) Mov.ai  - All Rights Reserved
    Unauthorized copying of this file, via any medium is strictly prohibited
    Proprietary and confidential

    This is a sample statistics callback which is responsible for getting all robots
    information such as distance travelled, number of carts delivered etc.

    This callback is called for the following functions
        -> getTasks    :return all Tasks.
        -> saveTask    :saves a Task.
        -> deleteTask  :deletes a Task
"""
from movai_core_shared.logger import Log

from dal.models.scopestree import ScopesTree

LOGGER = Log.get_logger(__name__)

try:
    from movai_core_enterprise.models.taskentry import TaskEntry
except ImportError:
    LOGGER.warning("Failed to import TaskEntry , because movai_core_enterprise is not installed.")


class Tasks:
    @staticmethod
    def get_tasks():
        """returns all tasks"""
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
                output = {
                    "id": obj_dict.ref,
                    "Status": obj_dict.Status,
                    "Label": obj_dict.ref,
                    "Description": obj_dict.Description,
                    "TemplateID": obj_dict.TemplateID,
                    "Priority": obj_dict.Priority,
                }
                response[RESULT].append(output)
            response["success"] = True
        except Exception as e:
            LOGGER.warning("Caught exception in getTasks", e)
            raise e
        return response

    @staticmethod
    def save_task(data):
        """Add or update Task"""
        response = {"success": False}
        try:
            _id = data.get("id", None)
            if not _id:
                raise ValueError("Task entry is required")
            task_entry = TaskEntry(_id)
            for key in data:
                try:
                    if key in task_entry:
                        task_entry[key].value = data[key]
                except Exception as error:
                    LOGGER.error(error)
            task_entry.write()
            response["success"] = True
        except Exception as error:
            LOGGER.error("Caught exception while saving task", error)
        return response

    @staticmethod
    def delete_task(data):
        """Delete a task"""
        LOGGER.debug("debug FLEET TASKS deleteTask", data)
        response = {"success": False}
        try:
            task = ScopesTree()().TaskEntry[data["id"]]
            task.delete()
            response["success"] = True
        except Exception as error:
            LOGGER.error("Caught exception while delete task", error)
            raise error
        return response
