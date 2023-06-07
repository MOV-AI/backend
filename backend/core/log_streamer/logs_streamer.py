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
import uuid

from movai_core_shared.core.zmq_server import ZMQServer
from movai_core_shared.envvars import LOG_STREAMER_BIND_ADDR
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.log_client import LogClient
from backend.helpers.rest_helpers import fetch_request_params


class LogsStreamer(ZMQServer):

    def __init__(self, debug: bool = False) -> None:
        """Initializes the object.

        Args:
            debug (bool, optional): if True, will show debug logs while running ZMQServer
        """
        super().__init__(self.__class__.__name__, LOG_STREAMER_BIND_ADDR, debug)
        self._logger = Log.get_logger(self.__class__.__name__)
        self._clients = {}

    def is_client_registered(self, client_id: uuid.UUID) -> bool:
        """Checks if a client is registered.

        Args:
            client_id (uuid.UUID): The id of the client.

        Returns:
            bool: True if registered, False otherwise.
        """
        return client_id in self._clients
    
    def register_client(self, client: LogClient) -> uuid.UUID:
        """Register the client in the LogStreamer, so whenever a new log will arive it
        will be sent to this client if it pass the filter.

        Args:
            client (LogClient): the client to register.
        """
        if self.is_client_registered(client.id):
            self._logger.debug(f"The client: {client.id} is already registered in {self.__class__.__name__}")
            return
        self._clients[client.id] = client
        self._logger.debug(f"The client: {client.id} has been added to {self.__class__.__name__}")
        return

    def unregister_client(self, client: LogClient) -> bool:
        """Unregister a client from the LogStreamer.

        Args:
            client (LogClient): The client to remove.
        """
        if self.is_client_registered(client.id):
            self._clients.pop(client.id)
            self._logger.debug(f"The client: {client.id} was removed")

    async def handle_request(self, request: dict) -> dict:
        """Implements the handle_request function for ZMQServer.

        Args:
            request (dict): A request witho logs.

        Returns:
            dict: empty response
        """
        clients_to_remove = set()
        try:
            log_msg = LogRequest(**request)
            if self._debug:
                self._logger.debug(f"{self.__class__.__name__}: {log_msg.req_data.log_fields.message}")
            for client in self._clients.values():
                if client.is_alive():
                    await client.push(log_msg)
                else:
                    clients_to_remove.add(client)
                    
            for client in clients_to_remove:
                self.unregister_client(client)

            return {}
        except Exception as error:
            self._logger.error(str(error))
            return {}
    
    async def stream_logs(self, request: web.Request):
        """Stream logs from arriving from message-server to the client.

        Args:
            request (web.Request): The request from the client for websocket connection

        Returns:
            web.WebSocketResponse: The websocket response to the client.
        """
        
        if not self._running:
            self.run()
        client = LogClient()
        self.register_client(client)
        response = await client.run(request)
        return response
