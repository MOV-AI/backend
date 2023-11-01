"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer (erez@mov.ai) - 2022
"""
# Work in progress: development has not finished
from typing import List, Dict
from miracle import Acl

from movai_core_shared.envvars import REST_SCOPES
from movai_core_shared.logger import Log

from dal.models.scopestree import scopes
from dal.new_models import Role

LOGGER = Log.get_logger(__name__)


class PermissionsManager:
    """
    This class manages rolsources permissions and their association with the
    different roles in the system.
    """

    _DEFAULT_PERMISSIONS = ["create", "read", "update", "delete"]
    _EXECUTE_PERMISSIONS = _DEFAULT_PERMISSIONS + ["execute"]
    _SPECIAL_PERMISSIONS_MAP = {
        "Application": _EXECUTE_PERMISSIONS,
        "Callback": _EXECUTE_PERMISSIONS,
        "User2": _DEFAULT_PERMISSIONS,
    }

    _acl = Acl()
    _system_resources = []

    def __init__(self, roles: List[str] = []):
        self._init_resources()
        self._init_structure(roles)

    @classmethod
    def _init_resources(
        cls,
    ) -> None:
        cls._system_resources = REST_SCOPES.strip("()").split("|")
        cls._system_resources.append("Applications")

    @classmethod
    def _init_structure(cls, roles: List[str] = []) -> None:
        """Setup ACL for the current user role and user resources"""
        if len(roles) == 0:
            roles = Role.list_roles_names()
        for role_name in roles:
            try:
                role_obj = Role(role_name)
                for (resource_key, permissions) in role_obj.Resources.items():
                    for permission in permissions:
                        if permission:
                            cls.add_permission(role_obj.ref, resource_key, permission)
            except Exception as e:
                LOGGER.error(e)
                msg = f"{role_name} role is invalid, its permissions " f"won't be evaluated."
                LOGGER.warning(msg)

    @classmethod
    def add_permission(cls, role_name: str, resource_name: str, permission_name: str) -> None:
        msg = f"granting the {role_name} role {resource_name}:{permission_name} permission."
        LOGGER.info(msg)
        cls._acl.grant(role_name, resource_name, permission_name)

    @classmethod
    def remove_permission(cls, role_name: str, resource_name: str, permission_name: str) -> None:
        msg = f"revoking from {role_name} role {resource_name}:{permission_name} permission."
        LOGGER.info(msg)
        cls._acl.revoke(role_name, resource_name, permission_name)

    @classmethod
    def check_permission(
        cls, roles_names: List[str], resource_name: str, permission_name: str
    ) -> bool:
        msg = f"cheking for {roles_names} role {resource_name}:{permission_name} permission."
        return cls._acl.check_any(roles_names, resource_name, permission_name)

    @classmethod
    def get_roles(cls) -> Dict:
        """returns dict with available roles

        this has just a tiny little interface to keep this function alive

        use scopes().list_scopes(scope='Role') to get an actual list of scopes
        """
        return cls._acl.get_roles()

    @classmethod
    def get_resources(cls) -> List[str]:
        """:returns list with available resources"""
        return cls._acl.get_resources()

    @classmethod
    def get_permissions(cls, resource: str) -> List[str]:
        """:returns dict with available resources & permissions"""
        return cls._acl.get_permissions(resource)


PERM_MANAGER = PermissionsManager()


#    @staticmethod
#    def get_permissions() -> Dict:
#        """ :returns dict with available resources & permissions """
#
#        resources = PermissionsManager.get_resources()
#        resources_permissions = {}
#        # Scopes
#        for scope in resources:
#            try:
#                resources_permissions[scope] = PermissionsManager._SPECIAL_PERMISSIONS_MAP[scope]
#            except KeyError:
#                resources_permissions[scope] = PermissionsManager._DEFAULT_PERMISSIONS
#
#        applications = scopes().list_scopes(scope='Application')
#        resources_permissions['Applications'] = [app['ref'] for app in applications]
#
#        return resources_permissions
