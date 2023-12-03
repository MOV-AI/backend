"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from .api import API
from .statistics import Statistics
from .tasks import Tasks


fleetdashoboard_action_map = {
    # Api
    "startRobots": API.start_robots,
    "stopRobots": API.stop_robots,
    "setRobotsStarted": API.set_robots_started,
    "restartSession": API.restart_session,
    # statistics
    "getStats": Statistics.get_stats,
    "lastSessionStats": Statistics.last_session_stats,
    "cacheSessionStats": Statistics.cache_session_stats,
    # Tasks
    "getTasks": Tasks.get_tasks,
    "saveTask": Tasks.save_task,
    "deleteTask": Tasks.delete_task,
}
