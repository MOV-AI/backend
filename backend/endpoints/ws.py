"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

   Maintainers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements websockets REST API module/plugin
"""


import aiohttp_cors
from typing import List, Union
from aiohttp import web

from dal.classes.protocols.wsredissub import WSRedisSub

from backend.http import IWebApp, WebAppManager
from backend.endpoints.api.v1.restapi import (
    save_node_type,
    remove_flow_exposed_port_links,
    redirect_not_found,
)

from gd_node.protocols.http.movai_widget import MovaiWidget




class WSApp(IWebApp):
    """WS app module"""

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._app["connections"] = set()
        self._app["sub_connections"] = set()
        self.node_name = "backend"
        self.redis_sub = WSRedisSub(self._app, self.node_name)

    @property
    def routes(self) -> List[web.RouteDef]:
        """list of http routes"""
        return [
            web.get("/widget/support", self.test_support),
            web.get(self.redis_sub.http_endpoint, self.redis_sub.handler),
        ]

    @property
    def middlewares(self) -> List[web.middleware]:
        """list of app middlewares"""
        return [save_node_type, remove_flow_exposed_port_links, redirect_not_found]

    @property
    def cors(self) -> Union[None, aiohttp_cors.CorsConfig]:
        """return CORS setup, or None"""
        return None

    async def test_support(self, request):
        """check if there is support for the widget"""
        rsp = {
            "support": False,
            "error": False,
        }
        username = False
        fields = ["uid", "type", "name", "message"]

        ws_resp = web.WebSocketResponse()
        await ws_resp.prepare(request)

        async for msg in ws_resp:
            obj = msg.json()

            if all(field in obj for field in fields):
                widget = MovaiWidget(obj["name"], obj["uid"], obj["type"])
                rsp["support"] = widget.is_supported(self.node_name, username)
                rsp["uid"] = widget.uid
            else:
                for field in fields:
                    if field not in obj:
                        rsp["error"] = " Missing field '" + field + "'"
                        break
            await ws_resp.send_json(rsp)


WebAppManager.register("/ws/", WSApp)
