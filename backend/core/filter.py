from abc import ABC
import multiprocessing

from movai_core_shared.logger import Log

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
        

class LogManager:
    def __init__(self):
        # default stuff
        self._logger = Log.get_logger(self.__class__.__name__)


        self._queue: multiprocessing.Queue = None
        self.push_process: multiprocessing.Process = None
            # this is not a manager, run push_manager

            # By default, Queue uses a lock to ensure thread safety, it's a thread safe.
        self._queue = multiprocessing.Queue()
        self._logger.debug(
                "initializing seperate process for forwarding to manager...."
            )
        self.process_pool = list()
    
    def __del__(self):
        for push_process in self.process_pool:
            if push_process is not None:
                push_process.terminate()
                push_process.join()

        if self._queue is not None:
            self._queue.close()
            self._queue.join_thread()
