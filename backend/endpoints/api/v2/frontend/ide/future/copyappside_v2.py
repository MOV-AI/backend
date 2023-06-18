"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer (erez@mov.ai) - 2023
"""
from abc import ABC, abstractmethod
from typing import List
from aiohttp import web
from aiohttp.web_response import Response

from dal.models.callback import Callback
from dal.models.message import Message
from dal.models.scopestree import scopes

from backend.endpoints.api.v2.base import BaseWebApp
from backend.endpoints.api.v2.base import RestBaseClass
from backend.http import WebAppManager

class FrontendRestBaseClass(RestBaseClass, ABC):
    """A base class for the Frontend Rest API"""

    def __init__(self) -> None:
        """initalizes the object."""
        super().__init__()
        self._result = {}

    @abstractmethod
    def execute_imp(self) -> None:
        """This is an abstract method represent the core functionality to
        exceute for each one of the subclasses.
        This function is being called in the __call__ method after all
        required data has been fethced.
        """

    async def __call__(self, request: web.Request) -> Response:
        """This is an general function which acts as a general shell function
        for various endpoints implementation.
        it calls the execute_imp function after extracting all required data
        from the http request.

        Args:
            request (web.Request): The http request.

        Raises:
            web.HTTPForbidden: if it a UserPermissionError arises.
            web.HTTPBadRequest: if some other error arises.

        Returns:
            Response: The http response to the client.
        """
        try:
            self._request = request
            self.extract_user()
            await self.execute_imp()
            return web.json_response(self.validate_result(self._result), headers={"Server": "Movai-server"})
        except Exception as error:
            error_msg = f"{type(error).__name__}: {error}"
            self.log.error(error_msg)
            self.analyze_error(error, error_msg)

    async def extract_data(self):
        self._data = await self._request.json()
        
class GetFrontend(FrontendRestBaseClass):

    def __init__(self) -> None:
        super().__init__()
        self._permission = "read"

    async def execute_imp(self) -> None:
        """This method fetch the LdapConfig info from the DB."""
        self.check_permissions()


class CallbackEditor(FrontendRestBaseClass):

    def __init__(self) -> None:
        super().__init__()
        self.responses = {
            "init": Callback.export_modules,
            "get_libraries"  : Callback.get_modules,
            "get_all_libraries"  : Callback.fetch_modules_api,
            "get_messages"   : Message.fetch_portdata_messages,
            "get_msg_struct" : Message.get_structure,
            "library"        : self.describe_module,
        }

    async def execute_imp(self) -> None:
        try:
            self.extract_data()
            func = self._data.get("func")
            args = self._data.get("args", {})
            if func is None:
                raise web.HTTPBadRequest("missing 'func' argument")
            self._result = {"func": func, "result": self.responses[func](**args), "success": True}
        except Exception as error:
            exc_result = CallbackEditor.handle_exception(error)
            self._result = {"success": False, "error": exc_result}

    @staticmethod
    def handle_exception(exc: Exception):
        exc_classname = exc.__class__.__name__
        handle_map = {
            "IndentationError" : ["filename", "lineno", "msg", "offset", "text"],
            "SyntaxError" : ["filename", "lineno", "msg", "offset", "text"]
        }
        handler = lambda exc, names : {name: getattr(exc, name) for name in names}

        if exc_classname in handle_map:
            return {"type": exc_classname, "data": handler(exc, handle_map[exc_classname])}
        raise exc

    @staticmethod
    def describe_module(*, module, **kwargs):
        required = ["name", "toSelect"]
        if not all(x in module for x in required):
            return False
        to_return = {
            "module"   : Callback.get_methods(module["name"]),
            "toSelect" : module["toSelect"],
            "name"     : module["name"]
        }
        return to_return
    
    # check if useful
#    for x in module:
#        if not x in required:
#            to_return[x] = module[x]
#    for element_name in dir(mymodule):
#        element = getattr(mymodule, element_name)
#        el = {
#            'value': element_name,
#            'label': element_name,
#            'name' : element_name,
#        }
#        if inspect.isclass(element):
#             try:
#                 to_return['classes'].append(el)
#             except:
#                 print("ERROR CLASSES")
#        elif inspect.ismodule(element):
#            continue
#        elif hasattr(element, '__call__'):
#            if inspect.isbuiltin(element):
#                try:
#                    to_return['builtin_functions'].append(el)
#                except:
#                    print("ERROR BUILT-IN FUNCTION")
#            else:
#                try:
#                    to_return['functions'].append(el)
#                except:
#                    print("ERROR FUNCTION")
#                    pass
#        else:
#            try:
#                to_return['values'].append(el)
#            except:
#                print("ERROR VALUES")
#    return to_return

class CopyAppsIDE(FrontendRestBaseClass):
    async def execute_imp(self) -> None:
        self.extract_data()
        scope = self._data.get("scope")
        from_id = self._data.get("from_id")
        to_id = self._data.get("to_id")
        workspace = self._data.get("workspace")
        self._result["result"] = self.copy(scope, from_id, to_id, workspace)
        
    async def copy (self, scope, from_id, to_id, workspace="global"):
        response = {"success": False}

        # check if the a document with name 'to_name' already exists
        try:
            obj = scopes.from_path(to_id, scope=scope)
            # document already exists
            error_msg = f"{scope} {to_id} already exists"
            response["error"] = error_msg
        except KeyError:
            # get the document to copy
            to_copy = getattr(scopes(), scope)[from_id]

            data = to_copy.serialize()
            data["Label"] = to_id

            # create the new document
            scopes(workspace=workspace).write(data, version="_unversioned_", ref=to_id, scope=scope)

            response = {"success": True}

        return response


class FlowAPI(FrontendRestBaseClass):

    async def execute_imp(self) -> None:
        self.extract_data()

    @staticmethod
    async def getCls(className):
        depClasses = {"Flow": DFlow, "StateMachine": DStateMachine}
        return depClasses[className]

    @staticmethod
    async def saveFlowLayers(flowId, layers, **ignore):
        """ Save the flow layers (Flow only)"""

        response = {"success": False}

        try:
            inst = getCls("Flow")(flowId)
            inst.Layers.update(layers)
            response = {"success": True}

        except Exception as e:
            raise

        return response

    def deleteLayer(flowId, layer, **ignore):
        """ Delete specific layer and remove from NodeLayers (Flow only)"""

        response = {"success": False}

        try:
            flowInst = getCls("Flow")(flowId)
            if layer in flowInst.Layers:

                # delete the layer
                del flowInst.Layers[layer]

                # check if there are any nodes in the deleted layer
                for nodeName, nodeValue in flowInst.NodeInst.items():
                    if nodeValue.NodeLayers:
                        if layer in nodeValue.NodeLayers:
                            newLayers = nodeValue.NodeLayers
                            newLayers.remove(layer)
                            flowInst.NodeInst[nodeName].NodeLayers = newLayers

            response = {"success": True}

        except Exception:
            raise

        return response
        
    def deleteNodeInst(scope, flowId, nodeId, nodeType = "MovAI/State", **ignore):
        """ delete nodeInst or State and related links"""

        response = {"success": False}

        nodeInstNames = {"Flow": "NodeInst", "StateMachine": "State"}
        if nodeType == "MovAI/Flow":
            nodeInstNames["Flow"] = "Container"
        
        try:
            inst = getCls(scope)(flowId)
            inst.delete(nodeInstNames[scope], nodeId)
            response = {"success": True}

        except Exception as e:
            raise

        return response
        
    def deleteLink(scope, flowId, linkId, **ignore):
        """ Delete the link """

        response = {"success": False}

        try:
            inst = getCls(scope)(flowId)
            if inst.delete_link(linkId):
                response["success"] = True
                response["id"] = linkId
                response["validate"] = inst.is_valid()
            else:
                raise Exception("Could not delete link")
                
        except KeyError:
            pass

        except Exception as e:
            raise

        return response
        
    def addLink(scope, flowId, link, **ignore):
        """ Add a new link """

        response = {"links": {}, "validate": {}, "success": False}

        try:
            inst = getCls(scope)(flowId)
            res = inst.add_link(**link) # (_id, link)

            if len(res) == 2:
                response["success"] = True
                response["links"] = [{"name": res[0], "value": res[1]}]
                response["validate"] = inst.is_valid()
            else:
                raise Exception("Could not create link")
                
        except KeyError:
            pass

        except Exception:
            raise

        return response


    def setNodePos(scope, flowId, nodeId, data, nodeType="", **ignore):
        ''' Set node new position '''

        nodeInstNames = {"Flow": "NodeInst", "StateMachine": "State"}
        response = {"success": False}

        try:
            obj = getCls(scope)(flowId)
            pos = (data.get("x", None), data.get("y", None))
            if pos[0] and pos[1]:
                # if the node is a Container
                if nodeType == "MovAI/Flow":
                    nodeObj = getattr(obj, "Container")[nodeId]
                    nodeObj.Visualization = [pos[0].get("Value", 0), pos[1].get("Value", 0)]
                else:
                    nodeObj = getattr(obj, nodeInstNames[scope])[nodeId]
                    nodeObj.Visualization["x"].Value = pos[0].get("Value", 0)
                    nodeObj.Visualization["y"].Value = pos[1].get("Value", 0)
                response = {"success": True}
            else:
                response = {"success": False, "error": "Invalid position"}
        except Exception:
            raise
        return response
        
    def setLinkDependency(flowId, linkId, dependency, **ignore):
        ''' Set the link dependecy level (Flow only) '''

        try:
            inst = getCls("Flow")(flowId)
            link = inst.Links[linkId]
            link["Dependency"] = dependency
            inst.Links[linkId] = link
            return {"success": True}
        except Exception:
            raise
        
    # new api alternative
    def _setLinkDependency(flowId, linkId, dependency, **ignore):
        ''' Set the link dependecy level (Flow only) '''

        try:
            Flow(flowId).Links[linkId].Dependency = dependency
            return {"success": True}
        except Exception:
            raise
        
    def copyNodeInst(scope, orgFlow, copyFlow, copyName, orgName, orgType, copyPosX, copyPosY, copyParams, **ignore):
        ''' 
            Copy a NodeInst, Container or State from orgFlow to copyflow
        '''
        
        label = {"NodeInst": "NodeLabel", "Container": "ContainerLabel", "State": "StateLabel"}
        response = {"success": False}
        
        try:

            # flow to update
            toFlow = getattr(scopes(), scope)[copyFlow]
            
            # flow to get data from
            fromFlow = getattr(scopes(), scope)[orgFlow]

            if orgType == "NodeInst" or orgType == "State":
                options = {"Visualization": {"x": {"Value": copyPosX}, "y": {"Value": copyPosY}}}
            else:
                options = {"Visualization": [copyPosX, copyPosY], "Parameter": copyParams }
                
            try:
                # can be NodeInst, Container or State
                nodeToCopy = getattr(fromFlow, orgType)[orgName].serialize()
            except Exception:
                # Node not found in flow
                response["error"] = f'"{orgName}" not found in flow {orgFlow}'
                return response
            
            # update position
            nodeToCopy.update(options)
            
            # update label
            nodeToCopy[label[orgType]] = copyName
            
            # save changes
            scopes().write({orgType: { copyName: { **nodeToCopy }}}, scope=scope, ref=toFlow.ref)
            
            # manually updates cached object
            toFlow[orgType][copyName] = nodeToCopy
            
            response["success"] = True
            response["error"] = None

        except Exception:
            raise

        return response
    
class FrontendAPI(BaseWebApp):
    """Web application for serving as the frontend api."""

    @property
    def routes(self) -> List[web.RouteDef]:
        """The list of routes for the ldap configuration api.

        Returns:
            List[web.RouteDef]: a list of RouteDef.
        """
        return [
            web.get(r"/", GetFrontend()),
            web.post(r"/callbackeditor", CallbackEditor()),
            web.post(r"/copyappside", CopyAppsIDE())
        ]


WebAppManager.register("/api/v2/Frontend", FrontendAPI)
