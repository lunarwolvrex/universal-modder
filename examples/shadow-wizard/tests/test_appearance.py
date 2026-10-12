import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("appearance_tool", Path(__file__).parents[1] / "tools" / "appearance.py")
appearance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appearance)


def fixture(tmp_path):
    # Synthetic metadata and stand-in bytes test the control plane, not asset compatibility.
    probe = tmp_path / "windows-probe.json"
    probe.write_text(json.dumps({"probe_version": 2, "platform": "Windows", "steam_build_id": "123456",
                                "executables": [{"relative_path": "Phoenix\\Binaries\\Win64\\HogwartsLegacy.exe",
                                                 "file_version": "synthetic", "bytes": 42}]}))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "candidate.fbx").write_bytes(b"synthetic-fbx-hash-fixture")
    (candidate / "generated.blend").write_bytes(b"synthetic-blend-hash-fixture")
    report = tmp_path / "validation.json"
    payload = {"schema_version": 1, "status": appearance.ASSET_STATUS, "profile": "hair_marker",
               "fbx_roundtrip_checked": True, "bone_names_hierarchy_rest_world_checked": True,
               "uvs_materials_finite_geometry_checked": True, "influences_per_vertex": 1,
               "fbx_bound_geometry_multisets_checked": True,
               "candidate_fbx_sha256": appearance.digest(candidate / "candidate.fbx"),
               "generated_blend_sha256": appearance.digest(candidate / "generated.blend"),
               "gameplay_tested": False, "creator_kit_import_tested": False}
    report.write_text(json.dumps(payload))
    return probe, candidate, report


def test_probe_summary_has_no_runtime_claim(tmp_path):
    probe, _, _ = fixture(tmp_path)
    summary = appearance.summarize_probe(probe)
    assert summary["steam_build_id"] == "123456"
    assert summary["probe_sha256"] == appearance.digest(probe)
    assert summary["gameplay_tested"] is False
    assert summary["creator_kit_build_verified"] is False


@pytest.mark.parametrize("update", [
    {"steam_build_id": None}, {"steam_build_id": "unknown"}, {"steam_build_id": "0"},
    {"executables": []}, {"platform": "Linux"}, {"probe_version": True},
    {"executables": [{"relative_path": "other.exe", "bytes": 1}]},
])
def test_probe_rejects_missing_machine_evidence(tmp_path, update):
    probe, _, _ = fixture(tmp_path)
    data = json.loads(probe.read_text())
    data.update(update)
    probe.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        appearance.summarize_probe(probe)


def test_probe_accepts_explicit_utf8_bom_from_powershell(tmp_path):
    probe, _, _ = fixture(tmp_path)
    probe.write_bytes(b"\xef\xbb\xbf" + probe.read_bytes())
    assert appearance.summarize_probe(probe)["steam_build_id"] == "123456"


def test_probe_accepts_version_three_without_assuming_kit_presence(tmp_path):
    probe, _, _ = fixture(tmp_path)
    payload = json.loads(probe.read_text())
    payload["probe_version"] = 3
    payload["creator_kit"] = {"detected": False}
    probe.write_text(json.dumps(payload))
    assert appearance.summarize_probe(probe)["creator_kit_build_verified"] is False


@pytest.mark.parametrize("changes", [
    {"profile": "full_body_experimental"}, {"fbx_roundtrip_checked": False},
    {"candidate_fbx_sha256": "stale"}, {"generated_blend_sha256": "stale"},
    {"gameplay_tested": True}, {"creator_kit_import_tested": True},
])
def test_candidate_rejects_invalid_or_stale_report(tmp_path, changes):
    _, candidate, report = fixture(tmp_path)
    data = json.loads(report.read_text())
    data.update(changes)
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        appearance.candidate_files(candidate, report)


def test_fbx_edit_invalidates_checkpoint(tmp_path):
    _, candidate, report = fixture(tmp_path)
    (candidate / "candidate.fbx").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        appearance.candidate_files(candidate, report)


def test_prepare_import_binds_exact_candidate_probe_and_scoped_destination(tmp_path):
    probe, candidate, report = fixture(tmp_path)
    output = tmp_path / "appearance-job.json"
    args = argparse.Namespace(probe=probe, candidate_dir=candidate, validation_report=report,
                              skeleton_asset="Skeleton'/Game/PrivateRig/Observed.Observed'",
                              physics_asset="/Game/PrivateRig/ObservedPhysics.ObservedPhysics",
                              output=output, import_report=tmp_path / "kit-result.json")
    result = appearance.prepare_import(args)
    job = json.loads(output.read_text())
    assert job["fbx_sha256"] == appearance.digest(candidate / "candidate.fbx")
    assert job["probe_sha256"] == appearance.digest(probe)
    assert job["validation_report_sha256"] == appearance.digest(report)
    assert job["skeleton_asset"] == "/Game/PrivateRig/Observed.Observed"
    assert job["destination_path"].startswith("/ShadowWizardAppearance/")
    assert result["gameplay_tested"] is False


def test_private_bundle_has_only_declared_import_files_and_no_cook_claim(tmp_path):
    _, candidate, report = fixture(tmp_path)
    output = tmp_path / "private-bundle.zip"
    appearance.bundle_candidate(argparse.Namespace(candidate_dir=candidate, validation_report=report, output=output))
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"candidate.fbx", "blender-validation.json", "IMPORT-MANIFEST.json"}
        manifest = json.loads(archive.read("IMPORT-MANIFEST.json"))
        assert manifest["contains_private_reference_skeleton"] is True
        assert manifest["cooked_game_mod"] is False
        assert manifest["gameplay_tested"] is False
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected


def test_bundle_does_not_overwrite_existing_file(tmp_path):
    _, candidate, report = fixture(tmp_path)
    output = tmp_path / "keep.zip"
    output.write_bytes(b"keep")
    with pytest.raises(ValueError):
        appearance.bundle_candidate(argparse.Namespace(candidate_dir=candidate, validation_report=report, output=output))
    assert output.read_bytes() == b"keep"


@pytest.mark.parametrize("reference", ["None", "/Game/../Something", "C:\\Private\\Skeleton", "Skeleton'/Game/X' trailing"])
def test_bad_asset_reference_cannot_be_used(reference):
    with pytest.raises(ValueError):
        appearance.asset_reference(reference)


def test_private_report_cannot_land_in_tracked_project_path():
    unsafe = appearance.PROJECT / "docs" / "must-not-be-written.json"
    assert not unsafe.exists()
    with pytest.raises(ValueError):
        appearance.write_new_json(unsafe, {"private": True})
    assert not unsafe.exists()
