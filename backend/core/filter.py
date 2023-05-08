from abc import ABC
import uuid
from aiohttp import web

from movai_core_shared.logger import Log
from movai_core_shared.core.
class ParamFilter(ABC):
    def __init__(self, name: str, value) -> None:
        super().__init__()
        self._name = name


class LogFilter:
    def __init__(self, **kwargs):
        self._limit = kwargs.get("limit")
        self._offset = kwargs.get("offset")
        self._robots = kwargs.get("robots")
        self._services = kwargs.get("services")
        self._level = kwargs.get("levels")
        self._message = kwargs.get("message")
        self._from = kwargs.get("fromDate")
        self._to = kwargs.get("toDate")
        self._pagination = kwargs.get("pagination")


class LogMessage:
    def __init__(self, request: dict) -> None:
        request["request"]
class Client:
    def __init__(self, filter) -> None:
        self._id = uuid.uuid4()
        self._filter = filter
        self._sock = web.WebSocketResponse()

    def prepare_socket(self, request: web.Request):
        if self._sock.can_prepare(request):
            self._sock.prepare(request)
        else:
            self._logger.warning("The socket could not be established")

    def __del__(self):
        try:
            self._sock.close()
        except Exception:
            self._sock.force_close()

    def send_msg(self, data: dict):
        try:
            self._sock.send_json(data)
        except ValueError as err:
            self.logger.error(err.__str__())
        except RuntimeError as err:
            self.logger.error(err.__str__())
        except TypeError as err:
            self.logger.error(err.__str__())

    @property
    def id(self):
        return self._id


class ClientManager:
    def __init__(self):
        self._clients = {}
        self._logger = Log.get_logger(self.__class__.__name__)
        self._server = ZM

    def add_client(self, client: Client) -> bool:
        if client.id in self._clients:
            self._logger.deubg(f"The client: {client.id} is already registered in {self.__class__.__name__}")
            return
        self._clients[client.id] = client
        self._logger.deubg(f"The client: {client.id} have been added to {self.__class__.__name__}")
        return client.id
    
    def remove_client(self, client: Client) -> bool:
        if client.id in self._clients:
            self._clients.pop(client.id)
            self._logger.deubg(f"The client: {client.id} was removed")

    def stream_to_client(self, id: str, data: str):
        if id not in self._clients:
            return
        client: Client = self._clients[id]
        client.send_msg(data)

    def handle_request(self, request: dict):
        pass

CLIENT_MANAGER = ClientManager()
