"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Usage:
        Basic 0MQ client for connecting 0MQ servers.

   Developers:
   - Erez Zomer (erez@mov.ai) - 2023
"""
import asyncio
import uuid
from logging import Logger

from aiohttp import WSMsgType, web
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.log_filter import LogFilter
from backend.helpers.rest_helpers import fetch_request_params

QUEUE_SIZE = 100000


class LogClient:
    def __init__(self, logger: Logger = None) -> None:
        self._id = uuid.uuid4()
        if logger is None:
            logger = Log.get_logger(self.__class__.__name__)
        self._logger = logger
        self._sock = None
        self._filter = None
        self._ws = None
        self._queue = asyncio.Queue(QUEUE_SIZE)

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def socket(self) -> web.WebSocketResponse:
        return self._sock

    async def prepare_socket(self, request: web.Request):
        """prepares the socket

        Args:
            request (web.Request): the request for websocket.

        Raises:
            web.HTTPError: in case the socket can't be prepared.

        Returns:
            web.WebSocketResponse: The websocket reponse object.
        """
        ws = web.WebSocketResponse()
        if ws.can_prepare(request):
            await ws.prepare(request)
            self._ws = ws
            return ws
        else:
            error_msg = "The socket could not be established"
            self._logger.warning(error_msg)
            raise web.HTTPError(error_msg)

    async def push(self, request: LogRequest):
        """Push a message to client's queue.

        Args:
            request (LogRequest): The LogRequest from the message-server.
        """
        if self._filter.filter_msg(request):
            await self._queue.put(request)

    async def send_msg(self, request: LogRequest):
        """Sends a log message to the client by the client format.

        Args:
            request (LogRequest): The LogRequest from the message-server.
        """
        self._validate_socket()
        try:
            log_msg = request.get_client_log_format()
            await self._ws.send_json(log_msg)
        except (ValueError, RuntimeError, TypeError) as err:
            self.logger.error(err.__str__())

    async def stream_msgs(self):
        """Pops requests from the queue and sends them to the client in a loop.
        runs as long as the websocket is not closed.
        """
        while self.is_alive():
            msg = await self._queue.get()
            await self.send_msg(msg)

    async def listen_to_client_msgs(self):
        """listens for client msgs and repond if necessary."""
        self._validate_socket()
        async for msg in self._ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == "close":
                    self._logger.debug(
                        "closing the websocket connection for client id: {self._id}"
                    )
                    await self._ws.close()
            elif msg.type == WSMsgType.ERROR:
                self._logger.error(f"ws connection closed with exception {ws.exception()}")

    async def run(self, request: web.Request):
        """Runs the client object in oreder to stream logs from backed to client.

        Args:
            request (web.Request): The websocket request from the client.

        Returns:
             web.WebSocketResponse: The websocket reponse object.
        """
        params = fetch_request_params(request)
        self._filter = LogFilter(**params)
        await self.prepare_socket(request)
        asyncio.create_task(self.listen_to_client_msgs())
        await self.stream_msgs()
        return self._ws

    def is_alive(self) -> bool:
        """Checks if the socket is not closed.

        Returns:
            bool: True if open, False otherwise.
        """
        if self._ws is None:
            return False
        return not self._ws.closed

    def _validate_socket(self):
        """Validates the websocket attribute.

        Raises:
            TypeError: in case the websocket is not initialized.
            ConnectionError: in case the socket is closed.
        """
        if self._ws is None:
            raise TypeError("The websocket is not initialized for client {self._id}")
        if not self.is_alive():
            raise ConnectionError(f"The websocket for client {self.id} is closed!")
