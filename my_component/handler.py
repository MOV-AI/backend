"""Main package module. Contains the handler, executors and other modules inside.# noqa: E501"""
import argparse
import sys

import my_component.utils.logger as logging
from my_component.dummy_operation.operation_executer import OperationExecuter

executors = {
    "command_operation": OperationExecuter,
}


def handle():
    """Entrypoint method of the package. It handles commands to the executers"""
    parser = argparse.ArgumentParser(description="DUMMY COMPONENT DESCRIPTION")

    parser.add_argument("command", help="Command to be executed.")
    parser.add_argument("--dummy_global_arg", help="global arg description")

    # executor arguments
    for executer in executors.values():
        executer.add_expected_arguments(parser)

    args = parser.parse_args()

    try:
        executor = executors[args.command]()
    except KeyError:
        logging.error(
            "Invalid command: "
            + args.command
            + ". Supported commands are: ("
            + " ".join(map(str, executors))
            + ")"
        )
        sys.exit()

    executor.execute(args)


if __name__ == "__main__":
    handle()
