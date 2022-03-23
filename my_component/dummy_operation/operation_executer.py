"""Module where all the behaviour of a command should be destributed."""
import my_component.utils.logger as logging

# TEMPLATE-CHANGE-ME: Adapt the executer to your context


class OperationExecuter:
    """Executer Class should be a representation of a package behaviour"""

    def __init__(self):
        """If your executor requires some initialization, use the class constructor for it"""
        logging.info("Init")

    def execute(self, args):
        """Method where the main behaviour of the executer should be"""
        logging.info("execute behaviour")
        logging.info(args)

    @staticmethod
    def add_expected_arguments(parser):
        """Method exposed for the handle to append our executer arguments."""
        parser.add_argument(
            "--executor_specific_arg",
            help="specific argument needed for this executor",
        )
