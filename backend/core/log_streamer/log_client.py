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
from logging import Logger
import uuid
import asyncio

from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.log_filter import LogFilter

QUEUE_SIZE = 100000

class LogClient:
    def __init__(self, filter: LogFilter, logger: Logger = None) -> None:
        self._id = uuid.uuid4()
        self._filter = filter
        if logger is None:
            logger = Log.get_logger(self.__class__.__name__)
        self._logger = logger
        self._sock = None
        self._queue = asyncio.Queue(max_size=QUEUE_SIZE)

    @property
    def id(self):
        return self._id

    @property
    def socket(self):
        return self._sock
    
    def set_socket(self, sock: web.WebSocketResponse):
        if self._sock is None:
            self._sock = sock
        else:
            self._logger.warnnin("Socket is already set")

    def __del__(self):
        try:
            self._sock.close()
        except Exception:
            self._sock.force_close()

    async def push(self, request: LogRequest):
        await self._queue.put(request)

    async def send_msg(self, msg: LogRequest):
        try:
            if self._filter.filter_msg(msg):
                log_request = msg.dict()
                log_data = log_request.get("log_data")
                log_data.pop("measurement")
                await self._sock.send_json(log_data)
        except (ValueError ,RuntimeError, TypeError) as err:
            self.logger.error(err.__str__())

    async def stream_msgs(self):
        while True:
            msg = self._queue.get()
            self.send_msg(msg)
        
    def run(self):
        asyncio.create_task(self.stream_msgs())
        
            