from .ide import ide_action_map
from .fleetdashboard import fleetdashoboard_action_map
from .taskmanager import taskmanager_action_map

frontend_map = {
    "ide": ide_action_map,
    "fleetdashoboard": fleetdashoboard_action_map,
    "taskmanager": taskmanager_action_map,
}
