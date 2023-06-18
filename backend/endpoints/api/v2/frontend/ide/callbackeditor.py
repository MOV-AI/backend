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
from dal.models.scopestree import scopes

from backend.endpoints.api.v2.base import BaseWebApp
from backend.endpoints.api.v2.base import RestBaseClass
from backend.http import WebAppManager

class FrontendRestBaseClass(RestBaseClass, ABC):
    """A base class for the Frontend Rest API"""

    _allowed_funcs = {
        "init": Callback.export_modules,
        "getlibraries"  : Callback.get_modules,
        "getalllibraries"  : Callback.fetch_modules_api,
        "getmessages"   : Message.fetch_portdata_messages,
        "getmsgstruct" : Message.get_structure,
        "library"        : Callback.get_methods
    }

    def __init__(self) -> None:
        """initalizes the object."""
        super().__init__()
        self._result = {}
        self._args = {}
        self._func = None

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
            self.extract_params()
            await self.execute_imp()
            return web.json_response(self._result, headers={"Server": "Movai-server"})
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.handle_exception(error)
            self._result = {"success": False, "error": exc_result}
            return web.json_response(self._result, headers={"Server": "Movai-server"})

    @staticmethod
    async def handle_exception(exc: Exception):
        exc_classname = exc.__class__.__name__
        handle_map = {
            "IndentationError" : ["filename", "lineno", "msg", "offset", "text"],
            "SyntaxError" : ["filename", "lineno", "msg", "offset", "text"]
        }
        handler = lambda exc, names : {name: getattr(exc, name) for name in names}

        if exc_classname in handle_map:
            return {"type": exc_classname, "data": handler(exc, handle_map[exc_classname])}
        raise exc

    def extract_func(self):
        """Extracts function name from request.
        """
        self._func = self._request.match_info.get("func")
        if self._func is None:
            raise web.HTTPBadRequest(reason=f"The function can not be None.")
        if self._func not in self._allowed_funcs:
            raise web.HTTPBadRequest(reason=f"The function: {self._func} is not defined")

    def extract_args(self):
        """Extract arguments from payload.
        """
        self._args = self._data.get("args", {})


class Getfunc(FrontendRestBaseClass):

    async def execute_imp(self) -> None:
        try:
            self.extract_func()
            self._result = {"result": self._allowed_funcs[self._func](**self._args), "success": True}
        except Exception as error:
            exc_result = self.handle_exception(error)
            self._result = {"success": False, "error": exc_result}

class GetLibrary(Getfunc):

    def execute_imp(self):
        module = self._params.get("module")
        if module is None:
            raise web.HTTPBadRequest(reason="The module parameter is missing.")
        required = ["name", "toSelect"]
        if not all(x in module for x in required):
            raise web.HTTPBadRequest(reason=f"The module {module} does not have all the required attributes.")
        try:
            result = {
                "module"   : self._allowed_funcs["library"](module["name"]),
                "toSelect" : module["toSelect"],
                "name"     : module["name"]
            }
            self._result = {"result": result, "success": True}
        except Exception as error:
            exc_result = self.handle_exception(error)
            self._result = {"success": False, "error": exc_result}
    
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
            web.get(r"/{func}/", Getfunc())
        ]


WebAppManager.register("/api/v2/frontend/callbackeditor", FrontendAPI)
