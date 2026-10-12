"""Prepare private Creator Kit imports; this does not cook or install a game mod.

Run from examples/shadow-wizard with normal Python. All FBX files and reports
remain outside Git or in this example's ignored .local directory. The official
Creator Kit performs avatar assembly and upload/cloud cooking separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parent.parent
ASSET_STATUS = "asset_candidate_only_not_hogwarts_tested"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_constant=invalid)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def private_output(path):
    path = Path(path).expanduser().resolve()
    for parent in (path, *path.parents):
        if not (parent / ".git").exists():
            continue
        root = subprocess.run(["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=False)
        if root.returncode:
            continue
        require(path.is_relative_to((PROJECT / ".local").resolve()),
                "Private assets/reports in Git must be in this example's .local directory")
        ignored = subprocess.run(["git", "-C", root.stdout.strip(), "check-ignore", "--", str(path)],
                                 capture_output=True, check=False)
        require(ignored.returncode == 0, "Private .local outputs must be ignored by Git")
        break
    return path


def write_new_json(path, payload):
    path = private_output(path)
    require(not path.exists(), f"Refusing to overwrite existing output: {path}")
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def summarize_probe(path):
    probe = read_json(path)
    require(type(probe) is dict, "Probe output must be a JSON object")
    require(type(probe.get("probe_version")) is int and probe["probe_version"] in (1, 2, 3),
            "Expected Windows probe version 1, 2 or 3")
    require(probe.get("platform") == "Windows", "Expected the Windows probe output")
    build = probe.get("steam_build_id")
    require(type(build) is str and re.fullmatch(r"[0-9]+", build) is not None and int(build) > 0,
            "Probe must identify an installed Steam build; rerun it on the Windows game PC")
    executables = probe.get("executables")
    require(type(executables) is list and len(executables) > 0, "Probe has no game executable")
    observed = []
    for item in executables:
        require(type(item) is dict, "Invalid probe executable record")
        require(item.get("relative_path") in ("Phoenix\\Binaries\\Win64\\HogwartsLegacy.exe", "HogwartsLegacy.exe"),
                "Unexpected executable in probe output")
        require(type(item.get("bytes")) is int and item["bytes"] > 0,
                "Probe executable size must be positive")
        for field in ("file_version", "product_version"):
            require(item.get(field) is None or type(item[field]) is str, "Invalid executable version")
        observed.append({key: item.get(key) for key in ("relative_path", "file_version", "product_version", "bytes")})
    return {"schema_version": 1, "platform": "Windows", "steam_build_id": build,
            "executables": observed, "probe_sha256": digest(path),
            "evidence": "user-supplied machine metadata; not a game runtime test",
            "creator_kit_build_verified": False, "gameplay_tested": False}


def candidate_files(directory, report_path):
    directory = Path(directory).expanduser().resolve()
    report_path = Path(report_path).expanduser().resolve()
    fbx = directory / "candidate.fbx"
    blend = directory / "generated.blend"
    require(fbx.is_file() and blend.is_file(), "Candidate directory needs candidate.fbx and generated.blend")
    report = read_json(report_path)
    require(type(report) is dict and type(report.get("schema_version")) is int and report["schema_version"] == 1,
            "Expected current Blender validation report")
    require(report.get("status") == ASSET_STATUS, "Report is not a Blender asset-candidate result")
    require(report.get("profile") == "hair_marker", "Only the head-bound hair_marker profile belongs in HairStyle")
    require(report.get("fbx_roundtrip_checked") is True, "Run the Blender validate command with --roundtrip-fbx first")
    require(report.get("bone_names_hierarchy_rest_world_checked") is True and
            report.get("uvs_materials_finite_geometry_checked") is True and
            report.get("fbx_bound_geometry_multisets_checked") is True,
            "Required geometry/skin/rig validation is missing")
    require(report.get("influences_per_vertex") == 1, "Unexpected generated skin influence policy")
    require(report.get("candidate_fbx_sha256") == digest(fbx), "FBX changed after validation; revalidate it")
    require(report.get("generated_blend_sha256") == digest(blend), "Blend file changed after validation; revalidate it")
    require(report.get("gameplay_tested") is False and report.get("creator_kit_import_tested") is False,
            "Blender validation must not assert native game/Kit test results")
    return fbx, blend, report_path, report


def asset_reference(value):
    value = value.strip()
    match = re.fullmatch(r"[A-Za-z0-9_]+['\"](/[^'\"]+)['\"]", value)
    if match:
        value = match.group(1)
    require(re.fullmatch(r"/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)+(?:\.[A-Za-z0-9_]+)?", value) is not None,
            "Use the actual Skeleton/PhysicsAsset Copy Reference path from Creator Kit")
    package, separator, object_name = value.partition(".")
    require(not separator or object_name == package.rsplit("/", 1)[1],
            "Copy Reference must identify the package's asset, not a subobject")
    return value


def prepare_import(args):
    output = private_output(args.output)
    report_output = private_output(args.import_report)
    require(not output.exists() and not report_output.exists(), "Use new job and import-report paths")
    probe = summarize_probe(args.probe)
    fbx, _blend, validation_path, _validation = candidate_files(args.candidate_dir, args.validation_report)
    skeleton = asset_reference(args.skeleton_asset)
    physics = asset_reference(args.physics_asset)
    payload = {
        "schema_version": 1,
        "plugin_name": "ShadowWizardAppearance",
        "asset_name": "SK_SWPlaceholderHair",
        "destination_path": "/ShadowWizardAppearance/AvatarPresets/HairStyle/SWPlaceholderHair",
        "fbx_path": str(fbx), "fbx_sha256": digest(fbx),
        "skeleton_asset": skeleton, "physics_asset": physics,
        "report_path": str(report_output),
        "probe_sha256": probe["probe_sha256"], "steam_build_id": probe["steam_build_id"],
        "validation_report_path": str(validation_path), "validation_report_sha256": digest(validation_path),
    }
    write_new_json(output, payload)
    return {"job": str(output), "steam_build_id": probe["steam_build_id"],
            "status": "private_import_job_prepared_not_a_cooked_mod", "gameplay_tested": False}


def bundle_candidate(args):
    output = private_output(args.output)
    require(output.suffix.lower() == ".zip", "Use a .zip filename for the private import bundle")
    require(not output.exists(), "Refusing to overwrite an existing bundle")
    fbx, _blend, report_path, _report = candidate_files(args.candidate_dir, args.validation_report)
    receipt = {
        "schema_version": 1, "purpose": "private_creator_kit_import_only",
        "contains_private_reference_skeleton": True,
        "cooked_game_mod": False, "gameplay_tested": False,
        "files": {"candidate.fbx": digest(fbx), "blender-validation.json": digest(report_path)},
        "note": "Do not upload this ZIP or FBX to GitHub or as a Creator Kit cooked mod. Import the mesh in the Kit, assemble the HairStyle, and use Upload Mod for official cloud cooking.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Own the file exclusively before cleanup becomes possible. A concurrent
    # creator must not lose its file when exclusive creation fails.
    stream = output.open("xb")
    owned_stat = os.fstat(stream.fileno())
    try:
        with stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(fbx, "candidate.fbx")
                archive.write(report_path, "blender-validation.json")
                archive.writestr("IMPORT-MANIFEST.json", json.dumps(receipt, indent=2) + "\n")
        with zipfile.ZipFile(output) as archive:
            require(archive.testzip() is None, "Private bundle failed its integrity check")
            for name, expected in receipt["files"].items():
                require(hashlib.sha256(archive.read(name)).hexdigest() == expected,
                        "Import input changed while bundling; recreate and revalidate the candidate")
            require(json.loads(archive.read("blender-validation.json"))["candidate_fbx_sha256"]
                    == receipt["files"]["candidate.fbx"], "Bundle and validation report disagree")
    except BaseException:
        if output.exists():
            current = output.stat()
            if (current.st_dev, current.st_ino) == (owned_stat.st_dev, owned_stat.st_ino):
                output.unlink()
        raise
    return {"bundle": str(output), "sha256": digest(output),
            "status": "private_import_bundle_only_not_installable", "gameplay_tested": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe-summary")
    probe.add_argument("--probe", required=True)
    probe.add_argument("--output", required=True)
    bundle = commands.add_parser("bundle-candidate")
    job = commands.add_parser("prepare-import")
    for child in (bundle, job):
        child.add_argument("--candidate-dir", required=True)
        child.add_argument("--validation-report", required=True)
        child.add_argument("--output", required=True)
    job.add_argument("--probe", required=True)
    job.add_argument("--skeleton-asset", required=True)
    job.add_argument("--physics-asset", required=True)
    job.add_argument("--import-report", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "probe-summary":
            result = summarize_probe(args.probe)
            write_new_json(args.output, result)
        elif args.command == "prepare-import":
            result = prepare_import(args)
        else:
            result = bundle_candidate(args)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        parser.exit(2, f"appearance: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
