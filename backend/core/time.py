from datetime import datetime

def current_time_string() -> str:
    return datetime.now().strftime("%d/%m/%Y at %H:%M:%S")

def current_timestamp_float() -> float:
    return datetime.now().timestamp()

def current_timestamp_int() -> int:
    return int(datetime.now().timestamp())

def delta_time_int(delta: int) -> int:
        """returns a future time in timestamp format.

        Args:
            expiration_delta (int): the time delta from now.

        Returns:
            int: an int representing the time delta.
        """
        return int((datetime.now() + delta).timestamp())

def delta_time_float(delta: int) -> float:
        """returns a future time in timestamp format.

        Args:
            expiration_delta (int): the time delta from now.

        Returns:
            float: an float representing the time delta.
        """
        return (datetime.now() + delta).timestamp()
