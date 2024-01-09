"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from dal.om.callback import Callback
from dal.om.message import Message


class CallbcakEditor:
    @staticmethod
    def get_libraries(*args, **kwargs):
        return Callback.get_modules()

    @staticmethod
    def init(*args, **kwargs):
        Callback.export_modules()
        return True

    @staticmethod
    def get_all_libraries(*args, **kwargs):
        print("Get all libraries called")
        return Callback.fetch_modules_api()

    @staticmethod
    def get_messages(*args, **kwargs):
        return Message.fetch_portdata_messages()

    @staticmethod
    def get_msg_struct(*, message, **kwargs):
        return Message.get_structure(message)

    @staticmethod
    def describe_module(*, module, **kwargs):
        required = ["name", "toSelect"]
        if not all(x in module for x in required):
            return False
        to_return = {
            "module": Callback.get_methods(module["name"]),
            "toSelect": module["toSelect"],
            "name": module["name"],
        }
        return to_return
