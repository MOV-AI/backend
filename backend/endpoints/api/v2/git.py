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
    VersionDoesNotExist, RepositoryDoesNotExist, NoChangesToCommit, FileDoesNotExist
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
    if "version" not in request.rel_url.query:
        return {"error": "version must be specified in QUERY param 'version'"}
    version = request.rel_url.query["version"]
    path = request.rel_url.query["path"]

    return {"success": [scope, version, path]}


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

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    workspace = scopes(workspace="git")
    try:
        data = await loop.run_in_executor(
            executor, functools.partial(workspace.read, scope=scope, ref=path, version=version)
        )
    except VersionDoesNotExist:
        err = web.HTTPNotFound(reason=f"version '{version}' does not exist in {scope}")
        err.message = f"version {version} does not exist in {scope}"
        return err
    except RepositoryDoesNotExist:
        err = web.HTTPNotFound(reason=f"Repository {scope} does not exist")
        err.message = f"Repository {scope} does not exist"
        return err

    return web.json_response(data, headers={"Server": "Movai-server"})


async def delete_document(request: web.Request):
    """
    """
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err 
    scope, version, path = ret["success"]
    _check_user_permission(request, scope, "delete")

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    workspace = scopes(workspace="git")
    try:
        commit_sha = await loop.run_in_executor(executor,
                                            functools.partial(workspace.delete,
                                                              {},
                                                              scope=scope,
                                                              ref=path,
                                                              version=version)
                                            )
    except FileDoesNotExist:
        return web.json_response(f"File {path} Does Not Exist", headers={"Server": "Movai-server"})
    return web.json_response(commit_sha, headers={"Server": "Movai-server"})


async def create_or_update_document(request: web.Request):
    """
    """
    ret = _parse_request_params(request)
    if "error" in ret:
        err = web.HTTPBadRequest(reason=ret["error"])
        err.message = ret["error"]
        return err 
    scope, version, path = ret["success"]
    body = await request.json()
    _check_user_permission(request, scope, "create")

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    workspace = scopes(workspace="git")
    try:
        commit_sha = await loop.run_in_executor(executor,
                                                functools.partial(workspace.write,
                                                                body["data"],
                                                                scope=scope,
                                                                ref=path,
                                                                version=version)
                                                )
    except NoChangesToCommit:
        return web.json_response("No Changes to commit, same file", headers={"Server": "Movai-server"})

    return web.json_response(commit_sha, headers={"Server": "Movai-server"})


async def pull_update_project(request: web.Request):
    """
    """
    scope = _parse_request_scope(request)
    branch = parse.unquote(request.match_info["branch"])

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    workspace = scopes(workspace="git")
    fetch_info = await loop.run_in_executor(executor,
                                            functools.partial(workspace.pull,
                                                              scope=scope,
                                                              branch=branch)
                                            )
    return web.json_response(fetch_info, headers={"Server": "Movai-server"})


async def list_project_versions(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    versions = workspace.list_versions(scope=scope, ref="tags")
    versions = [str(t) for t in versions]

    return web.json_response({"remote": scope, "versions": versions}, headers={"Server": "Movai-server"})


async def list_project_branches(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    branches = workspace.list_versions(scope=scope, ref="branches")

    return web.json_response({"remote": scope, "branches": branches}, headers={"Server": "Movai-server"})


async def list_models(request: web.Request):
    scope = _parse_request_scope(request)

    workspace = scopes(workspace="git")
    models: dict = workspace.list_scopes(scope=scope)

    return web.json_response({"remote": scope, "models": models}, headers={"Server": "Movai-server"})


class GitAPI(BaseWebApp):
    """Web application for serving as the database api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the database api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.put(r"/{remote}/{user}/{project}/pull/{branch}", pull_update_project),
            web.get(r"/{remote}/{user}/{project}/versions", list_project_versions),
            web.get(r"/{remote}/{user}/{project}/branches", list_project_branches),
            web.get(r"/{remote}/{user}/{project}/models", list_models),
            web.get(r"/{remote}/{user}/{project}", get_document),
            web.delete(r"/{remote}/{user}/{project}", delete_document),
            web.put(r"/{remote}/{user}/{project}", create_or_update_document),

        ]


WebAppManager.register("/api/v2/git", GitAPI)
