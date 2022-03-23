import unittest
import mock
from my_component.dummy_operation.operation_executer import OperationExecuter
import argparse


argeparse_extra_arg = argparse.Namespace(
    command="command_operation", workspace="DUMMY_PATH", dummy_arg="test"
)


# TODO adapt the test of your own executor
class TestOperationExecutor(unittest.TestCase):
    @mock.patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(command="command_operation"),
    )
    def test_operation_execute(self, mock):
        OperationExecuter().execute(argeparse_extra_arg)
        print("TODO")
