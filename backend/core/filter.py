from abc import ABC, abstractmethod
from logging import Logger
import uuid
from aiohttp import web


from movai_core_shared.logger import Log
from movai_core_shared.core.zmq_server import ZMQServer
from movai_core_shared.envvars import BACKEND_SERVER_BIND_ADDR

from dal.messages.log_data import LogRequest

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


class Client:
    def __init__(self, filter: LogFilter, logger: Logger = None) -> None:
        self._id = uuid.uuid4()
        self._filter = filter
        if logger is None:
            logger = Log.get_logger(self.__class__.__name__)
        self._logger = logger
        self._sock = web.WebSocketResponse()

    @property
    def id(self):
        return self._id
        

    def __del__(self):
        try:
            self._sock.close()
        except Exception:
            self._sock.force_close()

    async def send_msg(self, msg: LogRequest):
        try:
            if self._filter.filter_msg(msg):
                await self._sock.send_json(msg)
        except ValueError as err:
            self.logger.error(err.__str__())
        except RuntimeError as err:
            self.logger.error(err.__str__())
        except TypeError as err:
            self.logger.error(err.__str__())



class LogsServer(ZMQServer):

    def __init__(self, server_name: str, bind_addr: str, ) -> None:
        self._logger = Log.get_logger(server_name)
        super().__init__(self.__class__.__name__, BACKEND_SERVER_BIND_ADDR, self._logger)
        self._clients = {}
        self.init_server()
        self.run()

    def add_client(self, client: Client) -> bool:
        if client.id in self._clients:
            self._logger.debug(f"The client: {client.id} is already registered in {self.__class__.__name__}")
            return
        self._clients[client.id] = client
        self._logger.debug(f"The client: {client.id} have been added to {self.__class__.__name__}")
        return client.id

    def remove_client(self, client: Client) -> bool:
        if client.id in self._clients:
            self._clients.pop(client.id)
            self._logger.debug(f"The client: {client.id} was removed")

    def prepare_socket(self, request: web.Request):
        ws = web.WebSocketResponse()
        if ws.can_prepare(request):
            ws.prepare(request)
            return ws
        else:
            error_msg = "The socket could not be established"
            self._logger.warning(error_msg)
            raise web.HTTPError(error_msg)

    async def _handle_request(self, request: dict):
        try:
            status = 200
            params = fetch_request_params(request)
            filter = LogFilter(**params)
            client = Client(filter)
            ws = self.prepare_socket(request)
            if ws is None:

            self.add_client(client)
            request = await ws.receive_json()
            ws.set_status(status)
            log_msg = LogRequest(request)
            for client in self._clients.values():
                await client.send_msg(log_msg)
            return ws
        except Exception as error:
            status = 401
            raise web.HTTPBadRequest(reason=error)
        
        