"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Usage:
        Basic 0MQ client for connecting 0MQ servers.

   Developers:
   - Erez Zomer (erez@mov.ai) - 2023
"""
from aiohttp import web
import logging
import queue
from threading import Thread

from movai_core_shared.core.zmq_server import ZMQServer
from movai_core_shared.envvars import LOG_STREAMER_BIND_ADDR
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.log_client import LogClient
from backend.core.log_streamer.log_filter import LogFilter
from backend.helpers.rest_helpers import fetch_request_params


class LogsStreamer(ZMQServer):

    def __init__(self, debug: bool = False) -> None:
        """Initializes the object.

        Args:
            debug (bool, optional): if True, will show debug logs while running ZMQServer
        """
        super().__init__(self.__class__.__name__, LOG_STREAMER_BIND_ADDR, debug)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._clients = {}
        self.init_server()

    def add_client(self, client: LogClient) -> bool:
        if client.id in self._clients:
            self._logger.debug(f"The client: {client.id} is already registered in {self.__class__.__name__}")
            return
        self._clients[client.id] = client
        self._logger.debug(f"The client: {client.id} have been added to {self.__class__.__name__}")
        return client.id

    def remove_client(self, client: LogClient) -> bool:
        if client.id in self._clients:
            self._clients.pop(client.id)
            self._logger.debug(f"The client: {client.id} was removed")

    async def handle_request(self, request: dict) -> dict:
        """Implements the handle_request function for ZMQServer.

        Args:
            request (dict): A request witho logs.

        Returns:
            dict: response
        """
        try:
            log_msg = LogRequest(**request)
            if self._debug:
                self._logger.debug(f"{self.__class__.__name__}: {log_msg.req_data.log_fields.message}")
            for client in self._clients.values():
                client.push(log_msg)
            return {}
        except Exception as error:
            self._logger.error(str(error))
            return {}

    def prepare_socket(self, request: web.Request):
        """prepares the socket

        Args:
            request (web.Request): the request for websocket.

        Raises:
            web.HTTPError: _description_

        Returns:
            _type_: _description_
        """
        ws = web.WebSocketResponse()
        if ws.can_prepare(request):
            ws.prepare(request)
            return ws
        else:
            error_msg = "The socket could not be established"
            self._logger.warning(error_msg)
            raise web.HTTPError(error_msg)

    async def open_connection(self, request: web.Request) -> LogClient:
        try:
            params = fetch_request_params(request)
            ws = self.prepare_socket(request)
            filter = LogFilter(**params)
            client = LogClient(filter)
            client.set_socket(ws)
            #self.add_client(client)
            return client
            
        except Exception as error:
            self._logger.error(str(error))
            raise web.HTTPError(str(error))
        
    async def stream_logs(self, request: web.Request):
        client = self.open_connection(request)
        client_thread = Thread(target=client.stream_msgs())
        client_thread.start()