"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Moawiya Mograbi (moawiya@mov.ai) - 2023

   This module implements RestAPI endpoints to access the notifications
   in the Message Server
"""
from typing import List
from aiohttp import web, web_request
from backend.http import WebAppManager
from .base import BaseWebAp
from movai_core_shared.core.message_client import MessageClient
from movai_core_shared.envvars import MESSAGE_SERVER_BIND_ADDR
from movai_core_shared.consts import NOTIFICATIONS_HANDLER_MSG_TYPE
import jsonpickle


def get_emails(request: web.Request):
    return web.json_response([], headers={"Server": "Movai-server"})


def send_email(request: web.Request):
    client = MessageClient(MESSAGE_SERVER_BIND_ADDR)
    recipients = parse.unquote(request.match_info["recipients"])
    subject = parse.unquote(request.match_info["subject"])
    body = parse.unquote(request.match_info["body"])
    subject = None
    attachment_path = None
    attachment_data = None
    if "attachment_path" in request:
        attachment_path = parse.unquote(request.match_info["attachment_path"])
    if "subject" in request:
        subject = parse.unquote(request.match_info["subject"])
    if attachment_path:
        with open(attachment_path, "rb") as f:
            attachment_data = jsonpickle.encode(f.read())

    data = {
                "req_type": NOTIFICATIONS_HANDLER_MSG_TYPE
                "req_data": {
                    "recipients": recipients,
                    "notification_type": "smtp",
                    "body": body,
                }
            }

    if subject:
        data.update({"subject": subject})
    if attachment_data:
        data.update({"attachment_data": attachment_data})

    res = client.send_request(NOTIFICATIONS_HANDLER_MSG_TYPE, data)

    return web.json_response({"result": res}, headers={"Server": "Movai-server"})


def send_sms(request: web.Request):
    client = MessageClient(MESSAGE_SERVER_BIND_ADDR)
    recipients = parse.unquote(request.match_info["recipients"])
    msg = parse.unquote(request.match_info["msg"])
    data = {
                "req_type": NOTIFICATIONS_HANDLER_MSG_TYPE
                "req_data": {
                    "notification_type": "sms"
                    "recipients": recipients,
                    "msg": msg
                }
            }

    res = client.send_request(NOTIFICATIONS_HANDLER_MSG_TYPE, data)

    return web.json_response({"resutl": res}, headers={"Server": "Movai-server"})


def send_user_notifications(request: web.Request):
    client = MessageClient(MESSAGE_SERVER_BIND_ADDR)
    msg = parse.unquote(request.match_info["msg"])
    fleet = parse.unquote(request.match_info["fleet"])
    robot_name = parse.unquote(request.match_info["robot_name"])
    robot_id = parse.unquote(request.match_info["robot_id"])
    service = parse.unquote(request.match_info["service"])

    data = {
                "req_type": NOTIFICATIONS_HANDLER_MSG_TYPE
                "req_data": {
                    "notification_type": "user"
                    "msg": msg,
                    "tags": {
                        "fleet": fleet,
                        "robot_id": robot_id,
                        "robot_name": robot_name,
                        "service": service
                    }
                }
            }

    res = client.send_request(NOTIFICATIONS_HANDLER_MSG_TYPE, data)

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
            web.post(r"/email", send_email)
        ]


WebAppManager.register("/api/v2/notify", NotificationsAPI)
