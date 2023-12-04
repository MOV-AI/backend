from .ide import ide_action_map, ide_enterprise_map
from .fleetdashboard import fleetdashoboard_action_map, fleetdashoboard_enterprise_map
from .taskmanager import taskmanager_action_map, taskmanager_enterprise_map

frontend_map = {
    "ide": {
        "action": ide_action_map,
        "enterprise": ide_enterprise_map
    },
    "fleetdashboard": {
        "action": fleetdashoboard_action_map,
        "enterprise": fleetdashoboard_enterprise_map
    },
    "taskmanager": {
        "action": taskmanager_action_map,
        "enterprise": taskmanager_enterprise_map
    }
}
