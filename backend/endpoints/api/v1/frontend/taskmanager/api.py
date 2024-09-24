"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from movai_core_shared.logger import Log


LOGGER = Log.get_logger(__name__)

try:
    from movai_core_enterprise.gdnode.taskgenerator import TaskGenerator
except ImportError:
    LOGGER.warning(
        "Failed to import TaskGenerator, because movai_core_enterprise is not installed."
    )


def on_gen_task():
    """
    triggers tasks re-generation
    current tasks will be replaced
    """
    LOGGER.info("generating tasks")
    TaskGenerator().generate_tasks()
    LOGGER.info("finished generating new tasks")
