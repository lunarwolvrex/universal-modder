"""Synthetic host for the Lua mechanic, not a Hogwarts Legacy adapter."""
import json
import os
from pathlib import Path
import tempfile

from lupa.lua54 import LuaRuntime


def from_lua(value, array=False):
    if not hasattr(value, "items"):
        return value
    items = list(value.items())
    if not items and array:
        return []
    if items and all(isinstance(k, int) for k, _ in items):
        keys = sorted(k for k, _ in items)
        if keys == list(range(1, len(items) + 1)):
            return [from_lua(value[k]) for k in keys]
    return {k: from_lua(v, array=k in {"rivals", "adaptations", "remembered_categories"}) for k, v in items}


def to_lua(runtime, value):
    if value is None:
        raise ValueError("Checkpoint null values are invalid; absent fields must be omitted")
    if isinstance(value, dict):
        table = runtime.table()
        for k, v in value.items():
            table[k] = to_lua(runtime, v)
        return table
    if isinstance(value, list):
        return runtime.table_from([to_lua(runtime, v) for v in value])
    return value


def open_ledger(profile, snapshot=None):
    if snapshot is not None:
        validate_snapshot_shape(snapshot)
    runtime = LuaRuntime(unpack_returned_tuples=True)
    module = runtime.execute(
        (Path(__file__).parent / "Scripts" / "rival_core.lua").read_text(encoding="utf-8")
    )
    ledger = module.new(profile, to_lua(runtime, snapshot) if snapshot is not None else None)
    return runtime, ledger


def validate_snapshot_shape(snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("rivals"), list):
        raise ValueError("Checkpoint must be an object containing a rivals array")
    for rival in snapshot["rivals"]:
        if not isinstance(rival, dict) or not isinstance(rival.get("adaptations"), list):
            raise ValueError("Each rival must be an object containing an adaptations array")


def save_checkpoint(path, ledger):
    """Atomic synthetic checkpoint; caller must choose a mod-only sidecar path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = from_lua(ledger.snapshot(ledger))
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_checkpoint(path, profile):
    # Parsing errors and incompatible profiles are errors, never silent resets.
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate checkpoint key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Nonfinite checkpoint number: {value}")

    snapshot = json.loads(Path(path).read_text(encoding="utf-8"),
                          object_pairs_hook=unique_object, parse_constant=invalid_constant)
    validate_snapshot_shape(snapshot)
    return open_ledger(profile, snapshot)
