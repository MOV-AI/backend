"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Moawiya Mograbi (moawiya@mov.ai) - 2023

   This module implements RestAPI endpoints to access the notifications
   in the Message Server
"""
from typing import List, Dict, Any
import json
from aiohttp import web
from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager
from .db import _check_user_permission
from dal.models.var import Var

def _set_alerts_config(data: dict):
    """
    Set the alerts config
    """
    var_global = Var("global")
    setattr(var_global, "alertsConfig", data)


async def set_alerts_config(request: web.Request):
    data = None
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        raise web.HTTPBadRequest(reason="alerts not in data")
    if "alerts" not in data:
        raise web.HTTPBadRequest(reason="alerts not in data")

    alerts = data["alerts"]
    _check_user_permission(request, "EmailsAlertsConfig", "update")
    alertsConfig = _get_alerts_config()
    alertsConfig["alerts"] = alerts
    _set_alerts_config(alertsConfig)
    return web.json_response(
        alertsConfig,
        headers={"Server": "Movai-server"},
    )


async def set_alerts_emails(request: web.Request):
    data = None
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        raise web.HTTPBadRequest(reason="emails not in data")
    if "emails" not in data:
        raise web.HTTPBadRequest(reason="\"emails\" not in data")

    recipients = data["emails"]
    _check_user_permission(request, "EmailsAlertsRecipients", "update")

    alertsConfig = _get_alerts_config()
    alertsConfig["emails"] = recipients
    _set_alerts_config(alertsConfig)
    return web.json_response(
        alertsConfig,
        headers={"Server": "Movai-server"},
    )


def _get_alerts_config() -> Dict[str, Any]:
    return Var("global").get("alertsConfig")


async def get_alerts_emails(request: web.Request) -> web.json_response:
    _check_user_permission(request, "EmailsAlertsRecipients", "read")
    alertsConfig = _get_alerts_config()
    return web.json_response(alertsConfig["emails"], headers={"Server": "Movai-server"})


async def get_alerts_config(request: web.Request):
    _check_user_permission(request, "EmailsAlertsConfig", "read")
    alertsConfig = _get_alerts_config()
    return web.json_response(alertsConfig["alerts"], headers={"Server": "Movai-server"})


class EmailsAlertsAPI(BaseWebApp):
    """Web application for serving as the database api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the alerts api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.post(r"/emails", set_alerts_emails),
            web.post(r"/config", set_alerts_config),
            web.get(r"/emails", get_alerts_emails),
            web.get(r"/config", get_alerts_config),
        ]


WebAppManager.register("/api/v2/alerts", EmailsAlertsAPI)

