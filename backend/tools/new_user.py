# create a new user
import argparse
from errno import EEXIST, EINVAL, ENOEXEC
from getpass import getpass

from movai_core_shared.logger import Log
from movai_core_shared.exceptions import PasswordError, UserAlreadyExist
from movai_core_shared.envvars import DEFAULT_ROLE_NAME
from movai_core_shared.consts import INTERNAL_DOMAIN

from dal.models.acl import NewACLManager
from dal.models.internaluser import InternalUser
from dal.models.role import Role


LOGGER = Log.get_logger(__name__)


def create_new_user(username: str, password: str, superuser: bool) -> int:
    """_summary_

    Args:
        username (str): the name of the user to create.
        password (str): the password of the user.
        superuser (bool): should the user have superuser permissions.

    Returns:
        int: os error code for the operation.
            possible values:
                0 - success.
                8 - format error.
                17 - already exists.
                22 - invalid argument.
    """
    resources = NewACLManager.get_permissions()

    try:
        if not InternalUser.is_exist(INTERNAL_DOMAIN, username):
            if Role.is_exist(DEFAULT_ROLE_NAME):
                role_obj = Role(DEFAULT_ROLE_NAME)
                role_obj.update(resources=resources)
            else:
                Role.create(name=DEFAULT_ROLE_NAME, resources=resources)

        user_obj = InternalUser.create(
            account_name=username,
            password=password,
            roles=[DEFAULT_ROLE_NAME],
            common_name=username.capitalize(),
            super_user=superuser,
        )
        role_obj = Role(DEFAULT_ROLE_NAME)
        role_obj.update_time()
    except PasswordError as e:
        LOGGER.error(e)
        exit(ENOEXEC)
    except UserAlreadyExist as e:
        LOGGER.error(e.__str__())
        exit(EEXIST)
    except ValueError as e:
        LOGGER.error(e)
        exit(EINVAL)


def main():
    parser = argparse.ArgumentParser(description="Create a new Mov.ai user.")
    parser.add_argument("-u", "--username", help="Username", type=str, required=True)
    parser.add_argument("-p", "--password", help="User password", type=str, required=False)
    parser.add_argument(
        "-s",
        "--superuser",
        help="turns on the superuser flag",
        action="store_true",
        default=False,
    )

    args, _ = parser.parse_known_args()

    if args.password is None:
        args.password = getpass("Enter Password:")

    create_new_user(**vars(args))


if __name__ == "__main__":
    main()
