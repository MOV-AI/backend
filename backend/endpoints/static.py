"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

   Maintainers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements static HTTP files module/plugin
"""

import asyncio

from typing import List, Union
from mimetypes import guess_type

import aiohttp_cors
from aiohttp import web

from dal.movaidb import MovaiDB

from gd_node.protocols.http.middleware import (
    save_node_type,
    remove_flow_exposed_port_links,
    redirect_not_found,
)

from backend.http import IWebApp, WebAppManager
from urllib.parse import unquote


class StaticApp(IWebApp):
    """handles static files"""

    @property
    def routes(self) -> List[web.RouteDef]:
        """list of http routes"""
        return [web.get(r"/{package_name}/{package_file:.*}", self.get_static_file)]

    @property
    def middlewares(self) -> List[web.middleware]:
        """list of app middlewares"""
        return [save_node_type, remove_flow_exposed_port_links, redirect_not_found]

    @property
    def cors(self) -> Union[None, aiohttp_cors.CorsConfig]:
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
        # all paths here are safe
        return [r"/.*"]

    #
    # handlers
    #

    @staticmethod
    def _fetch_file_from_redis(package_name: str, package_file: str) -> str:
        """this is blocking thus needs to be run on an executor"""

        decoded_package_name = unquote(package_file)
        # use MovaiDB().get() increase performance
        _file = MovaiDB().get(
            {"Package": {package_name: {"File": {decoded_package_name: {"Value": "*"}}}}}
        )
        try:
            return _file["Package"][package_name]["File"][decoded_package_name]["Value"]
        except KeyError:
            return ""

    async def get_static_file(self, request: web.Request) -> web.Response:
        """get static file from Package"""

        try:
            package_name = request.match_info["package_name"]
            package_file = request.match_info["package_file"]

            
            # get file from redis
            output = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_file_from_redis, package_name, package_file
            )

            if not output:
                raise web.HTTPNotFound()

            # guess content type
            content_type = guess_type(package_file)[0]

            return web.Response(
                body=output,
                content_type=content_type,
                headers={"Server": "Movai-server"},
            )
        except web.HTTPException as e:
            # re-raise
            raise e
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))


WebAppManager.register("/static/", StaticApp)
