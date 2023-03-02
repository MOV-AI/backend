from typing import List
from abc import ABC, abstractclassmethod

from movai_core_shared.logger import Log
from movai_core_shared.consts import INTERNAL_DOMAIN
from movai_core_shared.exceptions import (
    AclObjectDoesNotExist,
    AuthorizationError,
    DomainDoesNotExist,
    InitializationError,
    InvalidCredentials,
    UserDoesNotExist,
)

from dal.models.model import Model
from dal.models.aclobject import AclObject, AclUser, AclGroup
from dal.models.ldapconfig import LdapConfig
from dal.models.internaluser import InternalUser
from dal.models.remoteuser import RemoteUser

from backend.core.ldap import LDAPHandler, LDAPUser, LDAPGroup


class AuthenticationBaseInf(ABC):
    """This is an abstract class to define the interface the Authentication
    manager expect to get.
    """

    log = Log.get_logger(__name__)

    @abstractclassmethod
    def authenticate(self, username: str, password: str) -> bool:
        """This abstract function defines user authentication.

        Args:
        username - the login name of the user who wants login.
        password - the password of the user.
        """

    @abstractclassmethod
    def authorize(self, username: str) -> bool:
        """This abstract function defines user authorization

        Args:
        username - the login name of the user who wants login.
        """

    @abstractclassmethod
    def get_user_obj(self, domain_name: str, username: str) -> Model:
        """This abstract function returns the user object in the correct type

        Args:
        domain_name - the name of the domain the user is member of.
        username - the login name of the user who wants login.

        Returns:
        the correct Model for user object
        """


class RemoteAuthenticationBaseInf(AuthenticationBaseInf):
    @abstractclassmethod
    def search_obj(self, common_name: str, object_type: str, results_limit: int = 20) -> list:
        """This function search for an object on a sprcific domain.

        Args:
            common_name (str): the known name for the object
            object_type (str): user or groups
            results_limit (int, optional): limits the amount of results.
                Defaults to 20.

        Returns:
            list: a list of objects that came up in the query, list
                size cannot exceed results_limit argument.
        """


class InternalAuthentication(AuthenticationBaseInf):
    """This class implements the authentication interface in order to
    authenticate internal users.
    """

    def __init__(self, domain_name: str) -> None:
        """This function initializes the InternalAuthentication interface

        Args:
            domain_name (str): the name which symbols the domain for internal
            users.
        """
        self.domain_name = domain_name
        self.internal_user = None

    def init_user(self, account_name: str) -> None:
        """A helper method for loading the correct user details from DB.

        Args:
            username - the name of the user to load.
        """
        self.internal_user = InternalUser.get_user_by_name(self.domain_name, account_name)

    def authenticate(self, account_name: str, password: str) -> bool:
        """This method authenticates internal users against DB records.

        Args:
            username - the name of the user who logs in.
            password (str): the password for the corresponding user.

        Returns:
            bool: return True if authentication succeeds, False otherwise
        """
        self.init_user(account_name)
        return self.internal_user.verify_password(password)

    def authorize(self, account_name: str) -> bool:
        """This method is not implemented in this interface

        Args:
        username - the name of the user who logs in.

        Returns:
            bool: return True if user is defined in access list,
            False otherwise.
        """
        return True

    def get_user_obj(self, domain_name: str, account_name: str) -> Model:
        """This method returns the user in the correct model.

        Args:
        domain_name (str) - the name symbols the domain for internal
            users.

        Returns:
        the User object which represent internal users.
        """
        self.init_user(account_name)
        return self.internal_user


class PAMAuthentication(RemoteAuthenticationBaseInf):
    """This class implements the authentication interface in order to
    authenticate and authorize host machine users through PAM.
    """

    def __init__(self, domain_name: str) -> None:
        """initializes the PAMAuthentication interface

        Args:
            domain_name (str): the name of the host machine which the user
            belongs to.
        """
        self.domain_name = domain_name

    def authenticate(self, username: str, password: str) -> bool:
        """authenticate a user with the host machine.

        Args:
        username - the name of the user who logs in.
        password - the password for the corresponding user.

        Returns:
            bool: return True if authentication succeeds, False otherwise
        """
        # TODO
        pass

    def authorize(self, username: str) -> bool:
        """verifies that a user is allowed to login

        Args:
        username - the name of the user who logs in.

        Returns:
            bool: return True if user is defined in access list,
            False otherwise.
        """
        # TODO
        pass

    def get_user_obj(self, domain: str, username: str) -> Model:
        """This method returns the user in the correct model.

        Args:
        domain_name (str) - he name of the host machine which the user
            belongs to.

        Returns:
        The RemoteUser Model.
        """
        # TODO
        pass

    def search_obj(self, common_name: str, object_type: str, results_limit: int = 20) -> list:
        """This function search for an object on a sprcific domain.

        Args:
            common_name (str): the known name for the object
            object_type (str): user or groups
            results_limit (int, optional): limits the amount of results.
                Defaults to 20.

        Returns:
            list: a list of objects that came up in the query, list
                size cannot exceed results_limit argument.
        """
        # TODO
        pass


class LDAPAuthentication(RemoteAuthenticationBaseInf):
    """This class implements the authentication interface in order to
    authenticate and authorize users through LDAP connection.
    """

    def __init__(self, domain_name: str) -> None:
        """initializes the LDAPAuthentication interface

        Args:
            domain_name (str): the name of the domain which the user
            belongs to.
        """
        self.domain_name = domain_name
        self.init_ldap_handler()
        self.ldap_user = None
        self.ldap_group = None
        self.remote_user = None
        self.prev_groups = set()
        self.current_groups = []

    def init_ldap_handler(self):
        self.handler = LDAPHandler(self.domain_name)

    def init_ldap_user(self, account_name: str) -> None:
        """A helper method for loading the correct user details from LDAP
        server.

        Args:
            account_name (str)- the account name of the user to load.
        """
        self.ldap_user = LDAPUser(self.domain_name, account_name, self.handler)

    def init_ldap_group(self, account_name: str) -> None:
        """A helper method for loading the correct group details from LDAP
        server.

        Args:
            account_name - the account name of the group to load.
        """
        self.ldap_group = LDAPGroup(self.domain_name, account_name, self.handler)

    def _is_user_in_users_list(self, acl_user: list) -> AclUser:
        """checks if a given user is found on of the authorized users list
        based on the user SID.

        Returns:
            bool: True if the user is found on the list

        Raises:
            DoesNotExist: in case user in not found on users access list.
        """
        user_is_allowed = False
        allowed_user = AclUser.get_object_by_name(self.domain_name, self.ldap_user.account_name)
        if self.ldap_user.sid == allowed_user.ID:
            acl_user.append[allowed_user]
            user_is_allowed = True
        return user_is_allowed

    def _is_user_in_groups_list(self, groups_objects: List[AclObject]) -> list:
        """checks wheather a group which contains the user as a member is found
        on of the groups access list.

        Returns:
            list: a list of AclObjects with all the groups in the access list
                which the user is member of.
        """
        user_in_group_list = False
        try:
            current_groups = AclGroup.list_group_names(self.domain_name)
            for group_name in current_groups:
                if self._is_user_member_of_group(group_name):
                    user_in_group_list = True
                    group_object = AclGroup.get_object_by_name(self.domain_name, group_name)
                    groups_objects.append(group_object)
            return user_in_group_list
        except AclObjectDoesNotExist as a:
            error_msg = f"There was a problem loading the AclObject {a}"
            raise AuthorizationError(error_msg)

    def _is_user_member_of_group(self, account_name: str) -> bool:
        """check if a user is a member of specific group.

        Args:
        account_name (str): the account_name of the group.

        Returns:
            bool: True if the user is found to be a member of the group,
            False otherwise.
        """
        user_is_a_member = False
        self.init_ldap_group(account_name)
        for member in self.ldap_group.members:
            try:
                member_object = LDAPGroup.get_member_object(self.domain_name, member, self.handler)
                if isinstance(member_object, LDAPUser):
                    if self.ldap_user.sid == member_object.sid:
                        user_is_a_member = True
                        break
            except InitializationError as i:
                self.log.error(i)
                continue
        return user_is_a_member

    def init_user(self, remote_user: dict):
        """A helper method for loading the correct user details from DB.

        Args:
            username - the name of the user to load.
        """
        try:
            self.remote_user = RemoteUser.get_user_by_name(self.domain_name, remote_user["AccountName"])
            self.remote_user.update(remote_user)
        except UserDoesNotExist:
            self.remote_user = RemoteUser.create(
                domain_name=self.domain_name,
                account_name=remote_user["AccountName"],
                common_name=remote_user["CommonName"],
                user_type=remote_user['Type'],
                roles=remote_user["Roles"],
                email=remote_user['Email'],
                super_user=remote_user["SuperUser"],
                read_only=remote_user["ReadOnly"],
            )

    def create_remote_user_dict(self, acl_objects: list) -> dict:
        remote_user = {
            "DomainName": self.domain_name,
            "AccountName": self.ldap_user.account_name,
            "CommonName": self.ldap_user.common_name,
            "Roles": [],
            "Email": self.ldap_user.principal_name,
            "Type": "LDAP",
            "ReadOnly": False,
            "SuperUser": False,
            "SendReport": False,
        }
        roles = set()
        for obj in acl_objects:
            if obj is not None:
                for role in obj.Roles:
                    roles.add(role)
                if obj.ReadOnly:
                    remote_user["ReadOnly"] = True
                if obj.SuperUser:
                    remote_user["SuperUser"] = True
        remote_user["Roles"] = list(roles)
        return remote_user

    def authenticate(self, username: str, password: str) -> bool:
        """authenticate a user with the LDAP server (AD)

        Args:
        username - the name of the user who logs in.
        password - the password for the corresponding user.

        Returns:
            bool: return True if authentication succeeds, False otherwise
        """
        self.init_ldap_handler()
        self.init_ldap_user(username)
        return self.ldap_user.authenticate(password)

    def authorize(self, account_name: str) -> bool:
        """verifies that a user is allowed to login

        Args:
        account_name - the name of the user who logs in.

        Returns:
            bool: return True if user is defined in access list,
            False otherwise.
        """
        user_allowed = False
        acl_objects = []
        self.init_ldap_user(account_name)
        try:
            if AclUser.is_exist(self.ldap_user._domain_name, self.ldap_user._account_name):

                acl_user = AclUser.get_object_by_name(self.ldap_user._domain_name, self.ldap_user._account_name)
                acl_objects.append(acl_user)
                user_allowed = True

            if self._is_user_in_groups_list(acl_objects):
                user_allowed = True

            if user_allowed:
                remote_user = self.create_remote_user_dict(acl_objects)
                self.init_user(remote_user)

            return user_allowed
        except AclObjectDoesNotExist:
            error_msg = (
                "There was a problem loading the AclObject that " f"match {self.ldap_user.principal_name} account"
            )
            raise AuthorizationError(error_msg)

    def get_user_obj(self, domain: str, username: str) -> Model:
        """This method returns the user in the correct model.

        Args:
        domain_name (str): the name of the domain which the user
            belongs to.

        Returns:
        the RemoteUser object which represent ldap users.
        """
        return self.remote_user

    def search_obj(self, common_name: str, object_type: str, limit: int = 20) -> list:
        """This function search for an object on the domain.

        Args:
            common_name (str): the known name for the object
            object_type (str): user or groups
            results_limit (int, optional): limits the amount of results.
                Defaults to 20.

        Returns:
            list: [description]
        """
        self.init_ldap_handler()
        return self.handler.search_object(common_name, object_type, limit=limit)


class AuthenticationManager:
    """This class abstracts the login process for different type of users by
    encapsulating authentication interfaces for different types of user
    mangement systems"""

    log = Log.get_logger('AuthenticationManager')

    def __init__(self, auto_init: bool = True) -> None:
        """initializes the AuthenticationManager object.

        Args:
            auto_init (bool, optional): determine if auto init method should
            be called, Defaults to True.
        """
        self.domain_list = [INTERNAL_DOMAIN]
        self.infs = {}
        if auto_init:
            self._auto_init()

    def _auto_init(self) -> None:
        """registers internal and host domains, than register LDAP
        configurations found in DB.
        """
        self.register_authenticator(INTERNAL_DOMAIN, InternalAuthentication(INTERNAL_DOMAIN))
        self._init_ldap_domains()

    def _init_ldap_domains(self) -> None:
        """helper function to query all ldap configurations from DB"""
        for ldap_domain in LdapConfig.list_config_names():
            self.log.debug(f"appending ldap domain: {ldap_domain}")
            self.domain_list.append(ldap_domain)
            self.register_authenticator(ldap_domain, LDAPAuthentication(ldap_domain))

    def register_authenticator(self, domain: str, interface: AuthenticationBaseInf) -> bool:
        """Registers new authentication interfaces

        Args:
        domain (str): a key value for interface registeration.
        interface (AuthenticationBaseInf): the object to register.

        Returns:
            (bool): True if registeration succeeds, False otherwise.
        """
        if self.infs.get(domain) is None:
            self.log.debug(f"registering domain: {domain} with authenticator of type" f"{interface.__class__.__name__}")
            self.infs[domain] = interface
            return True
        else:
            self.log.warning(f"interface {domain} already exist, please unregister it first")
            return False

    def unregister_authenticator(self, domain_name: str) -> bool:
        """Unregisters authentication interfaces

        Args:
        domain_name (str): a key value representing the interface
            to unregister.

        Returns:
            (bool): True if unregisteration succeeds, False otherwise.
        """
        try:
            self.infs.pop(domain_name)
            return True
        except KeyError:
            error_msg = f"domain {domain_name} is not registered on the system"
            self.log.error(error_msg)
            return False

    def verify_user(self, domain_name: str, account_name: str, password: str):
        """this functions handles both authentication and authorization
        process for a user to login

        Args:
            domain_name (str): the domain the user belongs to.
            account_name (str): the name of the user to log in.
            password (str): the password of the corresponding user.

        Raises:
            InvalidCredentials: if the user credentials are incorrect.
            AuthorizationError: if the user is not allowed to log in
                the system.
            DomainDoesNotExist: if the domain does not exist.
        """
        try:
            if self.infs[domain_name].authenticate(account_name, password):
                if self.infs[domain_name].authorize(account_name):
                    info_msg = f"User {account_name}@{domain_name} is " "authorized to access the system."
                    self.log.info(info_msg)
                else:
                    warn_msg = f"User {account_name}@{domain_name} is not " "authorized to access the system."
                    self.log.warning(warn_msg)
                    raise AuthorizationError(warn_msg)
            else:
                error_msg = "invalid username/password"
                raise InvalidCredentials(error_msg)
        except KeyError:
            error_msg = f"domain {domain_name} is not registered on the system"
            self.log.error(error_msg)
            raise DomainDoesNotExist(error_msg)

    def get_user(self, domain_name: str, account_name: str) -> Model:
        """return the user in the correct type: (User, RemoteUser)

        Args:
        domain_name (str): the domain the user belongs to.
        account_name (str): the name of the user to log in.

        Returns:
            (Model): a User or RemoteUser object
        """
        try:
            user = self.infs[domain_name].get_user_obj(domain_name, account_name)
            return user
        except KeyError:
            error_msg = f"domain {domain_name} is not registered on the system"
            self.log.error(error_msg)
            raise DomainDoesNotExist(error_msg)

    def search_objects(self, domain_name: str, common_name: str, object_type: str) -> list:
        """search an object in the desired domain.

        Args:
            domain_name (str): the domain the user belongs to.
            account_name (str): the name of the user to log in.
            object_type (str): users or groups

        Returns:
            dict: a dictionary containing user details.
        """
        try:
            search_results = self.infs[domain_name].search_obj(common_name, object_type)
            return search_results
        except KeyError:
            error_msg = f"domain {domain_name} is not registered on the system"
            self.log.error(error_msg)
            raise DomainDoesNotExist(error_msg)

    def get_domains(self) -> list:
        """This function returns a list of the registered domains.

        Returns:
            list: a list containing the domains names of the different
                interfaces registered.
        """
        domains = []
        for domain in self.infs.keys():
            domains.append(domain)
        return domains


AUTH_MANAGER = AuthenticationManager()
