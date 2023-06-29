'''
    Copyright (C) Mov.ai  - All Rights Reserved
    Unauthorized copying of this file, via any medium is strictly prohibited
    Proprietary and confidential

    This is a sample statistics callback which is responsible for getting all robots
    information such as distance travelled, number of carts delivered etc.

    This callback is called for the following functions
        -> cache_session_stats    : called everytime the system was running (right side in top bar) and it stops to get the last start/end time and update the cache in redis
        -> last_session_stats     : called once to get the cached statistics values
        -> get_stats             : called every 10s to refresh the data in the charts
    It's important to remark that if the system is not running in FleetDashboard app, the get_stats function is not going to be called

    DEBUG INFO:
        1) If it's necessary to send any error message back to the UI, it's necessary to add an "error" property in the response object returned
        2) To debug 'cache_session_stats', you need to start and stop the system in FleetDashboard
            2.1) It will call this function to update the cached statistics data
        3) To debug 'last_session_stats', you just need to refresh the page
            3.1) It will call this function to fetch the cached values
        4) To debug 'get_stats', you need to have the system running in FleetDashboard
            4.1) It will automatically call to fetch new results to refresh data in charts (every 10s)
'''
from datetime import date, datetime
import time
import pytz

from movai_core_shared.common.utils import is_enterprise
from movai_core_shared.logger import Log

from dal.models.var import Var
from dal.scopes.robot import Robot
from dal.scopes.configuration import Configuration
from dal.scopes.fleetrobot import FleetRobot

LOGGER = Log.get_logger(__name__)

try:
    from movai_core_enterprise.message_client_handlers.metrics import Metrics
except ImportError:
    LOGGER.warning("movai_core_enterprise is not installed")    




# parameters
CONFIG_NAME = "project"
MANAGER_DEFAULT = "manager"
TIMEZONE_DEFAULT = "Europe/Berlin"

try:
    project_config = Configuration(CONFIG_NAME).get_value()
    timezone = project_config['check_work_conditions']['timezone']
    manager = project_config['manager_name']
except Exception as e:
    timezone = TIMEZONE_DEFAULT
    manager = MANAGER_DEFAULT
    LOGGER.error(f"Error in configuration {CONFIG_NAME}", e)

# instanciate database vars
gvar = Var('Global')

# get all fleet robots except manager
robots = set([FleetRobot(robot).RobotName for robot in Robot.get_all()]) - {manager}

# get timezone
tz = pytz.timezone(timezone)

# consts
BUBBLE_1 = "bubble1"
BUBBLE_2 = "bubble2"
BAR_1 = "bar1"
BAR_2 = "bar2"
LINE_CHART = "lineChart"

GLOBAL_BLACKLIST = []

#  format values from global var (current_date) and get today's date
use_old_format = isinstance(gvar.current_date, date)
today_date = datetime.now(tz).date()
if use_old_format or gvar.current_date is None:
    current_date = gvar.current_date
else:
    current_date = datetime.date(datetime.strptime(gvar.current_date, '%Y-%m-%d'))
# reset fleet variables on new day
if current_date is None or current_date < today_date:
    gvar.current_date = today_date.strftime("%Y-%m-%d")
    LOGGER.debug('Resetting day vars')
    for robot in robots:
        fvar = Var('Fleet', robot)
        fvar.time_today = 0
        fvar.kms_today = 0
        fvar.carts_today = 0

def clean_statistics(stats):
    """
        Remove each statistics related to robot that are not well defined in Redis
        Or was already removed

        Returns:
            dict:Individual statiscts from valid robots only
    """
    for index, stat in enumerate(stats):
        if not stat['robot'] or stat['robot'] not in robots or stat['robot'] in GLOBAL_BLACKLIST:
            stats.pop(index)
    return stats

def validate_statistics(statistics):
    """
        Remove statistics related to robot that are not well defined in Redis
        Or was already removed

        Returns:
            dict:Statiscts from valid robots only
    """
    valid_statistics = {}
    try:
        valid_statistics[BUBBLE_1] = clean_statistics(statistics[BUBBLE_1])
        valid_statistics[BUBBLE_2] = clean_statistics(statistics[BUBBLE_2])
        valid_statistics[BAR_1] = clean_statistics(statistics[BAR_1])
        valid_statistics[BAR_2] = clean_statistics(statistics[BAR_2])
        statistics.update(valid_statistics)
    except KeyError:
        LOGGER.debug("lastSessionStats Var not found", ui=True)
    return statistics

def time_km_per_robot_today():
    """
        Time in operation and kms per robot today
        Use case: 
            Populate "Time in operation and Kms Today" chart (bubble1)
        
        Returns:
            array:List of robots with its kilometers/time data today
    """
    time_kms = []
    for robot in robots:
        try:
            fvar = Var('Fleet', robot)
            time = fvar.time_today
            kms = fvar.kms_today
        except Exception:
            time = 0
            kms = 0
        time_kms.append({'x': kms, 'y': time, 'robot': robot})
    return time_kms

def time_km_per_robot():
    """
        Time in operation and kms per robot lifelong
        Use case: 
            Populate "Time in operation and Kms" chart (bubble2)
        
        Returns:
            array:List of robots with its kilometers/time data accumulated
    """
    time_kms = []
    for robot in robots:
        try:
            fvar = Var('Fleet', robot)
            time = fvar.time_lifetime
            kms = fvar.kms_lifetime
        except Exception:
            time = 0
            kms = 0
        time_kms.append({'x': kms, 'y': time, 'robot': robot})
    return time_kms

def carts_per_robot():
    """
        Carts pulled per robot accumulated
        Use case: 
            Populate "Total carts per Robot" chart (bar2)

        Returns:
            array:List of robots with its quantity of pulled carts accumulated
    """
    carts = []
    for robot in robots:
        try:
            carts_lifetime = Var('Fleet', robot).carts_lifetime
            carts.append({'data': carts_lifetime, 'robot': robot})
        except Exception:
            carts.append({'data': 0, 'robot': robot})
    return carts

def carts_per_robot_today():
    """
        Carts pulled per robot today
        Use case: 
            Populate "Total carts per Robot Today" chart (bar1)

        Returns:
            array:List of robots with its quantity of pulled carts today
    """
    carts = []

    for robot in robots:
        try:
            carts_today = Var('Fleet', robot).carts_today
            carts.append({'data': carts_today, 'robot': robot})
        except Exception:
            carts.append({'data': 0, 'robot': robot})
        
    return carts

def line_chart():
    """ 
        Number of carts per robot during session (line chart)
        Use cases: 
            Populate main chart with carts_per_robot and total_timeseries variables
            Populate 'Delivered Carts' with deliveriesNumber variable 
        
        Returns:
            Object containing overall data to build line chart and fill deliveriesNumber
    """

    response = {"success": False}

    metrics_name = 'numberOfDeliveries'
    carts_per_robot = {}   # {<robot id>: <robot data>, }
    total_timeseries = [] # [ {'t': <timestamp>, 'y': <accumulated delivered carts>}]
    totals_per_robot = {}  # {<robot id>: <total carts delivered>}
    totals = 0

    # series format: {<robot name>: <robot data>}
    # robot data format: [ {'t': <timestamp>, 'y': <accumulated delivered carts>}]
    if not is_enterprise:
        LOGGER.error("cannot initalize metrics because movai_core_enterprise is not installed")
        return
    
    metrics = Metrics()
    try:
        # session start time; gives last hour by default
        start_time = Var('global').get('startTime') or (time.time() - 3600)
        entries = metrics.get_metrics(metrics_name)
        entries.reverse()

        # add first point
        total_timeseries.append({'t': start_time, 'y': 0})

        for entry in entries:
            _robot = entry.get("robot")
            _timestamp = entry.get("time")
            _value = int((entry.get("v", 1) or 1)) # or 1 - in case value is None

            if _timestamp >= start_time:

                # calculate carts per robots
                totals_per_robot.update({_robot: totals_per_robot.get(_robot, 0) + _value})
                _values = carts_per_robot.setdefault(_robot, [{'t': start_time, 'y': 0}])
                _values.append({'t': _timestamp, 'y': totals_per_robot.get(_robot)})

                # update totals
                totals = totals + _value
                total_timeseries.append({'t': _timestamp, 'y': totals})

        # add final point
        current_time = time.time()

        for _robot, _values in carts_per_robot.items():
            _values.append({'t': current_time, 'y': totals_per_robot.get(_robot, 0)})

        total_timeseries.append({'t': current_time, 'y': totals})

        # response
        response = {"carts_per_robot": carts_per_robot, "total_timeseries": total_timeseries, "deliveriesNumber": totals}

    except Exception as e:
        LOGGER.error(e)
        raise e

    return response


class Statistics:
    @staticmethod
    def get_stats(blacklist):
        """
            Get statistics to populate charts
            Use case:
                Gather information to populate/refresh values in charts in statistics page

            Parameters:
                blacklist (array):The list of robots names to be used in line_chart function

            Returns:
                Collects results from internal functions to return data to populate charts
        """
        GLOBAL_BLACKLIST = blacklist
        bar1 = carts_per_robot_today()
        bar2 = carts_per_robot()
        bubble1 = time_km_per_robot_today()
        bubble2 = time_km_per_robot()

        # Compose response output 
        output = {}
        output[BUBBLE_1] = bubble1
        output[BUBBLE_2] = bubble2
        output[BAR_1] = bar1
        output[BAR_2] = bar2
        output[LINE_CHART] = line_chart()

        response = {"success": True}
        response.update({"result": validate_statistics(output)})

        return response

    @staticmethod
    def last_session_stats(blacklist):
        """
            Get last session data redis var last_session_stats 
            Use cases:
                Returns last session statistics values in cache

            Raises:
                Exception: If last_session_stats doesn't exists in global var in redis

            Returns:
                Last session statistics values in cache
        """ 

        GLOBAL_BLACKLIST = blacklist

        response = {'success': False}

        try:
            response['result'] = Var('global').get('lastSessionStats') or {}
            response['result'] = validate_statistics(response['result'])
            response['success'] = True

        except Exception as e:
            LOGGER.error(e)
            raise e

        return response

    @classmethod
    def cache_session_stats(cls, startTimeVar, endTimeVar, blacklist):
        """ 
            Get the session cached statistics values
            Use case: 
                Whenever the system stops, update cache in redis and returns last start/end time to calculate 'Last Session Duration' value

            Parameters:
                start_time_var (str):The name of the start_time_var variable in redis
                end_time_var (str):The name of the end_time_var variable in redis

            Raises:
                Exception: If variable names doesn't exists in redis

            Returns:
                Object containing start/end time of last session and last statistics data in cache
        """
        response = {'success': False}

        try:
            cache = cls.get_stats(blacklist)
            response = cache.get('result', {})
            start_time = Var('global').get(startTimeVar)
            end_time = Var('global').get(endTimeVar)

            response.update({endTimeVar: end_time, startTimeVar: start_time, 'success': True })

            Var('global').lastSessionStats = response

        except Exception as e:
            LOGGER.error(e)
            raise e

        return response