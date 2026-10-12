# Shadow Wizard development journal

## Scope and current evidence

The user chose Hogwarts Legacy with persistent rivals inspired by Middle-earth: Shadow of War. Store: Steam. Reported install: `C:\Program Files (x86)\Steam\steamapps\common\Hogwarts Legacy`. The installation is not mounted in this Linux cloud session; game build and live testing access remain unknown. No game folders, saves, loaders or registry settings have been changed.

Route: independently implemented rival-memory mechanic inside a real Hogwarts host, initially tested against a synthetic host. This recreates selected ideas, not Shadow of War's native Nemesis implementation or data. Hogwarts would own player movement and combat. Intended initial target: Windows Steam; exact loader/build compatibility remains unverified. The prototype itself runs in the cloud with Python and Lua. It uses no game files and does not run either original game.

Knowledge-base queries: Hogwarts has no matching note. The Shadow of War Goblins of War note reports working loose game database tribe modding, with persistence verified by its author/user. It does not expose a transferable Nemesis API. Nearest mechanic-transplant precedent: Faith Runner (Mirror's Edge movement in real hosts), referenced in `skills/mashup-mods/references/mashup-cases.md`; our system is a discrete rival ledger rather than movement simulation. Shared lessons: isolate the mechanic, specify host ownership, and separate synthetic from real-game evidence.

Before building, the user was told the first slice: named enemy identity, encounter memory, bounded spell-category adaptation, promotion after player defeat and checkpoint persistence. Native callbacks, spawning, UI and save integration are deferred until game-specific evidence exists. Values are original prototype tuning, not extracted retail values.

## Validation target

Run the actual Lua rules under Lua 5.4 through lupa. Verify state transitions, adaptation limits, identity stability, round-trip disk checkpoints, profile isolation, corrupt-state rejection and no mutation on invalid events. Then require real-game evidence from the user's exact build; a synthetic demo cannot prove Hogwarts integration.

## Lab and continuation

`tools/probe-hogwarts.ps1` is read-only metadata inspection for the Windows machine. It reports Steam build ID, executable versions and loader file presence. It installs nothing. Before any later loader install or modded launch, identify and back up the actual save/config/game files and record the restore command here. The repository requires separate permission before installing loaders into game folders or driving input; no such action is being attempted now. No backup is needed for this prototype because it has no access to game data.

## Results

`uv run pytest -q`: 39 passed. `uv run python demo.py`: actual Lua 5.4 rules passed a fresh-runtime disk checkpoint reload, confirming rank 2 and remembered fire at illustrative multiplier 0.75. Initial pytest collection failed because the test entrypoint lacked project imports; fixed with an explicit pytest pythonpath setting. Review found empty-table JSON ambiguity and null-value erasure; schema-aware arrays, strict JSON shapes, null rejection and duplicate-key checks now prevent silent resets. Checkpoint replacement failure leaves the old file intact and removes temporary files.

The Lua author also exercised 300 deterministic randomized encounters and snapshot round trips; the numbered pytest results above are the reproducible packaged suite. A separate reviewer inspected core state invariants and the read-only PowerShell probe. Windows runtime behavior and every native game feature remain unverified.

Source research pins and limitations are in docs/FIELD_NOTE.md. No community source was copied into this project. All game APIs, actor identities and loader compatibility remain diagnostic leads. No external publication or installer execution occurred.

## Talion player-character addition

The user also requested playing as Talion in Hogwarts Legacy. Added the character feature to the project scope and docs/TALION.md, using the ranger appearance with native Hogwarts movement/spells as the first target. No owned Talion source assets or Hogwarts target skeleton are accessible here, so no model replacement or working asset converter has been produced. Archive extraction evidence from the Shadow of War field note does not establish skinned-model decoding. Version 2 of the read-only Windows probe includes Hogwarts package formats and optional Shadow of War Steam build/archive metadata without exporting or changing game data. The original rival Lua implementation is unchanged. The first prototype archive is retained; the updated archive is a separate artifact.

Probe v2 received an independent source review for PowerShell 5.1 syntax and read-only operations, with no material issue identified; Windows execution remains unverified. At that stage, the updated local field note validated, and the publishing checker reported 14 files, zero failures, zero warnings. This lint result was not character or game validation. The toolkit checkout was unchanged before the later repository migration below.

## Connected repository migration

The user requested repository identification and a commit or pull request. The connected origin is `https://github.com/lunarwolvrex/universal-modder`; the initial local branch was `work`, at commit `2c2201437ca676fb4e5f06a18fff6e8db99eef0f`, matching remote `main`. No shadow-wizard files were tracked or present in that main tree. The working tree was clean.

Moved the complete prototype directory into the previously absent `examples/shadow-wizard` path on feature branch `codex/shadow-wizard-prototype`. Existing examples and toolkit files were preserved. Updated the README with repository-relative PowerShell commands, and included the example's lockfile through a local ignore exception. Runtime environments, caches and generated checkpoints remain ignored. The earlier scratch ZIP artifacts are retained outside the repository.

This migration places the source/probe in the connected checkout. GitHub publication requires a successful push and separate remote verification; a local branch or commit alone does not establish publication. The native game and Talion limitations remain unchanged.
