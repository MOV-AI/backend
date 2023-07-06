"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer (erez@mov.ai) - 2022

   Module that implements version 2 of the REST APi module/plugin
"""

from abc import ABC, abstractmethod
from typing import List
from aiohttp import web
from aiohttp.web_response import Response

from dal.models.role import Role

from backend.http import WebAppManager
from backend.endpoints.api.v2.base import BaseWebApp, RestBaseClass


class RoleRestBaseClass(RestBaseClass, ABC):
    """A Base class for Rest API of Role."""

    def __init__(self) -> None:
        """initalizes the object"""
        super().__init__()
        self._result = {}

    def extract_scope(self) -> None:
        """sets the scope the call is directed too."""
        self._scope_name = Role.__name__
        self._scope = self.scope_classes.get(self._scope_name)

    @abstractmethod
    async def execute_imp(self) -> None:
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
            self.extract_scope()
            await self.execute_imp()
            return web.json_response(
                self.validate_result(self._result), headers={"Server": "Movai-server"}
            )
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetScope(RoleRestBaseClass):
    """This class serves the Role read endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the role info from the DB."""
        self.extract_object()
        self.check_permissions()
        if self._object_name:
            self.query_object()
        else:
            self.query_scope()


class PostScope(GetScope):
    """This class serves the Role create endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "create"

    async def execute_imp(self) -> None:
        """This method create new Role in the DB."""
        self.check_permissions()
        payload = await self._request.json()
        data = payload.get("data")
        role_obj: Role = Role.create(data["Label"], data["Resources"])
        role_obj.update_time()
        self._result["success"] = True
        self._result["name"] = data["Label"]


class PutScope(GetScope):
    """This class serves the Role update endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "update"

    async def execute_imp(self) -> None:
        """This method updates an Role object in the DB."""
        self.extract_object()
        self.check_permissions()
        payload = await self._request.json()
        data = payload["data"]
        if data.get("Resources") is None:
            raise web.HTTPBadRequest(reason="Resources is missing from request body")
        self._object.update(data["Resources"])
        self._object.update_time()
        self._result["success"] = True
        self._result["name"] = data["Label"]


class DeleteScope(GetScope):
    """This class serves the Role delete endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "delete"

    async def execute_imp(self) -> None:
        """This method deletes an Role object from the DB."""
        self.extract_object()
        self.check_permissions()
        Role.remove(self._object_name)
        self._result["success"] = True
        self._result["name"] = self._object_name


class RoleWebApp(BaseWebApp):
    """Web application for serving Role api."""

    def __init__(self, app: web.Application):
        self.object_path = r"/{object_name}/"
        super().__init__(app)

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the access list api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """

        return [
            web.get(r"/", GetScope()),
            web.get(self.object_path, GetScope()),
            web.post(r"/", PostScope()),
            web.post(self.object_path, PutScope()),
            web.delete(self.object_path, DeleteScope()),
        ]


WebAppManager.register("/api/v2/Role", RoleWebApp)
