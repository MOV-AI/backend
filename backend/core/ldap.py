import ldap3
from ldap3 import Server, ServerPool, Connection, Tls
from ldap3.core.exceptions import LDAPException, LDAPExceptionError, LDAPInvalidCredentialsResult

from movai_core_shared.logger import Log
from movai_core_shared.exceptions import InitializationError, LdapConfigDoesNotExist
from movai_core_shared.envvars import (
    LDAP_SEARCH_TIME_LIMIT,
    LDAP_CONNECTION_RECEIVE_TIMEOUT,
    LDAP_POOLING_LOOP_TIMEOUT,
)

from dal.models.ldapconfig import LdapConfig


class LDAPConnectionBuilder:
    """This class is builder class for the ldap3's Connection object"""

    log = Log.get_logger("LDAPConnectionBuilder")

    def __init__(self, ldap_config: LdapConfig) -> None:
        """This fuction initializes the object by getting a configuration object.

        Args:
            ldap_config (LdapConfig): the config is a set of values that
            controls the ldap communication.
        """
        self._ldap_config = ldap_config
        self._servers = []
        self._pool = ServerPool(pool_strategy=ldap3.FIRST, active=3, exhaust=True)
        self._tls = Tls()
        self._connection = None
        ldap3.set_config_parameter("POOLING_LOOP_TIMEOUT", LDAP_POOLING_LOOP_TIMEOUT)

    def create_tls(self) -> None:
        """This function create the Tls object required for the server object."""
        self._tls = Tls(version=self._ldap_config.SSLVersion)

    def create_server(self, host: str, port: str) -> None:
        """This function create the Server object required for the Connection
        object.

        Args:
            host (str): the ip or name of the LDAP server
            port (str): the port used for connetion (usually it is 389 for
            unsecured communaction or 636 for encrypted connection).
        """
        if isinstance(host, str) and host != "":
            server = Server(host, port=port, use_ssl=True, get_info=ldap3.ALL, tls=self._tls)
            if server not in self._pool.servers:
                self._pool.add(server)
            else:
                self.log.warning(f"server {server} is already in server pool")

    def create_connection(self, username: str, password: str) -> None:
        """This function creates the Connection object

        Args:
            username (str): the user which will be used by ldap library to
            access ldap servers for querying info.
            password (str): the password for this user.

        Raises:
            LDAPExceptionError: raised exception in case the connection object
            initialization fails.
        """
        self._connection = Connection(
            self._pool,
            user=username,
            password=password,
            auto_bind=ldap3.AUTO_BIND_NONE,
            authentication=ldap3.SIMPLE,
            client_strategy=ldap3.SYNC,
            check_names=True,
            read_only=True,
            lazy=False,
            raise_exceptions=True,
            auto_range=True,
            receive_timeout=LDAP_CONNECTION_RECEIVE_TIMEOUT,
        )
        if self._connection is None:
            error_msg = "Failed to create connection object"
            self.log.error(error_msg)
            raise LDAPExceptionError(error_msg)

    def build_connection_object(self) -> Connection:
        """This function builds the connection object with its subcomponents.

        Returns:
            Connection: Connection object which enables communication with the
             ldap servers.
        """
        self.create_tls()
        self.create_server(self._ldap_config.PrimaryHost, self._ldap_config.PrimaryPort)
        self.create_server(self._ldap_config.SecondaryHost, self._ldap_config.SecondaryPort)
        self.create_connection(self._ldap_config.bind_username, self._ldap_config.password)
        return self._connection


class LDAPBaseClass:

    log = Log.get_logger("LDAPBaseClass")

    def __init__(self) -> None:
        self._initialized = False

    def check_initialization(self) -> None:
        """checks if the object is initialized.

        Raises:
            InitializationError: if the object is not initialized.
        """
        if not self._initialized:
            error_msg = "object not initialized"
            self.log.error(error_msg)
            raise InitializationError(error_msg)


class LDAPHandler(LDAPBaseClass):
    """This class handles the ldap communication, it holds the connection
    object and enables the user to authenticate different users with the ldap
     serves or query info about objects in the ldap DB
    """

    def __init__(self, domain_name: str) -> None:
        """this function initializes the object, it expects a configuration
         name to load from DB

        Args:
            domain_name (str): the name of the AD domain (LDAP) which the
             handler would connect to.
        """
        self.log.debug(f"loading LdapConfig: {domain_name}")
        self._domain_name = domain_name
        try:
            self._ldap_config: LdapConfig = LdapConfig.get_config_by_name(domain_name)
            self.ldap_connention = LDAPConnectionBuilder(
                self._ldap_config
            ).build_connection_object()
            self._initialized = True
        except LdapConfigDoesNotExist:
            self._initialized = False
            self.log.error(f"Failed to initialize {self.__class__.__name__}")

    def validate_configuration(self) -> bool:
        """validates the configuration against a server

        Returns:
            bool: True if validation succeeds, False otherwise.
        """
        self.check_initialization()
        status = False
        try:
            self.ldap_connention.bind()
            self._ldap_config.update_validation(status)
            self.log.info(f"Succesfully validated {self._domain_name} LDAP " "Configuration.")
            status = True
        except LDAPException:
            self._ldap_config.update_validation(status)
            self.log.warning(f"Failed to validate {self._domain_name} LDAP " "Configuration.")
        return status

    def authenticate_user(self, username: str, password: str) -> bool:
        """this method is used to to check if supplied user credentials are
        able to bind to ldap server.

        Args:
            username (str): the name of the user authenticate against the AD
            domain (LDAP server).
            password (str): the password for this user.

        Returns:
            bool: returns True if authentication succeeds
        """
        try:
            self.check_initialization()
            original_username = self._ldap_config.username
            original_password = self._ldap_config.password
            tmp_config = self._ldap_config
            tmp_config.username = username
            tmp_config.password = password
            tmp_connention = LDAPConnectionBuilder(tmp_config).build_connection_object()
            self._ldap_config.username = original_username
            self._ldap_config.password = original_password
            tmp_connention.bind()
            msg = f"successfully authenticated user {username} with" f"domain {self._domain_name}"
            self.log.info(msg)
            self.ldap_connention.unbind()
            return True
        except LDAPInvalidCredentialsResult as e:
            self.log.warning(
                f"Failed to Authenticate {username} thorugh LDAP at" f" {self._domain_name}"
            )
            self.log.warning(f"details: {e.description}")
        return False

    def get_object_info(
        self,
        search_filter: str = "(objectclass=person)",
        search_attributes: list = ["objectSid"],
        object_type: str = "user",
        limit: int = 1,
    ) -> list:
        """This method queries LDAP server for info about object.

        Args:
            search_base ([type], optional): the exact location in the LDAP
            server search tree where the query will look for the object.
            Defaults to None.
            search_filter ([type], optional): filters to use in the query to
            narrow the search results. Defaults to None.
            search_attributes (list, optional): the type of info that will be
            returned for each each of the objects that resulted in the query.
            Defaults to ["objectSid"].

        Returns:
            list: list with the LDAP query results.
        """
        self.check_initialization()
        search_results = []
        search_base = str(self._ldap_config.users_dn)
        if object_type == "group":
            search_base = self._ldap_config.groups_dn
        if search_filter is None and object_type == "group":
            search_filter = "(objectclass=group)"
        self.ldap_connention.bind()
        self.log.debug(
            "LDAP connection has successfully bound user"
            f" {self._ldap_config.username} with domain"
            f" {self._ldap_config.domain_name}"
        )
        self.log.debug(
            f"""querying LDAP server:
                            search_base: {search_base},
                            search_filter: {search_filter},
                            attributes: {search_attributes}"""
        )
        self.ldap_connention.search(
            search_base=search_base,
            search_filter=search_filter,
            attributes=search_attributes,
            size_limit=limit,
            time_limit=LDAP_SEARCH_TIME_LIMIT,
        )
        search_results = self.ldap_connention.entries[0:limit]
        if len(search_results) == 0:
            error_msg = "Ldap query did not return any results"
            self.log.warning(error_msg)
        self.ldap_connention.unbind()
        return search_results

    def search_object(
        self, common_name: str, object_type: str, attributes: list = [], limit: int = 1000
    ) -> list:
        """This function will search an object on the LDAP directory by his
        common name field,

        Args:
            common_name (str): the common name of the object to look for.
            object_type (str): user or group.
            attributes (list, optional): which attributes to retrieve about the
                object. Defaults to [].
            limit (int, optional): max num of results to return.
                Defaults to 1000.

        Returns:
            list: a list containing all objects that came up on the search.
        """
        search_filter = (
            f"(&(cn={common_name+'*'})" f"(objectclass=user)" f"(!(isCriticalSystemObject=True)))"
        )
        if not attributes:
            attributes = ["sAMAccountName", "cn", "objectSid"]
        if object_type == "group":
            search_filter = search_filter.replace("user", "group")
        results = []
        for obj in self.get_object_info(
            search_filter=search_filter,
            search_attributes=attributes,
            object_type=object_type,
            limit=limit,
        ):
            obj_required_details = {}
            obj_required_details["CommonName"] = str(obj["cn"])
            obj_required_details["AccountName"] = str(obj["sAMAccountName"])
            obj_required_details["ID"] = str(obj["objectSid"])
            results.append(obj_required_details)
        return results

    def search_distinguished_name(self, distinguished_name: str) -> list:
        """This function searches an object in the LDAP directory by his
        distinguished name, and returns all the results it found.

        Args:
        distinguish_name (str): The object distinguished name.

        Returns:
         (list) - a list of all objects come up in the search.
        """
        search_base = self._ldap_config.users_dn
        search_filter = f"(distinguishedName={distinguished_name})"
        search_attributes = ["sAMAccountName", "objectClass"]
        if self.ldap_connention.bind():
            self.log.debug(
                "LDAP connection has successfully bound user"
                f" {self._ldap_config.users_dn} with domain"
                f" {self._ldap_config.domain_name}"
            )
            self.log.debug(
                f"""querying LDAP server:
                                search_base: {search_base},
                                search_filter: {search_filter},
                                attributes: {search_attributes}"""
            )
            self.ldap_connention.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=search_attributes,
                time_limit=LDAP_SEARCH_TIME_LIMIT,
            )

            if len(self.ldap_connention.entries) == 0:
                search_base = self._ldap_config.groups_dn
                self.ldap_connention.search(
                    search_base=search_base,
                    search_filter=search_filter,
                    attributes=search_attributes,
                    time_limit=LDAP_SEARCH_TIME_LIMIT,
                )
            try:
                search_result = self.ldap_connention.entries[0]
                self.ldap_connention.unbind()
                return search_result
            except IndexError:
                self.log.warning("ldap query did not return any results")
                return []
            except LDAPException as ldap_exception:
                self.log.warning(ldap_exception)
                return []


class LDAPObject(LDAPBaseClass):
    """This class represent an object that got returned from the query of the
    LDAP server, it's mainly focuses on info which is common for user and
    group objects
    """

    def __init__(
        self, domain_name: str, account_name: str, object_type: str, ldap_handler: LDAPHandler
    ) -> None:
        """This function initialized the LDAPObject

        Args:
            domain_name (str): the domain in which the object exist
            (e.g.: example.com).
            account_name (str): the object account name
            (e.g.: johns for johns@example.com).
            ldap_handler (LDAPHandler): a handler to query the LDAP server.
        """
        self._domain_name = domain_name
        self._account_name = account_name
        self._object_type = object_type
        if isinstance(ldap_handler, LDAPHandler):
            self._handler = ldap_handler
        else:
            self._handler = LDAPHandler(self._domain_name)
        self._obj_info = {}
        self._search_filter = ""
        self._search_attributes = [
            "name",
            "distinguishedName",
            "sAMAccountName",
            "cn",
            "objectCategory",
            "objectClass",
            "objectGUID",
            "objectSid",
        ]

    def is_initialized(self):
        return self._initialized

    def init_object(self):
        """a helper function for inializing the object"""
        self._init_object(filter=self._search_filter, attributes=self._search_attributes)

    def _init_object(self, filter=None, attributes=None) -> dict:
        """This method is using the ldap server to quiery tne information
        about the object from LDAP server

        Args:
            filter ([type], optional): The fields and values to filter the
            search results. Defaults to None.
            attributes ([type], optional): which type of fields to return with
            the result. Defaults to None.

        Raises:
            Exception: if there are no resultes an exception would be raised

        Returns:
            dict: a dictionary  the required attribues specified at function
            call
        """
        obj_info = self._handler.get_object_info(
            search_filter=filter, search_attributes=attributes, object_type=self._object_type
        )
        if not obj_info:
            self._initialized = False
            raise InitializationError("Failed to initialize object")
        else:
            self._obj_info = obj_info[0]
            self._initialized = True

    @property
    def distinguished_name(self) -> str:
        """Property attribute fo object distinguished name field.

        Returns:
            str: the distinguished name (e.g.:CN=John Smith,CN=Users,
            DC=example,DC=com)
        """
        self.check_initialization()
        return str(self._obj_info["distinguishedName"])

    @property
    def account_name(self) -> str:
        """Property attribute fo object account name field.

        Returns:
            str: the account name (e.g.: johns)
        """
        self.check_initialization()
        return str(self._obj_info["sAMAccountName"])

    @property
    def common_name(self) -> str:
        """Property attribute fo object common name field.

        Returns:
            str: the common name (e.g.: John Smith)
        """
        self.check_initialization()
        return str(self._obj_info["cn"])

    @property
    def category(self) -> str:
        """Property attribute fo object category field.

        Returns:
            str: the object category (e.g.: CN=Person,CN=Schema,
            CN=Configuration,DC=example,DC=com)
        """
        self.check_initialization()
        return str(self._obj_info["objectCategory"])

    @property
    def type(self) -> str:
        """Property attribute fo object objectClass field.

        Returns:
            str: the object objectClass (e.g.: top, person,
             organizationalPerson, user)
        """
        self.check_initialization()
        return str(self._obj_info["objectClass"])

    @property
    def guid(self) -> str:
        """Property attribute fo object guid field.

        Returns:
            str: the object guid
        """
        self.check_initialization()
        return str(self._obj_info["objectGUID"])

    @property
    def sid(self) -> str:
        """Property attribute fo object sid field.

        Returns:
            str: the object sid
        """
        self.check_initialization()
        return str(self._obj_info["objectSid"])

    def display_info(self):
        """This method display the info gathered on the object"""
        self.check_initialization()
        self.log.info(f"distinguished_name: {self.distinguished_name}")
        self.log.info(f"account_name: {self.account_name}")
        self.log.info(f"common_name: {self.common_name}")
        self.log.info(f"category: {self.category}")
        self.log.info(f"sid: {self.sid}")

    def convert_to_dict(self) -> dict:
        """This method converts the object attributes info to a dictionary.

        Returns:
            dict: a dictionary which its keys conforms to object attributes,
            or None if object failed to initialized.
        """
        info = {}
        self.check_initialization()
        info["distinguished_name"] = self.distinguished_name
        info["account_name"] = self.account_name
        info["common_name"] = self.common_name
        info["category"] = self.category
        info["type"] = self.type
        info["guid"] = self.guid
        info["sid"] = self.sid
        return info


class LDAPUser(LDAPObject):
    """This class represent all rellevant user info queried from the LDAP
    server, it inherits from LDAPObject.
    """

    def __init__(self, domain_name: str, user_name: str, ldap_handler: LDAPHandler = None) -> None:
        """initilizes the object with info returned from the query.

        Args:
        username - the account_name of the user to look for in LDAP server.
        ldap_handler - a handler to query the LDAP server.
        """
        super().__init__(domain_name, user_name, "user", ldap_handler)
        self._search_filter = f"(&(sAMAccountName={self._account_name})(objectClass=person))"
        self._search_attributes.extend(
            ["displayName", "givenName", "sn", "userPrincipalName", "memberOf"]
        )
        self.init_object()

    @property
    def display_name(self) -> str:
        """Property attribute for user display name field.

        Returns:
            str: the user display name
        """
        self.check_initialization()
        return str(self._obj_info["displayName"])

    @property
    def principal_name(self) -> str:
        """Property attribute fo object principal name field.

        Returns:
            str: the user principal name (e.g.: johns@example.com)
        """
        self.check_initialization()
        return str(self._obj_info["userPrincipalName"])

    @property
    def member_of(self) -> list:
        """Property attribute for user member of field.

        Returns:
            str: the name of the groups the user is member of.
        """
        self.check_initialization()
        return self._obj_info["memberOf"]

    def display_info(self) -> None:
        """This method display the info gathered on the user object."""
        super().display_info()
        self.check_initialization()
        self.log.info(f"account_name: {self.account_name}")
        self.log.info(f"display_name: {self.display_name}")
        self.log.info(f"principal_name: {self.principal_name}")
        self.log.info(f"member_of: {self.member_of}")

    def convert_to_dict(self) -> dict:
        """this method converts the user attributes info to a dictionary.

        Returns:
            dictionary: the dictionary keys conforms to user attributes.
        """
        self.check_initialization()
        info = super().convert_to_dict()
        info["account_name"] = self.account_name
        info["display_name"] = self.display_name
        info["principal_name"] = self.principal_name
        info["member_of"] = self.member_of
        return info

    def authenticate(self, password: str) -> bool:
        """This method enables to authenticate the user with the LDAP
        server.
        """
        if not isinstance(password, str):
            raise ValueError("provided password is not in correct format")
        return self._handler.authenticate_user(self.account_name, password)


class LDAPGroup(LDAPObject):
    """This class represent all rellevant group info queried from the LDAP
    server, it inherits from LDAPObject.
    """

    def __init__(self, domain_name: str, group_name: str, ldap_handler: LDAPHandler = None) -> None:
        """initilizes the object with info returned from the query.

        Args:
        group_name - the account_name of the group to look for in LDAP server
        ldap_handler - a handler to query the LDAP server
        """
        super().__init__(domain_name, group_name, "group", ldap_handler)
        self._search_filter = f"(&(sAMAccountName={self._account_name})(objectclass=group))"
        self._search_attributes.extend(["member"])
        self.init_object()

    @property
    def members(self) -> list:
        """Property attribute for group members field.

        Returns:
            str: the list of members in a group
        """
        self.check_initialization()
        return self._obj_info["member"]

    def display_info(self):
        """This method display the info gathered on the group object"""
        super().display_info()
        self.check_initialization()
        self.log.info(f"members: {self.members}")

    def convert_to_dict(self):
        """this method converts the group attributes info to a dictionary.

        Returns:
            dictionary: the dictionary keys conforms to group attributes
        """
        info = super().convert_to_dict()
        info["members"] = self.members
        return info

    @classmethod
    def get_member_object(
        cls, domain_name: str, distinguished_name: str, ldap_handler: LDAPHandler
    ) -> LDAPObject:
        """This function queries LDAP server with maps a distinguished name to
        an account name and uses it to return the correct object.

        Args:
        domain_name (str): the name of the domain cotaining the object.
        distinguished_name - the account_name of the group to look for in \
            LDAP server.
        ldap_handler - a handler to query the LDAP server

        Raises:
            InitializationError - if search results haven't found this member.

        Returns:
            (LDAPObject): an LDAPUser or LDAPGroup with all relevant data.
        """
        if ldap_handler is None:
            ldap_handler = LDAPHandler(domain_name)
        obj_info = ldap_handler.search_distinguished_name(distinguished_name)
        if obj_info is None:
            raise InitializationError("invalid member details")
        account_name = str(obj_info["sAMAccountName"])
        if "person" in obj_info["objectClass"]:
            obj = LDAPUser(domain_name, account_name, ldap_handler)
        elif "group" in obj_info["objectClass"]:
            obj = LDAPGroup(domain_name, account_name, ldap_handler)
        return obj
