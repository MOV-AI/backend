"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
   Developers:
   - Pedro Cristóvão (pedro.cristovao@mov.ai) - 2021

   v.21.6
"""
from geometry_msgs.msg import Pose
import numpy

from movai_core_shared.common.utils import is_enterprise
from movai_core_shared.logger import Log

from dal.models.scopestree import ScopesTree
from dal.models.var import Var as Variable
from dal.scopes.fleetrobot import FleetRobot
from dal.scopes.package import Package

if is_enterprise:
    from movai_core_enterprise.scopes.graphicscene import GraphicScene


# constants
DEFAULT_SCENE_NAME = "default"

# global functions
LOGGER = Log.get_logger(__name__)


def sprint(string, *params):
    LOGGER.debug(string, params)


def get(obj, key):
    if key in obj:
        return obj[key]
    else:
        return None


def reduce(fold, iterable, base=0):
    acc = base
    for x in iterable:
        acc = fold(acc, x)
    return acc


def encode(x):
    return x.replace(" ", "")


def get_tree(scene_name):
    return MemorySingleton.get_tree(scene_name)


def get_complex_pos_ori(node_item):
    center = node_item["position"]
    quaternion = node_item["quaternion"]

    center = list(map(float, center))
    quaternion = list(map(float, quaternion))

    z_center = complex(center[0], center[1])

    theta_center = 2 * numpy.arctan2(quaternion[3], quaternion[0])
    exp_theta = numpy.exp(complex(0, theta_center))
    return z_center, exp_theta


def get_world_coordinates_reducer(acc, child):
    z_child, exp_child = get_complex_pos_ori(child)
    return acc[0] + acc[1] * z_child, acc[1] * exp_child


def get_complex_world_pos_ori(node_item, tree_object):
    path = tree_object.find_path(lambda node: node["name"] == node_item["name"])
    path = path[1:]  # remove globalRef
    return reduce(get_world_coordinates_reducer, path, (complex(0, 0), 1))


def default2redis(node_item, tree_object):
    z_final, exp_final = get_complex_world_pos_ori(node_item, tree_object)
    sprint("Position, quaternion", z_final, (exp_final))
    geometry_stamped = {
        "position": {"x": 0, "y": 0, "z": 0},
        "orientation": {"w": 1, "x": 0, "y": 0, "z": 0},
    }

    exp_final = numpy.sqrt(exp_final)

    sprint("Geometry", z_final, exp_final)

    # node_item['position'][0]
    geometry_stamped["position"]["x"] = z_final.real
    # node_item['position'][1]
    geometry_stamped["position"]["y"] = z_final.imag
    geometry_stamped["position"]["z"] = float(node_item["position"][2])
    # node_item['quaternion'][0]
    geometry_stamped["orientation"]["w"] = exp_final.real
    geometry_stamped["orientation"]["x"] = 0  # node_item['quaternion'][1]
    geometry_stamped["orientation"]["y"] = 0  # node_item['quaternion'][2]
    # node_item['quaternion'][3]
    geometry_stamped["orientation"]["z"] = exp_final.imag
    return geometry_stamped


def path2redis(path, tree_object):
    ans_path = {
        "keypoints": [],
        "trajectory": [],
        "weight": get(path, "weight")(1),
        "isBidirectional": get(path, "isBidirectional")(False),
    }

    z_center, exp_theta = get_complex_world_pos_ori(path, tree_object)
    theta_center = numpy.angle(exp_theta)

    for i in range(len(path["localPath"])):
        x, y, _ = path["localPath"][i]
        z = exp_theta * complex(x, y) + z_center
        ans_path["keypoints"].append(z.real)
        ans_path["keypoints"].append(z.imag)

    for i in range(len(path["splinePath"])):
        x, y, theta = path["splinePath"][i]
        z = exp_theta * complex(x, y) + z_center
        ans_path["trajectory"].append(z.real)
        ans_path["trajectory"].append(z.imag)
        ans_path["trajectory"].append(theta + theta_center)

    return ans_path


def box_region2redis(box_region, tree_object):
    ans_polygon = {"polygon": []}
    z_center, exp_theta = get_complex_world_pos_ori(box_region, tree_object)
    corners = box_region["corners"]
    z_corners = list(map(lambda x: complex(x[0], x[1]), corners))
    diff = z_corners[1] - z_corners[0]

    z_polygon = [
        exp_theta * z_corners[0] + z_center,
        exp_theta * (z_corners[0] + diff.real) + z_center,
        exp_theta * (z_corners[0] + diff) + z_center,
        exp_theta * (z_corners[0] + complex(0, diff.imag)) + z_center,
    ]

    for z in z_polygon:
        ans_polygon["polygon"].append([z.real, z.imag])

    return ans_polygon


def polygon2redis(polygon, tree_object):
    ans_polygon = {"polygon": [], "navigationAllowed": False}

    z_center, exp_theta = get_complex_world_pos_ori(polygon, tree_object)
    z_points = list(map(lambda x: complex(x[0], x[1]), polygon["localPolygon"]))

    for z in z_points:
        z = exp_theta * z + z_center
        ans_polygon["polygon"].append([z.real, z.imag])

    if "navigationAllowed" in polygon:
        ans_polygon["navigationAllowed"] = polygon["navigationAllowed"]
    return ans_polygon


def graph2redis(graph, tree_object):
    ans_graph = {
        "directed": True,
        "multigraph": False,
        "graph": {
            "keyValueMap": graph["keyValueMap"],
            "annotationPropOverrides": get(graph, "annotationPropOverrides")({}),
        },
    }
    ans_graph["nodes"] = [graph["vertices"][k] for k in graph["vertices"]]
    ans_graph["links"] = list(
        map(
            lambda edge: {
                "weight": edge["weight"],
                "keyValueMap": edge["keyValueMap"],
                "annotationPropOverrides": get(edge, "annotationPropOverrides")({}),
                "source": edge["ids"][0],
                "target": edge["ids"][1],
                "belongsSrc": edge["belongsSrc"],
                "belongsTrg": edge["belongsTrg"],
            },
            [graph["edges"][k] for k in graph["edges"]],
        )
    )
    sprint("Graph", ans_graph)
    return ans_graph


def landmark2redis(landmark, tree_object):
    ans_landmark = default2redis(landmark, tree_object)
    ans_landmark["landmarkType"] = landmark["landmarkType"]
    ans_landmark["landmarkID"] = landmark["landmarkID"]
    return ans_landmark


def obj2redis(obj, tree_object):
    default = default2redis
    type2redis_dict = {
        "Path": path2redis,
        "BoxRegion": box_region2redis,
        "PolygonRegion": polygon2redis,
        "GraphItem": graph2redis,
        "Landmark": landmark2redis,
    }
    obj_type = obj["type"]
    if obj_type in type2redis_dict:
        return type2redis_dict[obj_type](obj, tree_object)
    return default(obj, tree_object)


def add2scene_aux(tree_node, scene_name, tree_object, scene):
    encode_obj_type = encode(tree_node["item"]["type"])
    encode_key = encode(tree_node["name"])
    geometry_msg = obj2redis(tree_node["item"], tree_object)
    children = tree_node["children"]
    if children:
        for child in children:
            add2scene_aux(child, scene_name, tree_object, scene)
    try:
        sprint("Add GraphicScene AssetType and AssetName", encode_obj_type, encode_key)
        scene.AssetType[encode_obj_type].AssetName[encode_key] = {"Value": geometry_msg}
    except:
        sprint("Caught exception while creating")
        sprint("Add GraphicScene AssetType and AssetName", encode_obj_type, encode_key)
        scene.AssetType[encode_obj_type] = {"AssetName": {}}
        scene.AssetType[encode_obj_type].AssetName[encode_key] = {"Value": geometry_msg}

    # Add annotation
    add_annotation_to_object(
        scene,
        tree_node,
        encode_obj_type,
        encode_key,
        lambda obj: obj.Annotation,
        "Annotation",
        "keyValueMap",
    )
    add_annotation_to_object(
        scene,
        tree_node,
        encode_obj_type,
        encode_key,
        lambda obj: obj.AnnotationOverride,
        "AnnotationOverride",
        "annotationPropOverrides",
    )


def add2scene(tree_node, scene_name, tree_object):
    scene_scope = ScopesTree().from_path(scene_name, scope="GraphicScene")
    add2scene_aux(tree_node, scene_name, tree_object, scene_scope)
    scene_scope.write()


def add_annotation_to_object(
    scene,
    tree_node,
    obj_type,
    asset_name,
    prop_name_getter,
    prop_name,
    node_item_prop_name="keyValueMap",
):
    sprint("Add annotation to AssetType and AssetName", obj_type, asset_name)
    key_value_dict = get(tree_node["item"], node_item_prop_name)({})
    sprint(f"{node_item_prop_name} dict", key_value_dict)
    try:
        obj = scene.AssetType[obj_type].AssetName[asset_name]
        if prop_name_getter(obj):
            for annot in prop_name_getter(obj):
                del obj[prop_name][annot]
        for key in key_value_dict:
            obj[prop_name][key] = {"Value": key_value_dict[key]}
    except Exception as e:
        sprint(f"Caught exception while adding annotation {prop_name}", e)


def del2scene_aux(obj_name, scene_name, scene_scope):
    # Delete Node on Key Scene
    try:
        node = TreeObject(get_tree(scene_name)).get_node(
            lambda node_in_tree: node_in_tree["name"] == obj_name
        )
        if node:
            children = node["children"]
            if children:
                for child in children:
                    del2scene_aux(child["name"], scene_name, scene_scope)
            node_type = node["item"]["type"]
            sprint(
                "Deleting GraphicScene, AssetType and AssetName",
                encode(node_type),
                encode(obj_name),
            )
            del scene_scope.AssetType[encode(node_type)].AssetName[encode(obj_name)]

    except Exception as e:
        sprint("Caught Exception while del2scene", e)


def del2scene(obj_name, scene_name):
    scene_scope = ScopesTree().from_path(scene_name, scope="GraphicScene")
    del2scene_aux(obj_name, scene_name, scene_scope)
    scene_scope.write()


def reset_scene(scene_path):
    scene = ScopesTree().from_path(scene_path, scope="GraphicScene")
    types = list(filter(lambda x: x != "memory", list(scene.AssetType)))
    for asset_type in types:
        del scene.AssetType[asset_type]
    scene.AssetType["memory"].AssetName["tree"] = {"Value": []}
    scene.write()


# global classes
class MemorySingleton:
    __instance = None

    @staticmethod
    def get_instance(scene_name=DEFAULT_SCENE_NAME):
        """Static access method."""
        if not MemorySingleton.__instance or MemorySingleton.__instance.scene_name != scene_name:
            MemorySingleton(scene_name)
        return MemorySingleton.__instance

    @staticmethod
    def set_tree(tree=None, scene_name=DEFAULT_SCENE_NAME):
        MemorySingleton.get_instance(scene_name).__set_tree(tree)

    @staticmethod
    def get_tree(scene_name=DEFAULT_SCENE_NAME):
        return MemorySingleton.get_instance(scene_name).__get_tree()

    def __init__(self, scene_name):
        """Virtually private constructor."""
        MemorySingleton.__instance = self
        self.scene_name = scene_name
        self.memory = GraphicScene(scene_name).AssetType["memory"]

    def __set_tree(self, tree=[]):
        self.memory.add("AssetName", "tree", Value=tree)

    def __get_tree(self):
        if "tree" not in self.memory.AssetName:
            self.__set_tree()
        return self.memory.AssetName["tree"].Value


class TreeObject:
    def __init__(self, tree):
        # Actually is a forest of trees
        self.tree = tree

    @staticmethod
    def get_node_recursive(tree, predicate):
        for node in tree:
            if predicate(node):
                return node
            answer = TreeObject.get_node_recursive(node["children"], predicate)
            if answer:
                return answer
        return None

    @staticmethod
    def get_parent_node_recursive(tree, predicate, parent):
        for node in tree:
            if predicate(node):
                return parent
            answer = TreeObject.get_parent_node_recursive(node["children"], predicate, node)
            if answer:
                return answer
        return None

    @staticmethod
    def find_path_recursive(tree, predicate):
        # Depth first search
        for node in tree:
            if predicate(node):
                return [node["item"]]
            # add parent
            if "children" in node:
                for child in node["children"]:
                    child_result = TreeObject.find_path_recursive([child], predicate)
                    if len(child_result) != 0:
                        return [node["item"]] + child_result
        return []

    def get_node(self, predicate):
        if self.tree:
            return TreeObject.get_node_recursive(self.tree, predicate)
        return None

    def get_parent_node(self, child_predicate):
        if self.tree:
            return TreeObject.get_parent_node_recursive(self.tree, child_predicate, None)
        return None

    def find_path(self, predicate):
        """
        :param predicate: predicate to stop search
        """
        return TreeObject.find_path_recursive(self.tree, predicate)


class Viewer:
    @classmethod
    def on_save(cls, tree, scene_name=DEFAULT_SCENE_NAME):
        sprint("Saving scene tree", tree)

        def update_tree():
            reset_scene(scene_name)
            for leaf in tree:
                sprint("add new", leaf["name"])
                cls.on_addNodeItem(leaf, None, scene_name)

        update_tree()

    @staticmethod
    def on_addNodeItem(tree_node, parent_name, scene_name=DEFAULT_SCENE_NAME):
        sprint("Adding node ", tree_node["name"])
        tree = TreeObject(get_tree(scene_name))
        if parent_name:
            parent_node = tree.get_node(lambda node: parent_name == node["name"])
            if parent_node:
                parent_node["children"].append(tree_node)
                add2scene(tree_node, scene_name, tree)
        else:
            # remove node if already exists
            ans = list(filter(lambda node: tree_node["name"] != node["name"], tree.tree))
            ans.append(tree_node)
            tree.tree = ans
            add2scene(tree_node, scene_name, tree)

        MemorySingleton.set_tree(tree.tree, scene_name)

    @staticmethod
    def on_deleteNodeByName(node_name, scene_name=DEFAULT_SCENE_NAME):
        sprint("Delete node: ", node_name)

        del2scene(node_name, scene_name)

        tree = TreeObject(get_tree(scene_name))
        parent_node = tree.get_parent_node(lambda node: node_name == node["name"])
        if parent_node:
            parent_node["children"] = list(
                filter(lambda child: child["name"] != node_name, parent_node["children"])
            )
        else:
            tree.tree = list(filter(lambda node: node_name != node["name"], tree.tree))

        MemorySingleton.set_tree(tree.tree, scene_name)

    @classmethod
    def on_updateNode(cls, tree_node, parent_name, old_name=None, scene_name=DEFAULT_SCENE_NAME):
        sprint("Updating node...", tree_node["name"], old_name)
        retrieved_node = TreeObject(get_tree(scene_name)).get_node(
            lambda node: node["name"] == old_name
            if old_name is not None
            else node["name"] == tree_node["name"]
        )
        if retrieved_node:

            def delete_add_object():
                sprint("delete old", retrieved_node["name"])
                cls.on_deleteNodeByName(retrieved_node["name"], scene_name=scene_name)
                sprint("add new", tree_node["name"])
                cls.on_addNodeItem(tree_node, parent_name, scene_name)

            delete_add_object()

    @classmethod
    def on_retrieveScene(cls, scene_path=DEFAULT_SCENE_NAME):
        cls.migrate_poses_in_scene(scene_path)
        my_scopes = ScopesTree()
        scene = my_scopes.from_path(scene_path, scope="GraphicScene")
        sprint("Scene types", scene_path, list(scene.AssetType))
        return scene.AssetType["memory"].AssetName["tree"].Value.value

    @staticmethod
    def on_delete_map(map_name):
        """Delete map from packages
        Parameters:
            map_name (str) : map name (like: "default" or "default.yaml")
        """
        name = map_name.split(".")[0]
        package = Package("maps")
        for map_address in package.File:
            package_map_name = map_address.split(".")[0]
            if name == package_map_name:
                sprint("Deleting map", map_address)
                package.delete("File", map_address)

    @staticmethod
    def on_delete_mesh(mesh_name):
        Package("meshes").delete("File", mesh_name)

    @staticmethod
    def on_delete_point_cloud(point_cloud_name):
        Package("point_clouds").delete("File", point_cloud_name)

    @staticmethod
    def migrate_poses_in_scene(scene_path):
        try:
            types = ["KeyPoint", "Map", "Mesh", "GlobalRef", "Robot", "PointCloud", "NodeItem"]
            scene_name = scene_path.split("/")[-1]
            scopes = ScopesTree()
            new_scene = scopes().GraphicScene[scene_name]
            scene = GraphicScene(scene_name)
            for t in types:
                try:
                    for i in new_scene.AssetType[t].AssetName:
                        point = new_scene.AssetType[t].AssetName[i].Value
                        sprint("Migrate value", t, i)
                        if isinstance(point._value, Pose):
                            scene.AssetType[t].AssetName[i].Value = point.value
                except Exception as e:
                    sprint("Caught exception while migrating types...", e)
                    pass
        except Exception as e:
            sprint("Caught exception while migrating poses", e)
            pass

    @staticmethod
    def get_computed_annotations(annotations_name):
        """
        Returns {computed_annotations: List<Value>, errors: List<Error>}
        """
        sprint("Get computed annotations", annotations_name)
        computed_annotations_dict = {}
        for annotation_name in annotations_name:
            try:
                annotation = ScopesTree().from_path(annotation_name, scope="Annotation")
                computed_annotations_dict.update(annotation.get_computed_annotation())
            except Exception as e:
                sprint("Caught Exception while computing annotation", annotation_name, e)
        return list(computed_annotations_dict.values())

    @staticmethod
    def set_robot_mesh(robot_id, mesh_name):
        """
        Sets robot mesh in DB
        """
        robot = FleetRobot(robot_id)
        try:
            robot.Parameter["mesh"].Value = mesh_name
        except Exception as e:
            sprint("Caught exception in set robot mesh", e)
            robot.add("Parameter", "mesh").Value = mesh_name

    @staticmethod
    def set_robot_pose_estimation(robot_name, pose, params):
        """
        Set variable Var:<robot_name>@pose_estimation
        """
        sprint("Set pose estimation:", robot_name, pose, params)
        Variable("Fleet", _robot_name=robot_name).set(
            f"pose_estimation", {"pose": pose, "params": params}
        )

    @staticmethod
    def set_robot_pose_goal(robot_name, pose):
        """
        Set variable Var:<robot_name>@pose_goal
        """
        sprint("Set pose goal:", robot_name, pose)
        Variable("Fleet", _robot_name=robot_name).set(f"pose_goal", pose)
