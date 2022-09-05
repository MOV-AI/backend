"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Paulino (tiago@mov.ai) - 2020

    Maintainers:
    - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Rest API
"""
import asyncio
import json
import re
import requests
import jwt
import yaml
import bleach
import inspect
from datetime import datetime, date
from mimetypes import guess_type
from string import Template
from typing import Any, List, Union
from aiohttp import web
from dal.scopes import Callback, Configuration

try:
    from movai_core_enterprise.models import (
        SharedDataEntry,
        SharedDataTemplate,
        TaskEntry,
        TaskTemplate,
        GraphicScene,
        Annotation,
        Layout,
    )

    enterprise_scope = {
        "SharedDataTemplate": SharedDataTemplate,
        "SharedDataEntry": SharedDataEntry,
        "TaskTemplate": TaskTemplate,
        "TaskEntry": TaskEntry,
        "GraphicScene": GraphicScene,
        "Annotation": Annotation,
        "Layout": Layout,
    }
except ImportError:
    enterprise_scope = {}

from dal.scopes import Flow
from dal.movaidb import MovaiDB
from dal.helpers import Helpers
from gd_node.statemachine import StateMachine
from .models.user import User
from dal.models import Var
from .models.role import Role
from dal.models import ACLManager
from gd_node.callback import GD_Callback
from movai_core_shared.envvars import SCOPES_TO_TRACK
from gd_node.metrics import Metrics
from dal.scopes import Robot, Package, Node, Form
from urllib.parse import unquote
from movai_core_shared import Log
from backend.endpoints.api.v1.models.application import Application

LOGGER = Log.get_logger("RestAPI")
PAGE_SIZE = 100


class JWTMiddleware:
    """JWT authentication middleware"""

    def __init__(self, secret: str, safelist: List[str] = None):
        """Initialize middleware
        secret -> the JWT secret
        safelist -> an initial pattern list
        """
        self._secret = secret
        self._safelist = []
        if safelist is not None:
            self._safelist.extend(safelist)

    def add_safe(self, paths: Union[str, List[str]], prefix: str = None) -> None:
        """Add paths to bypass auth list"""

        if isinstance(paths, str):
            paths = [paths]

        if prefix is None:
            prefix = ""

        prefix = prefix.rstrip("/")

        self._safelist.extend([prefix + path for path in paths])

    def _is_safe(self, request: web.Request) -> bool:
        q_string = request.query_string
        xss_check_dict = urllib.parse.parse_qs(q_string)
        for key, value in request.query.items():
            if key in xss_check_dict and value == bleach.clean(xss_check_dict[key][0]):
                xss_check_dict.pop(key)
            else:
                return False
        if q_string.encode("ascii", "ignore").decode() != q_string or len(xss_check_dict) > 0:
            # contains non-ascii chars
            return False
        decoded_params = urllib.parse.unquote(q_string)
        if '<script>' in decoded_params:
            raise requests.exceptions.InvalidHeader('Risky URL params passed')
        if request.method == "OPTIONS":
            return True

        for pattern in self._safelist:
            if re.match(pattern, request.path) is not None:
                return True

        # else
        return False

    @web.middleware
    async def middleware(self, request, handler):
        """the actual middleware JWT authentication verify"""

        safe = self._is_safe(request)

        token = None
        try:
            if "token" in request.query:
                token = request.query["token"]
            elif "Authorization" in request.headers:
                _, token = request.headers["Authorization"].strip().split(" ")
        except ValueError:
            if not safe:
                raise web.HTTPForbidden(reason="Invalid authorization header")

        if token is None and not safe:
            raise web.HTTPUnauthorized(reason="Missing authorization token")

        token_data = None
        try:
            token_data = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as exc:
            if not safe:
                raise web.HTTPForbidden(
                    reason="Invalid authorization token, {}".format(str(exc))
                )

        if token_data:
            try:
                user = User(token_data["username"])
                request["user"] = user
            except Exception as e:
                LOGGER.error(
                    f"caught exception while getting user object, \
                             exception: {e}"
                )
                raise web.HTTPForbidden(reason="Invalid user.")

        return await handler(request)


@web.middleware
async def save_node_type(request, handler):
    """Saves the node type when a node is changed"""
    response = await handler(request)

    if request.method in ("POST", "PUT"):
        scope = request.match_info.get("scope")
        if scope == "Node":
            id_ = request.match_info.get("name")
            if id_:
                Node(id_).set_type()
            else:
                data = await request.json()
                label = data["data"].get("Label")
                # change to Node(label=label).set_type()
                Node(label).set_type()

    return response


@web.middleware
async def remove_flow_exposed_port_links(request, handler):
    """Search end remove ExposedPort links"""

    scope = request.match_info.get("scope")

    if not scope == "Flow":
        # Wait for the request to resolve
        response = await handler(request)
    else:
        flow_obj = None
        old_flow_exposed_ports = {}

        if request.match_info.get("name"):
            try:
                flow_obj = Flow(name=request.match_info.get("name"))
                old_flow_exposed_ports = {**flow_obj.ExposedPorts}
            except Exception as e:
                LOGGER.warning(
                    f"caught exception while getting Flow \
                               {request.match_info.get('name')}, \
                               exception: {e}"
                )
                pass

        # Wait for the request to resolve
        response = await handler(request)

        if request.method in ("POST", "PUT", "DELETE"):
            if flow_obj:
                # Check if ExposedPort was deleted
                deleted_exposed_ports = Flow.exposed_ports_diff(
                    old_flow_exposed_ports, flow_obj.ExposedPorts
                )

                LOGGER.info(f"Deleted exposed ports result: {deleted_exposed_ports}")

                # Loop trough all deleted ports and delete Links associated to that exposed port
                for node in deleted_exposed_ports:
                    for deleted_exposed_port in node.values():
                        node_inst_name = next(iter(deleted_exposed_port))
                        for port in deleted_exposed_port[node_inst_name]:
                            port_name = re.search(r"^.+/", port)[0][:-1]
                            flow_obj.delete_exposed_port_links(
                                node_inst_name, port_name
                            )

            if request.get("scope_delete"):
                # Flow was deleted
                await asyncio.get_event_loop().run_in_executor(
                    None, Flow.on_flow_delete, request.match_info.get("name")
                )

    return response


@web.middleware
async def redirect_not_found(request, handler):
    try:
        response = await handler(request)
        if response.status != 404:
            return response
        message = response.message
        return web.json_response({"error": message})
    except web.HTTPException:
        raise


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
            "Callback": Callback,
            "Flow": Flow,
            "Form": Form,
            "Node": Node,
            "Package": Package,
            "StateMachine": StateMachine,
            "User": User,
            "Configuration": Configuration,
            "Role": Role,
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
            scope_obj = self.scope_classes["Callback"](name=callback_name)
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
            )
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

    async def get_logs(self, request) -> web.Response:
        """Get logs from HealthNode using get_logs in Logger class
        path:
            /logs/

        parameters:
            level
            offset
            message
            limit
            tags
            services
        """

        params = RestAPI.fetch_logs_url_params(request)

        # empty list, request should be sent to health-node directly
        try:
            status = 200
            output = Log.get_logs(pagination=True, **params)
        except Exception as e:
            status = 401
            output = {"error": str(e)}

        return web.json_response(output, status=status)

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
            "message": message,
            "services": services,
            "from_": log_start_time,
            "to_": log_end_time,
        }

    async def get_robot_logs(self, request) -> web.Response:
        """Get logs from specific robot using the robot name
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
        robot_name = request.match_info["robot_name"]
        db = MovaiDB("global")
        robot_id = None
        for key, val in db.search_by_args(scope="Robot")[0]["Robot"].items():
            if "RobotName" in val and val["RobotName"] == robot_name:
                robot_id = key
                break
        if robot_id is None:
            LOGGER.error(f"robot {robot_name} not found in DB")
            response = web.json_response(
                {"error": f"robot {robot_name} not found"}, status=404
            )
            response.message = f"robot {robot_name} not found in system"
            return response
        ip_key = {"Robot": {robot_id: {"IP": {}}}}
        ip = db.get_value(ip_key)

        if Robot().fleet.IP == ip:
            # we are already inside our robot, no need for new request.
            response = await self.get_logs(request)
            return response

        url = f"https://{ip}/api/v1/logs/?"
        params = RestAPI.fetch_logs_url_params(request)
        # we do not send robot id as param so we can call
        # health-node next
        status = 200
        try:
            response = requests.get(
                url, params=params, headers=request.headers, timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            LOGGER.warning(f"fetching logs for robot {robot_name} failed")
            status = 401
            output = {"error": str(e)}
        else:
            try:
                output = json.loads(response.text)
            except json.JSONDecodeError as e:
                output = {"error": f"error decoding response {e}"}

        return web.json_response(output, status=status)

    async def get_permissions(self, request):
        try:
            output = ACLManager.get_permissions()
            return web.json_response(output, status=200)
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

    async def get_metrics(self, request):
        """Get metrics from HealthNode"""

        name = request.rel_url.query.get("name")
        limit = request.rel_url.query.get("limit", 1000)
        offset = request.rel_url.query.get("offset", 0)
        tags = request.rel_url.query.get("tags")

        # Fetch all responses within one Client session,
        # keep connection alive for all requests.
        try:
            status = 200
            metrics = Metrics()
            output = metrics.get_metrics(
                name=name,
                limit=limit,
                offset=offset,
                tags=tags.split(",") if tags else [],
                pagination=True,
            )
        except Exception as e:
            status = 401
            output = {"error": str(e)}

        return web.json_response(output, status=status)

    async def get_spa(self, request):
        """get spa code and inject server params"""

        app_name = request.match_info["app_name"]
        content_type = "text/html"

        try:
            app = Application(app_name)
            content_type = guess_type(app.EntryPoint)[0]
            html = Package(app.Package).File[app.EntryPoint].Value
            html = self.spa_parse_template(app, html, request)

        except Exception as error:
            html = f"<div style='top:40%;left:35%;position:absolute'><p>Error while trying to serve {app_name}</p><p style='color:red'>{error}</p></div>"

        return web.Response(body=html, content_type=content_type)

    def spa_parse_template(self, application, html, request):
        """parse application params"""

        serverdata = {"pathname": f"{self.api_version}apps/{application.name}/"}
        try:
            # get app configuration
            serverdata.update(self.get_spa_configuration(application))
            # get  application meta-data
            serverdata.update(
                {"Application": application.get_dict()["Application"][application.name]}
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

    def get_spa_configuration(self, application):
        """get default configuration and updated it with user custom configuration"""
        output = {}

        configs = [application.Configuration, application.CustomConfiguration]
        for cfg_name in configs:
            try:
                obj = Configuration(cfg_name)
                _json = dict(yaml.safe_load(obj.Yaml) or {})
                output.update(_json)
            except Exception as error:
                LOGGER.info(str(error))

        return output

    # ---------------------------- GET SET TO VARS -----------------------------

    async def post_reset_password(self, request: web.Request) -> web.Response:
        """Reset user password : Only possible if superuser

        args:
            request (web.Request)

        request payload:
            - required:
                * new_password (str): the new password
                * confirm_password (str): the confirm password

         returns:
            web.json_response({'success': True}) or
            web.HTTPBadRequest(reason)
        """

        try:
            username = request.match_info["name"]

            data = await request.json()

            is_superuser = request.get("user").Superuser is True

            if not is_superuser:
                raise ValueError(
                    "Not Authorized: Only superuser allowed to reset-password"
                )

            User.reset(
                username=username,
                new_pass=data.get("new_password"),
                confirm_pass=data.get("confirm_password"),
                current_pass=False,
                validate_current_pass=False,
            )

        except Exception as error:
            raise web.HTTPBadRequest(reason=str(error))

        return web.json_response({"success": True})

    async def post_change_password(self, request: web.Request) -> web.Response:
        """Change user password

        args:
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
            raise web.HTTPBadRequest(reason=str(error))

        return web.json_response({"success": True})

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
            output["value"] = value
            return web.json_response(output)
        raise web.HTTPBadRequest(reason="Required keys (scope, key) not found.")

    async def set_key_value(self, request: web.Request) -> web.Response:
        """[POST] api set key value handler
        curl -d "scope=fleet&key=agv1@qwerty&value=123456" -X POST http://localhost:5003/api/v1/database/
        """
        data = await request.json()
        key = data.get("key", None)  # fleet: robot_name@key_name
        value = data.get("value", None)
        scope = data.get("scope", None)
        if all([key, value, scope]):
            if scope == "fleet":
                try:
                    _robot_name, key = key.split("@")
                    var_scope = Var(scope=scope, _robot_name=_robot_name)
                except Exception as error:
                    raise web.HTTPBadRequest(reason=str(error))
            else:
                var_scope = Var(scope=scope)
            setattr(var_scope, key, value)
            return web.json_response({"key": key, "value": value, "scope": scope})
        raise web.HTTPBadRequest(reason="Required keys (scope, key, value) not found.")

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
            output = Package(package_name).File[package_file].Value
            return web.Response(body=output, content_type=content_type)
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

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
            package.add(
                "File", f"{package_file}", Value=bytes(data), FileLabel=package_file
            )
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})
        return web.json_response({"success": True})

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
            except Exception:
                raise web.HTTPNotFound(reason="Required scope not found.")

            # Check User permissions
            if not scope_obj.has_scope_permission(request.get("user"), "read"):
                raise web.HTTPForbidden(reason="User does not have Scope permission.")

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

            scope_result = MovaiDB().get_by_args(scope)
            result = scope_result.get(scope, {})

        if not result:
            raise web.HTTPNotFound(reason="Required scope not found.")

        try:
            json_result = json.dumps(result, default=self.json_serializer_converter)
            validated_result = json.loads(json_result)
        except Exception as e:
            LOGGER.error(f"caught error while creating json, exception: {e}")
            raise web.HTTPBadRequest(reason="Error when serializing JSON response.")

        return web.json_response(validated_result)

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
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

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
        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

        return web.json_response({"success": True})

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
                raise web.HTTPBadRequest(
                    reason="Invalid data format. Must be json type."
                )
        except Exception as e:
            LOGGER.warning(f"got an exception while parsing data, see error:{e}")
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

                except Exception as e:
                    LOGGER.error(
                        f"Could not update Scope tracking changes. see error:{e}"
                    )

        except Exception as e:
            raise web.HTTPBadRequest(reason=str(e))

        return web.json_response({"success": True})

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
                raise web.HTTPForbidden(
                    reason="User does not have Scope create permission."
                )

            if not data["data"].get("Label", None):
                raise web.HTTPBadRequest(reason="Label is required to create new scope")

            try:
                label = data["data"].get("Label")
                scope_class = self.scope_classes.get(scope)
                struct = scope_class(label, new=True)
                struct.Label = label  # just for now, this wont be needed when we merge branch "labeling"
                _id = struct.name
                obj_created = _id

                scope_obj = scope_class(name=_id)
            except Exception:
                raise web.HTTPBadRequest(reason="This already exists")
        else:
            # Check if scope exists
            try:
                scope_class = self.scope_classes.get(scope)
                scope_obj = scope_class(name=_id)
            except Exception:
                raise web.HTTPNotFound(reason="Scope object not found")

            # Check User permissions on called scope
            if not scope_obj.has_scope_permission(request.get("user"), "update"):
                raise web.HTTPForbidden(
                    reason="User does not have Scope update permission."
                )

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
            new_dict.update(self.track_scope(request, scope))

            # Stored Scope Data (dict)
            try:
                movai_db = MovaiDB()
                old_dict = movai_db.get({scope: {_id: dict_key}}).get(scope).get(_id)
            except AttributeError:
                old_dict = {}

            pipe = movai_db.create_pipe()

            scope_updates = scope_obj.calc_scope_update(old_dict, new_dict)
            for scope_obj in scope_updates:
                to_delete = scope_obj.get("to_delete")
                if to_delete:
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

        except Exception as e:
            # an object was created but there was an error
            # object must be deleted
            if obj_created:
                movai_db.unsafe_delete({scope: {_id: "*"}})
            raise web.HTTPBadRequest(reason=str(e))

        return web.json_response({"success": resp, "name": _id})

    async def new_user(self, request: web.Request) -> web.Response:
        """Create new user

        args:
            equest (web.Request)

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
            raise web.HTTPBadRequest(reason=msg)

        except Exception as error:
            LOGGER.error(f"{type(error).__name__}: {error}")
            raise web.HTTPBadRequest(reason=str(error))

        return web.json_response({"success": True})
    
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
            app_name = request.match_info.get('app_name', None)
            scope_obj = self.scope_classes['Callback'](name=PLACEHOLDER_CB_NAME)
            if not scope_obj.has_permission(request.get('user'), 'execute', app_name):
                raise ValueError("User does not have permission")

            callback = GD_Callback(PLACEHOLDER_CB_NAME, "", "")
            callback.execute({})
            builtins = callback.user.globals
            output = {key: self.create_builtin(key, builtins[key]) for key in builtins}
        except Exception as error:
            raise web.HTTPBadRequest(
                reason=str(error), headers={"Server": "Movai-server"}
            )

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
            obj.update({"LastUpdate": {"date": _date, "user": request["user"].Label}})

        return obj
