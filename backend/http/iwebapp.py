"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Dor Marcous (dor@mov.ai) - 2022

   Root module for all REST API apps
"""
from typing import List, Union, Generator, Tuple
from aiohttp import web

import aiohttp_cors


class IWebApp:
    """Base interface for a rest api module"""

    def __init__(self, app: web.Application):
        self._app = app

    @property
    def routes(self) -> List[web.RouteDef]:
        """list of http routes"""
        return []

    @property
    def middlewares(self) -> List[web.middleware]:
        """list of app middlewares"""
        return []

    @property
    def cors(self) -> Union[None, aiohttp_cors.CorsConfig]:
        """return CORS setup, or None"""
        return None

    @property
    def safe_list(self) -> Union[None, List[str]]:
        """list of auth-safe paths/patterns
        should be a list of regex patterns
        """
        return None


class WebAppManager:
    """Manager of Web Application classes"""

    _apps = {}

    @staticmethod
    def register(path: str, cls: type(IWebApp)) -> None:
        """register a web app class to a path"""
        if path in WebAppManager._apps:
            # perhaps even raise
            return
        WebAppManager._apps[path] = cls

    @staticmethod
    def get_servers() -> Generator[Tuple[type(IWebApp), str], None, None]:
        """get list of registered classes"""
        # swap key/value
        yield from ((cls, prefix) for prefix, cls in WebAppManager._apps.items())
