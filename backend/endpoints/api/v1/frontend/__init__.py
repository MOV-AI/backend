from .fleetmanager import fleetmanager_action_map, fleetmanager_enterprise_map
from .ide import ide_action_map, ide_enterprise_map
from .taskmanager import taskmanager_action_map, taskmanager_enterprise_map

frontend_map = {
    "fleetmanager": {
        "action": fleetmanager_action_map,
        "enterprise": fleetmanager_enterprise_map
    },
    "ide": {
        "action": ide_action_map,
        "enterprise": ide_enterprise_map
    },
    "taskmanager": {
        "action": taskmanager_action_map,
        "enterprise": taskmanager_enterprise_map
    }
}
