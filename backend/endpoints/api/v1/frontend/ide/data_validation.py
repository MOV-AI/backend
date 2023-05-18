"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

"""

import re

from dal.models.scopestree import ScopesTree

class DataValidation:
    self._actions = {}
def validate_configuration(config_string):
    """
    Validate a configuration with configuration string.

    Keyword arguments:
    config_string -- string of form '$(config <name>(.<key>*))' 

    """
    try:
        regex = r"^\$\(config \w+(\.\w+)*\)$"
        matches = re.finditer(regex, config_string, re.MULTILINE)
        matches_size = len([x for x in matches])
        if matches_size == 0:
            return False
        config_key_path = config_string.replace("$(config ","").replace(")", "").split(".")
        config_name = config_key_path[0]
        config_key_path.pop(0)
        config = ScopesTree()().Configuration[config_name]
        val = config.get_value()
        for key in config_key_path:
            val = val[key]
        return True
    except Exception as e:
        print("Caught exception", e)
        return False

def validate_configuration_raw(value):
    """
    Validate configuration name/keys

    Keyword arguments:
    value -- holds a configuration name/path: '<name>(.<key>*)'
    """
    try:
        configKeyPath = value.split('.')
        configName = configKeyPath[0]
        configKeyPath.pop(0)
        scopes = ScopesTree()
        config = scopes().Configuration[configName]
        val = config.get_value()
        for key in configKeyPath:
            val = val[key]
        return True
    except Exception as err:
        logger.warning(f"Caught exception {err}")
        return False

key2action_map = {
    "validateConfiguration": validate_configuration,
    "validateConfigurationRaw": validate_configuration_raw
}

try:
    response = {"success": True}
    response["result"] = key2action_map[msg["func"]](msg["args"])

except Exception as e:
    response = {"success": False, "error": str(e)}