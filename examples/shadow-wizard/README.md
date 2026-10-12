# Shadow Wizard: rival-memory prototype

An original first slice for **Hogwarts Legacy with persistent rivals inspired by Shadow of War and Talion as the player character**. This build runs the Lua mechanic in a synthetic host. **It is not an installable Hogwarts mod:** automatic enemy tracking, native combat/save integration and the Talion character replacement are unfinished.

The prototype remembers an enemy across encounters and disk reloads, promotes a rival after a player defeat, and recommends bounded adaptations to repeated spell categories. Hogwarts should retain its native movement, spells, combat and quest behavior. Rules use illustrative tuning rather than retail Shadow of War data; no game assets or extracted code are included.

## Run the prototype

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/) on your Windows PC. From the repository root in PowerShell:

```powershell
Set-Location .\examples\shadow-wizard
uv sync --locked --group dev
uv run python demo.py
uv run python -m pytest -q
```

On Linux/macOS, use `cd examples/shadow-wizard` from the repository root and run the same uv commands. The dependency lockfile is included. The prototype does not install a Hogwarts loader or change either game.

The demo creates a named rival, records three fire hits followed by a player defeat, writes a JSON checkpoint, opens a fresh Lua runtime, and verifies that the returning rival remembers fire at rank 2. Its default checkpoint is temporary. To retain evidence, use `uv run python demo.py --state .local/new-demo.json`; the demo rejects existing paths. JSON checkpoint writes are atomic in the synthetic harness and never touch game saves. Run only one writer per checkpoint.

`Scripts/rival_core.lua` is the actual portable Lua 5.4 rule implementation. Python/lupa is only the test host; it does not communicate with Hogwarts. See [rules](docs/RULES.md) and [boundary contract](docs/CONTRACT.md).

Validation: **39 tests passed**, plus the checkpoint reload demo. Research findings and remaining integration requirements are recorded in [the local field note](docs/FIELD_NOTE.md).

[Talion's character feature](docs/TALION.md) records the intended ranger appearance, private asset conversion route and game checks. No Talion model or game assets are included. The existing rival rules work independently of the planned appearance.

## Inspect your Windows install

From `examples/shadow-wizard` in your Windows checkout, run this read-only probe:

```powershell
powershell -NoProfile -File .\tools\probe-hogwarts.ps1
```

It defaults to your reported path, `C:\Program Files (x86)\Steam\steamapps\common\Hogwarts Legacy`. For another Steam library, pass `-GameRoot 'D:\SteamLibrary\steamapps\common\Hogwarts Legacy'`. Version 2 also checks Hogwarts package-format counts and Shadow of War metadata in that Steam library. For a source install elsewhere, add `-ShadowOfWarRoot` with its actual path. Return the JSON output to continue build-specific integration. It reads manifests and file metadata only, changes no files, starts no processes and collects no credentials or save/model contents. The probe has been source-reviewed here; Windows execution remains unverified.

## Integration research and next slice

The source-inspected Hogwarts projects [Wandsong](https://github.com/matalvernaz/wandsong/tree/af85d885df6fa5193ec117002348eef7bbd505cf) and [HL-UE4SS](https://github.com/igromanru/HL-UE4SS/tree/c24de144ec2475f07ed96ced223d68a11c87a28a) demonstrate community Lua tooling. They use different UE4SS builds; compatibility must be checked against your Steam build rather than assuming the latest works. This prototype is not based on copied code from either project.

Wandsong's newer combat code explicitly labels callback delivery unproven. Its `OnNPC_Damaged` observation lacks a validated victim/spell identity; runtime actor paths do not establish persistent IDs. No validated player-death or save-slot API was found in the inspected source. These block automatic rival behavior. Official Creator Kit availability and suitability were not verified because relevant official sites were inaccessible from this session; it remains an alternative to evaluate.

Before an in-game build, establish a working loader/toolchain, an eligible enemy's stable identity, landed-spell and player-death events, and a safe mapping of mod checkpoints to character/save slots. Then prove a rival returns after a real save/reload and that adaptations affect only that rival. Back up the actual saves/config and record a restore path before modded launches. Loader installation and automated input require separate permission under the toolkit's instructions; neither is attempted by this project.

The current cloud host has no Windows drive mount or game-control connection. Your provided Windows path cannot be opened here. A reachable Windows session or user-run diagnostics/testing is needed for the next step. Prototype verification demonstrates the rules only, not gameplay in either retail game.
