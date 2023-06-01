from abc import ABC, abstractmethod
from logging import Logger
import uuid
from aiohttp import web

from movai_core_shared.core.zmq_server import ZMQServer
from movai_core_shared.envvars import LOG_STREAMER_BIND_ADDR
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.helpers.rest_helpers import fetch_request_params

class ParamFilter(ABC):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    @abstractmethod
    def filter_msg(self, msg: LogRequest):
        pass

    @property
    def name(self) -> str:
        return self._name

class StrParam(ParamFilter):
    def __init__(self, name: str, value) -> None:
        super().__init__(name)
        if not isinstance(value, str):
            raise ValueError("value must be an string")
        self._value = value


class IntParam(ParamFilter):
    def __init__(self, name: str, value) -> None:
        super().__init__(name)
        if not isinstance(value, int):
            raise ValueError("value must be an int")
        self._value = value


class ListParam(StrParam):
    def __init__(self, name: str, value) -> None:
        super().__init__(name, value)
        if not isinstance(value, list):
            self._value = [value]


class RobotParam(ListParam):
    def __init__(self, value) -> None:
        super().__init__("robots", value)

    def filter_msg(self, msg: LogRequest):
        return msg.req_data.log_tags.robot  in self._value


class ServiceParam(ListParam):
    def __init__(self, value) -> None:
        super().__init__("services", value)

    def filter_msg(self, msg: LogRequest):
        return msg.req_data.log_tags.service in self._value


class LevelParam(ListParam):
    def __init__(self, value) -> None:
        super().__init__("levels", value)

    def filter_msg(self, msg: LogRequest):
        return msg.req_data.log_tags.level in self._value


class MessageParam(StrParam):
    def __init__(self, value) -> None:
        super().__init__("message", value)

    def filter_msg(self, msg: LogRequest):
        return msg.req_data.log_fields.message in self._value


class FromDateParam(int):
    def __init__(self, value) -> None:
        super().__init__("fromDate", value)

    def filter_msg(self, msg: LogRequest):
        return msg.created >= self._value
    

class ToDateParam(int):
    def __init__(self, value) -> None:
        super().__init__("toDate", value)

    def filter_msg(self, msg: LogRequest):
        return msg.created < self._value


class LogFilter:
    _filters_types = {
         "robots": RobotParam,
         "services": ServiceParam,
         "Levels": LevelParam,
         "message": MessageParam,
         "fromDate": FromDateParam,
         "toDate": ToDateParam
     }

    def __init__(self, **params):
        self._filters = []
        for key, val in params.items():
            if key in self._filters_types and val is not None:
                filter = self._filters_types[key](val)
                self._filters.append(filter)
        
    def filter_msg(self, msg: LogRequest) -> bool:
        for filter in self._filters():
            if not filter.filter_msg(msg):
                return False
        return True