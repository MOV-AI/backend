"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer (erez@mov.ai) - 2023
"""
from abc import ABC, abstractmethod
from typing import List
from aiohttp import web
from aiohttp.web_response import Response

from dal.models.callback import Callback
from dal.models.message import Message

from backend.endpoints.api.v2.base import BaseWebApp
from backend.endpoints.api.v2.base import RestBaseClass
from backend.http import WebAppManager

class FrontendRestBaseClass(RestBaseClass, ABC):
    """A base class for the Frontend Rest API"""

    def __init__(self) -> None:
        """initalizes the object."""
        super().__init__()
        self._result = {}

    @abstractmethod
    def execute_imp(self) -> None:
        """This is an abstract method represent the core functionality to
        exceute for each one of the subclasses.
        This function is being called in the __call__ method after all
        required data has been fethced.
        """

    async def __call__(self, request: web.Request) -> Response:
        """This is an general function which acts as a general shell function
        for various endpoints implementation.
        it calls the execute_imp function after extracting all required data
        from the http request.

        Args:
            request (web.Request): The http request.

        Raises:
            web.HTTPForbidden: if it a UserPermissionError arises.
            web.HTTPBadRequest: if some other error arises.

        Returns:
            Response: The http response to the client.
        """
        try:
            self._request = request
            self.extract_user()
            await self.execute_imp()
            return web.json_response(self.validate_result(self._result), headers={"Server": "Movai-server"})
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetFrontend(FrontendRestBaseClass):

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.check_permissions()


class CallbackEditor(FrontendRestBaseClass):

    def __init__(self) -> None:
        super().__init__()
        self.responses = {
            "init": Callback.export_modules,
            "get_libraries"  : Callback.get_modules,
            "get_all_libraries"  : Callback.fetch_modules_api,
            "get_messages"   : Message.fetch_portdata_messages,
            "get_msg_struct" : Message.get_structure,
            "library"        : self.describe_module,
        }

    def execute_imp(self) -> None:
        try:
            key = self._request["func"]
            args = self._request.get("args", {})
            response = {"func": key, "result": self.responses[key](**args), "success": True}
            return response
        except Exception as error:
            exc_result = CallbackEditor.handle_exception(error)
            response = {"success": False, "error": exc_result}

    @staticmethod
    def handle_exception(exc: Exception):
        exc_classname = exc.__class__.__name__
        handle_map = {
            "IndentationError" : ["filename", "lineno", "msg", "offset", "text"],
            "SyntaxError" : ["filename", "lineno", "msg", "offset", "text"]
        }
        handler = lambda exc, names : {name: getattr(exc, name) for name in names}

        if exc_classname in handle_map:
            return {"type": exc_classname, "data": handler(exc, handle_map[exc_classname])}
        raise exc

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
    
    # check if useful
#    for x in module:
#        if not x in required:
#            to_return[x] = module[x]
#    for element_name in dir(mymodule):
#        element = getattr(mymodule, element_name)
#        el = {
#            'value': element_name,
#            'label': element_name,
#            'name' : element_name,
#        }
#        if inspect.isclass(element):
#             try:
#                 to_return['classes'].append(el)
#             except:
#                 print("ERROR CLASSES")
#        elif inspect.ismodule(element):
#            continue
#        elif hasattr(element, '__call__'):
#            if inspect.isbuiltin(element):
#                try:
#                    to_return['builtin_functions'].append(el)
#                except:
#                    print("ERROR BUILT-IN FUNCTION")
#            else:
#                try:
#                    to_return['functions'].append(el)
#                except:
#                    print("ERROR FUNCTION")
#                    pass
#        else:
#            try:
#                to_return['values'].append(el)
#            except:
#                print("ERROR VALUES")
#    return to_return
    
    

class FrontendAPI(BaseWebApp):
    """Web application for serving as the frontend api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the ldap configuration api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/", GetFrontend()),
            web.get(r"/callbackeditor", CallbackEditor()),
        ]


WebAppManager.register("/api/v2/Frontend", FrontendAPI)
