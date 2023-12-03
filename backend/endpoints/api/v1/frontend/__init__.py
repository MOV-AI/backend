from aiohttp import web
from typing import List

from backend.endpoints.api.v2.base import BaseWebApp
from backend.http import WebAppManager

from .ide import ide_action_map
from .fleetdashboard import fleetdashoboard_action_map
from .taskmanager import taskmanager_action_map

frontend_map = {
    "ide": ide_action_map,
    "fleetdashoboard": fleetdashoboard_action_map,
    "taskmanager": taskmanager_action_map
}


async def entry(request: web.Request):
    try:
        response = {"success": True}
        app = request.match_info.get("app", False)
        if not app or app not in frontend_map:
            raise web.HTTPBadRequest(reason=f"unsupprted app {app}")
        action_map = frontend_map[app]
        data = await request.json()
        func = data.get("func")
        if func is None:
            raise ValueError("the 'func' argument is missing in request's body!")
        elif func not in action_map:
            raise ValueError(f"{func} unknown function, it is not found in the ide action map.")
        args = data.get("args")
        response["result"] = action_map[func](**args)
    except Exception as exc:
        response = {"success": False, "error": str(exc)}

    return web.json_response(response)


class FrontendApi(BaseWebApp):
    """Web application for serving as the frontend api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the ldap configuration api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.post(r"/{app}/", entry),
        ]


WebAppManager.register("/api/v1/frontend", FrontendApi)