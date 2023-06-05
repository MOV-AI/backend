"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Usage:
        Basic 0MQ client for connecting 0MQ servers.

   Developers:
   - Erez Zomer (erez@mov.ai) - 2023
"""
import logging

from movai_core_shared.core.zmq_server import ZMQServer
from movai_core_shared.envvars import LOG_STREAMER_BIND_ADDR
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest


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
        
    async def handle_request(self, request: dict) -> dict:
        """Implements the handle_request function for ZMQServer.

        Args:
            request (dict): A request witho logs.

        Returns:
            dict: response
        """
        try:
            log_msg = LogRequest(**request)
            print(f"{self.__class__.__name__}: {log_msg.req_data.log_fields.message}")
            return {}
        except Exception as error:
            self._logger.error(str(error))
            return {}
