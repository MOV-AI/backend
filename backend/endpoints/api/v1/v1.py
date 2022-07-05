"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

   Maintainers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements version 1 of the REST APi module/plugin
"""

from typing import List

import aiohttp_cors
from aiohttp import web
from backend.http import IWebApp, WebAppManager
from movai_core_shared.envvars import REST_SCOPES
from backend.endpoints.api.v1.restapi import (
    RestAPI,
    redirect_not_found,
    remove_flow_exposed_port_links,
    save_node_type,
)


class RestV1App(IWebApp):
    """the actual version 1 API"""

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._node_name = "backend"
        self._rest_api = RestAPI(self._node_name)

    @property
    def routes(self) -> List[web.RouteDef]:
        """list of routes"""
        address_format = r"/{scope:%s}/{name}/"
        return [
            web.post(
                r"/User/{name}/reset-password/", self._rest_api.post_reset_password
            ),
            web.post(r"/upload/{package_name}/", self._rest_api.upload_static_file),
            web.get(r"/logs/", self._rest_api.get_logs),
            web.get(r"/logs/{robot_name}", self._rest_api.get_robot_logs),
            web.get(r"/metrics/", self._rest_api.get_metrics),
            web.get(r"/apps/{app_name}/{tail:.*}", self._rest_api.get_spa),
            web.get(
                r"/database/{scope:(global|fleet)}/{key}/", self._rest_api.get_key_value
            ),
            eb.delete(r'/lock/{name}/', self._rest_api.delete_lock),
            web.post(r"/database/", self._rest_api.set_key_value),
            web.post(r"/function/{cb_name}/", self._rest_api.cloud_func),
            web.get(r"/permissions/", self._rest_api.get_permissions),
            web.get(address_format % REST_SCOPES, self._rest_api.get_scope),
            web.post(address_format % REST_SCOPES, self._rest_api.post_to_scope),
            web.put(address_format % REST_SCOPES, self._rest_api.add_to_scope),
            web.delete(address_format % REST_SCOPES, self._rest_api.delete_in_scope),
            web.get(r"/{scope:%s}/" % REST_SCOPES, self._rest_api.get_scope),
            web.post(r"/{scope:%s}/" % REST_SCOPES, self._rest_api.post_to_scope),
            web.post(r"/newUser/", self._rest_api.new_user),
        ]

    @property
    def middlewares(self) -> List[web.middleware]:
        return [save_node_type, remove_flow_exposed_port_links, redirect_not_found]

    @property
    def cors(self) -> aiohttp_cors.CorsConfig:
        """return CORS setup, or None"""
        return aiohttp_cors.setup(
            self._app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            },
        )

    @property
    def safe_list(self) -> List[str]:
        # apps can be accessed without auth
        return [r"/apps/.*$"]


WebAppManager.register("/api/v1/", RestV1App)
