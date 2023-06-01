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

from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.filter import LogFilter

class Client:
    def __init__(self, filter: LogFilter, logger: Logger = None) -> None:
        self._id = uuid.uuid4()
        self._filter = filter
        if logger is None:
            logger = Log.get_logger(self.__class__.__name__)
        self._logger = logger
        self._sock = None

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
