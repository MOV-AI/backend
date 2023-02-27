"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Moawiya Mograbi (moawiya@mov.ai) - 2023

   This module implements RestAPI endpoints to access the notifications
   in the Message Server
"""
import jsonpickle

from typing import List
from aiohttp import web
from backend.http import WebAppManager
from backend.endpoints.api.v2.base import BaseWebApp

# from .base import BaseWebAp
from movai_core_shared.core.message_client import MessageClient
from movai_core_shared.envvars import MESSAGE_SERVER_BIND_ADDR
from movai_core_shared.consts import NOTIFICATIONS_HANDLER_MSG_TYPE



async def get_emails(request: web.Request):
    return web.json_response("Not Supported yet", headers={"Server": "Movai-server"})


async def send_email(request: web.Request):
    client = MessageClient(MESSAGE_SERVER_BIND_ADDR)
    body = await request.json()
    recipients = body["recipients"]
    subject = body["subject"]
    body = body["body"]
    subject = None
    attachment_path = None
    attachment_data = None
    if "attachment_path" in body:
        attachment_path = body["attachment_path"]
    if "subject" in body:
        subject = body["subject"]
    if attachment_path:
        with open(attachment_path, "rb") as f:
            attachment_data = jsonpickle.encode(f.read())

    data = {
        "req_type": NOTIFICATIONS_HANDLER_MSG_TYPE,
        "req_data": {
            "recipients": recipients,
            "notification_type": "smtp",
            "body": body,
        },
    }

    if subject:
        data.update({"subject": subject})
    if attachment_data:
        data.update({"attachment_data": attachment_data})

    res = client.send_request(NOTIFICATIONS_HANDLER_MSG_TYPE, data, response_required=True)

    return web.json_response({"result": res}, headers={"Server": "Movai-server"})


async def send_sms(request: web.Request):
    return web.json_response("Not Supported yet", headers={"Server": "Movai-server"})

async def send_user_notifications(request: web.Request):
    client = MessageClient(MESSAGE_SERVER_BIND_ADDR)
    body = await request.json()

    data = {
        "req_type": NOTIFICATIONS_HANDLER_MSG_TYPE,
        "req_data": {
            "notification_type": "user",
            "msg": body["msg"],
            "robot_id": "" if "robot_id" not in body else body["robot_id"],
            "robot_name": body["robot_name"],
        },
    }

    res = client.send_request(NOTIFICATIONS_HANDLER_MSG_TYPE, data, response_required=True)

    return web.json_response({"resutl": res}, headers={"Server": "Movai-server"})


class NotificationsAPI(BaseWebApp):
    """Web application for serving as the database api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the database api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/emails", get_emails),
            web.post(r"/sms", send_sms),
            web.post(r"/user", send_user_notifications),
            web.post(r"/email", send_email),
        ]


WebAppManager.register("/api/v2/notify", NotificationsAPI)
