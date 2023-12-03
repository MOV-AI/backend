# required keys:
#    func - name of the method to call
# optional keys:
#    args - dictionary to pass to method (positional arguments not allowed)
#
# curl example with localhost server 
#    curl -d "{\"func\":\"get_msg_struct\", \"args\":{\"message\": \"geometry_msgs/Twist\"}}" -X POST http://localhost:5003/api/v1/function/SERVER3_CODEEDITOR2/

from aiohttp import web

from dal.models.callback import Callback
from dal.models.message import Message

class CallbcakEditor:

    @staticmethod    
    def get_libraries(*args, **kwargs):
        return Callback.get_modules()

    @staticmethod
    def init(*args, **kwargs):
        Callback.export_modules()
        return True

    @staticmethod
    def get_all_libraries(*args, **kwargs):
        print("Get all libraries called")
        return Callback.fetch_modules_api()

    @staticmethod
    def get_messages(*args, **kwargs):
        return Message.fetch_portdata_messages()

    @staticmethod
    def get_msg_struct(*, message, **kwargs):
        return Message.get_structure(message)

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
    
#def handle_exception(exception):
#    exc_classname = exception.__class__.__name__
#    handle_map = {
#        "IndentationError" : ["filename", "lineno", "msg", "offset", "text"], 
#        "SyntaxError" : ["filename", "lineno", "msg", "offset", "text"],
#    }
#    handler = lambda e, names : {name: getattr(e, name) for name in names}
#    
#    if exc_classname in handle_map:
#        return {"type": exc_classname, "data": handler(e, handle_map[exc_classname])}
#    raise exception
#

#async def callback_editor(request: web.Request) -> web.Response:
#    try:
#        msg = await request.json()
#        key = msg["func"]
#        args = msg.get("args", {})
#        response = {"func": key, "result": responses[key](**args), "success": True}
#        return web.json_response(response)
#    except Exception as err:
#        #exc_result = handle_exception(err)
#        response = {"success": False, "error": str(err)}
