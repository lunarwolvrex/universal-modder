"""Run the avatar authoring tool with real Blender and synthetic original assets.

Normal Python entry point (not a pytest test)::

    python tests/blender_avatar_smoke.py --blender blender

All FBX/BLEND fixtures and reports are created in a temporary directory.
No Hogwarts/Creator Kit assets, runtime, or compatibility are tested here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PROJECT = Path(__file__).resolve().parent.parent
TOOL = PROJECT / "tools" / "blender_avatar.py"


def fixture(directory):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig_data = bpy.data.armatures.new("SW_TestOriginalRigData")
    rig = bpy.data.objects.new("SW_TestOriginalRig", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    root = rig_data.edit_bones.new("OriginalRoot")
    root.head, root.tail = (0, 0, 0), (0, 0, 0.5)
    spine = rig_data.edit_bones.new("OriginalSpine")
    spine.head, spine.tail, spine.parent = (0, 0, 0.5), (0, 0, 1.5), root
    head = rig_data.edit_bones.new("OriginalHead")
    head.head, head.tail, head.parent = (0, 0, 1.5), (0, 0, 1.8), spine
    extra = rig_data.edit_bones.new("OriginalUnweightedBone")
    extra.head, extra.tail, extra.parent = (0, 0, 1), (0.3, 0, 1), spine
    bpy.ops.object.mode_set(mode="OBJECT")
    # Nonzero world translation exercises parent/world-transform preservation.
    rig.location = (0.25, -0.5, 0.1)
    dummy_data = bpy.data.meshes.new("SW_TestReferenceGeometryNeverCopy")
    dummy_data.from_pydata([(42, 43, 44), (43, 43, 44), (42, 44, 44)], [], [(0, 1, 2)])
    dummy_data.update()
    dummy = bpy.data.objects.new("SW_TestReferenceGeometryNeverCopy", dummy_data)
    bpy.context.scene.collection.objects.link(dummy)
    dummy.parent = rig
    dummy.vertex_groups.new(name="OriginalHead").add([0, 1, 2], 1, "REPLACE")
    modifier = dummy.modifiers.new("ReferenceDummySkin", "ARMATURE")
    modifier.object = rig
    dummy.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=str(directory / "original-reference.fbx"), use_selection=True,
        object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
        use_armature_deform_only=False, bake_anim=False, axis_forward="-Y", axis_up="Z",
        apply_unit_scale=True, global_scale=1, bake_space_transform=False,
    )
    mapping = {
        "schema_version": 1, "profile": "hair_marker", "parts": {"head": {
            "bone": "OriginalHead", "radius_start_ratio": 0.35,
            "radius_end_ratio": 0.3, "length_start_ratio": 0.65,
            "length_end_ratio": 1.3,
        }},
    }
    # Windows PowerShell 5.1 Out-File -Encoding utf8 emits a BOM.
    (directory / "mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8-sig")
    print("SHADOW_WIZARD_SYNTHETIC_FIXTURE_OK")


def run_blender(blender, script, arguments, *, succeeds=True):
    command = [blender, "--background", "--factory-startup", "--python-exit-code", "7",
               "--python", str(script), "--", *map(str, arguments)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
    successful = result.returncode == 0
    if successful != succeeds:
        raise AssertionError(f"Unexpected Blender exit {result.returncode}: {result.stdout}\n{result.stderr}")
    if succeeds and script == TOOL and "SHADOW_WIZARD_AVATAR_OK" not in result.stdout:
        raise AssertionError("Tool exited without its success marker")
    if not succeeds and "SHADOW_WIZARD_AVATAR_ERROR" not in result.stderr:
        raise AssertionError(f"Expected deliberate validation rejection: {result.stdout}\n{result.stderr}")
    return result


def check_generated(arguments):
    import bpy

    source = Path(arguments[0])
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    objects = list(bpy.context.scene.objects)
    assert len(objects) == 2
    mesh = next(obj for obj in objects if obj.type == "MESH")
    rig = next(obj for obj in objects if obj.type == "ARMATURE")
    assert {bone.name for bone in rig.data.bones} == {
        "OriginalRoot", "OriginalSpine", "OriginalHead", "OriginalUnweightedBone"}
    assert rig.data.bones["OriginalHead"].parent.name == "OriginalSpine"
    assert rig.data.bones["OriginalSpine"].parent.name == "OriginalRoot"
    assert rig.data.bones["OriginalUnweightedBone"].parent.name == "OriginalSpine"
    assert len(mesh.data.vertices) == 18 and len(mesh.data.polygons) == 32
    assert all(len(vertex.groups) == 1 and vertex.groups[0].weight == 1
               for vertex in mesh.data.vertices)
    assert [group.name for group in mesh.vertex_groups] == ["OriginalHead"]
    assert all(abs(value) < 3 for vertex in mesh.data.vertices for value in vertex.co)
    assert not any("NeverCopy" in obj.name for obj in objects)
    assert not bpy.data.images and not bpy.data.actions
    print("SHADOW_WIZARD_GENERATED_INSPECTION_OK")


def corrupt_candidate(arguments):
    """Move one exported vertex while preserving counts and all skin weights."""
    import importlib.util
    import bpy

    spec = importlib.util.spec_from_file_location("shadow_wizard_avatar_test_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    armature = module.import_reference(Path(arguments[0]))
    mesh = next(obj for obj in bpy.context.scene.objects if obj.type == "MESH")
    original_counts = (len(mesh.data.vertices), len(mesh.data.polygons))
    mesh.data.vertices[0].co.x += 0.01
    mesh.data.update()
    assert (len(mesh.data.vertices), len(mesh.data.polygons)) == original_counts
    module.export_fbx(Path(arguments[1]), armature, mesh)
    print("SHADOW_WIZARD_CORRUPTED_SAME_COUNT_FIXTURE_OK")


def smoke(blender, directory):
    checks = 0
    run_blender(blender, Path(__file__), ["fixture", directory])
    reference = directory / "original-reference.fbx"
    mapping = directory / "mapping.json"
    run_blender(blender, TOOL, ["inspect", "--reference-fbx", reference,
                              "--report", directory / "inspect.json"])
    inspection = json.loads((directory / "inspect.json").read_text())
    assert inspection["mapping_template"]["profile"] == "hair_marker"
    assert set(inspection["mapping_template"]["parts"]) == {"head"}
    assert inspection["mapping_template"]["parts"]["head"]["bone"] is None
    checks += 1
    output = directory / "candidate"
    build = ["build", "--reference-fbx", reference, "--mapping", mapping, "--output-dir", output]
    run_blender(blender, TOOL, build)
    report = json.loads((output / "validation.json").read_text())
    assert report["discarded_reference_mesh_objects"] == 1
    assert report["weighted_bones"] == ["OriginalHead"]
    assert report["native_bones"] == 4
    assert report["profile"] == "hair_marker"
    assert report["candidate_fbx_sha256"] == hashlib.sha256(
        (output / "candidate.fbx").read_bytes()).hexdigest()
    assert report["generated_blend_sha256"] == hashlib.sha256(
        (output / "generated.blend").read_bytes()).hexdigest()
    assert report["gameplay_tested"] is False and report["creator_kit_import_tested"] is False
    checks += 1
    run_blender(blender, Path(__file__), ["check", output / "generated.blend"])
    checks += 1
    run_blender(blender, TOOL, ["validate", "--blend", output / "generated.blend",
                              "--roundtrip-fbx", output / "candidate.fbx",
                              "--report", directory / "roundtrip.json"])
    roundtrip = json.loads((directory / "roundtrip.json").read_text())
    assert roundtrip["fbx_roundtrip_checked"] is True
    assert roundtrip["fbx_bound_geometry_multisets_checked"] is True
    assert roundtrip["profile"] == "hair_marker"
    assert roundtrip["candidate_fbx_sha256"] == report["candidate_fbx_sha256"]
    assert roundtrip["generated_blend_sha256"] == report["generated_blend_sha256"]
    checks += 1
    corrupted = directory / "same-count-corrupted.fbx"
    run_blender(blender, Path(__file__), ["corrupt", output / "candidate.fbx", corrupted])
    rejected = run_blender(blender, TOOL, [
        "validate", "--blend", output / "generated.blend", "--roundtrip-fbx", corrupted,
        "--report", directory / "corrupted-report.json"], succeeds=False)
    assert "bound vertices geometry" in rejected.stderr
    assert not (directory / "corrupted-report.json").exists()
    checks += 1
    # Existing generated outputs must be preserved byte for byte.
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    run_blender(blender, TOOL, build, succeeds=False)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    checks += 1
    baseline = json.loads(mapping.read_text(encoding="utf-8-sig"))
    invalid_documents = []
    missing = json.loads(mapping.read_text(encoding="utf-8-sig"))
    missing["parts"] = {}
    invalid_documents.append(missing)
    unknown_bone = json.loads(mapping.read_text(encoding="utf-8-sig"))
    unknown_bone["parts"]["head"]["bone"] = "InventedGameBone"
    invalid_documents.append(unknown_bone)
    nan_radius = json.loads(mapping.read_text(encoding="utf-8-sig"))
    nan_radius["parts"]["head"]["radius_start_ratio"] = float("nan")
    invalid_documents.append(nan_radius)
    inverted = json.loads(mapping.read_text(encoding="utf-8-sig"))
    inverted["parts"]["head"]["length_end_ratio"] = 0
    invalid_documents.append(inverted)
    wrong_slot = json.loads(mapping.read_text(encoding="utf-8-sig"))
    wrong_slot["parts"]["torso"] = baseline["parts"]["head"]
    invalid_documents.append(wrong_slot)
    unknown_field = json.loads(mapping.read_text(encoding="utf-8-sig"))
    unknown_field["parts"]["head"]["copy_reference_geometry"] = True
    invalid_documents.append(unknown_field)
    for index, document in enumerate(invalid_documents):
        invalid = directory / f"invalid-{index}.json"
        invalid.write_text(json.dumps(document), encoding="utf-8")
        target = directory / f"invalid-output-{index}"
        run_blender(blender, TOOL, ["build", "--reference-fbx", reference,
                                  "--mapping", invalid, "--output-dir", target], succeeds=False)
        assert not target.exists()
        checks += 1
    duplicate = directory / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1,"profile":"hair_marker","parts":{}}',
                         encoding="utf-8")
    run_blender(blender, TOOL, ["build", "--reference-fbx", reference,
                              "--mapping", duplicate, "--output-dir", directory / "duplicate-output"],
                succeeds=False)
    assert not (directory / "duplicate-output").exists()
    checks += 1
    # A private report/asset must not be written to tracked project locations.
    unsafe = PROJECT / "docs" / "SHOULD_NOT_BE_WRITTEN-private-rig.json"
    assert not unsafe.exists()
    run_blender(blender, TOOL, ["inspect", "--reference-fbx", reference, "--report", unsafe],
                succeeds=False)
    assert not unsafe.exists()
    checks += 1
    print(f"{checks} Blender synthetic checks passed; no Creator Kit or Hogwarts gameplay tested.")


def main():
    if "--" in sys.argv:
        arguments = sys.argv[sys.argv.index("--") + 1:]
        if arguments[0] == "fixture":
            fixture(Path(arguments[1]))
        elif arguments[0] == "check":
            check_generated(arguments[1:])
        elif arguments[0] == "corrupt":
            corrupt_candidate(arguments[1:])
        else:
            raise ValueError("Unknown Blender smoke action")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    args = parser.parse_args()
    blender = shutil.which(args.blender)
    if blender is None:
        raise SystemExit("Blender executable is required for the synthetic smoke test")
    with tempfile.TemporaryDirectory(prefix="shadow-wizard-original-avatar-") as name:
        smoke(blender, Path(name))


if __name__ == "__main__":
    main()
