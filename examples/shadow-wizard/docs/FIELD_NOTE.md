---
kind: game
title: "Rival memory in Hogwarts Legacy: synthetic Lua slice and integration blockers"
game: "Hogwarts Legacy"
games_also: ["Middle-earth: Shadow of War"]
game_version: "Steam; user's installed build not yet inspected"
platform: windows
engine: unreal
route: reimplementation
tools: ["Python 3.12.14", "lupa 2.6 / Lua 5.4", "pytest 9.1.1", "uv 0.12.23"]
status: in-progress
date: 2026-10-11
agents: ["Codex (GPT-6)"]
humans: []
links:
  - "https://github.com/matalvernaz/wandsong/tree/af85d885df6fa5193ec117002348eef7bbd505cf"
  - "https://github.com/igromanru/HL-UE4SS/tree/c24de144ec2475f07ed96ced223d68a11c87a28a"
  - "https://github.com/UE4SS-RE/RE-UE4SS/tree/d935b5b23bac03b65c14ae38382b02007204cc2e"
tags: [mashup, rival-memory, lua, prototype, synthetic-validation]
---

# Rival memory in Hogwarts Legacy: synthetic Lua slice and integration blockers

## Setup

The user requested Hogwarts Legacy with persistent rivals inspired by Shadow of War, using Steam. Their Windows installation cannot be accessed from the Linux cloud machine. No game binary/build, loader installation or native runtime was inspected. A read-only PowerShell probe is included for the Windows machine, but has not been executed on Windows.

The actual rules run under Lua 5.4 through lupa 2.6 with Python 3.12.14. The prototype was initially developed outside the toolkit checkout, then moved into `examples/shadow-wizard` at the user's request. From that directory, install dependencies with `uv sync --locked --group dev`, then use `uv run python -m pytest -q` and `uv run python demo.py`. Existing toolkit source and examples were preserved.

## Route and why

Independent mechanic recreation in a real host, first exercised against a synthetic host. Hogwarts is intended to own combat and movement. The rival ledger owns stable mod IDs, ranks, category memory and profile-specific checkpoints. This is an original interpretation of persistent rivals, not extraction or execution of the native Nemesis implementation. A future verified game adapter would apply the ledger's suggestions. No game adapter exists in this slice.

## How the game works: source-inspected leads only

Wandsong at commit af85d885df6fa5193ec117002348eef7bbd505cf supplies community Hogwarts UE4SS code. Its combat file registers encounter/death callbacks but explicitly says delivery of those events is unproven. Damage feedback lacks a validated victim identity and spell ID. Target actor paths and character labels do not establish stable enemy identity across saves. The inspected source did not establish a game save-slot or player-death API suitable for the ledger.

HL-UE4SS at c24de144ec2475f07ed96ced223d68a11c87a28a references experimental UE4SS v3.0.1-201-g7cd4e3f; Wandsong references stable v3.0.1. These are different configurations. Do not assume compatibility from a generic Unreal playbook or copy one over an existing setup. Official-site research was restricted by network access; Creator Kit suitability remains unverified.

The existing Shadow of War Goblins of War field note reports real-game persistence through database tribe cloning. That finding does not provide a portable Nemesis runtime API.

## Verification

Synthetic tests: 39 passed with actual Lua rules, covering promotion, survival, terminal death, adaptation caps and thresholds, deterministic ordering, invalid-event rollback, profile isolation, dense arrays, corruption rejection and atomic file replacement failure. The demo writes state, opens a fresh Lua runtime, reloads the disk checkpoint and verifies rank 2 plus remembered fire at an illustrative multiplier of 0.75. These numbers are original prototype tuning.

The toolkit publishing checker passed with zero failures and warnings before this note was added; final packaging checks are recorded in MODLOG.md. No native game session, spawn, combat change, save-slot mapping, screenshot, Windows probe run or installer was validated. Status remains in-progress.

## Gotchas

1. Empty Lua tables cannot identify JSON arrays. Symptom: an empty rivals or adaptations list serialized as an object. Fix: schema-aware array conversion, including empty-list tests.
2. JSON null converted to Lua nil can erase fields or reset a ledger. Symptom: a null root looked like new state; a null array entry vanished. Fix: require checkpoint object/list shapes, reject null nested values and duplicate keys before conversion, and fail without changing files.
3. Runtime actor identity is not persistence. Copying a UObject path into a checkpoint does not prove the same rival can be recognized after reload. Resolve identity on the actual Steam build before tracking ambient enemies.
4. A post-hook that reports damage cannot automatically supply a safe pre-hit resistance modifier. Prove the native combat entrypoint and victim/spell parameters separately; presentation multipliers in this build have no game effect.

## Assets

None. Only original code, documentation and synthetic names are included.

## Open questions

The game build, loader compatibility, persistent enemy/save-slot identity, landed-spell and player-death callbacks, safe enemy eligibility and native return/spawn behavior all require Windows game access. Backups and explicit permission precede any later loader install or automated input. No files have been installed into either game.

## Talion appearance follow-up

The user added Talion as the desired player character. The initial scope is his ranger appearance with Hogwarts' native movement/spells. No source assets are available and no model replacement has been implemented. An archived [HL Modding Guide](https://github.com/AutumnFloof/HL-Modding-Guide/tree/dce8a24ce546fa9a3642574b6077c7b30200076c) provides a source-inspected wand skeletal-mesh replacement/cooking workflow; it does not validate a full player swap. [HL-Discoveries](https://github.com/1kaliel/HL-Discoveries/tree/5d08fecd3849223a6c2e4567fca065ee4324d4f8) warns that Creator Kit discoveries do not prove runtime availability. No verified Talion skinned export tool was identified.

The expanded read-only probe checks both Steam installs (Shadow of War appid 356190), target package-format counts and source archive metadata. It still does not export assets or execute on Windows in this session. The intended private conversion and required native animation/cutscene checks are in docs/TALION.md. Rival-rule code is unchanged, and its previous 39 passing tests do not validate the appearance feature.

## Creator Kit appearance authoring follow-up

Official primary text has now been read: [Customizations & Assets](https://support.curseforge.com/support/solutions/articles/9000259715-hogwarts-legacy-creators-customizations-assets), [Getting Started](https://support.curseforge.com/support/solutions/articles/9000258592-hogwarts-legacy-creators-getting-started), [Upload/onboarding](https://support.curseforge.com/support/solutions/articles/9000259765-hogwarts-legacy-creators-phx-ux-upload-and-onboarding-for-creator-kit) and [Testing before publishing](https://support.curseforge.com/support/solutions/articles/9000258593-hogwarts-legacy-creators-testing-your-mod-before-publishing-it). This supersedes the earlier text-only research blocker for these pages. Image-host export settings and WB FAQ pages remained inaccessible.

The smallest documented extension is an original HairStyle. CharacterCreator Avatar Preset / Student creates a new part, its AvatarPresetDefinition and mod-owned table/mutator extension. A CharacterPiece with classification Human, type Hair, gender Any and the candidate DefaultMesh is bound to that preset. The official guide warns that Set Character Look Override persists across all player saves; it must not be used here. The existing controller and gameplay assets are left alone.

Added original placeholder Blender generation, asset/FBX validation, a private import-bundle helper and guarded Creator Kit Python importer. Blender 4.3.2 passes 14 synthetic checks, including complete rig preservation, original geometry/weights, FBX roundtrip and same-count geometry corruption rejection. The importer has 35 fake-Unreal contract checks and Python 3.7 grammar validation. These are development checks, not native compatibility. The actual Windows probe, reference rig, native editor/cloud cooking and game tests remain missing. The mod stays in-progress, and the detailed in-game checklist remains NOT RUN.

Cloud cooking/install is the supported official route. Source ZIPs/FBX are not installed by copying to a guessed game directory. Author testing uses MODS / Library / Uploaded / Install and an enabled mod-save copy. Keep compiled/private rig assets out of GitHub; the repository carries source tooling and instructions only.
