"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Module that implements backup previewer
"""

# pylint: disable=unused-argument

import os
import pathlib
import collections.abc

from typing import List
from aiohttp import web

import tools.backup

from dal.movaidb import MovaiDB
from backend.http import IWebApp, WebAppManager


class BackupApp(IWebApp):
    """Backup Web App module"""

    MOVAI_USERSPACE = os.getenv("MOVAI_USERSPACE", "/opt/mov.ai/user")
    PROJ_PATH = os.path.join(MOVAI_USERSPACE, "database")
    PROJ_PATH_OBJ = pathlib.Path(PROJ_PATH)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis_db = MovaiDB()

    @property
    def routes(self) -> List[web.RouteDef]:
        """list of http routes"""
        return [
            web.get("/projects/", self.get_projects),
            web.get("/types/", self.get_types),
            web.get("/docs/", self.get_docs),
            web.get("/compare/", self.get_compare),
        ]

    # middlewares, cors and safe_list are default (None/empty)

    #
    # handlers
    #

    async def get_projects(self, request: web.Request) -> web.Response:
        """/projects/
        list of available projects
        """

        project_list = []

        try:
            for entry in BackupApp.PROJ_PATH_OBJ.iterdir():
                if entry.is_dir():
                    project_list.append(entry.name)
        except FileNotFoundError:
            return web.json_response(
                {"success": False, "error": "Projects Path not found"},
                headers={"Server": "Movai-server"},
            )

        return web.json_response(
            {"success": True, "result": project_list},
            headers={"Server": "Movai-server"},
        )

    async def get_types(self, request: web.Request) -> web.Response:
        """/types/?project=<project>
        list of available types in the project + "All" and "Manifest"
        """

        try:
            project_query = request.query["project"]
        except KeyError:
            return web.json_response(
                {"success": False, "error": "Missing 'project' parameter"},
                headers={"Server": "Movai-server"},
            )

        project_path = (BackupApp.PROJ_PATH_OBJ / project_query).resolve()

        # quick validation
        if project_path.parent != BackupApp.PROJ_PATH_OBJ:
            return web.json_response(
                {"success": False, "error": "Possible path traversal attempt :)"},
                headers={"Server": "Movai-server"},
            )
        if not project_path.is_dir():
            return web.json_response(
                {"success": False, "error": "Project is not valid"},
                headers={"Server": "Movai-server"},
            )

        # get scope/types list
        # default 'All' and 'Manifest'
        type_list = ["All"]
        manifest_file = project_path / "manifest.txt"
        if manifest_file.exists() and manifest_file.is_file():
            type_list.append("Manifest")

        # now do the thing
        for entry in project_path.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                # NOTE: for now we're trusting the user on this one,
                # eventually validate if type is known
                type_list.append(entry.name)

        return web.json_response({"success": True, "result": type_list}, headers={"Server": "Movai-server"})

    async def get_docs(self, request: web.Request) -> web.Response:
        """/docs/?project=<project>&type=<type>
        list available objects/docs for type
        """

        try:
            project_query = request.query["project"]
        except KeyError:
            return web.json_response(
                {"success": False, "error": "Missing 'project' parameter"},
                headers={"Server": "Movai-server"},
            )

        try:
            type_query = request.query["type"]
        except KeyError:
            return web.json_response(
                {"success": False, "error": "Missing 'type' parameter"},
                headers={"Server": "Movai-server"},
            )

        if type_query in ("All", "Manifest"):
            return web.json_response(
                {"success": False, "error": "Type is not valid"},
                headers={"Server": "Movai-server"},
            )

        project_path = (BackupApp.PROJ_PATH_OBJ / project_query).resolve()
        type_path = (project_path / type_query).resolve()

        # quick validation
        if project_path.parent != BackupApp.PROJ_PATH_OBJ or type_path.parent != project_path:
            return web.json_response(
                {"success": False, "error": "Possible path traversal attempt:)"},
                headers={"Server": "Movai-server"},
            )
        if not project_path.is_dir():
            return web.json_response(
                {"success": False, "error": "Project is not valid"},
                headers={"Server": "Movai-server"},
            )
        if not type_path.is_dir():
            return web.json_response(
                {"success": False, "error": "Type is not valid"},
                headers={"Server": "Movai-server"},
            )

        # get doc/obj list
        doc_list = []

        # find json objects/files
        doc_list.extend([entry.stem for entry in type_path.glob("*.json")])
        # and for packages (remove if unnecessary)
        if type_query == "Package":
            doc_list.extend([entry.name for entry in type_path.iterdir() if entry.is_dir()])

        # now the result
        return web.json_response({"success": True, "result": doc_list}, headers={"Server": "Movai-server"})

    async def get_compare(self, request: web.Request) -> web.Response:
        """/compare/?project=<project>&type=<type>&name=<doc_name>
        compare objects from filesystem/userspace and redis
        """

        try:
            project_query = request.query["project"]
        except KeyError:
            return web.json_response(
                {"success": False, "error": "Missing 'project' parameter"},
                headers={"Server": "Movai-server"},
            )
        try:
            type_query = request.query["type"]
        except KeyError:
            return web.json_response(
                {"success": False, "error": "Missing 'type' parameter"},
                headers={"Server": "Movai-server"},
            )

        # validate project
        project_path = (BackupApp.PROJ_PATH_OBJ / project_query).resolve()
        if not (project_path.is_dir() and project_path.parent == BackupApp.PROJ_PATH_OBJ):
            return web.json_response(
                {"success": False, "error": "Project is invalid"},
                headers={"Server": "Movai-server"},
            )

        importer = FakeImporter(project_path.name)

        objects_to_import = {}

        if type_query == "All":
            # cool
            pass
        elif type_query == "Manifest":
            objects_to_import = importer.read_manifest(str(project_path / "manifest.txt"))
        else:
            # "validate" type query
            type_path = (project_path / type_query).resolve()
            # get the object to import
            try:
                name_query = request.query["name"]
            except KeyError:
                return web.json_response(
                    {"success": False, "error": "Missing 'name' parameter"},
                    headers={"Server": "Movai-server"},
                )
            objects_to_import = {type_path.name: [name_query]}

        try:
            importer.run(objects_to_import)
        except tools.backup.ImportException as e:
            return web.json_response(
                {
                    "success": False,
                    "error": f"Error fetching objects to compare: {str(e)}",
                },
                headers={"Server": "Movai-server"},
            )

        # and extract stuff
        mega_fs_dict = importer._mega_dict

        # now fetch all the affeced objects from redis
        mega_rs_dict = {}
        for scope in mega_fs_dict:
            for obj in mega_fs_dict[scope]:
                obj_dict = self._redis_db.get({scope: {obj: "*"}})
                update_dict(mega_rs_dict, obj_dict)
        # apply mega_fs_dict to mega_rs_dict, modifying fs one
        add_dict(mega_fs_dict, mega_rs_dict)
        # send result
        return web.json_response(
            {
                "success": True,
                "result": [
                    mega_rs_dict,  # current
                    mega_fs_dict,  # after import
                ],
            },
            headers={"Server": "Movai-server"},
        )


def add_dict(base, data):
    """merge 2 dicts by adding the extra values from `data` to `base`"""
    for k, v in data.items():
        if isinstance(v, collections.abc.Mapping):
            base[k] = add_dict(base.get(k, {}), v)
        else:
            base[k] = base.get(k, v)
    return base


def update_dict(base, data):
    """recursive dict.update()"""
    for k, v in data.items():
        if isinstance(v, collections.abc.Mapping):
            base[k] = update_dict(base.get(k, {}), v)
        else:
            base[k] = v
    return base


class FakeImporter(tools.backup.Importer):
    """import all the objects and dependencies into a giant dict"""

    def __init__(self, project):
        super().__init__(project)
        self._mega_dict = {}

    def _import_data(self, scope, name, data):
        self.set_imported(scope, name)
        update_dict(self._mega_dict, data)


WebAppManager.register("/backup/", BackupApp)
