# required keys:
#    func - name of the method to call
# optional keys:
#    args - dictionary to pass to method (positional arguments not allowed)
#
# curl example with localhost server 
#    curl -d "{\"func\":\"get_msg_struct\", \"args\":{\"message\": \"geometry_msgs/Twist\"}}" -X POST http://localhost:5003/api/v1/function/SERVER3_CODEEDITOR2/
from aiohttp import web

from gd_node.callback import Callback
from gd_node.message import Message


from backend.endpoints.api.v1.frontend.general import Responses


class CallbackEditor:

    def __init__(self) -> None:
        self._responses = Responses()
        self._responses.register_response("init", Callback.export_modules)
        self._responses.register_response("get_libraries", Callback.get_modules)
        self._responses.register_response("get_all_libraries", Callback.fetch_modules_api)
        self._responses.register_response("get_messages", Message.fetch_portdata_messages)
        self._responses.register_response("get_msg_struct", Message.get_structure)
        self._responses.register_response("library", self.describe_module)

    @staticmethod
    def describe_module(*, module, **kwargs):
        required = ["name", "toSelect"]
        if not all(x in module for x in required):
            return False
        to_return = {
            "module"   : Callback.get_methods(module["name"]),
            "toSelect" : module["toSelect"],
            "name"     : module["name"]
        }
        return to_return

    def handle_exception(exception):
        exc_classname = e.__class__.__name__
        handle_map = {
            "IndentationError" : ["filename", "lineno", "msg", "offset", "text"], 
            "SyntaxError" : ["filename", "lineno", "msg", "offset", "text"]
        }
        handler = lambda e, names : {name: getattr(e, name) for name in names}

        if exc_classname in handle_map:
            return {"type": exc_classname, "data": handler(e, handle_map[exc_classname])}
        raise exception

    async def execute(self, request: web.Request):
        """execute the requested func.

        Args:
            request (web.Request): _description_
        """
        try:
            data = await request.json()
            key = data.get("func")
            args = data.get("args", {})
            response = {"func": key, "result": self._responses[key](**args), "success": True}
        except Exception as e:
            exc_result = self.handle_exception(e)
            response = {"success": False, "error": exc_result}
        
