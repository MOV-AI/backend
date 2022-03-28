"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

   Maintainers:
   - Dor Marcous (dor@mov.ai) - 2022

   Module that implements authentication REST API module/plugin
"""

# watch for this
# pylint: disable=broad-except

from typing import Union, List

import aiohttp_cors

from aiohttp import web
# todo import from gd node
from endpoints.api.v1.models.user import User

from backend.http import IWebApp, WebAppManager
# Todo: move restapi to here
from gd_node.gdnode.protocols.restapi import (
    save_node_type,
    remove_flow_exposed_port_links,
    redirect_not_found)


class AuthApp(IWebApp):
    """ handles the web app authentication """

    # __init__ is the same

    @property
    def routes(self) -> List[web.RouteDef]:
        """ list of http routes """
        return [
            web.post(r'/token-auth/', self.post_token_auth),
            web.post(r'/token-refresh/', self.post_token_refresh),
            web.post(r'/token-verify/', self.post_token_verify)
        ]

    @property
    def middlewares(self) -> List[web.middleware]:
        """ list of app middlewares """
        return [
            save_node_type,
            remove_flow_exposed_port_links,
            redirect_not_found
        ]

    @property
    def cors(self) -> Union[None, aiohttp_cors.CorsConfig]:
        """ return CORS setup, or None """
        return aiohttp_cors.setup(self._app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

    @property
    def safe_list(self) -> Union[None, List[str]]:
        """ list of auth-safe paths """
        # it's basically all of them
        return [
            r'/token-auth/$',
            r'/token-refresh/$',
            r'/token-verify/$'
        ]

    #
    # handlers
    #

    async def post_token_auth(self, request: web.Request) -> web.Response:
        """ Get API Token """
        try:
            data = await request.json()

            user_obj = User(data["username"])

            if not user_obj.verify_password(data["password"]):
                raise ValueError('invalid username/password')

            # Password is correct, create output
            status = 200
            output = {
                'access_token': user_obj.get_token(),
                'refresh_token': user_obj.get_refresh_token(),
                'error': False
            }
        except Exception:
            status = 401
            output = {
                'access_token': False,
                'refresh_token': False,
                'error': 'Bad credentials'
            }

        # Return
        return web.json_response(output, status=status)

    async def post_token_refresh(self, request: web.Request) -> web.Response:
        """ Get new API Token """

        output = {
            'access_token': False,
            'refresh_token': False,
            'error': False
        }

        try:
            data = await request.json()

            token_data = User.verify_token(data['token'])

            if token_data['sub'] != 'refresh':
                raise ValueError('Invalid refresh token')

            user_obj = User(token_data['message']['name'])
            output['access_token'] = user_obj.get_token()
            output['refresh_token'] = user_obj.get_refresh_token()
            output['error'] = False

            return web.json_response(output)

        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

    async def post_token_verify(self, request: web.Request) -> web.Response:
        """ Verify is API Token is valid """

        output = {
            'result': False,
            'error': False
        }

        try:
            data = await request.json()

            try:
                User.verify_token(data['token'])
            except Exception:
                output['result'] = False
            else:
                output['result'] = True

            return web.json_response(output)

        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))


WebAppManager.register('/auth/', AuthApp)
