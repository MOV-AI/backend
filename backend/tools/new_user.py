# create a new user
import argparse
from dal.models import User
from dal.scopes import scopes


def main(args):
    username = args.username
    password = args.password

    try:
        new_user = scopes().create(
            scope="User", ref=username
        )  # User(username, new=True)
    except ValueError:  # already exists
        new_user = User(username)

    new_user.Label = username
    new_user.Password = new_user.hash_password(password)
    # default applications
    try:
        new_user.Applications.append("Develop")
    except AttributeError:
        new_user.Applications = ["Develop"]

    if args.super:
        new_user.Superuser = True

    # save to db
    new_user.write()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Create a new Mov.ai user.")
    parser.add_argument(
        "-u", "--username", help="Username", type=str, required=True, metavar=""
    )
    parser.add_argument(
        "-p", "--password", help="User password", type=str, required=True, metavar=""
    )
    parser.add_argument(
        "-s", "--superuser", help="Set user as super", dest="super", action="store_true"
    )
    parser.set_defaults(super=False)

    args, unknown = parser.parse_known_args()
    main(args)
