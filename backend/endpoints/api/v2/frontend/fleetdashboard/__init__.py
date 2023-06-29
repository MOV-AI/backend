from .api import API
from .statistics import Statistics
from .tasks import Tasks


fleetdashoboard_action_map = {
    #Api
    "startRobots": API.start_robots,
    "stopRobots": API.stop_robots,
    "setRobotsStarted": API.set_robots_started,
    "restartSession": API.restart_session,
    #statistics
    "getStats": Statistics.get_stats,
    "lastSessionStats": Statistics.last_session_stats,
    'cacheSessionStats': Statistics.cache_session_stats,
    #Tasks
    "getTasks": Tasks.getTasks,
    "saveTask": Tasks.saveTask,
    "deleteTask": Tasks.deleteTask
}

supported_cb = (
"fleetDashboard.api",
"fleetDashboard.statistics",
"fleetDashboard.tasks"
)
