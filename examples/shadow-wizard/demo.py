"""Demonstrate rival memory across a disk checkpoint, with no game running."""
import argparse
from pathlib import Path
import tempfile

from harness import from_lua, load_checkpoint, open_ledger, save_checkpoint


def demo(state):
    runtime, ledger = open_ledger("synthetic-demo")
    ledger.observe(ledger, "rival-001", "The Ember Duelist")
    ledger.begin_encounter(ledger, "rival-001")
    for _ in range(3):
        ledger.hit(ledger, "rival-001", "fire")
    ledger.resolve(ledger, "rival-001", "player_defeated")
    save_checkpoint(state, ledger)
    runtime, restored = load_checkpoint(state, "synthetic-demo")
    encounter = from_lua(restored.begin_encounter(restored, "rival-001"))
    assert encounter["rank"] == 2
    assert "fire" in encounter["remembered_categories"]
    assert encounter["damage_multipliers"]["fire"] == 0.75
    print("SYNTHETIC DEMO — no game integration")
    print("The Ember Duelist defeated the player after three fire hits.")
    print("Saved state to disk, created a new Lua runtime, then reloaded it.")
    print("Returning rival: rank 2, remembers fire; suggested fire damage multiplier: 0.75.")
    print("Native enemy spawning, combat changes and UI are not implemented.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, help="Optional new demo checkpoint path; existing files are protected")
    args = parser.parse_args()
    if args.state:
        if args.state.exists():
            parser.error("--state must name a new file; existing checkpoints are not overwritten by the demo")
        demo(args.state)
    else:
        with tempfile.TemporaryDirectory(prefix="shadow-wizard-") as temporary:
            demo(Path(temporary) / "demo-state.json")
