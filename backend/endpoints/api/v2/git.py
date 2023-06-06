"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Moawiya Mograbi (moawiya@mov.ai) - 2022

   This module implements RestAPI endpoints to access the new
   GIT database layer
"""
import functools
import asyncio
from typing import List, Tuple
from aiohttp import web, web_request
from urllib import parse
from dal.models.scopestree import scopes
from backend.http import WebAppManager
from .base import BaseWebApp
from dal.exceptions import (
    VersionDoesNotExist,
    RepositoryDoesNotExist,
    NoChangesToCommit,
    FileDoesNotExist,
    GitPermissionErr,
    TagAlreadyExist,
)


def _check_user_permission(request: web_request, scope: str, permission_name: str):
    """
    A function to check user permissions
        raising HTTPForbidden if user has no permission
    """
    user = request["user"]
    if not user.has_permission(scope, permission_name):
        raise web.HTTPForbidden(reason="User does not have permission.")


def _parse_request_scope(request: web.Request) -> str:
    remote = parse.unquote(request.match_info["remote"])
    user = parse.unquote(request.match_info["user"])
    project = parse.unquote(request.match_info["project"])

    return f"{remote}:{user}/{project}"


def _parse_request_params(request: web.Request) -> Tuple:
    """
    Parse a request

    Return: GIT SSH Link, version, path
    """
    scope = _parse_request_scope(request)
    if "path" not in request.rel_url.query:
        return {"error": "file path must be specified in QUERY param 'path'"}
    path = request.rel_url.query["path"]
    version = parse.unquote(request.match_info["version"])

    return {"success": [scope, version, path]}


async def root(request: web.Request):
    return web.json_response("GIT functionality root", headers={"Server": "Movai-server"})


async def get_document(request: web.Request):
    """
    Get a specific version of a document
    Endpoint: /api/v2/git/<user>/<project>/<version>/<path>
    Method: Get
    Return list of all versions available of a document:
    Returns the data
    {
        "workspace" : "workspace id",
        "scope" : "<scope_id">
        "ref" : "<ref">
        "versions" : [ { "tag": "<version_tag>", "date" : "<version_date" } ]
    }
    """
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err
    scope, version, path = ret["success"]
    _check_user_permission(request, scope, "read")

    workspace = scopes(workspace="git")

    ret = await execute_check_exception(
        request, workspace.read, scope=scope, ref=path, version=version
    )
    if isinstance(ret, web.HTTPClientError):
        return ret

    data = ret
    return web.json_response(data, headers={"Server": "Movai-server"})


async def delete_document(request: web.Request):
    """ """
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err
    scope, version, path = ret["success"]
    _check_user_permission(request, scope, "delete")

    workspace = scopes(workspace="git")

    ret = await execute_check_exception(
        request, workspace.delete, {}, scope=scope, ref=path, version=version
    )
    if isinstance(ret, web.HTTPClientError):
        return ret

    commit_sha = ret
    return web.json_response(commit_sha, headers={"Server": "Movai-server"})


async def create_or_update_document(request: web.Request):
    """ """
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err
    scope, version, path = ret["success"]
    body = await request.json()
    _check_user_permission(request, scope, "create")

    workspace = scopes(workspace="git")
    try:
        ret = await execute_check_exception(
            request, workspace.write, body["data"], scope=scope, ref=path, version=version
        )
    except NoChangesToCommit:
        return web.json_response(
            "No Changes to commit, same file", headers={"Server": "Movai-server"}
        )

    if isinstance(ret, web.HTTPClientError):
        return ret

    commit_sha = ret
    return web.json_response(commit_sha, headers={"Server": "Movai-server"})


async def pull_update_project(request: web.Request):
    """ """
    scope = _parse_request_scope(request)
    version = parse.unquote(request.match_info["version"])
    workspace = scopes(workspace="git")

    ret = await execute_check_exception(request, workspace.pull, scope=scope, branch=version)
    if isinstance(ret, web.HTTPClientError):
        return ret

    fetch_info = ret
    return web.json_response(fetch_info, headers={"Server": "Movai-server"})


async def execute_check_exception(request, func, *args, **kwargs):
    try:
        scope = _parse_request_scope(request)
        loop = asyncio.get_event_loop()

        ret = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    except GitPermissionErr:
        err = web.HTTPForbidden(reason="Git Server Permission Error, check permissions")
        err.message = "Git Server Permission Error, check permissions"
        return err
    except VersionDoesNotExist:
        version = parse.unquote(request.match_info["version"])
        err = web.HTTPNotFound(reason=f"version '{version}' does not exist in {scope}")
        err.message = f"version {version} does not exist in {scope}"
        return err
    except RepositoryDoesNotExist:
        err = web.HTTPNotFound(reason=f"Repository {scope} does not exist")
        err.message = f"Repository {scope} does not exist"
        return err
    except FileDoesNotExist as e:
        if e.args[0].find("id_rsa") != -1:
            err = web.HTTPForbidden(
                reason="No SSH Key was found on Robot for authentication purpose"
            )
            err.message = "No SSH Key was found on Robot for authentication purpose"
        else:
            err = web.HTTPNotFound(reason=e.args[0])
            err.message = e.args[0]
        return err
    except TagAlreadyExist:
        err = web.HTTPConflict(reason=f"requested version already exist in {scope}")
        err.message = f"requested version already exist in {scope}"
        return err

    return ret


async def list_project_versions(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    ret = await execute_check_exception(request, workspace.list_versions, scope=scope, ref="tags")
    if isinstance(ret, web.HTTPClientError):
        return ret

    versions = [str(t) for t in ret]
    return web.json_response(
        {"remote": scope, "versions": versions}, headers={"Server": "Movai-server"}
    )


async def list_project_branches(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    ret = await execute_check_exception(
        request, workspace.list_versions, scope=scope, ref="branches"
    )
    if isinstance(ret, web.HTTPClientError):
        return ret

    branches = ret
    return web.json_response(
        {"remote": scope, "branches": branches}, headers={"Server": "Movai-server"}
    )


async def list_models(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    ret = await execute_check_exception(request, workspace.list_scopes, scope=scope)
    if isinstance(ret, web.HTTPClientError):
        return ret

    models = ret
    return web.json_response(
        {"remote": scope, "models": models}, headers={"Server": "Movai-server"}
    )


async def create_tag(request: web.Request):
    scope = _parse_request_scope(request)
    tag = parse.unquote(request.match_info["tag"])
    base_version = parse.unquote(request.match_info["base_version"])
    body = await request.json()
    message = f"creating version {tag}"
    if "message" in body:
        message = body["message"]

    workspace = scopes(workspace="git")

    ret = await execute_check_exception(
        request,
        workspace.create_version,
        tag,
        scope=scope,
        base_version=base_version,
        message=message,
    )
    if isinstance(ret, web.HTTPClientError):
        return ret

    return web.json_response(ret, headers={"Server": "Movai-server"})


async def undo_document(request: web.Request):
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err
    scope, version, path = ret["success"]
    _check_user_permission(request, scope, "read")

    workspace = scopes(workspace="git")
    prev_version = workspace.prev_version(scope=scope, version=version)

    ret = await execute_check_exception(
        request, workspace.read, scope=scope, ref=path, version=prev_version
    )
    if isinstance(ret, web.HTTPClientError):
        return ret

    data = ret
    return web.json_response(data, headers={"Server": "Movai-server"})


async def publish(request: web.Request):
    scope = _parse_request_scope(request)
    branch = parse.unquote(request.match_info["branch"])
    workspace = scopes(workspace="git")

    if workspace.push(scope, branch):
        ret = "Success"
    else:
        ret = "Fail"

    return web.json_response(ret, headers={"Server": "Movai-server"})


class GitAPI(BaseWebApp):
    """Web application for serving as the database api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the database api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/", root),
            # path is in the body
            web.put(r"/{remote}/{user}/{project}/{version}/pull", pull_update_project),
            web.get(r"/{remote}/{user}/{project}/versions", list_project_versions),
            web.get(r"/{remote}/{user}/{project}/branches", list_project_branches),
            web.get(r"/{remote}/{user}/{project}/models", list_models),
            web.post(r"/{remote}/{user}/{project}/version/{base_version}/{tag}", create_tag),
            web.post(r"/{remote}/{user}/{project}/{branch}/publish", publish),
            web.post(r"/{remote}/{user}/{project}/{version}/undo", undo_document),
            web.get(r"/{remote}/{user}/{project}/{version}", get_document),
            web.delete(r"/{remote}/{user}/{project}/{version}", delete_document),
            web.put(r"/{remote}/{user}/{project}/{version}", create_or_update_document),
        ]


WebAppManager.register("/api/v2/git", GitAPI)
