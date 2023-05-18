class Responses:
    def __init__(self) -> None:
        self._responses = {}

    def register_response(self, name, response):
        if response is None:
            raise ValueError("Response is None!")
        self._responses[name] = response