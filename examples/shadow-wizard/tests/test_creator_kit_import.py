"""Contract tests with fake Unreal APIs; these are NOT Creator Kit/game tests."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "creator_kit_import.py"
spec = importlib.util.spec_from_file_location("shadow_wizard_creator_kit_import", MODULE_PATH)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class Properties:
    def __init__(self, values):
        self.values = dict(values)

    def get_editor_property(self, name):
        return self.values[name]

    def set_editor_property(self, name, value):
        if name not in self.values:
            raise KeyError(name)
        self.values[name] = value


class Asset(Properties):
    def __init__(self, path, values=None):
        super().__init__(values or {})
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]


class Skeleton(Asset):
    pass


class PhysicsAsset(Asset):
    pass


class SkeletalMesh(Asset):
    pass


class MaterialInterface(Asset):
    pass


class FbxImportUI(Properties):
    def __init__(self):
        super().__init__({
            name: None for name in (
                "import_mesh", "import_as_skeletal", "mesh_type_to_import",
                "automated_import_should_detect_type", "import_animations", "import_textures",
                "import_materials", "skeleton", "create_physics_asset", "physics_asset",
            )
        })
        self.values["skeletal_mesh_import_data"] = Properties({
            name: None for name in (
                "update_skeleton_reference_pose", "use_t0_as_ref_pose",
                "import_morph_targets", "import_mesh_lods",
            )
        })


class AssetImportTask(Properties):
    def __init__(self):
        super().__init__({
            name: None for name in (
                "filename", "destination_path", "destination_name", "replace_existing",
                "automated", "save", "options",
            )
        })
        self.values["imported_object_paths"] = []


class FakeUnreal:
    def __init__(self, tmp_path, job):
        project = tmp_path / "CreatorKitProject"
        self.descriptor = (project / "Mods" / job["plugin_name"]
                           / f"{job['plugin_name']}.uplugin")
        self.descriptor.parent.mkdir(parents=True)
        self.descriptor.write_text(json.dumps({"CanContainContent": True}), encoding="utf-8")
        self.SystemLibrary = SimpleNamespace(get_engine_version=lambda: "4.27.2-0+Test")
        self.Paths = SimpleNamespace(project_dir=lambda: str(project))
        self.FbxImportUI = FbxImportUI
        self.AssetImportTask = AssetImportTask
        self.Skeleton = Skeleton
        self.PhysicsAsset = PhysicsAsset
        self.SkeletalMesh = SkeletalMesh
        self.MaterialInterface = MaterialInterface
        self.FBXImportType = SimpleNamespace(FBXIT_SKELETAL_MESH="skeletal")
        self.skeleton = Skeleton(job["skeleton_asset"])
        self.physics = PhysicsAsset(job["physics_asset"])
        self.assets = {self.skeleton.path: self.skeleton, self.physics.path: self.physics}
        self.actions = []
        self.dirty_packages = set()
        self.tasks = []
        self.import_hook = None
        self.EditorAssetLibrary = SimpleNamespace(
            does_asset_exist=lambda path: path in self.assets,
            list_assets=self.list_assets,
            save_loaded_asset=self.save_loaded_asset,
        )
        self.EditorLoadingAndSavingUtils = SimpleNamespace(
            get_dirty_content_packages=lambda: [
                SimpleNamespace(get_path_name=lambda path=path: path)
                for path in self.dirty_packages
            ],
        )
        self.AssetToolsHelpers = SimpleNamespace(get_asset_tools=lambda: self)

    def load_asset(self, path):
        return self.assets.get(path)

    def list_assets(self, path, recursive=True, include_folder=False):
        assert recursive is True and include_folder is False
        return [asset.get_path_name() for key, asset in self.assets.items()
                if key.startswith(path + "/")]

    def save_loaded_asset(self, asset, only_if_is_dirty=False):
        assert only_if_is_dirty is False
        self.actions.append(("save", asset.path))
        self.dirty_packages.discard(asset.path)
        return True

    def import_asset_tasks(self, tasks):
        self.actions.append(("import",))
        self.tasks.extend(tasks)
        task = tasks[0]
        destination = task.values["destination_path"]
        mesh_path = f"{destination}/{task.values['destination_name']}"
        mesh = SkeletalMesh(mesh_path, {"skeleton": self.skeleton, "physics_asset": self.physics})
        material = MaterialInterface(f"{destination}/SW_Original_HairMarker")
        for obj in (mesh, material):
            self.assets[obj.path] = obj
            self.dirty_packages.add(obj.path)
        task.values["imported_object_paths"] = [mesh.get_path_name(), material.get_path_name()]
        if self.import_hook:
            self.import_hook(task, mesh, material)


@pytest.fixture
def prepared(tmp_path):
    fbx = tmp_path / "candidate.fbx"
    fbx.write_bytes(b"fake FBX fixture; not a Hogwarts asset")
    fbx_hash = hashlib.sha256(fbx.read_bytes()).hexdigest()
    validation = tmp_path / "roundtrip.json"
    validation.write_text(json.dumps({
        "schema_version": 1,
        "profile": "hair_marker",
        "status": "asset_candidate_only_not_hogwarts_tested",
        "influences_per_vertex": 1,
        "gameplay_tested": False,
        "creator_kit_import_tested": False,
        "fbx_roundtrip_checked": True,
        "candidate_fbx_sha256": fbx_hash,
        "bone_names_hierarchy_rest_world_checked": True,
        "uvs_materials_finite_geometry_checked": True,
        "fbx_bound_geometry_multisets_checked": True,
    }), encoding="utf-8")
    job = {
        "schema_version": 1,
        "plugin_name": "ShadowWizardAppearance",
        "asset_name": "SK_SWPlaceholderHair",
        "destination_path": "/ShadowWizardAppearance/AvatarPresets/HairStyle/SWPlaceholderHair",
        "fbx_path": str(fbx),
        "fbx_sha256": fbx_hash,
        "validation_report_path": str(validation),
        "validation_report_sha256": hashlib.sha256(validation.read_bytes()).hexdigest(),
        "skeleton_asset": "/Game/Observed/Skeleton",
        "physics_asset": "/Game/Observed/Physics",
        "report_path": str(tmp_path / "import-report.json"),
        # Preparation evidence may carry extra fields; no credentials/assets.
        "probe_sha256": "a" * 64,
        "steam_build_id": "123",
    }
    job_path = tmp_path / "job.json"
    fake = FakeUnreal(tmp_path, job)
    return job, job_path, fake


def execute(prepared):
    job, job_path, fake = prepared
    job_path.write_text(json.dumps(job), encoding="utf-8")
    return kit.run(job_path, unreal_module=fake)


def failed(prepared, message):
    with pytest.raises(kit.ImportFailure, match=message) as error:
        execute(prepared)
    return error.value.report


def test_importable_without_unreal_or_blender():
    assert callable(kit.run)


def test_valid_new_import_preserves_native_references_and_saves_only_owned_outputs(prepared):
    job, _, fake = prepared
    report = execute(prepared)
    assert report["status"] == "imported_pending_manual_binding_and_game_test"
    assert report["native_validated"] is False and report["game_verified"] is False
    assert report["native_import_executed"] is True
    assert report["asset_count"] == 2
    assert set(report["preservation"].values()) == {"not_touched"}
    assert all(path.startswith(job["destination_path"] + "/") for path in report["saved_asset_paths"])
    assert not ({fake.skeleton.path, fake.physics.path} & set(report["saved_asset_paths"]))
    task = fake.tasks[0]
    assert task.values["save"] is False and task.values["replace_existing"] is False
    assert task.values["automated"] is True
    ui = task.values["options"].values
    assert ui["import_mesh"] is True and ui["import_as_skeletal"] is True
    assert ui["mesh_type_to_import"] == "skeletal"
    assert ui["automated_import_should_detect_type"] is False
    assert ui["import_animations"] is False and ui["import_textures"] is False
    assert ui["import_materials"] is True
    assert ui["create_physics_asset"] is False and ui["physics_asset"] is fake.physics
    assert ui["skeleton"] is fake.skeleton
    assert set(ui["skeletal_mesh_import_data"].values.values()) == {False}
    assert fake.skeleton.values == {} and fake.physics.values == {}
    assert json.loads(Path(job["report_path"]).read_text()) == report


@pytest.mark.parametrize("field,value,message", [
    ("schema_version", True, "schema_version"),
    ("plugin_name", "../Game", "plugin_name"),
    ("asset_name", "Wrong", "asset_name"),
    ("destination_path", "/Game/Player", "owned import folder"),
    ("fbx_path", "missing.fbx", "existing FBX"),
    ("fbx_sha256", "f" * 64, "FBX SHA-256 mismatch"),
    ("skeleton_asset", "", "observed native"),
    ("physics_asset", "/Game/Observed/Physics:Subobject", "invalid asset path"),
    ("validation_report_sha256", "f" * 64, "report SHA-256 mismatch"),
])
def test_invalid_job_performs_no_native_writes(prepared, field, value, message):
    job, _, fake = prepared
    job[field] = value
    report = failed(prepared, message)
    assert fake.actions == []
    assert report["native_import_executed"] is False


@pytest.mark.parametrize("field,value,message", [
    ("profile", "full_body_experimental", "hair_marker"),
    ("fbx_roundtrip_checked", False, "roundtrip"),
    ("candidate_fbx_sha256", "f" * 64, "does not validate"),
    ("fbx_bound_geometry_multisets_checked", False, "required validation"),
])
def test_blender_report_linkage_checked_before_native_import(prepared, field, value, message):
    job, _, fake = prepared
    path = Path(job["validation_report_path"])
    validation = json.loads(path.read_text())
    validation[field] = value
    path.write_text(json.dumps(validation), encoding="utf-8")
    job["validation_report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    failed(prepared, message)
    assert fake.actions == []


def test_missing_official_mod_or_noncontent_mod_blocks_import(prepared):
    _, _, fake = prepared
    fake.descriptor.write_text('{"CanContainContent": false}', encoding="utf-8")
    failed(prepared, "CanContainContent")
    assert fake.actions == []


def test_uncreated_official_mod_blocks_import(prepared):
    _, _, fake = prepared
    fake.descriptor.unlink()
    failed(prepared, "Create the official content mod")
    assert fake.actions == []


def test_missing_api_and_unsupported_engine_block_import(prepared):
    _, _, fake = prepared
    fake.SystemLibrary.get_engine_version = lambda: "5.4.4-0+Test"
    failed(prepared, "Unreal 4.27")
    assert fake.actions == []


def test_missing_dirty_package_api_blocks_import(prepared):
    _, _, fake = prepared
    del fake.EditorLoadingAndSavingUtils
    failed(prepared, "Required Unreal API.*EditorLoadingAndSavingUtils")
    assert fake.actions == []


def test_missing_required_editor_property_blocks_import(prepared):
    _, _, fake = prepared

    class MissingPropertyUI(FbxImportUI):
        def __init__(self):
            super().__init__()
            del self.values["physics_asset"]

    fake.FbxImportUI = MissingPropertyUI
    failed(prepared, "Required editor property.*physics_asset")
    assert fake.actions == []


def test_reference_class_must_match_and_alias_resolution_is_rejected(prepared):
    job, _, fake = prepared
    fake.assets[job["skeleton_asset"]] = PhysicsAsset(job["skeleton_asset"])
    failed(prepared, "load as Skeleton")
    assert fake.actions == []


def test_native_reference_cannot_resolve_to_an_alias(prepared):
    job, _, fake = prepared
    fake.assets[job["physics_asset"]] = PhysicsAsset("/Game/Unexpected/Physics")
    failed(prepared, "resolved to an unexpected asset")
    assert fake.actions == []


def test_existing_destination_is_never_replaced(prepared):
    job, _, fake = prepared
    path = job["destination_path"] + "/" + job["asset_name"]
    original = SkeletalMesh(path)
    fake.assets[path] = original
    failed(prepared, "already exists")
    assert fake.assets[path] is original and fake.actions == []


def test_existing_destination_material_is_never_overwritten(prepared):
    job, _, fake = prepared
    path = job["destination_path"] + "/SW_Original_HairMarker"
    fake.assets[path] = MaterialInterface(path)
    failed(prepared, "already contains assets")
    assert fake.actions == []


def test_unexpected_reference_after_import_leaves_unsaved_outputs(prepared):
    _, _, fake = prepared

    def change_reference(task, mesh, material):
        mesh.values["skeleton"] = Skeleton("/Game/Unexpected/Skeleton")

    fake.import_hook = change_reference
    report = failed(prepared, "unexpected skeleton")
    assert fake.actions == [("import",)]
    assert report["saved_asset_paths"] == []
    assert report["partial_outputs_require_manual_review"] is True
    assert len(report["imported_asset_paths"]) >= 2


def test_unexpected_physics_reference_is_rejected_before_saving(prepared):
    _, _, fake = prepared

    def change_reference(task, mesh, material):
        mesh.values["physics_asset"] = PhysicsAsset("/Game/Unexpected/Physics")

    fake.import_hook = change_reference
    failed(prepared, "unexpected physics asset")
    assert fake.actions == [("import",)]


def test_foreign_output_is_rejected_and_never_saved(prepared):
    _, _, fake = prepared

    def foreign_output(task, mesh, material):
        foreign = MaterialInterface("/Game/Unexpected/Material")
        fake.assets[foreign.path] = foreign
        task.values["imported_object_paths"].append(foreign.get_path_name())

    fake.import_hook = foreign_output
    report = failed(prepared, "outside the owned destination")
    assert fake.actions == [("import",)] and report["saved_asset_paths"] == []
    assert any("/Game/Unexpected/Material" in path for path in report["imported_asset_paths"])


def test_new_skeleton_even_inside_owned_folder_is_rejected(prepared):
    _, _, fake = prepared

    def new_skeleton(task, mesh, material):
        extra = Skeleton(task.values["destination_path"] + "/UnexpectedSkeleton")
        fake.assets[extra.path] = extra
        task.values["imported_object_paths"].append(extra.get_path_name())

    fake.import_hook = new_skeleton
    failed(prepared, "unexpected non-material asset")
    assert fake.actions == [("import",)]


def test_registry_output_missing_from_task_is_retained_for_manual_review(prepared):
    _, _, fake = prepared

    def missing_task_output(task, mesh, material):
        task.values["imported_object_paths"] = [mesh.get_path_name()]

    fake.import_hook = missing_task_output
    report = failed(prepared, "absent from task output")
    assert len(report["imported_asset_paths"]) == 2
    assert report["saved_asset_paths"] == []
    assert fake.actions == [("import",)]


def test_native_partial_failure_retains_inventory_without_rollback(prepared):
    _, _, fake = prepared

    def partial_failure(task, mesh, material):
        raise RuntimeError("native import failed after creating candidate")

    fake.import_hook = partial_failure
    report = failed(prepared, "native import failed")
    assert report["native_import_executed"] is True
    assert report["status"] == "import_failed"
    assert report["partial_outputs_require_manual_review"] is True
    assert report["saved_asset_paths"] == [] and len(report["imported_asset_paths"]) >= 2
    assert fake.actions == [("import",)]


def test_report_overwrite_guard_precedes_native_import(prepared):
    job, _, fake = prepared
    Path(job["report_path"]).write_text("keep this report", encoding="utf-8")
    failed(prepared, "Refusing to overwrite report")
    assert Path(job["report_path"]).read_text() == "keep this report"
    assert fake.actions == []


def test_native_skeleton_becoming_dirty_fails_before_any_save(prepared):
    _, _, fake = prepared

    def dirty_native_skeleton(task, mesh, material):
        fake.dirty_packages.add(fake.skeleton.path)

    fake.import_hook = dirty_native_skeleton
    report = failed(prepared, "dirtied reference or unrelated packages")
    assert fake.actions == [("import",)] and report["saved_asset_paths"] == []
    assert report["unexpected_dirty_package_paths"] == [fake.skeleton.path]
    assert "do not save" in report["dirty_package_review_note"]


def test_preexisting_native_target_dirty_blocks_import(prepared):
    _, _, fake = prepared
    fake.dirty_packages.add(fake.physics.path)
    report = failed(prepared, "reference target is already dirty")
    assert fake.actions == []
    assert report["preexisting_dirty_package_paths"] == [fake.physics.path]


def test_preexisting_unrelated_dirty_user_work_is_preserved(prepared):
    _, _, fake = prepared
    unrelated = "/Game/UserWork/EditedMaterial"
    fake.dirty_packages.add(unrelated)
    report = execute(prepared)
    assert report["unexpected_dirty_package_paths"] == []
    assert fake.dirty_packages == {unrelated}
    assert not any(action == ("save", unrelated) for action in fake.actions)


def test_unexpected_dirty_package_after_save_is_detected_without_saving_native_target(prepared):
    _, _, fake = prepared
    native_save = fake.save_loaded_asset

    def dirty_on_save(asset, only_if_is_dirty=False):
        result = native_save(asset, only_if_is_dirty)
        fake.dirty_packages.add(fake.skeleton.path)
        return result

    fake.EditorAssetLibrary.save_loaded_asset = dirty_on_save
    report = failed(prepared, "dirtied reference or unrelated packages")
    assert len(report["saved_asset_paths"]) == 1
    assert ("save", fake.skeleton.path) not in fake.actions
    assert report["unexpected_dirty_package_paths"] == [fake.skeleton.path]
