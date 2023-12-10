"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

    Maintainers:
    - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020
    - Erez Zomer (erez@mov.ai) - 2022

   Rest API
"""
import json
import urllib.parse
from datetime import datetime, date
import inspect
from mimetypes import guess_type
from string import Template
from urllib.parse import unquote
from typing import Any, List
import pydantic

from aiohttp import web

from movai_core_shared.common.utils import is_enterprise
from movai_core_shared.exceptions import MovaiException, NotSupported
from movai_core_shared.envvars import SCOPES_TO_TRACK
from movai_core_shared.logger import Log, LogsQuery

from dal.helpers.helpers import Helpers
from dal.models.acl import NewACLManager
from dal.models.lock import Lock
from dal.models.var import Var
from dal.new_models.role import Role
from dal.movaidb import MovaiDB
from dal.new_models import Application
from dal.new_models import Callback
from dal.new_models import Configuration
from dal.new_models import Node
from dal.new_models import Flow
from dal.scopes.form import Form
from dal.new_models import Message
from dal.new_models import Package
from dal.new_models import Ports
from dal.scopes.robot import Robot
from dal.scopes.statemachine import StateMachine
from dal.scopes.user import User

try:
    from movai_core_enterprise.message_client_handlers.metrics import Metrics
    from movai_core_enterprise.new_models import Annotation
    from movai_core_enterprise.scopes.graphicscene import GraphicScene
    from movai_core_enterprise.scopes.layout import Layout
    from movai_core_enterprise.scopes.shareddatatemplate import SharedDataTemplate
    from movai_core_enterprise.scopes.shareddataentry import SharedDataEntry
    from movai_core_enterprise.scopes.tasktemplate import TaskTemplate
    from movai_core_enterprise.scopes.taskentry import TaskEntry

    enterprise_scope = {
        "Metrics": Metrics,
        "Annotation": Annotation,
        "GraphicScene": GraphicScene,
        "Layout": Layout,
        "SharedDataEntry": SharedDataEntry,
        "SharedDataTemplate": SharedDataTemplate,
        "TaskEntry": TaskEntry,
        "TaskTemplate": TaskTemplate,
    }
    ENTERPRISE = True
except ImportError:
    enterprise_scope = {}
    ENTERPRISE = False

from gd_node.callback import GD_Callback

from backend.endpoints.api.v1.robot_reovery import trigger_recovery_aux
from backend.endpoints.api.v1.frontend import frontend_map
from backend.helpers.rest_helpers import deprecate_endpoint, fetch_request_params

LOGGER = Log.get_logger(__name__)
PAGE_SIZE = 100


class MagicDict(dict):
    """Class that when accessing a not existing dict field, creates the field"""

    def __getitem__(self, name):
        try:
            return dict.__getitem__(self, name)
        except KeyError:
            value = self[name] = type(self)()
            return value


class RestAPI:
    """Class that serves REST methods to communicate with database"""

    def __init__(self, node_name, api_version="/api/v1/"):
        self.api_version = api_version
        self.node_name = node_name
        self.scope_classes = {
            "Application": Application,
            "Callback": Callback,
            "Configuration": Configuration,
            "Flow": Flow,
            "Form": Form,
            "Message": Message,
            "Node": Node,
            "Package": Package,
            "Ports": Ports,
            "Role": Role,
            "StateMachine": StateMachine,
            "User": User,
        }
        self.scope_classes.update(enterprise_scope)

    async def cloud_func(self, request):
        """Run specific callback"""
        callback_name = request.match_info["cb_name"]
        # AppName to use in Callback permission validation
        app_name = request.match_info.get("app_name", None)

        try:
            callback = GD_Callback(callback_name, self.node_name, "cloud", False)

            # Check User permissions
            #scope_obj = self.scope_classes["Callback"](name=callback_name)
            scope_obj = Callback(callback_name)
            if not scope_obj.has_permission(request.get("user"), "execute", app_name):
                raise ValueError("User does not have permission")

            body = {}
            if request.can_read_body:
                body = await request.json()
            # Get status code from callback variable, defaults to 200 OK
            callback.user.globals.update(
                {
                    "web": web,
                    "request": request,
                    "msg": body,
                    "response": {},
                    "status_code": 200,
                }
            )
            callback.execute(body)

            return web.json_response(
                callback.updated_globals["response"],
                status=callback.updated_globals["status_code"],
                headers={"Server": "Movai-server"},
            )
        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc), headers={"Server": "Movai-server"})

    async def frontend_apps(self, request: web.Request):
        try:
            response = {"success": True}
            app = request.match_info.get("app", False)
            if not app or app not in frontend_map:
                raise web.HTTPBadRequest(reason=f"unsupprted app {app}")
            action_map = frontend_map[app]["action"]
            enterprise_map = frontend_map[app]["enterprise"]
            data = await request.json()
            func = data.get("func")

            if func is None:
                raise ValueError("the 'func' argument is missing in request's body!")

            if func not in action_map:
                raise ValueError(f"{func} unknown function, it is not found in the {app} action map.")

            if func in enterprise_map and not is_enterprise():
                raise NotSupported(f"The {func} method is not supported for community edition.")

            args = data.get("args")
            if isinstance(args, dict):
                response["result"] = action_map[func](**args)
            elif isinstance(args, tuple):
                response["result"] = action_map[func](*args)
            else:
                response["result"] = action_map[func](args)
        except Exception as exc:
            response = {"success": False, "error": str(exc)}

        return web.json_response(response)

    async def get_logs(self, request) -> web.Response:
        """Get logs from HealthNode using get_logs in Logger class
        path:
            /logs/

        parameters:
            robots
            level
            offset
            message
            limit
            tags
            services
        """
        params = fetch_request_params(request)

        try:
            status = 200
            output = await LogsQuery.get_logs(pagination=True, **params)
        except Exception as err:
            status = 401
            output = {"error": str(err)}

        return web.json_response(output, status=status, headers={"Server": "Movai-server"})

    @staticmethod
    def fetch_logs_url_params(request) -> dict:
        """fetch logs request params and return them as dictionary

        Args:
            request (web request): the request object for /logs

        Returns:
            dict: dictionary including the request params
        """
        limit = request.rel_url.query.get("limit", 1000)
        offset = request.rel_url.query.get("offset", 0)
        level = request.rel_url.query.get("level", None)
        robots = request.rel_url.query.get("robots", [Robot().RobotName])
        tags = request.rel_url.query.get("tags", None)
        message = request.rel_url.query.get("message", None)
        services = request.rel_url.query.get("services", None)
        log_start_time = request.rel_url.query.get("fromDate", None)
        log_end_time = request.rel_url.query.get("toDate", None)

        # Replace %xx escapes by their single-character equivalent
        # get rid of spaces in case existed
        level = unquote(level) if level else None
        tags = unquote(tags) if tags else None

        # remove spaces around keywords
        level = [x.strip() for x in level.split(",")] if level else []
        tags = [x.strip() for x in tags.split(",")] if tags else []

        return {
            "limit": limit,
            "offset": offset,
            "level": level,
            "tags": tags,
            "robots": robots,
            "message": message,
            "services": services,
            "from_": log_start_time,
            "to_": log_end_time,
        }

    async def get_robot_logs(self, request) -> web.Response:
        """*** Deprecated! ***
        Get logs from specific robot using the robot name
        path:
            /logs/{robot_name}

        parameters:
            level
            offset
            message
            limit
            tags
            services
        """
        error_msg = "get_robot_logs is deprecated, please use get_logs with robots parameter"
        LOGGER.error(error_msg)
        response = web.json_response(
            {"error": error_msg}, status=404, headers={"Server": "Movai-server"}
        )
        response.message = "This function isn't supported anymore"
        return response

    async def get_permissions(self, request):
        try:
            output = NewACLManager.get_permissions()
            return web.json_response(output, status=200, headers={"Server": "Movai-server"})
        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc), headers={"Server": "Movai-server"})

    async def get_metrics(self, request):
        """Get metrics from message-server"""
        if not ENTERPRISE:
            output = {"error": "movai-core-enterprise is not installed."}
            return output

        params = fetch_request_params(request)
        # Fetch all responses within one Client session,
        # keep connection alive for all requests.
        if params.get("tags") is not None:
            tags = params["tags"].split(",")
        else:
            tags = []
        try:
            status = 200
            metrics = Metrics()
            output = metrics.get_metrics(
                **params,
                tags=tags,
                pagination=True,
            )
        except Exception as exc:
            status = 401
            output = {"error": str(exc)}

        return web.json_response(output, status=status, headers={"Server": "Movai-server"})

    async def get_spa(self, request):
        """get spa code and inject server params"""

        app_name = request.match_info["app_name"]
        content_type = "text/html"

        try:
            # Check sanity of request url parms
            decoded_params = urllib.parse.unquote(request.query_string)
            # Get app information
            app = Application(app_name)
            content_type = guess_type(app.EntryPoint)[0]
            # html = Package(app.Package).File[app.EntryPoint].Value
            html = Package(app.Package).get_value(app.EntryPoint)

            html = self.spa_parse_template(app, html, request)

        except Exception as error:
            html = f"<div style='top:40%;left:35%;position:absolute'><p>Error while trying to serve {app_name}</p><p style='color:red'>{error}</p></div>"

        return web.Response(
            body=html, content_type=content_type, headers={"Server": "Movai-server"}
        )

    def spa_parse_template(self, application: Application, html, request):
        """parse application params"""

        serverdata = {"pathname": f"{self.api_version}apps/{application.name}/"}
        try:
            # get app configuration
            serverdata.update(self.get_spa_configuration(application))
            # get  application meta-data
            serverdata.update(
                {"Application": application.model_dump()["Application"][application.name]}
            )
        except Exception as error:
            LOGGER.error(str(error))

        # add GET query to serverdata
        _request = {}
        for key, value in request.query.items():
            _request.update({key: value})
        serverdata.update({"request": _request})

        params = {
            "serverdata": json.dumps(serverdata),
            "label": application.Label,
            "description": application.Description,
        }
        return Template(html.decode("utf-8")).safe_substitute(**params)

    def get_spa_configuration(self, application: Application):
        """get default configuration and updated it with user custom configuration"""
        output = {}

        configs = [application.Configuration, application.CustomConfiguration]
        for cfg_name in configs:
            try:
                obj = Configuration(cfg_name)
                output.update(obj.data)
            except Exception as error:
                LOGGER.info(str(error))

        return output

    async def trigger_recovery(self, request: web.Request) -> web.Response:
        """[POST] api set recovery state
        curl -d "robot_id=01291370127" -X POST http://localhost:5003/api/v1/trigger-recovery/
        """

        try:
            data = await request.json()
            robot_id = data.get("id")
            trigger_recovery_aux(robot_id)

        except Exception as error:
            msg = f"Caught expection {error}"
            LOGGER.error(msg)
            raise web.HTTPBadRequest(reason=msg, headers={"Server": "Movai-server"})

        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    async def new_user(self, request: web.Request) -> web.Response:
        """Create new user
        Args:
            request (web.Request)

        request payload:
            - required keys:
                * Username (str): the new user
                * Password (str): the user password

            - optional:
                * all other fields in the User model

        returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """
        deprecate_endpoint()
        # Check User permissions
        if not request.get("user").has_permission("User", "create"):
            raise web.HTTPForbidden(reason="User does not have Scope permission.")
        try:
            data = await request.json()
            username = data.pop("Username")
            password = data.pop("Password")
            obj = User.create(username, password)

            for key, value in data.items():
                try:
                    setattr(obj, key, value)
                except AttributeError as error:
                    # ignore invalid keys sent in the request
                    LOGGER.error(f"{type(error).__name__}: {error}")

        except KeyError as error:
            msg = f"{error} is required"
            LOGGER.error(msg)
            raise web.HTTPBadRequest(reason=msg, headers={"Server": "Movai-server"})

        except Exception as error:
            LOGGER.error(f"{type(error).__name__}: {error}")
            raise web.HTTPBadRequest(reason=str(error), headers={"Server": "Movai-server"})

        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    async def post_reset_password(self, request: web.Request) -> web.Response:
        """Reset user password : Only possible if superuser
        Args:
            request (web.Request)

        request payload:
            - required:
                * new_password (str): the new password
                * confirm_password (str): the confirm password

         returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """
        deprecate_endpoint()
        try:
            username = request.match_info["name"]
            data = await request.json()
            is_superuser = request.get("user").Superuser is True
            if not is_superuser:
                raise ValueError("Not Authorized: Only superuser allowed to reset-password")
            User.reset(
                username=username,
                new_pass=data.get("new_password"),
                confirm_pass=data.get("confirm_password"),
                current_pass=False,
                validate_current_pass=False,
            )
        except Exception as error:
            raise web.HTTPBadRequest(reason=str(error), headers={"Server": "Movai-server"})
        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    async def post_change_password(self, request: web.Request) -> web.Response:
        """Change user password
        Args:
            request (web.Request)

        request payload:
            - required:
                * current_password (str): the old password
                * new_password (str): the new password
                * confirm_password (str): the confirm password

         returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """
        deprecate_endpoint()
        try:
            token = request.headers["Authorization"].strip().split(" ")[1]
            token_data = User.verify_token(token)
            username = token_data["message"]["name"]

            data = await request.json()

            User.reset(
                username=username,
                current_pass=data.get("current_password"),
                new_pass=data.get("new_password"),
                confirm_pass=data.get("confirm_password"),
                validate_current_pass=True,
            )
        except Exception as error:
            raise web.HTTPBadRequest(reason=str(error), headers={"Server": "Movai-server"})

        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    # -------------------------------- DELETE LOCKS -----------------------------------.

    async def delete_lock(self, request: web.Request) -> web.Response:
        """[DELETE] api delete key handler
        curl DELETE http://localhost:5003/api/v1/lock/{name}/
        """
        name = request.match_info["name"]
        try:
            mutex = Lock(name)
            if mutex.release():
                return web.json_response({"success": True}, headers={"Server": "Movai-server"})
            else:
                return web.json_response(
                    {
                        "success": False,
                        "message": "Unable to release lock as it was not owned.",
                    },
                    headers={"Server": "Movai-server"},
                )
        except MovaiException:
            raise web.HTTPBadRequest(reason="Lock not found.")

    # ---------------------------- GET SET DELETE TO VARS -----------------------------.

    async def get_key_value(self, request: web.Request) -> web.Response:
        """[GET] api get key value handler
        curl http://localhost:5003/api/v1/database/{scope_name}/{key_name}/
        """
        scope = request.match_info["scope"]
        key = request.match_info["key"]
        output = {"scope": scope, "key": key, "value": None}
        if all([scope, key]):
            if scope == "fleet":
                try:
                    _robot_name, key = key.split("@")
                    var_scope = Var(scope=scope, _robot_name=_robot_name)
                except Exception as error:
                    raise web.HTTPBadRequest(reason=str(error))
            else:
                var_scope = Var(scope=scope)
            value = var_scope.get(key)
            if isinstance(value, date):
                value = json.loads(json.dumps(value, default=str))
                output["is_date"] = True
            output["value"] = value
            return web.json_response(output, headers={"Server": "Movai-server"})
        raise web.HTTPBadRequest(
            reason="Required keys (scope, key) not found.",
            headers={"Server": "Movai-server"},
        )

    async def _forward_alerts_config(self, request: web.Request, data: dict) -> web.Response:
        from ..v2.db import _check_user_permission

        curr_alerts_config = Var("global").get("alertsConfig")
        set_emails = False
        set_alerts = False
        to_set = curr_alerts_config or {"emails": [], "alerts": []}

        if curr_alerts_config is None:
            if data["emails"]:
                _check_user_permission(request, "EmailsAlertsRecipients", "update")
                set_emails = True
            elif data["alerts"]:
                _check_user_permission(request, "EmailsAlertsConfig", "update")
                set_alerts = True
        else:
            if sorted(curr_alerts_config["emails"]) != sorted(data["emails"]):
                _check_user_permission(request, "EmailsAlertsRecipients", "update")
                set_emails = True
            elif sorted(curr_alerts_config["alerts"]) != sorted(data["alerts"]):
                _check_user_permission(request, "EmailsAlertsConfig", "update")
                set_alerts = True

        var_global = Var("global")
        if set_emails:
            to_set["emails"] = data["emails"]
            setattr(var_global, "alertsConfig", to_set)
        elif set_alerts:
            to_set["alerts"] = data["alerts"]
            setattr(var_global, "alertsConfig", to_set)

    async def set_key_value(self, request: web.Request) -> web.Response:
        """[POST] api set key value handler
        curl -d "scope=fleet&key=agv1@qwerty&value=123456" -X POST http://localhost:5003/api/v1/database/
        """
        data = await request.json()
        if "key" not in data:
            raise web.HTTPBadRequest(reason="Required key 'value' not found.")
        if "value" not in data:
            raise web.HTTPBadRequest(reason="Required 'key' not found.")
        if "scope" not in data:
            raise web.HTTPBadRequest(reason="Required key 'scope' not found.")
        key = data.get("key", None)  # fleet: robot_name@key_name
        value = data.get("value", None)
        scope = data.get("scope", None)
        if scope == "fleet":
            try:
                _robot_name, key = key.split("@")
                var_scope = Var(scope=scope, _robot_name=_robot_name)
            except Exception as error:
                raise web.HTTPBadRequest(reason=str(error))
        else:
            var_scope = Var(scope=scope)
        if key == "alertsConfig":
            # TODO: remove this when we remove the old alerts config
            # forward message to /api/v2/alerts/*
            await self._forward_alerts_config(request, data["value"])
        else:
            setattr(var_scope, key, value)

        return web.json_response(
            {"key": key, "value": value, "scope": scope},
            headers={"Server": "Movai-server"},
        )

    async def delete_key_value(self, request: web.Request) -> web.Response:
        """[DELETE] api delete key handler
        curl DELETE http://localhost:5003/api/v1/database/{scope_name}/{key_name}/
        """
        scope = request.match_info["scope"]
        key = unquote(request.match_info["key"])
        if all([scope, key]):
            if scope == "fleet":
                try:
                    _robot_name, key = key.split("@")
                    var_scope = Var(scope=scope, _robot_name=_robot_name)
                except Exception as error:
                    raise web.HTTPBadRequest(reason=str(error))
            else:
                var_scope = Var(scope=scope)
            var_scope.delete(name=key)
            return web.json_response({"success": True}, headers={"Server": "Movai-server"})
        raise web.HTTPBadRequest(reason="Required keys (scope, key) not found.")

    # ---------------------------- GET APPLICATIONS --------------------------------

    async def get_applications(self, request: web.Request) -> web.Response:
        """Get applications

        args:
            request (web.Request)

         returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """

        def create_application_format(url, label, icon, enable, app_type):
            return {
                "URL": url,
                "Label": label,
                "Icon": icon,
                "Enabled": enable,
                "Type": app_type,
            }

        try:
            permissions = NewACLManager.get_permissions()["Applications"]
            output = {"success": True, "result": []}

            apps: List[Application] = Application.get_all_models()
            for app in apps:
                url = app.Package if app.Type == "application" else app.EntryPoint
                label = app.Label
                icon = app.Icon
                enable = len(list(filter(lambda x: x == app.name, permissions))) > 0
                app_type = app.Type
                output["result"].append(
                    create_application_format(url, label, icon, enable, app_type)
                )

        except Exception as error:
            raise web.HTTPBadRequest(reason=str(error), headers={"Server": "Movai-server"})

        return web.json_response(output, headers={"Server": "Movai-server"})

    # ---------------------------- SERVE STATIC FILES FROM REDIS PACKAGES ----------

    async def old_get_static_file(self, request: web.Request) -> web.Response:
        """get static file from Package"""
        print(
            "static file called",
            request.match_info["package_name"],
            request.match_info["package_file"],
        )
        try:
            package_name = request.match_info["package_name"]
            package_file = request.match_info["package_file"]
            content_type = guess_type(package_file)[0]
            output = Package(package_name).get_value(package_file)
            return web.Response(
                body=output,
                content_type=content_type,
                headers={"Server": "Movai-server"},
            )
        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc))

    async def upload_static_file(self, request: web.Request) -> web.Response:
        package_name = request.match_info["package_name"]

        reader = await request.multipart()

        field = await reader.next()
        assert field.name == "name"
        package_file = (await field.read(decode=True)).decode("utf-8")

        field = await reader.next()
        assert field.name == "data"
        data = await field.read()
        try:
            package = Package.get_or_create(package_name)
            package.add("File", f"{package_file}", Value=bytes(data), FileLabel=package_file)
        except Exception as exc:
            return web.json_response(
                {"success": False, "error": str(exc)}, headers={"Server": "Movai-server"}
            )
        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    # ---------------------------- OPERATIONS TO SCOPES -----------------------------

    async def get_scope(self, request: web.Request) -> web.Response:
        """[GET] api get a full scope dict
        curl http://localhost:5003/api/v1/{scope}/{name}/
        """
        scope = request.match_info.get("scope")
        _id = request.match_info.get("name", False)

        if _id:
            try:
                scope_obj = self.scope_classes[scope](_id)
            except Exception as e:
                LOGGER.error(f"caught error while creating scope object, exception: {e}")
                raise web.HTTPNotFound(reason="Required scope not found.")

            # Check User permissions
            if not scope_obj.has_scope_permission(request.get("user"), "read"):
                raise web.HTTPForbidden(reason="User does not have Scope permission.")

            if issubclass(self.scope_classes[scope], pydantic.BaseModel ):
                scope_result = scope_obj.model_dump()
            else:
                scope_result = MovaiDB().get({scope: {_id: "**"}})
            result = scope_result[scope][_id]

            # If Scope User add permissions list
            if isinstance(scope_obj, User):
                result["resourcesPermissions"] = scope_obj.user_permissions()
                # do not send the user password with the object
                result.pop("Password", None)

        else:
            # Check User permissions
            if not request.get("user").has_permission(scope, "read"):
                raise web.HTTPForbidden(reason="User does not have Scope permission.")

            if issubclass(self.scope_classes[scope], pydantic.BaseModel ):
                objs = self.scope_classes[scope].get_all_models()

                scope_result = {obj.name: obj.model_dump()["Callback"][obj.name] for obj in objs}
                scope_result = {scope: scope_result}
            else:
                scope_result = MovaiDB().get_by_args(scope)
            result = scope_result.get(scope, {})

        if not result:
            raise web.HTTPNotFound(reason="Required scope not found.")

        try:
            json_result = json.dumps(result, default=self.json_serializer_converter)
            validated_result = json.loads(json_result)
        except Exception as exc:
            LOGGER.error(f"caught error while creating json, exception: {exc}")
            raise web.HTTPBadRequest(
                reason="Error when serializing JSON response.",
                headers={"Server": "Movai-server"},
            )

        return web.json_response(validated_result, headers={"Server": "Movai-server"})

    async def add_to_scope(self, request: web.Request) -> web.Response:
        """ [PUT] api add keys to scope
            curl -H 'Content-Type: application/json' -X PUT \
            -d '{"Node":{"yolo4":{"Persistent":true}}}' \
            http://localhost:5003/api/v1/{scope}/{name}/
        """
        scope = request.match_info["scope"]
        _id = request.match_info["name"]

        # Check User permissions
        if not request.get("user").has_permission(scope, "update"):
            raise web.HTTPForbidden(reason="User does not have Scope permission.")

        try:
            data = await request.json()

            # track scope changes
            data.update(self.track_scope(request, scope))

            _to_set = {scope: {_id: data}}
        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc))

        try:
            scope_class = self.scope_classes.get(scope)
            scope_class(_id)
        except Exception:
            raise web.HTTPNotFound(reason="This does not exist. To create use POST")

        # Check User permissions on called scope
        # Check User object permissions
        scope_obj = self.scope_classes[scope](name=_id)
        if not scope_obj.has_scope_permission(request.get("user"), "update"):
            raise web.HTTPForbidden(reason="User does not have permission.")

        try:
            MovaiDB().set(_to_set)
        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc))

        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    async def delete_in_scope(self, request: web.Request) -> web.Response:
        """ [DELETE] api add keys to scope
            curl -H 'Content-Type: application/json' -X DELETE \
            -d '{"Node":{"yolo4":{"Persistent":true}}}' \
            http://localhost:5003/api/v1/{scope}/{name}/
        """

        scope = request.match_info["scope"]
        _id = request.match_info["name"]

        # Check User scope permissions
        if not request.get("user").has_permission(scope, "delete"):
            raise web.HTTPForbidden(reason="User does not have permission.")

        try:
            scope_class = self.scope_classes.get(scope)
            scope_obj = scope_class(_id)
        except Exception:
            raise web.HTTPNotFound(reason="Scope does not exist.")

        # Check User object permissions
        if not scope_obj.has_scope_permission(request.get("user"), "delete"):
            raise web.HTTPForbidden(reason="User does not have permission.")

        try:
            data = await request.json()
            if data and not isinstance(data, dict):
                raise web.HTTPBadRequest(reason="Invalid data format. Must be json type.")
        except Exception as exc:
            LOGGER.warning(f"got an exception while parsing data, see error:{exc}")
            data = None

        try:
            if not data:
                force = request.rel_url.query.get("force")
                force = True if force == "" else bool(force)
                # TODO Temporary use force=True (because if Node has dependencies it should return list of those)
                scope_obj.remove(force=True)
                request["scope_delete"] = True  # Info to use on middleware
            else:
                # Info to use on middleware
                request["scope_delete_partial"] = True
                scope_obj.remove_partial(data)

                try:
                    MovaiDB().set({scope: {_id: self.track_scope(request, scope)}})

                except Exception as exc:
                    LOGGER.error(f"Could not update Scope tracking changes. see error:{exc}")

        except Exception as exc:
            raise web.HTTPBadRequest(reason=str(exc))

        return web.json_response({"success": True}, headers={"Server": "Movai-server"})

    async def post_to_scope(self, request: web.Request) -> web.Response:
        """ [POST] api add scope structure, do not send name to create
            curl -H 'Content-Type: application/json' -X POST \
            -d '{"data":{"Persistent":true, "Label":"jajaja"}, "key":"Parameter"}' \
            http://localhost:5003/api/v1/{scope}/{name}/
        """

        obj_created = None  # track if a new object was created
        scope = request.match_info.get("scope")
        _id = request.match_info.get("name", None)

        try:
            data = await request.json()
            if not data.get("data", None):
                raise ValueError("data is required")
        except Exception:
            raise web.HTTPBadRequest(reason="data is required")

        if not _id:
            # Check User permissions
            if not request.get("user").has_permission(scope, "create"):
                raise web.HTTPForbidden(reason="User does not have Scope create permission.")

            label = data["data"].get("Label", None)
            if not label:
                raise web.HTTPBadRequest(reason="Label is required to create new scope")

            try:
                if issubclass(self.scope_classes[scope], pydantic.BaseModel ):
                    scope_obj = self.scope_classes[scope](**{scope: {label: data["data"]}})
                else:
                    scope_class = self.scope_classes.get(scope)
                    struct = scope_class(label, new=True)
                    struct.Label = (
                        label  # just for now, this wont be needed when we merge branch "labeling"
                    )
                    _id = struct.name
                    obj_created = _id
                    scope_obj = scope_class(name=_id)
            except Exception:
                raise web.HTTPBadRequest(reason="This already exists")
        else:
            if issubclass(self.scope_classes[scope], pydantic.BaseModel ):
                # check if exist
                self.scope_classes[scope](_id)
                label = data["data"].get("Label")
                scope_obj = self.scope_classes[scope](**{scope: {label: data["data"]}}) 
            else:
                # Check if scope exists
                try:
                    scope_class = self.scope_classes.get(scope)
                    scope_obj = scope_class(name=_id)
                except Exception:
                    raise web.HTTPNotFound(reason="Scope object not found")

            # Check User permissions on called scope
            if not scope_obj.has_scope_permission(request.get("user"), "update"):
                raise web.HTTPForbidden(reason="User does not have Scope update permission.")


        if issubclass(self.scope_classes[scope], pydantic.BaseModel ):
            scope_obj.__dict__.update(self.track_scope(request, scope))
            scope_obj.save()
            resp = True
        else:
            try:
                # Add/Update Scope data in DB. Optimize set's and delete's

                # Validate 'key' param
                dict_key = "**"
                if data.get("key", None):
                    if not isinstance(data.get("key", None), dict):
                        raise ValueError("Invalid key format. Must be json type.")
                    dict_key = data.get("key")
                    Helpers.replace_dict_values(dict_key, "*", "**")

                # New Scope Data (dict)
                if not dict_key == "**":
                    new_dict = Helpers.update_dict(dict_key, data.get("data", {}))
                else:
                    new_dict = data.get("data", {})

                # track scope changes
                # update LastUpdate
                new_dict.update(self.track_scope(request, scope))

                # Stored Scope Data (dict)
                try:
                    movai_db = MovaiDB()
                    old_dict = movai_db.get({scope: {_id: dict_key}}).get(scope).get(_id)
                except AttributeError:
                    old_dict = {}

                pipe = movai_db.create_pipe()

                deleted = []
                scope_updates = scope_obj.calc_scope_update(old_dict, new_dict)
                for scope_obj in scope_updates:
                    to_delete = scope_obj.get("to_delete")
                    if to_delete:
                        if list(to_delete.keys())[0] == "PortsInst" and scope == "Node":
                            port_name = list(to_delete["PortsInst"].keys())[0]
                            if port_name not in deleted:
                                # in case we are deleting a Port from node, then use the regular delete
                                # in order to delete the exposedPorts from flows
                                Node(_id).delete("PortsInst", port_name)
                                deleted.append(port_name)
                        movai_db.unsafe_delete({scope: {_id: to_delete}}, pipe=pipe)

                    to_set = scope_obj.get("to_set")
                    if to_set:
                        movai_db.set({scope: {_id: to_set}}, pipe=pipe)

                # Execute
                resp = True
                if scope_updates:
                    resp = bool(movai_db.execute_pipe(pipe))

                # Store scope_updates on the request to use in middleware
                request["scope_updates"] = scope_updates

            except Exception as exc:
                # an object was created but there was an error
                # object must be deleted
                if obj_created:
                    movai_db.unsafe_delete({scope: {_id: "*"}})
                raise web.HTTPBadRequest(reason=str(exc))

        return web.json_response({"success": resp, "name": _id}, headers={"Server": "Movai-server"})

    # ---------------------------- GET CALLBACKS BUILTINS FUNCTIONS --------------------------------
    def create_builtin(self, label: str, builtin: Any) -> dict:
        """Util function for get_callback_builtins to create a builtin dictionary
        args:
            label (str): builtin label.
            builtin (Any): builtin data.
         returns:
            dict: dict({label: str, documentation: str, kind: str, methods: List[{label:str, documentation: str}]})
        """
        CLASS_KIND = "class"
        VARIABLE_KIND = "variable"
        FUNCTION_KIND = "function"
        try:
            if builtin is None:
                return {"label": label, "detail": "", "kind": VARIABLE_KIND}
            if (
                isinstance(builtin, str)
                or isinstance(builtin, bool)
                or isinstance(builtin, int)
                or isinstance(builtin, float)
            ):
                return {
                    "label": label,
                    "documentation": f"Constant of value {str(builtin)}",
                    "kind": VARIABLE_KIND,
                }
            if inspect.isclass(builtin):
                return {"label": label, "documentation": builtin.__doc__, "kind": CLASS_KIND}
            if inspect.isfunction(builtin) or inspect.ismethod(builtin):
                return {
                    "label": label,
                    "documentation": builtin.__doc__,
                    "kind": FUNCTION_KIND,
                }
            return {
                "label": label,
                "documentation": builtin.__doc__,
                "kind": VARIABLE_KIND,
                "methods": [
                    {
                        "label": method_name,
                        "documentation": builtin.__getattribute__(method_name).__doc__,
                    }
                    for method_name in dir(builtin)
                    if callable(getattr(builtin, method_name))
                ],
            }
        except Exception as error:
            raise error

    async def get_callback_builtins(self, request: web.Request) -> web.Response:
        """Get callback builtins
        args:
            request (web.Request)
         returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """
        PLACEHOLDER_CB_NAME = "place_holder"
        try:
            # validate permissions
            app_name = request.match_info.get("app_name", None)
            scope_obj = self.scope_classes["Callback"](name=PLACEHOLDER_CB_NAME)
            if not scope_obj.has_permission(request.get("user"), "execute", app_name):
                raise ValueError("User does not have permission")

            callback = GD_Callback(PLACEHOLDER_CB_NAME, "", "")
            callback.execute({})
            builtins = callback.user.globals
            output = {key: self.create_builtin(key, builtins[key]) for key in builtins}
        except Exception as error:
            raise web.HTTPBadRequest(reason=str(error), headers={"Server": "Movai-server"})

        return web.json_response(output, headers={"Server": "Movai-server"})

    @staticmethod
    def json_serializer_converter(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    @staticmethod
    async def fetch(url, session, headers=None):
        headers = headers if headers is not None else dict()
        async with session.get(url, headers=headers) as response:
            response = await response.json()
            return {"url": url, "response": response}

    def track_scope(self, request: web.Request, scope: str) -> dict:
        """returns an object with tracking info

        args:
            - request (web.Request)

        returns:
            - obj (dict)
        """

        obj = {}
        if scope in SCOPES_TO_TRACK:
            _date = datetime.now().strftime("%d/%m/%Y at %H:%M:%S")
            obj.update({"LastUpdate": {"date": _date, "user": request["user"].ref}})

        return obj
