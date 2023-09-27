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
import logging
import uuid


from movai_core_shared.core.zmq.zmq_subscriber import ZMQSubscriber
from movai_core_shared.core.zmq.zmq_manager import ZMQManager
from movai_core_shared.logger import Log
from movai_core_shared.messages.log_data import LogRequest

from backend.core.log_streamer.log_client import LogClient


class LogStreamer:
    def __init__(self, debug: bool = False) -> None:
        """Initializes the object.

        Args:
            debug (bool, optional): if True, will show debug logs.
        """
        self._debug = debug
        self._logger = logging.getLogger(self.__class__.__name__)
        self._subscriber: ZMQSubscriber = ZMQManager.get_async_subscriber("tcp://message-server:9001")
        self._clients = {}
        self._running = False

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
            self._logger.debug(
                f"The client: {client.id} is already registered in {self.__class__.__name__}"
            )
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

    async def handle(self, request: dict) -> dict:
        """Handles incoming messages.

        Args:
            request (dict): A request with logs.

        Returns:
            dict: empty response
        """
        clients_to_remove = set()
        try:
            log_msg = LogRequest(**request)
            if self._debug:
                self._logger.debug(
                    f"{self.__class__.__name__}: {log_msg.req_data.log_fields.message}"
                )
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

    async def listen(self):
        while self._running:
            msg = await self._subscriber.recieve()
            await self.handle(msg)
            #await asyncio.sleep(1.0)
            
    def start(self):
        self._running = True
        self._logger.info("starting log streamer server!")
        if asyncio._get_running_loop() is None:
            asyncio.run(self.listen())
        else:
            asyncio.create_task(self.listen())

    def stop(self):
        self._running = False

    if __name__ == "__main__":
        log_streamer = LogStreamer()
        log_streamer.start()