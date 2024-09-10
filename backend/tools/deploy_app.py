"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020

    Script to create/update movai applications
    Reads data from package.json file
"""
import argparse
import json
import os
from dal.movaidb import MovaiDB
from dal.scopes.application import Application

JSON_FILE = "package.json"


class AppException(Exception):
    pass


def get_json(root, key=None):
    if key is None:
        return root

    result = root
    _debug_key_stack = []
    for key_partial in key.strip(".").split("."):
        _debug_key_stack.append(key_partial)
        try:
            result = result[key_partial]
        except KeyError:
            raise AppException(
                f"Could not find application data (key '{'.'.join(_debug_key_stack)}' not found)"
            )
    return result


def main():
    """Create application based on package.json data"""

    parser = argparse.ArgumentParser(
        description="Expects package.json file with movai key. Deploys application."
    )

    parser.add_argument(
        "-p", "--path", help="Path to json file", type=str, required=False, default=""
    )
    parser.add_argument(
        "-f",
        "--file",
        help="json file name",
        type=str,
        required=False,
        default=JSON_FILE,
    )
    parser.add_argument(
        "-k", "--key", help="json movai key", type=str, required=False, default=None
    )

    try:
        deploy(parser.parse_args())
        exit(0)
    except AppException as error:
        print(str(error))
        exit(1)


def deploy(args):
    _file = os.path.join(args.path, args.file)
    if not os.path.exists(_file):
        raise AppException(f"Could not find file {args.file} in {args.path}")


    # Connect to DBs
    MovaiDB(db="global")
    MovaiDB(db="local")

    print("Reading file:", _file)

    with open(_file) as fjson:

        _json = json.load(fjson)

        app_json = get_json(_json, args.key)

        if not app_json.get("generateMetadata", False):
            # don't generate metadata
            return

        app = None

        try:
            app = Application(app_json["name"])
            print(f"Updating application {app.name}")

        except Exception:
            app = Application(app_json["name"], new=True)
            print(f"Creating application {app.name}")

        print(f"-" * 100)

        keys_to_skipe = ["name", "generateMetadata"]

        for key, value in app_json.items():

            if key in keys_to_skipe:
                continue

            if isinstance(value, dict):
                app_dict = getattr(app, key)
                app_dict.update(value)
                print(f"Setting key: {key} \nWith value:\n {value}")
                continue

            try:
                setattr(app, key, value)
                print(f"Setting key: {key} \nWith value:\n {value}")

            except AttributeError:
                print(f"Attribute {key} does not exist")


if __name__ == "__main__":

    main()
