"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Pedro Cristovao (Pedro Cristóvão <pedro.cristovao@mov.ai>) - 2023

   Module that implements robot recovery states
"""
from threading import Timer
from movai_core_shared.recovery import (
    RecoveryStates,
    RECOVERY_STATE_KEY,
    RECOVERY_TIMEOUT_IN_SECS,
    RECOVERY_RESPONSE_KEY,
)

from dal.models.var import Var


def trigger_recovery_aux(robot_id):
    """Set Var to trigger Recovery Robot.

    Args:
        robot_id (str): The id of the robot to trigger recovery.

    Raises:
        Exception: In case Var could not be found.
    """
    try:
        var_scope = Var(scope="fleet", _robot_name=robot_id)
        var_scope.set(RECOVERY_STATE_KEY, RecoveryStates.PUSHED.name)
        # If the state doesn't change after 15 secs, set a VAR to send a message to the interface
        timeout = Timer(RECOVERY_TIMEOUT_IN_SECS, lambda: recovery_timeout(robot_id))
        timeout.start()
    except Exception as exc:
        raise Exception("Caught exception in trigger recovery aux", exc)


def recovery_timeout(robot_id):
    """Handle recovery fail on timeout"""
    try:
        var_scope = Var(scope="fleet", _robot_name=robot_id)
        recovery_state = var_scope.get(RECOVERY_STATE_KEY)

        if recovery_state == RecoveryStates.PUSHED.name:
            response = {
                "success": False,
                "message": "Failed to recover robot"
            }
            var_scope.set(RECOVERY_RESPONSE_KEY, response)
            var_scope.set(RECOVERY_STATE_KEY, RecoveryStates.NOT_AVAILABLE.name)
    except Exception as exc:
        raise Exception("Caught exception in recovery timeout", exc)
