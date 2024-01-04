"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
import re

from movai_core_shared.logger import Log

from dal.new_models.configuration import Configuration


LOGGER = Log.get_logger(__name__)


class DataValidation:
    @staticmethod
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
            config_key_path = config_string.replace("$(config ", "").replace(")", "").split(".")
            config_name = config_key_path[0]
            config_key_path.pop(0)
            config = Configuration(config_name)
            val = config.get_value()
            for key in config_key_path:
                val = val[key]
            return True
        except Exception as err:
            LOGGER.error(f"Caught exception {err}")
            return False

    @staticmethod
    def validate_configuration_raw(value):
        """
        Validate configuration name/keys

        Keyword arguments:
        value -- holds a configuration name/path: '<name>(.<key>*)'
        """
        try:
            config_key_path = value.split(".")
            config_name = config_key_path[0]
            config_key_path.pop(0)
            config = Configuration(config_name)
            val = config.get_value()
            for key in config_key_path:
                val = val[key]
            return True
        except Exception as err:
            LOGGER.warning(f"Caught exception: {err}")
            return False
