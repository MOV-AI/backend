"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Alexandre Pires (alexandre.pires@mov.ai) - 2020

   This module implements RestAPI endpoints to access the new
   database layer
"""

import asyncio
import os
import tempfile
import urllib.parse
from datetime import datetime
from typing import List, Tuple

import aiohttp_cors
from aiohttp import web, web_request
from aiohttp.web_exceptions import HTTPForbidden

from backend.http import IWebApp, WebAppManager
# import from DAL
from movai.backup import BackupManager, RestoreManager
# import from DAL
from movai.data import WorkspaceManager, scopes
# import from DAL
from movai.models import Model
from endpoints.api.v2.models.user import User


async def get_document_versions(request: web.Request):
    """
    Get a specific version of a document
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>/<ref>
    Method: Get
    Return list of all versions available of a document:
    {
        "workspace" : "workspace id",
        "scope" : "<scope_id">
        "ref" : "<ref">
        "versions" : [ { "tag": "<version_tag>", "date" : "<version_date" } ]
    }
    """
    workspace = urllib.parse.unquote(request.match_info["workspace"])
    scope = urllib.parse.unquote(request.match_info["scope"])
    ref = urllib.parse.unquote(request.match_info["ref"])
    versions = scopes(workspace=workspace).list_versions(scope, ref)
    _check_user_permission(request, scope, "read")
    return web.json_response({
        "workspace": workspace,
        "scope": scope,
        "ref": ref,
        "versions": versions
    })


async def get_documents(request: web.Request):
    """
    Get all documents in a scope
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>
    Method: Get
    Return list of all documents available:
    {
        "workspace" : "workspace id",
        "scope" : "<scope_id">
        "scopes" : [ list of all scopes ]
    }
    """
    workspace = urllib.parse.unquote(request.match_info["workspace"])
    scope = urllib.parse.unquote(request.match_info["scope"])
    data = scopes(workspace=workspace).list_scopes(scope=scope)
    _check_user_permission(request, scope, "read")
    return web.json_response({
        "workspace": workspace,
        "scope": scope,
        "scopes": data
    })


async def get_all_documents(request: web.Request):
    """
    Get all documents available in a workspace
    Endpoint: /api/v2/db/<workspace_id>
    Method: Get
    Return list of all documents available:
    {
        "workspace" : "workspace id",
        "scopes" : [ list of all scopes ]
    }
    """
    workspace = urllib.parse.unquote(request.match_info["workspace"])
    data = scopes(workspace=workspace).list_scopes()
    readable_data = _get_multiple_docs_for_user(request, data, "read")

    return web.json_response({
        "workspace": workspace,
        "scopes": readable_data
    })


async def delete_workspace(request: web.Request):
    """
    Delete a workspace
    Endpoint: /api/v2/db
    Method: delete
    Return 200 if ok, 400 Error creating workspace
    """
    # TODO: decide what permissions needed for it, and implement (Nobody should ever delete workspace)

    workspace = urllib.parse.unquote(request.match_info["workspace"])
    try:
        WorkspaceManager.delete_workspace(workspace)
        return web.json_response({})
    except ValueError as e:
        raise web.HTTPBadRequest(reason="error deleting workspace") from e


async def create_workspace(request: web.Request):
    """
    Create a new workspace
    Endpoint: /api/v2/db
    Method: Post
    Return 200 if ok, 400 error creating workspace
    """
    # TODO: decide what permissions needed for it, and implement

    workspace = urllib.parse.unquote(request.match_info["workspace"])
    try:
        WorkspaceManager.create_workspace(workspace)
        return web.json_response({})
    except ValueError as e:
        raise web.HTTPBadRequest(reason="error creating workspace") from e


async def get_workspaces(_: web.Request):
    """
    List all available workspaces
    Endpoint: /api/v2/db
    Method: Get
    Return a list of the available workspaces:
    {
        "<workspace id>" : {
            "label" : "<workspace label>"
            "url" : "<workspace url"
        }
    }
    """
    # TODO: decide what permissions needed for it, and implement

    workspaces = WorkspaceManager.list_workspaces()

    result = {}
    for workspace in workspaces:
        result[workspace] = WorkspaceManager.workspace_info(workspace)

    return web.json_response(result)


async def create_document(request: web.Request):
    """
    Save a version of a document
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>/<ref>
    Method: Post
    Return 200 - ok, 400 error creating
    Body:
    {
        "data" | "src" : "<document data>" | "<document data source>"
    }
    """
    workspace, scope, ref, version = _check_user_permission_and_parse_request(request, "create")
    body = await request.json()

    try:
        data = body["data"]

        scopes(workspace=workspace).write(
            data, scope=scope, ref=ref, version=version)

        return web.json_response({})

    except KeyError:
        pass
    except ValueError as e:
        raise web.HTTPConflict(
            reason=str(e))

    try:
        data = scopes.read_from_path(body["src"])

        if not data:
            raise web.HTTPBadRequest(
                reason="Source scope not found")

        scopes(workspace=workspace).write(
            # for redis workspace, remove_extra deletes excessive keys there
            data, scope=scope, ref=ref, version=version, remove_extra=True)

        return web.json_response({})

    except KeyError as e:
        raise web.HTTPBadRequest(
            reason="wrong data or src") from e
    except ValueError as e:
        raise web.HTTPConflict(
            reason=str(e))


async def _update_doc_ver(request: web.Request):
    """
    internal function to update or patch document version
    """
    workspace, scope, ref, version = _check_user_permission_and_parse_request(request, "update")
    data = await request.json()

    date = datetime.now().strftime("%d/%m/%Y at %H:%M:%S")
    data["LastUpdate"] = {"date": date, "user": request["user"].Label}
    scopes(workspace=workspace).write(
        data, scope=scope, ref=ref, version=version)
    return workspace, scope, ref, version


async def update_document_version(request: web.Request) -> web.json_response:
    """
    Update a document version
    """
    await _update_doc_ver(request)
    return web.json_response({"success": True, "error": None})


async def patch_document_version(request: web.Request):
    """
    Update a part of a document version
    """
    workspace, scope, ref, version = await _update_doc_ver(request)

    return web.json_response({
        "workspace": workspace,
        "scope": scope,
        "ref": ref,
        "version": version,
    })


def _delete_document(request: web.Request, is_specific_version: bool) -> web.json_response:
    """
    Delete entire document or a specific version of it.
    """
    workspace, scope, ref, version = _check_user_permission_and_parse_request(request, "delete")
    ws = None
    try:
        ws = scopes(workspace=workspace)
        if is_specific_version:
            obj = getattr(ws, scope)[ref, version]
        else:
            obj = getattr(ws, scope)[ref]
        ws.delete(obj)
    except KeyError as e:
        # scope not found
        raise web.HTTPNotFound() from e
    except NotImplementedError as e:
        raise web.HTTPNotImplemented() from e
    finally:
        if ws is not None:
            ws.unload(scope=scope, ref=ref)

    return web.json_response({
        "workspace": workspace,
        "scope": scope,
        "ref": ref,
        "version": version
    })


async def delete_document_version(request: web.Request):
    """
    Delete a version of a document
    """

    return _delete_document(request, is_specific_version=True)


async def start_backup_data(request: web.Request) -> web.json_response:
    """
    Start a data backup of a set of data, the user must pass a list of
    objects to be archived
    Endpoint: /backup
    Method: Post
    Parameters:
        - shallow: if true will do a shallow search of dependencies,
                otherwise it will only export direct depedencies ( Default = False )
    Body: {
        metadata : {
            <meta data>
        },
        manifest: [
            <scopes to backup>
        ]
    }
    Return: {
        id : <job_id>
    }
    """
    # TODO: decide what permissions needed for it, and implement

    body = await request.json()

    # by default we do not so a shallow backup
    try:
        shallow_string = request.query["shallow"]
        shallow = shallow_string in ("true", "1")
    except KeyError:
        shallow = False

    try:
        manifest = list(body["manifest"])
    except KeyError as e:
        raise web.HTTPBadRequest(
            reason="manifest is required") from e

    metadata = body.get("metadata", {})
    job_id = BackupManager.create_job(manifest, shallow, metadata)
    state = BackupManager.get_job_state(job_id)

    # Since this operation is blocking we run it on a executor to make sure
    # we do not block the rest API server
    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor, BackupManager.start_job, job_id)

    return web.json_response({
        "id": job_id,
        "state": state
    })


async def get_backup_jobs_list(_: web.Request) -> web.json_response:
    """
    Get a list of backup jobs
    Endpoint: /backup
    Method: Get
    """
    # TODO: decide what permissions needed for it, and implement

    return web.json_response({
        "backup_jobs": list(BackupManager.list_jobs()),
    })


async def start_backup_clean(request: web.Request):
    """
    Force a backup jobs clean up
    Endpoint: /backup/clean
    Method: Post
    """
    # Since this operation is blocking we run it on a executor to make sure
    # we do not block the rest API server
    # TODO: decide what permissions needed for it, and implement

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor, BackupManager.clean_jobs)

    return web.json_response({
        "status": "Backup job cleaning started"
    })


async def get_backup_state(request: web.Request) -> web.json_response:
    """
    Get the state of a backup job
    Endpoint: /backup/<job_id>
    Method: Get
    Return: {
        "id" : <job_id>
        "state" : "started | finished"
    }
    """
    # TODO: decide what permissions needed for it, and implement

    job_id = request.match_info["job_id"]

    if not BackupManager.exists(job_id):
        raise web.HTTPBadRequest(
            reason="Invalid job id")

    state = BackupManager.get_job_state(job_id)
    return web.json_response({
        "id": job_id,
        "state": state
    })


async def get_backup_log(request: web.Request) -> web.json_response:
    """
    Get a backup log
    Endpoint: /backup/<job_id>/log
    Method: Get
    Return: text/plain
    """
    # TODO: decide what permissions needed for it, and implement

    job_id = request.match_info["job_id"]

    if not BackupManager.exists(job_id):
        raise web.HTTPBadRequest(
            reason="Invalid job id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={'Content-Type': 'text/plain'},
    )
    await response.prepare(request)
    await BackupManager.write_log(job_id, response)
    await response.write_eof()
    return response


async def get_backup_archive(request: web.Request) -> web.json_response:
    """
    Get a backup file
    Endpoint: /backup/<job_id>/archive
    Method: Get
    Return: application / gzip
    """
    # TODO: decide what permissions needed for it, and implement

    job_id = request.match_info["job_id"]
    if not BackupManager.exists(job_id):
        raise web.HTTPBadRequest(
            reason="Invalid job id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={'Content-Type': 'application/zip'},
    )
    await response.prepare(request)
    await BackupManager.write_archive(job_id, response)
    await response.write_eof()
    return response


async def start_restore_data(request: web.Request) -> web.json_response:
    """
    Start a data backup of a set of data, the user must pass a list of
    objects to be archived
    Endpoint: /restore
    Method: Post
    Body: application / gzip
    Return: {
        id : <job_id>
    }
    """
    # TODO: decide what permissions needed for it, and implement

    with tempfile.TemporaryDirectory() as temp_folder:
        os.makedirs(temp_folder, exist_ok=True)
        restore_file = os.path.join(str(temp_folder), "restore.zip")

        # Read the content from rh request
        with open(restore_file, 'wb') as restore_fp:
            while True:
                chunk, _ = await request.content.readchunk()
                if not chunk:
                    break
                restore_fp.write(chunk)

        job_id = RestoreManager.create_job(restore_file)
        state = RestoreManager.get_job_state(job_id)

        # Since this operation is blocking we run it on a executor to make sure
        # we do not block the rest API server
        executor = request.app["executor"]
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            executor, RestoreManager.start_job, job_id)

        return web.json_response({
            "id": job_id,
            "state": state
        })


async def get_restore_jobs_list(_: web.Request) -> web.json_response:
    """
    Get a list of restore jobs
    Endpoint: /restore
    Method: Get
    """
    # TODO: decide what permissions needed for it, and implement

    return web.json_response({
        "restore_jobs": list(RestoreManager.list_jobs()),
    })


async def start_restore_clean(request: web.Request) -> web.json_response:
    """
    Force a restore jobs clean up
    Endpoint: /restore/clean
    Method: Post
    """
    # Since this operation is blocking we run it on a executor to make sure
    # we do not block the rest API server
    # TODO: decide what permissions needed for it, and implement

    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor, RestoreManager.clean_jobs)

    return web.json_response({
        "status": "Restore jobs cleaning started"
    })


async def get_restore_state(request: web.Request) -> web.json_response:
    """
    Get the state of a restore job
    Endpoint: /restore/<job_id>
    Method: Get
    Return: {
        "id" : <job_id>
        "state" : "started | finished"
    }
    """
    # TODO: decide what permissions needed for it, and implement

    job_id = await _get_job_id(request)

    state = RestoreManager.get_job_state(job_id)
    return web.json_response({
        "id": job_id,
        "state": state
    })


async def get_restore_log(request: web.Request) -> web.json_response:
    """
    Get a backup log
    Endpoint: /restore/<job_id>/log
    Method: Get
    Return: text/plain
    """
    # TODO: decide what permissions needed for it, and implement
    job_id = await _get_job_id(request)

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={'Content-Type': 'text/plain'},
    )
    await response.prepare(request)
    await RestoreManager.write_log(job_id, response)
    await response.write_eof()
    return response


def _get_job_id(request):
    """
    get job id from request
    """
    job_id = request.match_info["job_id"]
    if not RestoreManager.exists(job_id):
        raise web.HTTPBadRequest(
            reason="Invalid job id")
    return job_id


def _rebuild_indexes(workspace: str):
    """
    Force rebuild indexes on the workspace
    """
    scopes(workspace=workspace).rebuild_indexes()


def _get_relations(workspace: str, scope: str, ref: str,
                   version: str, depth: str, search_filter: list = None,
                   expand: bool = True):
    """
    Get the document relations and then load all documents
    """
    relations = Model.get_relations(
        workspace=workspace, scope=scope, ref=ref, version=version,
        depth=int(depth), search_filter=search_filter)

    # If we just need the names we return the
    # object refs only
    if not expand:
        return list(relations)

    # we load all data from the persistent layer
    objs = {}
    for obj in relations:
        data = scopes.read_from_path(obj)
        for target_scope in data.keys():
            try:
                objs[target_scope].update(data[target_scope])
            except KeyError:
                objs.update(data)

    return objs


def _get_scope(workspace: str, scope: str, ref: str, version: str):
    """
    Get the scope document
    """
    return scopes(workspace=workspace).read(scope=scope, ref=ref, version=version)


def _check_user_permission_and_parse_request(request: web_request, permission_name: str) -> Tuple:
    """
    Parse a request and check user permission 
        raising HTTPForbidden if user has no permission

        Return: workspace, scope, ref, version
    """
    workspace, scope, ref, version = _parse_request(request)
    _check_user_permission(request, scope, permission_name)
    return workspace, scope, ref, version


def _get_user(request: web_request) -> User:
    """
    Get user class from request
    Args:
        request: web_request with the user name

    Returns: User class object

    """
    username = request["user"].Label
    if username is None:
        username = request["user"].name
    return User(username)


def _get_multiple_docs_for_user(request: web_request, data: List, permission_name: str):
    """
    Get all of the docs for a specific user
    Args:
        request: web_request
        data: the list of docs requested
        permission_name: string of the permission usually read

    Returns: a list of the readable data for the specific user

    """
    readable_data = list()
    user = _get_user(request)
    for doc_iterator in data:
        if user.has_permission(doc_iterator["scope"], permission_name):
            readable_data.append(doc_iterator)
    return readable_data


def _check_user_permission(request: web_request, scope: str, permission_name: str):
    """
    A function to check user permissions
        raising HTTPForbidden if user has no permission
    """
    user = _get_user(request)
    if not user.has_permission(scope, permission_name):
        raise web.HTTPForbidden(reason="User does not have permission.")


def _parse_request(request: web.Request) -> Tuple:
    """
        Parse a request

        Return: workspace, scope, ref, version
        """
    workspace = urllib.parse.unquote(request.match_info["workspace"])
    scope = urllib.parse.unquote(request.match_info["scope"])
    ref = urllib.parse.unquote(request.match_info["ref"])
    version = urllib.parse.unquote(request.match_info["version"])
    return workspace, scope, ref, version


async def delete_document(request: web.Request):
    """
    Delete a version of a document
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>/<ref>/<version_tag>
    Method: delete
    Return 200 - ok, 400 error creating
    """
    return _delete_document(request, is_specific_version=False)


async def get_document_version(request: web.Request) -> web.json_response:
    """
    Get a specific version of a document
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>/<ref>/<version_tag>
    Method: Get
    Return: document data
    """
    workspace, scope, ref, version = _check_user_permission_and_parse_request(request, "read")

    # Since this operation may be blocking if we try to is blocking we run it on a executor to make sure
    # we do not block the rest API server
    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, _get_scope, workspace, scope, ref, version)

    return web.json_response(data)


async def get_document_relations(request: web.Request) -> web.json_response:
    """
    Endpoint: /api/v2/db/<workspace_id>/<scope_id>/<ref>/<version_tag>/relations
    Method: Get

    Query Params:
        - depth : how deep we want to search for dependencies, the higher the costly
                  the operation ( default: 0 )
        - search_filter : what kind of scopes we want to be in the response ( default: all )
        - expand : if we want to have the data instead of references, if on the
                   operation will be costly ( default: false )

    Return: document relations, this operation can be costly
    depending on the depth or/and if we expand the results
    """
    # TODO: decide what permissions needed for it, and implement
    workspace, scope, ref, version = _parse_request(request)
    depth = request.query.get("depth", "0")

    # by default we get all the scopes
    try:
        search_string = request.query["search_filter"]
        search_filter = search_string.split(",")
    except KeyError:
        search_filter = None

    # by default we do not expand the objects
    try:
        expand_string = request.query["expand"]
        expand = expand_string in ("true", "1")
    except KeyError:
        expand = False

    # Since this operation is blocking we run it on a executor to make sur
    # we do not block the rest API server
    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    objs = await loop.run_in_executor(
        executor, _get_relations,
        workspace, scope, ref, version, depth, search_filter, expand)

    return web.json_response(objs)


async def rebuild_indexes(request: web.Request):
    """
    Forces a rebuild of indexes on a workspace, this operation
    is expensive should be called with caution
    Endpoint: /<workspace_id>/rebuild_indexes
    Method: Post
    """
    # TODO: decide what permissions needed for it, and implement
    workspace = urllib.parse.unquote(request.match_info["workspace"])

    # Since this operation is blocking we run it on a executor to make sur
    # we do not block the rest API server
    executor = request.app["executor"]
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor, _rebuild_indexes, workspace)

    return {
        "status": "workspace indexes rebuild started"
    }


class DatabaseAPI(IWebApp):
    """ the actual version 1 API """

    @property
    def routes(self) -> List[web.RouteDef]:
        """ list of routes """
        return [
            web.get(r'', get_workspaces),
            web.post(r'/backup', start_backup_data),
            web.get(r'/backup', get_backup_jobs_list),
            web.post(r'/backup/clean', start_backup_clean),
            web.get(r'/backup/{job_id}', get_backup_state),
            web.get(r'/backup/{job_id}/archive',
                    get_backup_archive),
            web.get(r'/backup/{job_id}/log', get_backup_log),
            web.post(r'/restore', start_restore_data),
            web.get(r'/restore', get_restore_jobs_list),
            web.get(r'/restore/{job_id}', get_restore_state),
            web.get(r'/restore/{job_id}/log', get_restore_log),
            web.post(r'/restore/clean', start_restore_clean),
            web.post(r'/{workspace}/rebuild-indexes', rebuild_indexes),
            web.post(r'/{workspace}', create_workspace),
            web.delete(r'/{workspace}', delete_workspace),
            web.get(r"/{workspace}", get_all_documents),
            web.get(r"/{workspace}/{scope}", get_documents),
            web.get(r"/{workspace}/{scope}/{ref}",
                    get_document_versions),
            web.post(r"/{workspace}/{scope}/{ref}/{version}",
                     create_document),
            web.delete(r"/{workspace}/{scope}/{ref}",
                       delete_document),
            web.get(r"/{workspace}/{scope}/{ref}/{version}",
                    get_document_version),
            web.put(r"/{workspace}/{scope}/{ref}/{version}",
                    update_document_version),
            web.patch(r"/{workspace}/{scope}/{ref}/{version}",
                      patch_document_version),
            web.delete(r"/{workspace}/{scope}/{ref}/{version}",
                       delete_document_version),
            web.get(r"/{workspace}/{scope}/{ref}/{version}/relations",
                    get_document_relations),
        ]

    @property
    def middlewares(self) -> List[web.middleware]:
        """ list of app middlewares """

        return []

    @property
    def cors(self) -> aiohttp_cors.CorsConfig:
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
    def safe_list(self) -> List[str]:
        """ apps that can be accessed without auth """
        return []


WebAppManager.register('/api/v2/db', DatabaseAPI)
