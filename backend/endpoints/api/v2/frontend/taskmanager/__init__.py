from .api import onGenTask
from .generate_sde import gen_shared_data_entries


taskmanager_action_map = {
    #Api
    "gen_task": onGenTask,
    #genereate_sde
    "gen_shared_data_entries": gen_shared_data_entries
}

taskmanager_cb = (
    "app-taskmanager.api",
    "TaskManager.generate_sde",
)
