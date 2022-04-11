"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements the backend server application
"""

import os
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web
from movai_core_shared.envvars import JWT_SECRET_KEY
from backend.endpoints.api.v1.restapi import JWTMiddleware

from . import http
from .endpoints.static import StaticApp

FE_PATH = os.getenv("FE_PATH", "/opt/mov.ai/frontend")
NODE_NAME = os.getenv("NODE_NAME", "backend")
HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HTTP_PORT", "5004"))


async def root(_: web.Request) -> web.Response:
    """web app root"""
    package_fs = "launcher"  # mov-fe-app-launcher
    package_redis = "mov-fe-app-launcher"
    file = "index.html"
    body = None
    try:
        with open(os.path.join(FE_PATH, package_fs, file)) as fd:
            body = fd.read()
    except OSError:
        body = StaticApp._fetch_file_from_redis(package_redis, file)
    if body is None:
        raise web.HTTPNotFound()

    content_type = "text/html"

    return web.Response(body=body, content_type=content_type)


def main():
    """backend entrypoint"""

    # TODO get hostname and port from params/env

    # initialize web app, this is the main/parent application
    # APIs and other applications are added as sub applications
    main_app = web.Application()
    main_app["executor"] = ThreadPoolExecutor(max_workers=10)

    # prepare JWT middleware
    jwt_mw = JWTMiddleware(JWT_SECRET_KEY)
    main_app.middlewares.append(jwt_mw.middleware)

    # setup main app
    main_app.add_routes([web.get("/", root)])

    # the root is auth-safe
    jwt_mw.add_safe(r"/$")

    for app_cls, http_prefix in http.WebAppManager.get_servers():
        # special case
        if http_prefix == "/auth/":
            # these go to the root application
            app_inst = app_cls(main_app)
            main_app.add_routes(app_inst.routes)
            if app_inst.safe_list is not None:
                jwt_mw.add_safe(app_inst.safe_list)
            continue
        # else
        webapp = web.Application()
        webapp["executor"] = main_app["executor"]
        app_inst: http.IWebApp = app_cls(webapp)
        # routes
        webapp.add_routes(app_inst.routes)
        # middlewares
        webapp.middlewares.extend(app_inst.middlewares)
        # cors setup
        cors = app_inst.cors
        if cors is not None:
            for route in webapp.router.routes():
                cors.add(route)
        # auth-safe endpoints
        safe = app_inst.safe_list
        if safe is not None:
            jwt_mw.add_safe(safe, prefix=http_prefix)
        # and add to the root
        main_app.add_subapp(http_prefix, webapp)

    # start the application
    # runs until interrupted
    web.run_app(main_app, host=HTTP_HOST, port=HTTP_PORT)
