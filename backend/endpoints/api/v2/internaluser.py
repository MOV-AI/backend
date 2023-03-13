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

from movai_core_shared.consts import INTERNAL_DOMAIN
from movai_core_shared.exceptions import (
    UserDoesNotExist,
    UserError,
    UserPermissionsError,
)

from dal.movaidb import MovaiDB
from dal.models.internaluser import InternalUser

from backend.http import WebAppManager
from backend.endpoints.api.v2.base import BaseWebApp, RestBaseClass


class InternalUserRestBaseClass(RestBaseClass, ABC):
    """A Base class for Rest API of InternalUser"""

    def __init__(self) -> None:
        """initalizes the object"""
        super().__init__()
        self._result = {}

    def extract_scope(self) -> None:
        """sets the scope the call is directed too."""
        self._scope_name = InternalUser.__name__
        self._scope = self.scope_classes.get(self._scope_name)

    def extract_object(self) -> None:
        """Extracts the object name and loads the object from  the DB.
        the object is the user name the call is directed too.

        Raises:
            web.HTTPNotFound: In case this user does not exist on DB.
        """
        self._object_name = self._request.match_info.get("object_name", False)
        account_name = self._object_name
        if self._object_name and issubclass(self._scope, InternalUser):
            self._object_name = self._object_name + "@" + INTERNAL_DOMAIN

        if self._object_name:
            try:
                self._object = self._scope(self._object_name)
            except KeyError:
                error_msg = f"The object  {self._scope_name}:" f"{account_name} does not exists."
                raise UserDoesNotExist(error_msg)

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
            self.extract_scope()
            await self.execute_imp()
            self._result["success"] = True
            return web.json_response(
                self.validate_result(self._result), headers={"Server": "Movai-server"}
            )
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetScope(InternalUserRestBaseClass):
    """This class serves the InternalUser read endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the InternalUser info from the DB."""
        self.extract_object()
        self.check_permissions()
        if self._object_name:
            query = {self._scope_name: {self._object_name: "**"}}
            scope_result = MovaiDB().get(query)
            self._result = scope_result[self._scope_name][self._object_name]
            self._result.pop("Password", None)
        else:
            scope_result = MovaiDB().get_by_args(self._scope_name)
            self._result = scope_result.get(self._scope_name, {})
            for key in self._result.keys():
                self._result[key].pop("Password", None)


class PostScope(GetScope):
    """This class serves the InternalUser create endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "create"

    async def execute_imp(self) -> None:
        """This method create new InternalUser in the DB."""
        self.check_permissions()
        data = await self._request.json()
        self.validate_role(data["Roles"])
        user_obj = InternalUser.create(
            data["AccountName"],
            data["Password"],
            data["Roles"],
            data["CommonName"],
            data["Email"],
            data["SuperUser"],
            data["ReadOnly"],
            data["SendReport"],
        )
        user_obj.update_time()


class PutScope(GetScope):
    """This class serves the InternalUser update endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "update"

    async def execute_imp(self) -> None:
        """This method updates an InternalUser object in the DB."""
        self.extract_object()
        self.check_permissions()
        data = await self._request.json()
        if "Roles" in data:
            self.validate_role(data["Roles"])
        self._object.update(data)
        self._object.update_time()


class DeleteScope(GetScope):
    """This class serves the InternalUser delete endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "delete"

    def validate_internaluser(self):
        if isinstance(self._user, InternalUser):
            if self._user.principal_name == self._object_name:
                error_msg = "User can not delete himself."
                raise UserPermissionsError(error_msg)

    async def execute_imp(self) -> None:
        """This method deletes an InternalUser object from the DB."""
        self.extract_object()
        self.check_permissions()
        self.validate_internaluser()
        self._object.remove(self._object.account_name)


class ResetPassword(InternalUserRestBaseClass):
    """This class serves the password reset endpoint."""

    def __init__(self) -> None:
        """initializes the object."""
        super().__init__()
        self._permission = "reset"

    async def execute_imp(self) -> None:
        """exceute the core functionallity for the http request.

        Args:
            data (dict): the data sent in the request
            result (dict): the result to send back to the client.
        """
        self.check_permissions()
        self.extract_object()
        data = await self._request.json()
        self._object.reset_password(data["NewPassword"], data["ConfirmPassword"])


class ChangePassword(InternalUserRestBaseClass):
    """This class serves the password change endpoint."""

    def validate_requesting_user(self) -> None:
        """Validates the requesting user is the same as the requested path.

        Raises:
            UserPermissionsError: if the requested user is different
        """
        if not isinstance(self._user, InternalUser):
            error_msg = "Only Internal users are allowed to change password"
            raise UserError(error_msg)

    async def execute_imp(self) -> None:
        self.validate_requesting_user()
        data = await self._request.json()
        self._user.change_password(
            data["CurrentPassword"], data["NewPassword"], data["ConfirmPassword"]
        )


class InternalUserWebApp(BaseWebApp):
    """Web application for serving InternalUser api."""

    def __init__(self, app: web.Application):
        super().__init__(app)

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the access list api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/", GetScope()),
            web.get(r"/{object_name}/", GetScope()),
            web.post(r"/new/", PostScope()),
            web.put(r"/{object_name}/", PutScope()),
            web.delete(r"/{object_name}/", DeleteScope()),
            web.post(r"/{object_name}/reset-password", ResetPassword()),
            web.post(r"/change-password", ChangePassword()),
        ]


WebAppManager.register("/api/v2/InternalUser", InternalUserWebApp)
