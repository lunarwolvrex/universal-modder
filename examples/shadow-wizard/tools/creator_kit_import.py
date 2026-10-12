"""Guarded FBX import for the OFFICIAL Hogwarts Legacy Creator Kit.

Create and Set Mod to the job's content mod manually in the Creator Kit first.
Inside its Python console, load this module and call ``run(job_path)``. Running
``py "C:/.../tools/creator_kit_import.py"`` uses the project's ignored
``.local/appearance-job.json``. This script never creates a mod, registers an
avatar, changes a CharacterPiece, or touches a player Blueprint/controller.

The schema_version=1 job requires fbx_path, fbx_sha256, validation_report_path,
validation_report_sha256, skeleton_asset and physics_asset. Use the ACTUAL
native asset paths observed in your Creator Kit,
not guessed game paths. Optional plugin_name, asset_name, destination_path and
report_path default to this project's owned hair-placeholder import location.
The FBX must be the original generated hair marker prepared by the companion
Blender workflow, with the host's private reference rig. Private FBX files,
Creator Kit assets and reports belong outside Git or in the ignored .local
directory. Never distribute its embedded host rig.

Generic Unreal 4.27 APIs are checked at runtime before importing anything. This
automation has not been exercised in the Hogwarts Creator Kit or the game.
Import success does not establish animation compatibility or a working mod.
After import, follow the documented manual CharacterPiece / AvatarPreset
binding, official packaging, and in-game checks. Failed partial imports remain
unsaved for manual review; this script never deletes or overwrites assets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN = "ShadowWizardAppearance"
DEFAULT_ASSET = "SK_SWPlaceholderHair"
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
ASSET_TOKEN = re.compile(r"[A-Za-z0-9_]+\Z")


class ImportFailure(RuntimeError):
    """A failed guard or import, with the reviewable report attached."""

    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _local_file(value, base):
    _require(isinstance(value, str) and value.strip(), "Expected a nonempty local file path")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def _private_report_path(value, base):
    target = _local_file(value, base)
    _require(target.suffix.lower() == ".json", "Report must have a .json suffix")
    _require(not target.exists(), f"Refusing to overwrite report: {target}")
    for parent in (target.parent, *target.parent.parents):
        if not (parent / ".git").exists():
            continue
        # /workspace and /tmp can have sandbox .git guard directories which
        # are not repositories. Never mistake those for real checkouts.
        try:
            found = subprocess.run(
                ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=False,
            )
        except FileNotFoundError as exc:
            raise ValueError("Git is required to verify an in-checkout report is ignored") from exc
        if found.returncode != 0:
            continue
        repo = Path(found.stdout.strip()).resolve()
        try:
            target.relative_to((PROJECT_ROOT / ".local").resolve())
            in_local = True
        except ValueError:
            in_local = False
        _require(in_local,
                 "Reports inside Git must use this project's ignored .local directory")
        ignored = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "--", str(target)],
            capture_output=True, text=True, check=False,
        )
        _require(ignored.returncode == 0, "The report path must be ignored by Git")
        break
    return target


def _asset_path(value, label):
    _require(isinstance(value, str) and value.startswith("/"),
             f"{label} must be an observed native /Mount/Folder/Asset path")
    package, separator, object_name = value.partition(".")
    components = package[1:].split("/")
    _require(len(components) >= 2 and all(ASSET_TOKEN.fullmatch(part) for part in components),
             f"{label} contains an invalid asset path")
    _require(not separator or object_name == components[-1],
             f"{label} must identify the asset itself, without a subobject or class wrapper")
    return package


def _hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _load_job(path):
    job_path = Path(path).expanduser().resolve()
    _require(job_path.is_file() and job_path.suffix.lower() == ".json",
             "Job must be an existing .json file")
    with job_path.open(encoding="utf-8-sig") as stream:
        job = json.load(stream)
    _require(isinstance(job, dict), "Job must be a JSON object")
    _require(type(job.get("schema_version")) is int and job["schema_version"] == 1,
             "Only schema_version 1 jobs are supported")
    return job_path, job


def _validate_job(job_path, job):
    plugin = job.get("plugin_name", DEFAULT_PLUGIN)
    asset = job.get("asset_name", DEFAULT_ASSET)
    _require(isinstance(plugin, str) and TOKEN.fullmatch(plugin), "Invalid plugin_name")
    _require(isinstance(asset, str) and asset.startswith("SK_")
             and TOKEN.fullmatch(asset[3:]), "asset_name must be an identifier beginning SK_")
    destination = f"/{plugin}/AvatarPresets/HairStyle/{asset[3:]}"
    _require(job.get("destination_path", destination) == destination,
             f"destination_path must be the owned import folder {destination}")
    source = _local_file(job.get("fbx_path"), job_path.parent)
    _require(source.is_file() and source.suffix.lower() == ".fbx",
             "fbx_path must be an existing FBX file")
    expected_hash = job.get("fbx_sha256")
    _require(isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash),
             "fbx_sha256 must be the exact lowercase SHA-256 from asset preparation")
    _require(_hash(source) == expected_hash, "FBX SHA-256 mismatch; revalidate and prepare a new job")
    validation_path = _local_file(job.get("validation_report_path"), job_path.parent)
    _require(validation_path.is_file() and validation_path.suffix.lower() == ".json",
             "validation_report_path must be the existing Blender roundtrip JSON report")
    validation_hash = job.get("validation_report_sha256")
    _require(isinstance(validation_hash, str) and re.fullmatch(r"[0-9a-f]{64}", validation_hash),
             "validation_report_sha256 must be the exact lowercase report SHA-256")
    _require(_hash(validation_path) == validation_hash, "Blender validation report SHA-256 mismatch")
    with validation_path.open(encoding="utf-8-sig") as stream:
        validation = json.load(stream)
    _require(isinstance(validation, dict) and type(validation.get("schema_version")) is int
             and validation["schema_version"] == 1, "Unsupported Blender validation report schema")
    _require(validation.get("profile") == "hair_marker", "Only the validated original hair_marker profile can be imported")
    _require(validation.get("status") == "asset_candidate_only_not_hogwarts_tested",
             "Expected the original Blender asset-candidate validation report")
    _require(validation.get("influences_per_vertex") == 1,
             "Only the original single-bone influence policy is supported")
    _require(validation.get("gameplay_tested") is False and validation.get("creator_kit_import_tested") is False,
             "Blender validation must not claim native Creator Kit/game tests")
    _require(validation.get("fbx_roundtrip_checked") is True,
             "Run Blender FBX roundtrip validation before importing")
    _require(validation.get("candidate_fbx_sha256") == expected_hash,
             "Blender report does not validate this candidate FBX")
    for field in ("bone_names_hierarchy_rest_world_checked", "uvs_materials_finite_geometry_checked",
                  "fbx_bound_geometry_multisets_checked"):
        _require(validation.get(field) is True, f"Blender report lacks required validation: {field}")
    return {
        "plugin_name": plugin,
        "asset_name": asset,
        "destination_path": destination,
        "fbx_path": str(source),
        "fbx_sha256": expected_hash,
        "validation_report_path": str(validation_path),
        "validation_report_sha256": validation_hash,
        "skeleton_asset": _asset_path(job.get("skeleton_asset"), "skeleton_asset"),
        "physics_asset": _asset_path(job.get("physics_asset"), "physics_asset"),
    }


def _api(unreal):
    for name in ("FbxImportUI", "AssetImportTask", "Skeleton", "PhysicsAsset", "SkeletalMesh",
                 "MaterialInterface", "FBXImportType", "SystemLibrary", "Paths",
                 "EditorAssetLibrary", "EditorLoadingAndSavingUtils", "AssetToolsHelpers", "load_asset"):
        _require(hasattr(unreal, name), f"Required Unreal API is unavailable: {name}")
    for owner, name in ((unreal.SystemLibrary, "get_engine_version"),
                        (unreal.Paths, "project_dir"),
                        (unreal.EditorAssetLibrary, "does_asset_exist"),
                        (unreal.EditorAssetLibrary, "list_assets"),
                        (unreal.EditorAssetLibrary, "save_loaded_asset"),
                        (unreal.EditorLoadingAndSavingUtils, "get_dirty_content_packages"),
                        (unreal.AssetToolsHelpers, "get_asset_tools")):
        _require(callable(getattr(owner, name, None)), f"Required Unreal method is unavailable: {name}")
    _require(hasattr(unreal.FBXImportType, "FBXIT_SKELETAL_MESH"),
             "Required Unreal FBX skeletal import enum is unavailable")
    version = unreal.SystemLibrary.get_engine_version()
    _require(isinstance(version, str) and re.match(r"^4\.27(?:\.|-)", version),
             f"Only the checked Unreal 4.27 API contract is supported; observed {version!r}")
    return version


def _get(obj, name):
    _require(callable(getattr(obj, "get_editor_property", None)), "Missing get_editor_property API")
    try:
        return obj.get_editor_property(name)
    except Exception as exc:
        raise ValueError(f"Required editor property is unavailable: {name}") from exc


def _set_checked(obj, values):
    _require(callable(getattr(obj, "set_editor_property", None)), "Missing set_editor_property API")
    # Probe every property before changing this transient options object.
    for name in values:
        _get(obj, name)
    for name, value in values.items():
        obj.set_editor_property(name, value)


def _path(obj):
    _require(callable(getattr(obj, "get_path_name", None)), "Asset has no get_path_name API")
    return _asset_path(obj.get_path_name(), "native asset")


def _reference(unreal, path, expected_class, label):
    obj = unreal.load_asset(path)
    _require(obj is not None and isinstance(obj, expected_class), f"{label} must load as {expected_class.__name__}")
    _require(_path(obj) == path, f"{label} resolved to an unexpected asset")
    return obj


def _list(unreal, path):
    values = unreal.EditorAssetLibrary.list_assets(path, recursive=True, include_folder=False)
    _require(values is not None and not isinstance(values, (str, bytes)),
             "Asset registry did not return a path array")
    return {_asset_path(value, "asset registry result") for value in values}


def _dirty_packages(unreal):
    values = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    _require(values is not None and not isinstance(values, (str, bytes)),
             "Dirty-content-package API did not return a package array")
    paths = set()
    for package in values:
        _require(callable(getattr(package, "get_path_name", None)),
                 "Dirty package lacks the native get_path_name API")
        path = package.get_path_name()
        _require(isinstance(path, str) and path.startswith("/"),
                 "Dirty package returned an unexpected path")
        paths.add(path)
    return paths


def _dirty_guard(unreal, before, settings, report):
    current = _dirty_packages(unreal)
    newly_dirty = current - before
    targets = {settings["skeleton_asset"], settings["physics_asset"]}
    unexpected = {path for path in newly_dirty
                  if not path.startswith(settings["destination_path"] + "/") or path in targets}
    report["newly_dirty_package_paths"] = sorted(newly_dirty)
    report["unexpected_dirty_package_paths"] = sorted(unexpected)
    _require(not unexpected,
             "Native import dirtied reference or unrelated packages; do not save those changes. "
             "Preserve pre-existing user work and review/restart the editor before retrying")


def _report_write(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run(job_path, unreal_module=None):
    """Import a new owned hair-placeholder asset; raise ImportFailure on failure.

    ``unreal_module`` is only for tests; normal callers use the actual Creator
    Kit's Python module. The returned/report JSON deliberately retains
    native_validated=False and game_verified=False: a native FBX import is only
    one step, before official avatar binding, packaging and gameplay testing.
    """
    report = {
        "schema_version": 1,
        "python_version": sys.version,
        "status": "preflight_failed",
        "native_validated": False,
        "game_verified": False,
        "native_import_executed": False,
        "imported_asset_paths": [],
        "saved_asset_paths": [],
        "preservation": {
            name: "not_touched" for name in (
                "player_controller", "movement", "animations", "combat", "spells", "progression",
            )
        },
        "native_target_policy": "No explicit target edits; native importer side effects checked with dirty-package guards",
        "manual_next_steps": [
            "Set the official mod active before import; this script cannot verify Set Mod.",
            "Bind a Human/Hair/Any CharacterPiece DefaultMesh to this skeletal mesh using the official workflow.",
            "Bind that CharacterPiece to the generated student HairStyle avatar preset.",
            "Package with the official Creator Kit and test in Hogwarts Legacy before calling the mod complete.",
        ],
    }
    report_path = None
    task = None
    settings = None
    unreal = unreal_module
    before = None
    dirty_before = None
    try:
        job_file, job = _load_job(job_path)
        report_path = _private_report_path(
            job.get("report_path", str(PROJECT_ROOT / ".local" / "kit-import-result.json")), job_file.parent,
        )
        settings = _validate_job(job_file, job)
        report.update(settings)
        if unreal is None:
            try:
                import unreal as unreal_native
            except ImportError as exc:
                raise ValueError("Run import inside the official Creator Kit Python environment") from exc
            unreal = unreal_native
        report["engine_version"] = _api(unreal)
        descriptor = (Path(unreal.Paths.project_dir()) / "Mods" / settings["plugin_name"]
                      / f"{settings['plugin_name']}.uplugin").resolve()
        _require(descriptor.is_file(), f"Create the official content mod first; missing {descriptor}")
        with descriptor.open(encoding="utf-8-sig") as stream:
            plugin = json.load(stream)
        _require(isinstance(plugin, dict) and plugin.get("CanContainContent") is True,
                 "The official mod descriptor must declare CanContainContent=true")
        report["plugin_descriptor"] = str(descriptor)
        skeleton = _reference(unreal, settings["skeleton_asset"], unreal.Skeleton, "skeleton_asset")
        physics = _reference(unreal, settings["physics_asset"], unreal.PhysicsAsset, "physics_asset")
        mount = f"/{settings['plugin_name']}"
        destination = settings["destination_path"]
        mesh_path = f"{destination}/{settings['asset_name']}"
        _require(not unreal.EditorAssetLibrary.does_asset_exist(mesh_path),
                 "Destination mesh already exists; never overwrite it")
        _require(not _list(unreal, destination),
                 "Destination folder already contains assets; choose a new owned asset name")
        before = _list(unreal, mount)
        dirty_before = _dirty_packages(unreal)
        report["preexisting_dirty_package_paths"] = sorted(dirty_before)
        _require(not {settings["skeleton_asset"], settings["physics_asset"]}.intersection(dirty_before),
                 "A native reference target is already dirty; preserve/review your existing edits before importing")
        ui = unreal.FbxImportUI()
        _set_checked(ui, {
            "import_mesh": True,
            "import_as_skeletal": True,
            "mesh_type_to_import": unreal.FBXImportType.FBXIT_SKELETAL_MESH,
            "automated_import_should_detect_type": False,
            "import_animations": False,
            "import_textures": False,
            "import_materials": True,
            "skeleton": skeleton,
            "create_physics_asset": False,
            "physics_asset": physics,
        })
        _set_checked(_get(ui, "skeletal_mesh_import_data"), {
            "update_skeleton_reference_pose": False,
            "use_t0_as_ref_pose": False,
            "import_morph_targets": False,
            "import_mesh_lods": False,
        })
        task = unreal.AssetImportTask()
        _get(task, "imported_object_paths")
        _set_checked(task, {
            "filename": settings["fbx_path"],
            "destination_path": destination,
            "destination_name": settings["asset_name"],
            "replace_existing": False,
            "automated": True,
            "save": False,
            "options": ui,
        })
        importer = unreal.AssetToolsHelpers.get_asset_tools()
        _require(callable(getattr(importer, "import_asset_tasks", None)),
                 "Required Unreal method is unavailable: import_asset_tasks")
        report["status"] = "import_failed"
        report["native_import_executed"] = True
        importer.import_asset_tasks([task])
        imported = {_asset_path(value, "import result") for value in _get(task, "imported_object_paths")}
        registry_new = _list(unreal, mount) - before
        # Inventory every new mod asset but save only the verified task output.
        # An incomplete task inventory needs manual review before any save.
        report["imported_asset_paths"] = sorted(imported | registry_new)
        _dirty_guard(unreal, dirty_before, settings, report)
        _require(not registry_new - imported,
                 "Native import created assets absent from task output; review them manually before saving")
        _require(imported and mesh_path in imported, "Import did not produce the requested skeletal mesh")
        _require(all(path.startswith(destination + "/") for path in imported),
                 "Import returned assets outside the owned destination; no assets will be saved")
        _require(not imported.intersection(before), "Import unexpectedly returned existing plugin assets")
        loaded = []
        for path in sorted(imported):
            obj = unreal.load_asset(path)
            _require(obj is not None and _path(obj) == path, "Imported asset failed to load at its exact path")
            if path == mesh_path:
                _require(isinstance(obj, unreal.SkeletalMesh), "Requested imported asset is not a SkeletalMesh")
                _require(_path(_get(obj, "skeleton")) == settings["skeleton_asset"],
                         "Imported mesh references an unexpected skeleton; no assets will be saved")
                _require(_path(_get(obj, "physics_asset")) == settings["physics_asset"],
                         "Imported mesh references an unexpected physics asset; no assets will be saved")
            else:
                _require(isinstance(obj, unreal.MaterialInterface),
                         "Import created an unexpected non-material asset; no assets will be saved")
            loaded.append((path, obj))
        # Even with reference-pose updates disabled, Unreal can merge/dirty a
        # native Skeleton. Check for that before saving, and after each save.
        # No direct setters or saves target game assets/player Blueprints.
        for path, obj in loaded:
            _dirty_guard(unreal, dirty_before, settings, report)
            _require(unreal.EditorAssetLibrary.save_loaded_asset(obj, only_if_is_dirty=False) is True,
                     f"Saving the owned imported asset failed: {path}")
            report["saved_asset_paths"].append(path)
            _dirty_guard(unreal, dirty_before, settings, report)
        report["status"] = "imported_pending_manual_binding_and_game_test"
        report["asset_count"] = len(imported)
        _report_write(report_path, report)
        return report
    except Exception as exc:
        # Never delete/rollback native assets: doing so could harm a user's
        # subsequent edits. Report any partial output for manual inspection.
        if task is not None and report["native_import_executed"]:
            retained = set(report["imported_asset_paths"])
            try:
                for value in _get(task, "imported_object_paths"):
                    try:
                        retained.add(_asset_path(value, "partial import result"))
                    except ValueError:
                        retained.add(str(value))
                if before is not None:
                    retained.update(_list(unreal, f"/{settings['plugin_name']}") - before)
                report["imported_asset_paths"] = sorted(retained)
            except Exception:
                report["partial_asset_inventory_incomplete"] = True
            report["partial_outputs_require_manual_review"] = True
            if dirty_before is not None:
                try:
                    _dirty_guard(unreal, dirty_before, settings, report)
                except Exception as dirty_error:
                    report["dirty_package_review_note"] = str(dirty_error)
        report["error"] = str(exc)
        if report_path is not None and not report_path.exists():
            try:
                _report_write(report_path, report)
            except Exception as report_error:
                report["report_write_error"] = str(report_error)
        raise ImportFailure(str(exc), report) from exc


if __name__ == "__main__":
    result = run(PROJECT_ROOT / ".local" / "appearance-job.json")
    print(json.dumps(result, indent=2))
