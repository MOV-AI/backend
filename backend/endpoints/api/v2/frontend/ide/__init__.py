from aiohttp import web
from typing import List


from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager

#from .callbackeditor import main
from .datavalidation import data_validation

class IdeApi(BaseWebApp):
    """Web application for serving as the frontend api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the ldap configuration api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            #web.get(r"/callbackeditor/", )
            web.post(r"/datavalidation/", data_validation)
            #web.get(r"/copyappside/", )
            #web.get(r"/flowapi/", )
        ]


WebAppManager.register("/api/v2/frontend/ide", IdeApi)
