import copy
import json

from lupa.lua54 import LuaError
import pytest

from harness import from_lua, load_checkpoint, open_ledger, save_checkpoint


def record(ledger, rival="rival-a"):
    return from_lua(ledger.get(ledger, rival))


def checkpoint(ledger):
    return from_lua(ledger.snapshot(ledger))


def create():
    runtime, ledger = open_ledger("slot-a")
    ledger.observe(ledger, "rival-a", "The Ember Duelist")
    return runtime, ledger


def encounter(ledger, category="fire", hits=3, outcome="player_defeated"):
    ledger.begin_encounter(ledger, "rival-a")
    for _ in range(hits):
        ledger.hit(ledger, "rival-a", category)
    ledger.resolve(ledger, "rival-a", outcome)


def test_memory_promotion_and_actual_disk_reload(tmp_path):
    runtime, ledger = create()
    encounter(ledger)
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, ledger)
    runtime, restored = load_checkpoint(path, "slot-a")
    assert checkpoint(restored) == checkpoint(ledger)
    returned = from_lua(restored.begin_encounter(restored, "rival-a"))
    assert returned["rank"] == 2
    assert returned["remembered_categories"] == ["fire"]
    assert returned["damage_multipliers"]["fire"] == 0.75


@pytest.mark.parametrize("outcome", ["enemy_escaped", "enemy_spared"])
def test_survivors_remember_without_promotion(outcome):
    runtime, ledger = create()
    encounter(ledger, outcome=outcome)
    rival = record(ledger)
    assert rival["rank"] == 1
    assert rival["adaptations"] == ["fire"]
    assert rival["status"] == "available"


def test_terminal_kill_is_not_resurrection():
    runtime, ledger = create()
    encounter(ledger, outcome="enemy_killed")
    rival = record(ledger)
    assert rival["status"] == "dead"
    assert rival["rank"] == 1
    assert rival["adaptations"] == []
    previous = checkpoint(ledger)
    with pytest.raises(LuaError):
        ledger.begin_encounter(ledger, "rival-a")
    assert checkpoint(ledger) == previous


def test_rank_and_adaptations_are_bounded():
    runtime, ledger = create()
    for category in ["fire", "control", "force", "curse"] * 3:
        encounter(ledger, category=category)
    rival = record(ledger)
    assert rival["rank"] == 5
    assert rival["player_defeats"] == 12
    assert rival["adaptations"] == ["fire", "control"]


def test_hits_reset_between_encounters_and_threshold():
    runtime, ledger = create()
    encounter(ledger, hits=2, outcome="enemy_escaped")
    assert record(ledger)["adaptations"] == []
    encounter(ledger, hits=1, outcome="enemy_escaped")
    assert record(ledger)["adaptations"] == []
    encounter(ledger, hits=3, outcome="enemy_escaped")
    assert record(ledger)["adaptations"] == ["fire"]


def test_dominant_spell_and_stable_tie_order():
    runtime, ledger = create()
    ledger.begin_encounter(ledger, "rival-a")
    for category in ["curse", "force", "control", "fire"]:
        ledger.hit(ledger, "rival-a", category)
    ledger.resolve(ledger, "rival-a", "enemy_escaped")
    assert record(ledger)["adaptations"] == ["fire"]


def test_enemy_identity_is_retained_and_get_is_detached():
    runtime, ledger = create()
    encounter(ledger)
    detached = ledger.get(ledger, "rival-a")
    detached.rank = 999
    detached.adaptations[1] = "curse"
    assert record(ledger)["rank"] == 2
    assert record(ledger)["adaptations"] == ["fire"]


def test_empty_checkpoint_has_json_arrays(tmp_path):
    runtime, ledger = open_ledger("empty-slot")
    path = tmp_path / "empty.json"
    save_checkpoint(path, ledger)
    payload = json.loads(path.read_text())
    assert payload["rivals"] == []
    runtime, restored = load_checkpoint(path, "empty-slot")
    assert checkpoint(restored) == payload


@pytest.mark.parametrize("event,args", [
    ("hit", ("rival-a", "fire")),
    ("resolve", ("rival-a", "player_defeated")),
    ("begin_encounter", ("missing",)),
    ("observe", ("invalid/path", "A name")),
    ("observe", ("rival-b", "bad\nname")),
])
def test_invalid_events_do_not_mutate(event, args):
    runtime, ledger = create()
    previous = checkpoint(ledger)
    with pytest.raises(LuaError):
        ledger[event](ledger, *args)
    assert checkpoint(ledger) == previous


def test_duplicate_begin_resolve_and_unknown_spell_do_not_mutate():
    runtime, ledger = create()
    ledger.begin_encounter(ledger, "rival-a")
    for event, args in [("begin_encounter", ("rival-a",)), ("hit", ("rival-a", "unknown")),
                        ("resolve", ("rival-a", "unknown"))]:
        previous = checkpoint(ledger)
        with pytest.raises(LuaError):
            ledger[event](ledger, *args)
        assert checkpoint(ledger) == previous
    ledger.resolve(ledger, "rival-a", "enemy_escaped")
    previous = checkpoint(ledger)
    with pytest.raises(LuaError):
        ledger.resolve(ledger, "rival-a", "player_defeated")
    assert checkpoint(ledger) == previous


def test_restore_rejects_cross_profile():
    runtime, ledger = create()
    with pytest.raises(LuaError):
        open_ledger("slot-b", checkpoint(ledger))


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(schema=99),
    lambda s: s["rivals"][0].update(rank=9),
    lambda s: s["rivals"][0].update(status="immortal"),
    lambda s: s["rivals"][0].update(adaptations=["unknown"]),
    lambda s: s["rivals"][0].update(adaptations=["fire", "fire"]),
    lambda s: s["rivals"].append(copy.deepcopy(s["rivals"][0])),
    lambda s: s["rivals"][0].update(encounters=-1),
    lambda s: s["rivals"][0].update(spell_counts={"fire": float("nan")}),
])
def test_restore_rejects_corruption(mutate):
    runtime, ledger = create()
    snapshot = checkpoint(ledger)
    mutate(snapshot)
    with pytest.raises(LuaError):
        open_ledger("slot-a", snapshot)


def test_checkpoint_and_restore_are_detached():
    runtime, ledger = create()
    snapshot = checkpoint(ledger)
    restored_runtime, restored = open_ledger("slot-a", snapshot)
    snapshot["rivals"][0]["display_name"] = "Changed externally"
    encounter(ledger)
    assert record(restored)["rank"] == 1
    assert record(restored)["display_name"] == "The Ember Duelist"


def test_full_ledger_limit_and_sorted_snapshot():
    runtime, ledger = open_ledger("full-slot")
    for i in reversed(range(128)):
        ledger.observe(ledger, f"rival-{i:03d}", "A duelist")
    ids = [r["id"] for r in checkpoint(ledger)["rivals"]]
    assert ids == sorted(ids)
    previous = checkpoint(ledger)
    with pytest.raises(LuaError):
        ledger.observe(ledger, "overflow", "A duelist")
    assert checkpoint(ledger) == previous


def test_failed_checkpoint_replacement_keeps_previous_file(tmp_path, monkeypatch):
    runtime, ledger = create()
    path = tmp_path / "rivals.json"
    save_checkpoint(path, ledger)
    previous = path.read_bytes()
    encounter(ledger)
    def fail(*args):
        raise OSError("simulated replace failure")
    monkeypatch.setattr("harness.os.replace", fail)
    with pytest.raises(OSError, match="simulated"):
        save_checkpoint(path, ledger)
    assert path.read_bytes() == previous
    assert sorted(p.name for p in tmp_path.iterdir()) == ["rivals.json"]


@pytest.mark.parametrize("payload", [
    "null", "[]", "1", '"not a checkpoint"', "{",
    '{"schema":1,"profile_id":"slot-a","rivals":{}}',
    '{"schema":1,"schema":99,"profile_id":"slot-a","rivals":[]}',
    '{"schema":NaN,"profile_id":"slot-a","rivals":[]}',
    '{"schema":1,"profile_id":"slot-a","rivals":[null]}',
    '{"schema":1,"profile_id":"slot-a","rivals":[],"unknown":null}',
])
def test_invalid_json_checkpoint_cannot_reset_ledger(tmp_path, payload):
    path = tmp_path / "corrupt.json"
    path.write_text(payload)
    with pytest.raises(ValueError):
        load_checkpoint(path, "slot-a")
    assert path.read_text() == payload


def test_json_adaptations_must_be_an_array(tmp_path):
    runtime, ledger = create()
    snapshot = checkpoint(ledger)
    snapshot["rivals"][0]["adaptations"] = {}
    path = tmp_path / "invalid-shape.json"
    path.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError):
        load_checkpoint(path, "slot-a")


def test_null_rival_field_cannot_disappear_before_validation():
    runtime, ledger = create()
    snapshot = checkpoint(ledger)
    snapshot["rivals"][0]["last_outcome"] = None
    with pytest.raises(ValueError, match="null"):
        open_ledger("slot-a", snapshot)
