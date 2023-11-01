#!/usr/bin/env python3
"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer  (erez@mov.ai) - 2022

Instructions for using this tool:
This tool has been created for manual operations relating to user management.
The too currently supports the following operations:
convert:    Converts an old User to the new InternalUser.
remove:     Removes an old user from the system.
create:     Creates a new user in the 'InternalUser' format.

notes:
* The convert command:
    - This command would not convert the old user permissions to the newly created user.
    - After a user has been converted it should be associated with a role.
* The remove command:
    - This command will only remove users from the old 'User' format.
    - Inorder to remove a user of type 'InternalUser', this action is only available from the application GUI.
* The create command:
    - The command can be followed with the '-s' flag to denote the user as a superuser.
    - A superuser is a user which have all the permissions avaiable on the system regardless
      of his associated roles.
"""
import sys
import argparse
from abc import ABC, abstractclassmethod, abstractmethod
from getpass import getpass

from movai_core_shared.envvars import DEFAULT_ROLE_NAME
from movai_core_shared.consts import INTERNAL_DOMAIN
from movai_core_shared.exceptions import UserDoesNotExist
from movai_core_shared.logger import Log

from dal.models.user import User
from dal.new_models import Role
from dal.models.internaluser import InternalUser

CONVERT_COMMAND = "convert"
REMOVE_COMMAND = "remove"
CREATE_COMMAND = "create"


class BaseCommand(ABC):
    """Base Class for the various tools commands."""

    def __init__(self, **kwargs) -> None:
        self.log = Log.get_logger(__name__)
        self.kwargs = kwargs
        self.username = self.kwargs["username"]

    def safe_execute(self) -> None:
        try:
            self.execute()
            sys.exit(0)
        except Exception as e:
            self.log.error(e.message)
            sys.exit(1)

    @abstractmethod
    def execute(self) -> None:
        """Executes the relevant command."""

    @abstractclassmethod
    def define_arguments(cls, subparsers) -> None:
        """An abstract function for implementing command arguments.

        Args:
            subparsers (_type_): _description_
        """

    def validate_user(self) -> None:
        """Verifies that the user actually exist.

        Raises:
            UserDoesNotExist: in case the user to be converted not exist.
        """
        if not User.is_exist(self.username):
            error_msg = f"The user {self.username} does not exist."
            raise UserDoesNotExist(error_msg)
        self.user = User(self.username)


class ConvertOldUser(BaseCommand):
    """Convert the a user from the old User format to new InternalUser format."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def execute(self) -> None:
        self.validate_user()
        if self.user.Role is None:
            if not Role.is_exist(DEFAULT_ROLE_NAME):
                Role.create_default_roles()
        InternalUser.convert_user(self.user)

    def __str__(self) -> str:
        return CONVERT_COMMAND

    @classmethod
    def define_arguments(cls, subparsers) -> None:
        convert_parser = subparsers.add_parser(
            CONVERT_COMMAND, help="Converts an old User to the new InternalUser"
        )
        convert_parser.add_argument(
            "-u",
            dest="username",
            metavar="<USERNAME>",
            type=str,
            help="username to convert",
            required=True,
        )


class RemoveOldUser(BaseCommand):
    """Removes the old User from the db."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def execute(self) -> bool:
        self.validate_user()
        self.user.delete()

    def __str__(self) -> str:
        return REMOVE_COMMAND

    @classmethod
    def define_arguments(cls, subparsers) -> None:
        remove_parser = subparsers.add_parser(REMOVE_COMMAND, help="Removes an existing old User")
        remove_parser.add_argument(
            "-u",
            dest="username",
            metavar="<USERNAME>",
            help="username to remove",
            type=str,
            required=True,
        )


class CreateNewUser(BaseCommand):
    """Creates a new InternalUser in the system."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def __str__(self) -> str:
        return CREATE_COMMAND

    def execute(self):
        role = self.kwargs.get("role", DEFAULT_ROLE_NAME)
        password = self.kwargs.get("password")
        if password is None:
            password = getpass("Please enter password: ")
        if not InternalUser.is_exist(INTERNAL_DOMAIN, self.username):
            if not Role.is_exist(role):
                self.log.warning(
                    f"The requested role does not exist, changing to default role: {DEFAULT_ROLE_NAME}"
                )
                role = DEFAULT_ROLE_NAME
                Role.create_default_roles()
        InternalUser.create(
            account_name=self.username,
            password=password,
            roles=[role],
            common_name=self.username.capitalize(),
            super_user=self.kwargs["superuser"],
        )
        role_obj = Role(role)
        role_obj.update_time()

    @classmethod
    def define_arguments(cls, subparsers) -> None:
        create_parser = subparsers.add_parser(CREATE_COMMAND, help="Creates a new InternalUser")
        create_parser.add_argument(
            "-u",
            dest="username",
            metavar="<USERNAME>",
            help="username to create",
            type=str,
            required=True,
        )
        create_parser.add_argument(
            "-p",
            metavar="<PASSWORD>",
            dest="password",
            help="User's password",
            type=str,
            required=False,
        )
        create_parser.add_argument(
            "-r",
            metavar="<ROLE>",
            dest="role",
            help="User's role",
            type=str,
            required=False,
        )
        create_parser.add_argument(
            "-s",
            dest="superuser",
            action="store_true",
            help="turns on the superuser flag",
            default=False,
            required=False,
        )


def define_arguments() -> None:
    """defining commnad line arguments."""
    tool_description = """The user tool is a script for manual user management,
    it currently supports the following commands: convert, remove and create.
    """
    parser = argparse.ArgumentParser(description=tool_description)
    subparsers = parser.add_subparsers(dest="command")
    ConvertOldUser.define_arguments(subparsers)
    RemoveOldUser.define_arguments(subparsers)
    CreateNewUser.define_arguments(subparsers)
    args = parser.parse_args()
    return vars(args)


def main() -> None:
    """General function to run the script with the correct command.

    Raises:
        Exception: In case the command is unknown.

    Returns:
        int: The output code from the tool.
    """
    tool = None
    kwargs = define_arguments()
    command = kwargs.pop("command")
    if command == CONVERT_COMMAND:
        tool = ConvertOldUser(**kwargs)
    elif command == REMOVE_COMMAND:
        tool = RemoveOldUser(**kwargs)
    elif command == CREATE_COMMAND:
        tool = CreateNewUser(**kwargs)
    if tool is not None:
        tool.safe_execute()


if __name__ == "__main__":
    main()
