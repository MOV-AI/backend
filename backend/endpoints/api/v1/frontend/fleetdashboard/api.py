import time

from movai_core_shared.logger import Log

from dal.scopes.fleetrobot import FleetRobot
from dal.scopes.robot import Robot
from dal.models.var import Var


ROBOT_STARTED_PARAM = "started"
START_TIME_VAR = "startTime"
END_TIME_VAR = "endTime"

LOGGER = Log.get_logger(__name__)


class API:
    @classmethod
    def set_robots_started(cls, robot_ids, value=False):
        """
        :param list<str> | str robotids: robot ids as list of ids or as single id
        :param boolean value
        """
        if robot_ids is None or "" == robot_ids or len(robot_ids) == 0:
            robot_ids = Robot().get_all()

        if isinstance(robot_ids, str):
            robot_ids = list(robot_ids)

        for id in robot_ids:
            robot = FleetRobot(id)
            try:
                robot.Parameter[ROBOT_STARTED_PARAM].Value = value
            except Exception as e:
                LOGGER.warn(
                    f"Caught exception in setting {ROBOT_STARTED_PARAM} Parameter with value {value} of robot id {id}",
                    e,
                )
                robot.add("Parameter", ROBOT_STARTED_PARAM).Value = value

    @classmethod
    def start_robots(cls, robot_ids):
        """
        :param list<str> | str robotids: robot ids as list of ids or as single id
        """
        cls.set_robots_started(robot_ids, True)
        if robot_ids is None or "" == robot_ids or 0 == len(robot_ids):
            Var("global").set(START_TIME_VAR, time.time())

    @classmethod
    def stop_robots(cls, robot_ids):
        """
        :param list<str> | str robotids: robot ids as list of ids or as single id
        """
        cls.set_robots_started(robot_ids, False)
        if robot_ids is None or "" == robot_ids or 0 == len(robot_ids):
            Var("global").set(END_TIME_VAR, time.time())

    @classmethod
    def restart_session(cls):
        current_time = time.time()

        Var("global").set(START_TIME_VAR, current_time)
        LOGGER.info("Session restarted")

        return {"startTimeVar": current_time}
