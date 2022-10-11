from abc import ABC, abstractmethod
from typing import List
from aiohttp import web
from aiohttp.web_response import Response

from movai_core_shared.exceptions import (
    LdapConfigDoesNotExist,
    LdapConfigInvalidStructure,
    UserPermissionsError,
)

from dal.models.ldapconfig import LdapConfig

from backend.core.ldap import LDAPHandler
from backend.core.login import AUTH_MANAGER, LDAPAuthentication

from backend.http import WebAppManager
from backend.endpoints.api.v2.base import BaseWebApp
from backend.endpoints.api.v2.base import RestBaseClass


class LdapConfigRestBaseClass(RestBaseClass, ABC):
    """A base class for the LdapConfig Rest API"""

    def __init__(self) -> None:
        """initalizes the object."""
        super().__init__()
        self._result = {}

    def extract_scope(self):
        """Determine the requested scope."""
        self._scope_name = LdapConfig.__name__
        self._scope = self.scope_classes.get(self._scope_name)

    def extract_object(self):
        """Extract the required object from DB.

        Raises:
            LdapConfigDoesNotExist: in case object can not be found.
        """
        super().extract_object(LdapConfigDoesNotExist)

    def validate_not_user_domain(self):
        if self._user.domain_name == self._object_name:
            error_msg = (
                f"User {self._user.principal_name} cannot remove "
                f"his own domain {self._object_name}."
            )
            self.log.error(error_msg)
            raise UserPermissionsError(error_msg)

    def validate_domain(self, domain_name):
        if domain_name != self._object_name:
            error_msg = (
                f"The LDAP configuration domain: {domain_name} is"
                f" different from path domain: {self._object_name}"
            )
            raise LdapConfigInvalidStructure(error_msg)

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
            self.extract_scope()
            await self.execute_imp()
            return web.json_response(
                self.validate_result(self._result), headers={"Server": "Movai-server"}
            )
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)


class GetLdapConfigurations(LdapConfigRestBaseClass):
    """Retrieve all the LDAP configurations registered on the system."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.extract_object()
        self.check_permissions()
        self.query_scope()


class GetLdapConfiguration(LdapConfigRestBaseClass):
    """Retrieve the LDAP configuration of a specific domain."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.extract_object()
        self.check_permissions()
        self.query_object()


class PostConfiguration(LdapConfigRestBaseClass):
    """Creates an LDAP configuration of a specific domain."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "create"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.check_permissions()
        data = await self._request.json()
        domain_name = data["DomainName"]
        obj = LdapConfig.create(data)
        if obj is not None:
            AUTH_MANAGER.register_authenticator(
                domain_name, LDAPAuthentication(domain_name)
            )
        self._result["success"] = True


class PutConfiguration(LdapConfigRestBaseClass):
    """Creates an LDAP configuration of a specific domain."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "update"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.extract_object()
        self.check_permissions()
        data = await self._request.json()
        domain_name = data.get("DomainName")
        if domain_name is not None:
            self.validate_domain(domain_name)
        self._object.update(data)
        self._result["success"] = True


class DeleteConfiguration(LdapConfigRestBaseClass):
    """Delete an LDAP configuration of a specific domain."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "delete"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.extract_object()
        self.validate_not_user_domain()
        self.check_permissions()
        self._scope.remove(self._object_name)
        AUTH_MANAGER.unregister_authenticator(self._object_name)
        self._result["success"] = True


class GetConfigurationValidation(LdapConfigRestBaseClass):
    """Validate the LDAP configuration of a specific domain."""

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method validate the configuration against the LDAP servers."""
        self.extract_object()
        self.check_permissions()
        ldap = LDAPHandler(self._object_name)
        self._result["success"] = await self.run_blocking_code(
            ldap.validate_configuration
        )


class PostConfigurationValidation(LdapConfigRestBaseClass):
    """creates a LDAP configurationm, validates it and than removes it."""

    def __init__(self) -> None:
        super().__init__()

    async def execute_imp(self) -> None:
        """This method creates an LdapConfig in the DB, validates it and
        than deletes it.
        """
        data = await self._request.json()
        domain_name = data["DomainName"]
        obj = LdapConfig.create(data)
        ldap = LDAPHandler(domain_name)
        self._result["success"] = await self.run_blocking_code(
            ldap.validate_configuration
        )
        obj.delete()


class LdapConfigAPI(BaseWebApp):
    """Web application for serving as the ldap configuration api."""

    domain = r"/{object_name}/"

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the ldap configuration api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/", GetLdapConfigurations()),
            web.get(self.domain, GetLdapConfiguration()),
            web.post(r"/new", PostConfiguration()),
            web.put(self.domain, PutConfiguration()),
            web.delete(self.domain, DeleteConfiguration()),
            web.get(r"/{object_name}/validate", GetConfigurationValidation()),
            web.post(r"/validate", PostConfigurationValidation()),
        ]


WebAppManager.register("/api/v2/LdapConfig", LdapConfigAPI)
