"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from .api import on_gen_task
from .generate_sde import gen_shared_data_entries


taskmanager_action_map = {
    # Api
    "gen_task": on_gen_task,
    # genereate_sde
    "gen_shared_data_entries": gen_shared_data_entries,
}

taskmanager_enterprise_map = {
    # Api
    "gen_task": on_gen_task,
    # genereate_sde
    "gen_shared_data_entries": gen_shared_data_entries,
}
