from movai_core_shared.common.utils import is_enterprise
from movai_core_shared.logger import Log


LOGGER = Log.get_logger(__name__)

try:
    from movai_core_enterprise.gdnode.taskgenerator import TaskGenerator
except ImportError:
    LOGGER.warning("movai_core_enterprise is not installed.")


def on_gen_task(**kwargs):
    """
    triggers tasks re-generation
    current tasks will be replaced
    """
    if is_enterprise:
        LOGGER.info("generating tasks")
        TaskGenerator().generate_tasks()
        LOGGER.info("finished generating new tasks")
    else:
        LOGGER.error("could not generate tasks because movai_core_enterprise is not installed.")
