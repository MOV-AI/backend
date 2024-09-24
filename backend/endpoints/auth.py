"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

   Maintainers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements authentication REST API module/plugin
"""

from typing import Union, List
import asyncio
from aiohttp import web
from ldap3.utils.conv import escape_filter_chars

from movai_core_shared.exceptions import (
    InitializationError,
    LoginError,
    UserDoesNotExist,
    InvalidToken,
)

from dal.models.internaluser import InternalUser
from dal.models.remoteuser import RemoteUser

from gd_node.protocols.http.middleware import (
    save_node_type,
    remove_flow_exposed_port_links,
    redirect_not_found,
)

from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager
from backend.core.login import AUTH_MANAGER
from dal.classes.utils.token import TokenManager, UserToken


class AuthApp(BaseWebApp):
    """This class handles WebApp authentication."""

    internal_user_types = ["INTERNAL"]
    remote_user_types = ["LDAP", "PAM"]

    @property
    def routes(self) -> List[web.RouteDef]:
        """This function defines the list of REST endpoint.

        Returns:
            List[web.RouteDef]: list of REST endpoints with the corresponding
                handling function.
        """
        return [
            web.post(r"/token-auth/", self.post_token_auth),
            web.post(r"/token-refresh/", self.post_token_refresh),
            web.post(r"/token-verify/", self.post_token_verify),
            web.post(r"/logout/", self.post_logout),
            web.get(r"/domains/", self.get_domains),
        ]

    @property
    def middlewares(self) -> List[web.middleware]:
        """This function returns a list of app middlewares.

        Returns:
            List[web.middleware]: a list containing all the middlewares to
            register.
        """
        return [save_node_type, remove_flow_exposed_port_links, redirect_not_found]

    @property
    def safe_list(self) -> Union[None, List[str]]:
        """This funtions returns a list of auth-safe paths

        Returns:
            Union[None, List[str]]: a union containng None or path.
        """
        return [
            r"/token-auth/$",
            r"/token-refresh/$",
            r"/token-verify/$",
            r"/domains/$",
        ]

    async def post_token_auth(self, request: web.Request) -> web.Response:
        """This function handles initial user authentication, if the
        authentication succeeds it returns a token to the client

        Args:
            request (web.Request): the http request containing user info:
            domain, username and password

        Returns:
            web.Response: a token or reason for failure.
        """
        output = {}
        status = 200
        try:
            asyncio.create_task(TokenManager.remove_all_expired_tokens())

            data = await request.json()
            domain = data["domain"].lower()
            username = data["username"]
            if username != escape_filter_chars(username):
                raise LoginError("invalid username")
            password = data["password"]

            try:
                AUTH_MANAGER.verify_user(domain, username, password)
            except (UserDoesNotExist, LoginError, InitializationError) as e:
                error_msg = "invalid username/password"
                self.log.warning(error_msg)
                raise LoginError(error_msg)
            user_obj = AUTH_MANAGER.get_user(domain, username)

            refresh_token = UserToken.generate_refresh_token(user_obj)
            access_token = UserToken.generate_access_token(
                user_obj, UserToken.get_token_id(refresh_token)
            )
            output["refresh_token"] = refresh_token
            output["access_token"] = access_token
            output["error"] = False

        except Exception as e:
            status = 401
            output = {
                "access_token": False,
                "refresh_token": False,
                "error": f"{e.__class__.__name__}: {e.__str__()}",
            }

        return web.json_response(output, status=status, headers={"Server": "Movai-server"})

    async def post_token_refresh(self, request: web.Request) -> web.Response:
        """This function genereated and new Refresh Token

        Args:
            request (web.Request): The token request from the client's browser

        Raises:
            ValueError: if the request doesn't contain the "refresh" value
                in the "sub field.
            web.HTTPBadRequest: any other exception arises from the request.

        Returns:
            web.Response: the generated token.
        """

        output = {"access_token": False}

        try:
            data = await request.json()
            token_str = data["token"]
            UserToken.verify_token(token_str)
            refresh_token_obj = UserToken.get_token_obj(token_str)

            if refresh_token_obj.subject != "Refresh":
                raise InvalidToken("Invalid refresh token")

            if refresh_token_obj.user_type in self.internal_user_types:
                user_obj = InternalUser.get_user_by_name(
                    refresh_token_obj.domain_name, refresh_token_obj.account_name
                )
            elif refresh_token_obj.user_type in self.remote_user_types:
                user_obj = RemoteUser.get_user_by_name(
                    refresh_token_obj.domain_name, refresh_token_obj.account_name
                )
            else:
                error_msg = f"Unknonwn user type: {refresh_token_obj.user_type}"
                self.log.error(error_msg)
                raise InvalidToken(error_msg)

            output["access_token"] = UserToken.generate_access_token(
                user_obj, refresh_token_obj.jwt_id
            )

            return web.json_response(output, headers={"Server": "Movai-server"})

        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

    async def post_token_verify(self, request: web.Request) -> web.Response:
        """This function verifies the Token sent from the client.

        Args:
            request (web.Request): the request containing the token from the
                client.

        Raises:
            web.HTTPBadRequest: any exception arises from the request.
        Returns:
            web.Response: a response specifying if the token was
                veified or not.
        """

        output = {"result": False}

        try:
            data = await request.json()
            token_str = data["token"]
            UserToken.verify_token(token_str)
            output["result"] = True
            return web.json_response(output, headers={"Server": "Movai-server"})
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

    async def post_logout(self, request: web.Request) -> web.Response:
        """This function revokes the token of a user on logout.

        Args:
            request (web.Request): the request containing the token from the
                client.

        Raises:
            web.HTTPBadRequest: any exception arises from the request.
        Returns:
            web.Response: a response specifying if the token was revoked.
        """
        if "token" in request.query:
            token_str = request.query["token"]
        elif "Authorization" in request.headers:
            _, token_str = request.headers["Authorization"].strip().split(" ")
        else:
            raise web.HTTPBadRequest(reason="Token is missing.")
        try:
            UserToken.revoke_token(token_str)
            output = {"result": True}
            return web.json_response(output)
        except Exception as e:
            raise web.HTTPBadRequest(reason=e)

    def get_domains(self, request: web.Request) -> web.Response:
        """This method will return a status message regarding the backend
        authentication web app.

        Args:
            request (web.Request): the HTTP request from client browser.

        Returns:
            web.Response: a json containing all required fields.
        """
        output = {"domains": []}
        output["domains"] = AUTH_MANAGER.get_domains()
        return web.json_response(output, headers={"Server": "Movai-server"})


WebAppManager.register("/auth/", AuthApp)
