"""Author an original hair-slot marker candidate around a PRIVATE reference rig.

Run with Blender 4.3+, never with normal Python::

    blender --background --factory-startup --python tools/blender_avatar.py -- \
      inspect --reference-fbx PRIVATE.fbx --report .local/rig-report.json
    blender --background --factory-startup --python tools/blender_avatar.py -- \
      build --reference-fbx PRIVATE.fbx --mapping .local/rig-map.json \
      --output-dir .local/avatar-candidate
    blender --background --factory-startup --python tools/blender_avatar.py -- \
      validate --blend .local/avatar-candidate/generated.blend \
      --roundtrip-fbx .local/avatar-candidate/candidate.fbx \
      --report .local/avatar-candidate/revalidation.json

Mapping schema version 1: ``{"schema_version": 1, "profile": "hair_marker", "parts": {"head":
{"bone": "OBSERVED_NAME", "radius_start_ratio": 0.5,
"radius_end_ratio": 0.5}}}``. The hair_marker profile requires ONLY head.
An explicit full_body_experimental profile supports all twelve REQUIRED_PARTS
below, plus optional neck, pelvis, hand_l, hand_r. Never bind a full-body
candidate as a hair piece. Each part
is an original tapered octagonal solid, rigidly weighted to one explicitly
selected deform bone. Radii are fractions of that bone's rest length.
Optional length_start_ratio/length_end_ratio default to 0/1; positions are
head + ratio * (tail-head). There are no guessed game bone names.

This intentionally crude marker does NOT copy source mesh vertices,
weights, materials, textures, or animations. It retains the private host
skeleton, so output FBX/BLEND files must never be committed or distributed
as extracted game assets. Outputs are allowed outside Git checkouts, or
inside this project's ignored .local directory. Existing output files are
never overwritten. Successful validation means a Blender asset candidate,
not Creator Kit acceptance or an in-game working mod. Import and avatar
binding must still be performed and verified in the actual Creator Kit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector


REQUIRED_PARTS = (
    "head", "torso", "upper_arm_l", "lower_arm_l", "upper_arm_r",
    "lower_arm_r", "upper_leg_l", "lower_leg_l", "upper_leg_r",
    "lower_leg_r", "foot_l", "foot_r",
)
OPTIONAL_PARTS = ("neck", "pelvis", "hand_l", "hand_r")
PART_FIELDS = {
    "bone", "radius_start_ratio", "radius_end_ratio",
    "length_start_ratio", "length_end_ratio",
}
SIGNATURE_KEY = "sw_private_skeleton_signature_v1"
MAPPING_KEY = "sw_original_mapping_v1"
MARKER_KEY = "sw_original_geometry_v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIDES = 8
STATUS = "asset_candidate_only_not_hogwarts_tested"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_number(value, label):
    require(type(value) in (int, float) and math.isfinite(value),
            f"{label} must be a finite number")
    return float(value)


def private_output_path(path):
    """Check resolved paths, including symlinks, before writing private data."""
    resolved = Path(path).expanduser().resolve()
    repo = None
    for parent in (resolved, *resolved.parents):
        if not (parent / ".git").exists():
            continue
        # Cloud sandboxes may mount empty read-only .git guard directories at
        # /tmp and /workspace. They are not connected Git repositories.
        found = subprocess.run(
            ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if found.returncode == 0:
            repo = Path(found.stdout.strip()).resolve()
            break
    if repo is not None:
        local = (PROJECT_ROOT / ".local").resolve()
        require(resolved.is_relative_to(local),
                "Private rig outputs inside Git must be in this project's .local directory")
        ignored = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "--", str(resolved)],
            capture_output=True, text=True, check=False,
        )
        require(ignored.returncode == 0,
                "The project's .local output must be ignored by Git")
    return resolved


def new_report(path, payload):
    target = private_output_path(path)
    require(not target.exists(), f"Refusing to overwrite report: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def source_file(path):
    source = Path(path).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == ".fbx",
            "Reference must be an existing private FBX file")
    return source


def import_reference(path, armature_name=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(path), use_anim=False, use_image_search=False,
        automatic_bone_orientation=False, force_connect_children=False,
        ignore_leaf_bones=False, use_custom_props=False,
    )
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if armature_name is not None:
        rigs = [obj for obj in rigs if obj.name == armature_name]
    require(len(rigs) == 1,
            "Reference must identify exactly one armature; use --armature with an observed object name")
    armature = rigs[0]
    require(len(armature.data.bones) > 0, "Reference armature is empty")
    require(all(math.isfinite(v) for row in armature.matrix_world for v in row),
            "Reference armature transform is nonfinite")
    require(abs(armature.matrix_world.determinant()) > 1e-12,
            "Reference armature transform is singular")
    return armature


def matrix_values(matrix):
    return [float(v) for row in matrix for v in row]


def skeleton_signature(armature):
    return {
        "armature_name": armature.name,
        "matrix_world": matrix_values(armature.matrix_world),
        "bones": {
            bone.name: {
                "parent": bone.parent.name if bone.parent else None,
                "deform": bool(bone.use_deform),
                "matrix_local": matrix_values(bone.matrix_local),
                "head_local": list(bone.head_local),
                "tail_local": list(bone.tail_local),
            }
            for bone in sorted(armature.data.bones, key=lambda item: item.name)
        },
    }


def close_values(actual, expected, label, tolerance=1e-5):
    require(len(actual) == len(expected), f"{label} dimensions changed")
    require(all(math.isfinite(a) and abs(a - b) <= tolerance
                for a, b in zip(actual, expected)), f"{label} changed")


def compare_skeleton(actual, expected, *, roundtrip=False):
    require(set(actual["bones"]) == set(expected["bones"]),
            "Skeleton bone names changed")
    close_values(actual["matrix_world"], expected["matrix_world"],
                 "Armature world transform", 1e-4 if roundtrip else 1e-6)
    for name, old in expected["bones"].items():
        new = actual["bones"][name]
        require(new["parent"] == old["parent"], f"Bone hierarchy changed: {name}")
        require(new["deform"] == old["deform"], f"Bone deform flag changed: {name}")
        close_values(new["matrix_local"], old["matrix_local"],
                     f"Bone rest transform {name}", 1e-4 if roundtrip else 1e-6)
        # FBX does not preserve Blender's terminal bone-tail display lengths.
        if not roundtrip:
            close_values(new["head_local"], old["head_local"], f"Bone head {name}")
            close_values(new["tail_local"], old["tail_local"], f"Bone tail {name}")


def geometry_signature(mesh):
    """Capture original positions/bindings without relying on FBX vertex IDs."""
    groups = {group.index: group.name for group in mesh.vertex_groups}
    vertices = [(tuple(float(value) for value in vertex.co),
                 groups[vertex.groups[0].group]) for vertex in mesh.data.vertices]
    triangles = [tuple(vertices[index] for index in polygon.vertices)
                 for polygon in mesh.data.polygons]
    return {"vertices": vertices, "triangles": triangles}


def compare_geometry(actual, expected, tolerance=1e-4):
    """Require the same coordinate/bone and oriented triangle multisets.

    FBX exporters can reindex vertices at UV seams, so IDs are not evidence
    that the bound geometry was preserved. Match positions and bone names,
    consuming each occurrence once; allow triangle cyclic shifts but never
    reverse winding. Absolute tolerance is in imported Blender mesh units.
    """
    def same_vertex(left, right):
        return left[1] == right[1] and all(abs(a - b) <= tolerance
                                          for a, b in zip(left[0], right[0]))

    def same_triangle(left, right):
        return any(all(same_vertex(left[index], right[(index + shift) % 3])
                       for index in range(3)) for shift in range(3))

    for kind, matcher in (("vertices", same_vertex), ("triangles", same_triangle)):
        remaining = list(expected[kind])
        require(len(actual[kind]) == len(remaining), f"FBX roundtrip changed {kind} count")
        for item in actual[kind]:
            match = next((index for index, candidate in enumerate(remaining)
                          if matcher(item, candidate)), None)
            require(match is not None,
                    f"FBX roundtrip changed bound {kind} geometry or triangle winding")
            remaining.pop(match)
        require(not remaining, f"FBX roundtrip lost bound {kind} geometry")


def read_mapping(path, armature):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate mapping key: {key}")
            result[key] = value
        return result

    with Path(path).open(encoding="utf-8-sig") as stream:
        document = json.load(stream, object_pairs_hook=unique_keys)
    require(type(document) is dict and set(document) == {"schema_version", "profile", "parts"},
            "Mapping must contain only schema_version, profile and parts")
    require(type(document["schema_version"]) is int and document["schema_version"] == 1,
            "Unsupported mapping schema_version")
    profile = document["profile"]
    require(profile in ("hair_marker", "full_body_experimental"), "Unsupported mapping profile")
    required = ("head",) if profile == "hair_marker" else REQUIRED_PARTS
    allowed = required if profile == "hair_marker" else REQUIRED_PARTS + OPTIONAL_PARTS
    parts = document["parts"]
    require(type(parts) is dict, "Mapping parts must be an object")
    require(set(required) <= set(parts), "Mapping is missing required profile parts")
    require(set(parts) <= set(allowed), "Unknown or unsupported profile part ID")
    validated = {}
    for role, entry in parts.items():
        require(re.fullmatch(r"[a-z_]+", role) is not None, "Invalid body part ID")
        require(type(entry) is dict and set(entry) <= PART_FIELDS,
                f"Unknown fields in part {role}")
        require({"bone", "radius_start_ratio", "radius_end_ratio"} <= set(entry),
                f"Part {role} needs bone and both radii")
        name = entry["bone"]
        require(type(name) is str and name in armature.data.bones,
                f"Part {role} must name an observed reference bone")
        bone = armature.data.bones[name]
        require(bone.use_deform, f"Part {role} must use a deform bone")
        length = (bone.tail_local - bone.head_local).length
        require(math.isfinite(length) and length > 1e-6,
                f"Part {role} uses a zero-length/invalid bone")
        start = finite_number(entry.get("length_start_ratio", 0), role + " start")
        end = finite_number(entry.get("length_end_ratio", 1), role + " end")
        require(-2 <= start < end <= 3, f"Part {role} needs -2 <= start < end <= 3")
        radii = [finite_number(entry[key], role + " " + key)
                 for key in ("radius_start_ratio", "radius_end_ratio")]
        require(all(0.001 <= value <= 10 for value in radii),
                f"Part {role} radii must be in [0.001, 10] bone lengths")
        validated[role] = {
            "bone": name, "radius_start_ratio": radii[0],
            "radius_end_ratio": radii[1], "length_start_ratio": start,
            "length_end_ratio": end,
        }
    return {"schema_version": 1, "profile": profile, "parts": validated}


def remove_private_geometry(armature):
    count = sum(obj.type == "MESH" for obj in bpy.context.scene.objects)
    world = armature.matrix_world.copy()
    armature.parent = None
    armature.matrix_world = world
    for obj in list(bpy.data.objects):
        if obj != armature:
            bpy.data.objects.remove(obj, do_unlink=True)
    armature.animation_data_clear()
    armature.data.animation_data_clear()
    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    for attribute in ("meshes", "materials", "textures", "images", "actions"):
        collection = getattr(bpy.data, attribute)
        for block in list(collection):
            collection.remove(block, do_unlink=True)
    # Do not carry imported custom properties into generated asset metadata.
    for owner in (armature, armature.data, *armature.data.bones, *armature.pose.bones):
        for key in list(owner.keys()):
            del owner[key]
    return count


def material_for(role):
    if role == "head":
        label, color = "SW_Original_HairMarker", (0.45, 0.13, 0.035, 1)
    elif role.startswith("hand") or role == "neck":
        label, color = "SW_Original_Mannequin", (0.48, 0.31, 0.18, 1)
    elif role.startswith("foot") or role.startswith("lower_leg"):
        label, color = "SW_Original_Boots", (0.045, 0.055, 0.065, 1)
    elif "arm" in role:
        label, color = "SW_Original_Leather", (0.19, 0.095, 0.04, 1)
    else:
        label, color = "SW_Original_Ranger", (0.075, 0.18, 0.095, 1)
    mat = bpy.data.materials.get(label)
    if mat is None:
        mat = bpy.data.materials.new(label)
        mat.diffuse_color = color
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = 0.82
        mat[MARKER_KEY] = True
    return mat


def create_geometry(armature, mapping):
    vertices, faces, face_uvs, face_materials, weights = [], [], [], [], {}
    materials = []
    for role, part in mapping["parts"].items():
        bone = armature.data.bones[part["bone"]]
        direction = bone.tail_local - bone.head_local
        length = direction.length
        axis = direction.normalized()
        helper = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
        tangent = axis.cross(helper).normalized()
        bitangent = axis.cross(tangent).normalized()
        start = bone.head_local + direction * part["length_start_ratio"]
        end = bone.head_local + direction * part["length_end_ratio"]
        first = len(vertices)
        for center, radius in ((start, part["radius_start_ratio"] * length),
                               (end, part["radius_end_ratio"] * length)):
            for side in range(SIDES):
                angle = 2 * math.pi * side / SIDES
                vertices.append(center + radius * (math.cos(angle) * tangent
                                                     + math.sin(angle) * bitangent))
        vertices.extend((start, end))
        weights.setdefault(bone.name, []).extend(range(first, first + 2 * SIDES + 2))
        material = material_for(role)
        if material not in materials:
            materials.append(material)
        material_index = materials.index(material)

        def triangle(indices, uv):
            faces.append(tuple(first + index for index in indices))
            face_uvs.append(uv)
            face_materials.append(material_index)

        for side in range(SIDES):
            nxt = (side + 1) % SIDES
            low, high = side / SIDES, (side + 1) / SIDES
            triangle((side, nxt, SIDES + nxt), ((low, 0), (high, 0), (high, 1)))
            triangle((side, SIDES + nxt, SIDES + side), ((low, 0), (high, 1), (low, 1)))
            angle, next_angle = side * 2 * math.pi / SIDES, (side + 1) * 2 * math.pi / SIDES
            ring_uv = (0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle))
            next_uv = (0.5 + 0.5 * math.cos(next_angle), 0.5 + 0.5 * math.sin(next_angle))
            triangle((2 * SIDES, nxt, side), ((0.5, 0.5), next_uv, ring_uv))
            triangle((2 * SIDES + 1, SIDES + side, SIDES + nxt),
                     ((0.5, 0.5), ring_uv, next_uv))
    mesh_data = bpy.data.meshes.new("SW_Original_RangerMesh")
    mesh_data.from_pydata(vertices, [], faces)
    mesh_data.update()
    mesh = bpy.data.objects.new("SW_RangerPlaceholder", mesh_data)
    bpy.context.scene.collection.objects.link(mesh)
    mesh.parent = armature
    mesh.matrix_parent_inverse = Matrix.Identity(4)
    mesh.matrix_basis = Matrix.Identity(4)
    for name, indices in weights.items():
        mesh.vertex_groups.new(name=name).add(indices, 1.0, "REPLACE")
    modifier = mesh.modifiers.new("SW_PrivateNativeRig", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    for material in materials:
        mesh_data.materials.append(material)
    uv = mesh_data.uv_layers.new(name="SW_OriginalUV")
    for polygon, coords, material_index in zip(mesh_data.polygons, face_uvs, face_materials):
        polygon.material_index = material_index
        for loop_index, coordinate in zip(polygon.loop_indices, coords):
            uv.data[loop_index].uv = coordinate
    mesh[MARKER_KEY] = True
    mesh[MAPPING_KEY] = json.dumps(mapping, sort_keys=True)
    return mesh


def validate_scene(armature, mesh, expected, *, imported=False):
    objects = list(bpy.context.scene.objects)
    require(len(objects) == 2 and {obj.type for obj in objects} == {"MESH", "ARMATURE"},
            "Candidate must contain only one mesh and one armature")
    compare_skeleton(skeleton_signature(armature), expected, roundtrip=imported)
    require(not armature.animation_data and not mesh.animation_data and not bpy.data.actions,
            "Candidate contains animation data")
    require(mesh.parent == armature, "Candidate mesh must be parented to the native rig")
    close_values(matrix_values(mesh.matrix_world), matrix_values(armature.matrix_world),
                 "Mesh versus armature transform", 1e-4 if imported else 1e-6)
    modifiers = [mod for mod in mesh.modifiers if mod.type == "ARMATURE"]
    require(len(modifiers) == 1 and len(mesh.modifiers) == 1 and modifiers[0].object == armature,
            "Candidate needs only its native armature modifier")
    require(mesh.data.vertices and mesh.data.polygons, "Candidate mesh is empty")
    require(mesh.data.uv_layers.active is not None, "Candidate mesh needs original UVs")
    groups = {group.index: group.name for group in mesh.vertex_groups}
    used = set()
    for vertex in mesh.data.vertices:
        require(all(math.isfinite(value) for value in vertex.co), "Nonfinite mesh vertex")
        require(len(vertex.groups) == 1, "Each authored vertex must have exactly one influence")
        influence = vertex.groups[0]
        name = groups[influence.group]
        require(name in armature.data.bones and armature.data.bones[name].use_deform,
                "Vertex group must refer to a native deform bone")
        require(math.isfinite(influence.weight) and abs(influence.weight - 1) <= 1e-6,
                "Vertex weights must be finite, positive and normalized to one")
        used.add(name)
    require(used == set(groups.values()), "Candidate has an empty vertex group")
    for polygon in mesh.data.polygons:
        require(len(polygon.vertices) == 3, "Candidate topology must be triangulated")
        a, b, c = (mesh.data.vertices[index].co for index in polygon.vertices)
        require((b - a).cross(c - a).length > 1e-12, "Candidate has a degenerate triangle")
        require(0 <= polygon.material_index < len(mesh.data.materials), "Invalid material index")
    for loop in mesh.data.uv_layers.active.data:
        require(all(math.isfinite(value) for value in loop.uv), "Nonfinite UV coordinate")
    require(bool(mesh.data.materials), "Candidate requires original solid-color materials")
    for material in mesh.data.materials:
        require(material is not None and material.name.startswith("SW_Original_"),
                "Unexpected candidate material")
        require(not material.use_nodes or not any(node.type == "TEX_IMAGE"
                for node in material.node_tree.nodes), "Candidate must not contain imported textures")
    return {
        "status": STATUS, "vertices": len(mesh.data.vertices),
        "triangles": len(mesh.data.polygons), "native_bones": len(armature.data.bones),
        "weighted_bones": sorted(used), "influences_per_vertex": 1,
        "bone_names_hierarchy_rest_world_checked": True,
        "uvs_materials_finite_geometry_checked": True,
        "gameplay_tested": False, "creator_kit_import_tested": False,
        "scope": "Blender asset checks only; native animations and gameplay require in-game testing",
    }


def export_fbx(path, armature, mesh):
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False, use_armature_deform_only=False, bake_anim=False,
        use_custom_props=False, global_scale=1.0, apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE", axis_forward="-Y", axis_up="Z",
        bake_space_transform=False, use_triangles=True, use_mesh_modifiers=True,
        mesh_smooth_type="FACE", path_mode="STRIP", embed_textures=False,
    )


def inspect(args):
    target = private_output_path(args.report)
    require(not target.exists(), f"Refusing to overwrite report: {target}")
    reference = source_file(args.reference_fbx)
    armature = import_reference(reference, args.armature)
    bones = [{"name": bone.name, "parent": bone.parent.name if bone.parent else None,
              "deform": bool(bone.use_deform), "rest_length": float(bone.length)}
             for bone in armature.data.bones]
    new_report(target, {
        "schema_version": 1, "status": STATUS,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "armature_name": armature.name, "candidate_bones": bones,
        "mapping_template": {"schema_version": 1, "profile": "hair_marker", "parts": {
            role: {"bone": None, "radius_start_ratio": None, "radius_end_ratio": None}
            for role in ("head",)}},
        "mapping_help": "Hair-marker profile: fit the original solid marker above the scalp by filling the head role with the observed head deform bone and finite radii in bone lengths. Optional length_start_ratio/end_ratio default to 0/1. Select the actual player reference rig manually in Creator Kit; no game bone name is inferred. Full-body experiments require a separate explicit profile and must not be bound as hair.",
        "privacy": "Local metadata only. Native skeleton and derived FBX/BLEND outputs remain private.",
    })


def build(args):
    output = private_output_path(args.output_dir)
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
            "Output directory must be absent or empty; existing files are preserved")
    reference = source_file(args.reference_fbx)
    armature = import_reference(reference, args.armature)
    mapping = read_mapping(args.mapping, armature)
    expected = skeleton_signature(armature)
    discarded = remove_private_geometry(armature)
    mesh = create_geometry(armature, mapping)
    bpy.context.view_layer.update()
    result = validate_scene(armature, mesh, expected)
    armature[SIGNATURE_KEY] = json.dumps(expected, sort_keys=True)
    result.update({
        "schema_version": 1, "blender_version": bpy.app.version_string,
        "profile": mapping["profile"],
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "discarded_reference_mesh_objects": discarded,
        "provenance": {"geometry": "original procedural octagonal solids",
                       "weights": "original single-bone assignments from explicit user mapping",
                       "materials_uvs": "original solid colors and procedural UVs",
                       "skeleton": "private reference retained unchanged; never publish FBX/BLEND"},
        "mapping": mapping,
        "export": {"animations": False, "leaf_bones": False, "deform_bone_pruning": False,
                   "axis_forward": "-Y", "axis_up": "Z", "global_scale": 1.0},
    })
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "generated.blend"))
    export_fbx(output / "candidate.fbx", armature, mesh)
    result["generated_blend_sha256"] = hashlib.sha256(
        (output / "generated.blend").read_bytes()).hexdigest()
    result["candidate_fbx_sha256"] = hashlib.sha256(
        (output / "candidate.fbx").read_bytes()).hexdigest()
    new_report(output / "validation.json", result)


def validate(args):
    target = private_output_path(args.report)
    require(not target.exists(), f"Refusing to overwrite report: {target}")
    source = Path(args.blend).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == ".blend", "Need generated .blend input")
    # Disable embedded auto-run scripts when opening any private Blender input.
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    require(len(rigs) == len(meshes) == 1, "Need exactly one candidate rig and mesh")
    armature, mesh = rigs[0], meshes[0]
    require(SIGNATURE_KEY in armature and mesh.get(MARKER_KEY) is True,
            "Input lacks generated candidate provenance and reference signature")
    expected = json.loads(armature[SIGNATURE_KEY])
    result = validate_scene(armature, mesh, expected)
    require(MAPPING_KEY in mesh, "Input lacks its original profile mapping")
    mapping = json.loads(mesh[MAPPING_KEY])
    require(mapping.get("profile") in ("hair_marker", "full_body_experimental"),
            "Generated candidate has an unsupported profile")
    authored_geometry = geometry_signature(mesh)
    result["schema_version"] = 1
    result["blender_version"] = bpy.app.version_string
    result["profile"] = mapping["profile"]
    result["generated_blend_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    if args.roundtrip_fbx:
        reference = source_file(args.roundtrip_fbx)
        armature = import_reference(reference)
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
        require(len(meshes) == 1, "Roundtrip FBX must contain only one mesh")
        roundtrip = validate_scene(armature, meshes[0], expected, imported=True)
        require(roundtrip["vertices"] == result["vertices"] and
                roundtrip["triangles"] == result["triangles"] and
                roundtrip["weighted_bones"] == result["weighted_bones"],
                "FBX roundtrip changed topology or weighted bone set")
        compare_geometry(geometry_signature(meshes[0]), authored_geometry)
        result["fbx_roundtrip_checked"] = True
        result["fbx_bound_geometry_multisets_checked"] = True
        result["candidate_fbx_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
        result["fbx_roundtrip_note"] = "Names, hierarchy, bind transforms, coordinate/bone vertex multisets, oriented triangle-corner multisets, weights and materials checked. Geometry tolerance: 0.0001 imported Blender units. Terminal bone-tail display lengths are reconstructed by the FBX importer. This does not validate Unreal/Creator Kit import."
    new_report(target, result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "build"):
        child = commands.add_parser(name)
        child.add_argument("--reference-fbx", required=True)
        child.add_argument("--armature", help="Explicit imported armature object name, if needed")
        if name == "inspect":
            child.add_argument("--report", required=True)
        else:
            child.add_argument("--mapping", required=True)
            child.add_argument("--output-dir", required=True)
    child = commands.add_parser("validate")
    child.add_argument("--blend", required=True)
    child.add_argument("--report", required=True)
    child.add_argument("--roundtrip-fbx")
    args = parser.parse_args(argv)
    require(bpy.app.version >= (4, 3, 0), "This tooling targets Blender 4.3 or later")
    {"inspect": inspect, "build": build, "validate": validate}[args.command](args)
    print("SHADOW_WIZARD_AVATAR_OK: " + args.command + "; " + STATUS)


if __name__ == "__main__":
    try:
        main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print("SHADOW_WIZARD_AVATAR_ERROR: " + str(error), file=sys.stderr)
        sys.exit(2)
