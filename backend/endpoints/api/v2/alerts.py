"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Moawiya Mograbi (moawiya@mov.ai) - 2023

   This module implements RestAPI endpoints to access the notifications
   in the Message Server
"""
import json
from pydantic import Field, BaseModel, EmailStr
from typing import List
from aiohttp import web
from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager
from .db import _check_user_permission
from dal.models.var import Var


class AlertsConfig(BaseModel):
    """pydantic class in order to validate
    """
    emails: List[EmailStr] = Field(default_factory=list)
    alerts: List[str] = Field(default_factory=list)

    class Config:
        validate_assignment = True

    class Meta:
        # global variables (like class variables)
        # will be initialized once
        var = Var("global")
        ALERTS_GLOBAL_VAR_STR = "alertsConfig"

    @classmethod
    def db_get(cls) -> "AlertsConfig":
        """
        get the alertsConfig Var from Redis and returns it
        """
        db_alerts_config = cls.Meta.var.get(cls.Meta.ALERTS_GLOBAL_VAR_STR)
        return cls(**db_alerts_config) if db_alerts_config else cls()

    def db_set(self) -> None:
        """
        Set current alerts config object in global Var with the recieved dict
        """
        setattr(self.Meta.var, self.Meta.ALERTS_GLOBAL_VAR_STR, self.dict())


async def set_alerts_config(request: web.Request):
    data = None
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        raise web.HTTPBadRequest(reason="alerts not in data")
    if "alerts" not in data:
        raise web.HTTPBadRequest(reason="alerts not in data")

    _check_user_permission(request, "EmailsAlertsConfig", "update")

    alertsConfig = AlertsConfig.db_get()
    alertsConfig.alerts = data["alerts"]
    alertsConfig.db_set()

    return web.json_response(
        alertsConfig.dict(),
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

    _check_user_permission(request, "EmailsAlertsRecipients", "update")

    alertsConfig = AlertsConfig.db_get()
    alertsConfig.emails = data["emails"]
    alertsConfig.db_set()

    return web.json_response(
        alertsConfig.dict(),
        headers={"Server": "Movai-server"},
    )



async def get_alerts_emails(request: web.Request) -> web.json_response:
    _check_user_permission(request, "EmailsAlertsRecipients", "read")
    alertsConfig = AlertsConfig.db_get()

    return web.json_response(alertsConfig.emails, headers={"Server": "Movai-server"})


async def get_alerts_config(request: web.Request):
    _check_user_permission(request, "EmailsAlertsConfig", "read")
    alertsConfig = AlertsConfig.db_get()

    return web.json_response(alertsConfig.alerts, headers={"Server": "Movai-server"})


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

