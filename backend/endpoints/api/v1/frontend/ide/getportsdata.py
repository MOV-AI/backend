"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
"""
from dal.new_models.message import Message


def get_ports_data():
    """Fetch the ports data from the message.

    Returns:
        PortsData: The port data
    """
    return Message.fetch_portdata_api()
