from abc import ABC, abstractmethod

from movai_core_shared.messages.log_data import LogRequest


class ParamFilter(ABC):
    """An abstract base class for various types of filter.
    """
    def __init__(self, name: str) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__()
        if not isinstance(name, str):
            raise ValueError("name must be of type string")
        self._name = name

    @abstractmethod
    def filter_msg(self, msg: LogRequest):
        """Abstract function for derived classes.

        Args:
            msg (LogRequest): The log msg to filter
        """
        pass

    @property
    def name(self) -> str:
        """property of the filter name.

        Returns:
            str: The name of the filter.
        """
        return self._name

class StrParam(ParamFilter):
    def __init__(self, name: str, value: str) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__(name)
        if not isinstance(value, str):
            raise ValueError("value must be of type string")
        self._value = value


class IntParam(ParamFilter):
    def __init__(self, name: str, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """        
        super().__init__(name)
        if not isinstance(value, int):
            raise ValueError("value must be an int")
        self._value = value


class ListParam(ParamFilter):
    def __init__(self, name: str, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """        
        super().__init__(name)
        if isinstance(value, str):
            self._value = [val.strip() for val in value.split(",")]
        elif isinstance(value, list):
            self._value = value


class RobotParam(ListParam):
    """A filter for robot name.
    """
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """        
        super().__init__("robots", value)

    def filter_msg(self, msg: LogRequest) -> bool:
        """filters a log messge based on robot name.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """
        return msg.req_data.log_tags.robot  in self._value


class ServiceParam(ListParam):
    """A filter for service name.
    """
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__("services", value)

    def filter_msg(self, msg: LogRequest):
        """filters a log messge based on service name.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """        
        return msg.req_data.log_tags.service in self._value


class LevelParam(ListParam):
    """A filter for level type.
    """
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__("levels", value)

    def filter_msg(self, msg: LogRequest):
        """filters a log messge based on level.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """
        return msg.req_data.log_tags.level in self._value


class MessageParam(StrParam):
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__("message", value)

    def filter_msg(self, msg: LogRequest):
        """filters a log messge based on message content.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """
        return msg.req_data.log_fields.message in self._value


class FromDateParam(int):
    """A filter for issue time is later than specific value.
    """
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__("fromDate", value)

    def filter_msg(self, msg: LogRequest):
        """filters a log messge if issue time is later than filter value.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """
        return msg.created >= self._value
    

class ToDateParam(int):
    """A filter for issue time is before than a specific value.
    """
    def __init__(self, value) -> None:
        """Ctor.

        Args:
            name (str): the name of the filter.
        """
        super().__init__("toDate", value)

    def filter_msg(self, msg: LogRequest):
        """filters a log messge if issue time is before filter value.

        Args:
            msg (LogRequest): The log message to filter.

        Returns:
            bool: True if log message can pass filter, False if not.
        """
        return msg.created < self._value


class LogFilter:
    """A class for filtering a log msg through several types of filters.
    """
    _filters_types = {
        "robot": RobotParam,
        "robots": RobotParam,
        "service": ServiceParam,
        "services": ServiceParam,
        "level": LevelParam,
        "Levels": LevelParam,
        "message": MessageParam,
        "messages": MessageParam,
        "fromDate": FromDateParam,
        "toDate": ToDateParam
     }

    def __init__(self, **params):
        """Ctor
        """
        self._filters = []
        for filter_name, filter_val in params.items():
            filter_name = filter_name.lower()
            if filter_name in self._filters_types and filter_val is not None:
                filter = self._filters_types[filter_name](filter_val)
                self._filters.append(filter)
        
    def filter_msg(self, msg: LogRequest) -> bool:
        """Checks that a LogRequest msg can pass the registered filters.

        Args:
            msg (LogRequest): The LogRequest from the message-server

        Returns:
            bool: True if can pass the filter, False otherwise.
        """
        for filter in self._filters:
            if not filter.filter_msg(msg):
                return False
        return True