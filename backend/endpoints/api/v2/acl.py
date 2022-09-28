from typing import List
from abc import ABC, abstractmethod
from aiohttp.web_response import Response
from aiohttp import web

from movai_core_shared.exceptions import (
    AclObjectDoesNotExist,
    AclObjectError,
    RestrictedPathError,
)

from dal.models.aclobject import AclGroup, AclObject, AclUser

from backend.core.login import AUTH_MANAGER
from backend.endpoints.api.v2.base import RestBaseClass, BaseWebApp
from backend.http import WebAppManager


class AclObjectRestBaseClass(RestBaseClass, ABC):
    """A Base class for Rest API of AclObject Model"""

    def __init__(self) -> None:
        """initalizes the object"""
        super().__init__()
        self._result = {}
        self.allowed_obj_types = ["user", "group"]

    def extract_scope(self) -> None:
        """sets the scope type."""
        self._scope_name = AclObject.__name__
        self._scope = self.scope_classes.get(self._scope_name)

    def extract_object(self) -> None:
        """Extracts the object name and loads the object from the DB.

        Raises:
            AclObjectDoesNotExist: In case this user does not exist on DB.
        """
        self.extract_domain()
        self.extract_obj_type()
        self.extract_account()
        if self._account_name:
            self._object_name = f"{self._account_name}@{self._domain_name}"
            try:
                self._object = self._scope(self._object_name)
            except KeyError:
                error_msg = (
                    f"The object  {self._scope_name}:"
                    f"{self._domain_name} does not exists."
                )
                raise AclObjectDoesNotExist(error_msg)

    def extract_domain(self):
        """extract domain name from path."""
        self._domain_name = self._request.match_info.get("domain_name")

    def extract_account(self):
        """extract user account name from path."""
        self._account_name = self._request.match_info.get("account_name")

    def extract_obj_type(self):
        """extract the type of object (user or group) from path.

        Raises:
            RestrictedPathError: if the object_type vars is not found in
                the allowed types.
        """
        self._obj_type = self._request.match_info.get("object_type", "user")
        if self._obj_type not in self.allowed_obj_types:
            error_msg = f"the path: {self._request.url} is restricted."
            raise RestrictedPathError(error_msg)

    def query_scope(self) -> None:
        """queries the whole scope from DB, returning all available objects
        with the specified domain.
        """
        super().query_scope()
        keys_to_remove = set()
        for key in self._result.keys():
            if (
                self._result[key]["ObjectType"] != self._obj_type
                or self._result[key]["DomainName"] != self._domain_name
            ):
                keys_to_remove.add(key)
        for key in keys_to_remove:
            self._result.pop(key)

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
            web.HTTPNotfound: if it a DoesNotExist or AclObjectDoesnotExist
                arises.
            web.HTTPBadRequest: if some other error arises.

        Returns:
            Response: The http response to the client.
        """
        try:
            self._result.clear()
            self._request = request
            self.extract_user()
            self.extract_scope()
            self.check_permissions()
            await self.execute_imp()
            return web.json_response(
                self.validate_result(self._result), headers={"Server": "Movai-server"}
            )
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetAclObject(AclObjectRestBaseClass):
    """Retrieve specific AclObject registered in the system."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the AclObject info from the DB."""
        self.extract_object()
        self.query_object()


class GetAclObjects(GetAclObject):
    """Retrieve all the AclObject registered in the system."""

    async def execute_imp(self) -> None:
        """This method fetch the AclObjects info from the DB."""
        self.extract_object()
        self.query_scope()


class SearchDomainObjects(GetAclObject):
    """Searches the domain for user or groups."""

    async def execute_imp(self) -> None:
        """Sends a query to ldap server to retrive objects conforms to
        object CommonName and type
        """
        self.extract_domain()
        self.extract_obj_type()
        common_name = self._request.query["common_name"]
        self._result = AUTH_MANAGER.search_objects(
            self._domain_name, common_name, self._obj_type
        )


class PostAclObjects(AclObjectRestBaseClass):
    """creates new AclObject in the system."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "create"

    async def execute_imp(self) -> None:
        """This method create the AclObject inside the DB."""
        self.extract_domain()
        self.extract_obj_type()
        acl_objects = await self._request.json()
        for acl_object in acl_objects:
            try:
                account_name = acl_object["AccountName"]
                self._result[account_name] = {}
                acl_object["DomainName"] = self._domain_name
                self.validate_role(acl_object["Roles"])
                if self._obj_type == self.allowed_obj_types[0]:
                    AclUser.create(acl_object)
                elif self._obj_type == self.allowed_obj_types[1]:
                    AclGroup.create(acl_object)
                self._result[account_name]["success"] = True
            except AclObjectError as error:
                self._result[account_name]["success"] = False
                self._result[account_name]["reason"] = error.__str__()


class PutAclObjects(AclObjectRestBaseClass):
    """Updates existing AclObjects in the system."""

    def __init__(self) -> None:
        """initializes the object."""
        super().__init__()
        self._permission = "update"

    async def execute_imp(self) -> None:
        """This method updates the requested object."""
        self.extract_domain()
        self.extract_obj_type()
        acl_objects = await self._request.json()
        for acl_object in acl_objects:
            try:
                account_name = acl_object["AccountName"]
                self._result[account_name] = {}
                if "Roles" in acl_object:
                    self.validate_role(acl_object["Roles"])
                obj = AclObject.get_object_by_name(self._domain_name, account_name)
                obj.update(acl_object)
                self._result[account_name]["success"] = True
            except AclObjectError as error:
                self._result[account_name]["success"] = False
                self._result[account_name]["reason"] = error.__str__()


class DeleteAclObjects(AclObjectRestBaseClass):
    """Deletes objects from the system."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "delete"

    async def execute_imp(self) -> None:
        """This method deletes the requested objects from the DB."""
        self.extract_domain()
        self.extract_obj_type()
        acl_objects = await self._request.json()
        for acl_object in acl_objects:
            try:
                account_name = acl_object["AccountName"]
                self._result[account_name] = {}
                AclObject.remove(
                    self._domain_name, acl_object["AccountName"], acl_object["ID"]
                )
                self._result[account_name]["success"] = True
            except AclObjectError as error:
                self._result[account_name]["success"] = False
                self._result[account_name]["reason"] = error.__str__()


class AclAPI(BaseWebApp):
    """Web application for serving as the access list api."""

    single_object_path = "{domain_name}/{object_type}/{account_name}"
    multiple_object_path = "{domain_name}/{object_type}"

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the access list api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(rf"/{self.multiple_object_path}/search", SearchDomainObjects()),
            web.get(rf"/{self.single_object_path}/", GetAclObject()),
            web.get(rf"/{self.multiple_object_path}/", GetAclObjects()),
            web.post(rf"/{self.multiple_object_path}/", PostAclObjects()),
            web.put(rf"/{self.multiple_object_path}/", PutAclObjects()),
            web.delete(rf"/{self.multiple_object_path}/", DeleteAclObjects()),
        ]


WebAppManager.register("/api/v2/Acl", AclAPI)
