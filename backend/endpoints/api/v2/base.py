from socket import gethostname
from typing import Any, List
import json
from datetime import date, datetime
import asyncio
import aiohttp_cors
from aiohttp import web
from aiohttp.web_response import Response

from movai_core_shared.logger import Log
from movai_core_shared.exceptions import (
    AclObjectAlreadyExist,
    AclObjectDoesNotExist,
    AlreadyExist,
    DoesNotExist,
    LdapConfigAlreadyExist,
    LdapConfigDoesNotExist,
    RoleAlreadyExist,
    RoleDoesNotExist,
    UserAlreadyExist,
    UserDoesNotExist,
    MovaiException,
    UserPermissionsError,
)


from dal.movaidb import MovaiDB
from dal.models.aclobject import AclObject
from dal.models.ldapconfig import LdapConfig

from dal.models.role import Role
from dal.models.internaluser import InternalUser
from dal.models.remoteuser import RemoteUser

from gd_node.protocols.http.middleware import redirect_not_found

from backend.http import IWebApp


class RestBaseClass:
    """Base class for REST operations"""

    log = Log.get_logger("RestBaseClass")

    def __init__(self) -> None:
        """initializes the object"""
        self.api_version = "/api/v2/"
        self.node_name = gethostname()
        self.scope_classes = {
            "InternalUser": InternalUser,
            "RemoteUser": RemoteUser,
            "LdapConfig": LdapConfig,
            "AclObject": AclObject,
            "Role": Role,
        }
        self._request = None
        self._user = None
        self._scope = None
        self._object = None
        self._data = None
        self._params = {}
        self._loop = asyncio.get_event_loop()
        self._permission = "read"

    @staticmethod
    def json_serializer_converter(obj):
        """JSON serializer for objects not serializable by default json code

        Args:
            obj (_type_): object to serialize.

        Raises:
            TypeError: if given type is not from correct type.

        Returns:
            _type_: a serialized type.
        """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    def extract_user(self):
        """Extract the user from the http request."""
        self._user = self._request.get("user")

    def extract_scope(self):
        """Determine the requested scope."""
        self._scope_name = self._request.match_info("scope")
        self._scope = self.scope_classes.get(self._scope_name)

    def extract_object(self, exception: MovaiException = DoesNotExist):
        """Extract the required object from DB.

        Args:
        exception (Movaiexception) - the type of exception to raise
            in case the object does not exist.

        Raises:
            DoesNotExist: in case object can not be found.
        """
        self._object_name = self._request.match_info.get("object_name", False)
        if self._object_name:
            try:
                self._object = self._scope(self._object_name)
            except KeyError:
                error_msg = (
                    f"The object {self._scope_name}:" f"{self._object_name} does not exists."
                )
                raise exception(error_msg)

    async def extract_data(self):
        """Extracts payload data from the request.
        """
        self._data = await self._request.json()

    async def extract_params(self):
        """Extract parametes from query string.
        """
        for param in self._request.query_string.split("&"):
            name, value = param.split("=")
            self._params[name] = value

    async def check_permissions(self):
        """checks user permission for the given scope.

        Raises:
            UserPermissionsError: in case the user is missing the required
            scope permission for the reuested scope.
        """
        if not self._user.has_permission(self._scope_name, self._permission):
            error_msg = (
                f"User does not have {self._permission} permission "
                f"for {self._scope_name} scope."
            )
            raise UserPermissionsError(error_msg)

    def validate_result(self, result: dict):
        """validate the result is serializeable before sending the response.

        Args:
            result (dict): a dictionary containing all response information.

        Raises:
            web.HTTPBadRequest: in case an error arise during serializing
                the response.

        Returns:
            _type_: an unserialized data.
        """
        try:
            json_result = json.dumps(result, default=self.json_serializer_converter)
            return json.loads(json_result)
        except Exception as exc:
            self.log.error(f"caught error while creating json, exception: {exc}")
            raise web.HTTPBadRequest(reason="Error when serializing JSON response.")

    @classmethod
    def validate_role(cls, roles: List[str]) -> None:
        if len(roles) == 0:
            error_msg = f"Role must be specified for every user or group."
            raise ValueError(error_msg)
        for role in roles:
            if not Role.is_exist(role):
                error_msg = f"The Role: {role} does not exist."
                raise RoleDoesNotExist(error_msg)

    def query_object(self):
        query = {self._scope_name: {self._object_name: "**"}}
        scope_result = MovaiDB().get(query)
        self._result = scope_result[self._scope_name][self._object_name]
        self._result.pop("Password", None)
        self._result.pop("SecretKey", None)

    def query_scope(self):
        scope_result = MovaiDB().get_by_args(self._scope_name)
        self._result = scope_result.get(self._scope_name, {})
        for key in self._result.keys():
            self._result[key].pop("Password", None)
            self._result[key].pop("SecretKey", None)

    async def run_blocking_code(self, func: callable, *args) -> Any:
        """Runs a blocking function that may take long time.

        Args:
            func (callable): The function to run.

        Returns:
            Any: The return value of the function.
        """

        executor = self._request.app["executor"]
        future = self._loop.run_in_executor(executor, func, *args)
        return await future

    def analyze_error(self, error: Exception, error_msg: str) -> None:
        """This function maps the exceptions throuwn by the system to
        an exception of http.

        Args:
            error (Exception): The thrown exception.
            error_msg (str): The error msg to show with the exception.

        Raises:
            web.HTTPForbidden: In case the endpoing get a UserPermissionError.
            web.HTTPNotFound: In case the endpoing get a DoesNotExist exception.
            web.HTTPConflict: In case the endpoing get a AlreadyExist exception.
            web.HTTPBadRequest: In case the endpoing get a MovaiException.
            web.HTTPInternalServerError: In case the endpoing get a general Exception.
        """
        if isinstance(error, (UserPermissionsError)):
            raise web.HTTPForbidden(reason=str(error_msg))
        elif isinstance(
            error,
            (
                DoesNotExist,
                UserDoesNotExist,
                RoleDoesNotExist,
                LdapConfigDoesNotExist,
                AclObjectDoesNotExist,
            ),
        ):
            raise web.HTTPNotFound(reason=str(error_msg))
        elif isinstance(
            error,
            (
                AlreadyExist,
                UserAlreadyExist,
                RoleAlreadyExist,
                LdapConfigAlreadyExist,
                AclObjectAlreadyExist,
            ),
        ):
            raise web.HTTPConflict(reason=str(error_msg))
        elif isinstance(error, MovaiException):
            raise web.HTTPBadRequest(reason=str(error_msg))
        elif isinstance(error, Exception):
            raise web.HTTPInternalServerError(reason=str(error_msg))


class GetScope(RestBaseClass):
    """A callable object (functor) for serivng as a get request handler."""

    def __call__(self, request: web.Request) -> Response:
        """A special function for making the class callable.

        Args:
            request (web.Request): the http request.

        Raises:
            web.HTTPNotFound: if the requested object is not found on DB.

        Returns:
            Response: the requested object details.
        """
        self._request = request
        self.extract_user()
        self.extract_scope()
        self.extract_object()
        self.check_permissions()
        result = {}

        if self._object_name:
            query = {self._scope_name: {self._object_name: "**"}}
            scope_result = MovaiDB().get(query)
            result = scope_result[self._scope_name][self._object_name]
        else:
            scope_result = MovaiDB().get_by_args(self._scope_name)
            result = scope_result.get(self._scope_name, {})
            for key in result.keys():
                result[key].pop("Password", None)

        if not result:
            raise web.HTTPNotFound(reason="Required scope not found.")

        return web.json_response(self.validate_result(result), headers={"Server": "Movai-server"})


class BaseWebApp(IWebApp):
    """Web application for serving as the access list api."""

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._node_name = gethostname()
        self.log = Log.get_logger(self.__class__.__name__)

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the access list api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return []

    @property
    def middlewares(self) -> List[web.middleware]:
        """This function defines the middlewares which are used in
        the access list api.

        Returns:
            List[web.middleware]: a list of middlewares.
        """
        return [redirect_not_found]

    @property
    def cors(self) -> aiohttp_cors.CorsConfig:
        """Defines the cors setup for the web application.

        Returns:
            aiohttp_cors.CorsConfig: a configuration of the cors setup.
        """
        return aiohttp_cors.setup(
            self._app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            },
        )

    @property
    def safe_list(self) -> List[str]:
        """defines the routes which do not require token validation.

        Returns:
            List[str]: list of routes.
        """
        return []
