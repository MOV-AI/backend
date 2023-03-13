"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer (erez@mov.ai) - 2022
"""

from abc import ABC, abstractmethod
from typing import List
from aiohttp import web
from aiohttp.web_response import Response

from backend.http import WebAppManager
from backend.endpoints.api.v2.base import BaseWebApp, RestBaseClass


class BaseUserRestBaseClass(RestBaseClass, ABC):
    """A Base class for Rest API of InternalUser"""

    def __init__(self) -> None:
        """initalizes the object"""
        super().__init__()
        self._result = {}

    @abstractmethod
    async def execute_imp(self) -> None:
        """This is an abstract method represent the core functionality to
        exceute for each one of the subclasses.
        This function is being called in the __call__ method after all
        required data has been fethced.

        Args:
            data (dict): The request supplied data.
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
            return web.json_response(
                self.validate_result(self._result), headers={"Server": "Movai-server"}
            )
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetUserPermissions(BaseUserRestBaseClass):
    """This class serves the BaseUser permissions endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the InternalUser info from the DB."""
        self._result["Roles"] = self._user.roles
        self._result["Permissions"] = self._user.get_effective_permissions()
        self._result["SuperUser"] = self._user.super_user


class BaseUserWebApp(BaseWebApp):
    """Web application for serving InternalUser api."""

    def __init__(self, app: web.Application):
        super().__init__(app)

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the access list api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [web.get(r"/effective-permissions", GetUserPermissions())]


WebAppManager.register("/api/v2/User", BaseUserWebApp)
