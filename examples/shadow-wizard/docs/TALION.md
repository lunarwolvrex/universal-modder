# Playing as Talion: requested character feature

The requested scope now includes **Talion as the visible player character in Hogwarts Legacy**, alongside persistent enemy rivals. Start with his ranger appearance: face/hair and ranger clothing, with Hogwarts' native movement, spellcasting, targeting, progression and quest interactions. Wraith transformations, sword combat, Shadow of War traversal and Talion's voice are separate features, not implied by a model replacement.

**Implementation status: blocked before asset conversion.** No Talion mesh, rig or textures are present; no playable Talion model or Hogwarts character replacement has been produced. The Windows installation cannot be accessed from the cloud session. The portable rival mechanic remains independent of the visual character feature.

The smaller [Creator Kit appearance slice](CREATOR_KIT_APPEARANCE.md) now implements original placeholder asset tooling and follows the official HairStyle workflow. Its controller, movement, animations, combat and progression stay native. It has not yet run in the Kit or game and does not supply Talion's model.

## Asset and host route

Use Talion assets only from the user's own Shadow of War installation, processed into a private working folder outside the project/package. Distribute original conversion code or instructions, not converted retail models/textures. No third-party model rip or game archive is included in this project.

The Shadow of War knowledge-base note demonstrates archive extraction with QuickBMS and `shadow_of_mordor.bms` version 0.4. That evidence concerns LTAR archives and database files, not a decoded skinned Talion export. QuickBMS archive extraction does not by itself produce a character ready for Blender or Unreal. The Talion archive entry, skinned mesh format, skeleton and texture conversion remain to be established from the owned install; no converter is being claimed.

On the Hogwarts side, the official Creator Kit's player-avatar/custom skeletal-mesh instructions have now been read. The initial implementation uses a new HairStyle with a mod-owned CharacterPiece and original marker mesh. Extending this to Talion's head/body needs appropriate native part types, facial/animation compatibility and owned source conversion; it has not been verified. The community UE4SS projects inspected for rivals do not establish a complete playable-character model swap pipeline.

## Source-inspected leads and limits

- [AutumnFloof's HL Modding Guide](https://github.com/AutumnFloof/HL-Modding-Guide/tree/dce8a24ce546fa9a3642574b6077c7b30200076c) documents a **wand** skeletal-mesh replacement using an Unreal 4.27.2 project named Phoenix, the original target armature, matching asset paths and IoStore output. It is an archived, older guide. Its reported wand workflow is useful evidence about cooking and skinning, not evidence that a Talion body can be replaced on the current game build. Do not apply its version/settings blindly.
- [HL-Discoveries](https://github.com/1kaliel/HL-Discoveries/tree/5d08fecd3849223a6c2e4567fca065ee4324d4f8) records Creator Kit build 1404437 discovery data. Its own warning says editor-discovered candidates do not establish runtime availability. Names and paths in a dataset are leads to investigate, not confirmed import/spawn APIs.
- The [QuickBMS source mirror's documentation](https://github.com/LittleBigBug/QuickBMS/blob/master/readme.md) explains archive listing/extraction. The source-game field note is the evidence for the Shadow of War format script. Neither establishes a complete Talion mesh/skeleton exporter.

No existing Talion-for-Hogwarts mod was verified during research. Search coverage was limited, and some official/Nexus pages were inaccessible; this does not establish that none exists.

One concrete skeleton-inspection lead from HL-Discoveries' `data/animation.clip/0.json` is `/Game/RiggedObjects/Characters/Biped_Skeleton.Biped_Skeleton`. It appears in editor discovery data; its role as the user's retail player skeleton is unverified. Confirm actual mesh/animation bindings before using that path or a rig exported from it.

## First real asset slice

1. Record both game builds and identify Hogwarts' stock player skeletal mesh/skeleton, material slots, appearance/equipment assembly and animation bindings using supported tools.
2. Locate Talion's model, skeleton and associated materials in the owned source installation; decode one model privately and inspect it in Blender. Verify a recognizable model with valid triangles, UVs, bone weights and bind pose before building a general converter.
3. Map the model to the host player's skeleton and animations. Check proportions, units, axes, root transform, hand alignment, joint deformation, bounds and LODs. Different bone names or similar-looking rigs do not prove compatibility.
4. Determine how the host assembles the face, hair and clothing so the appearance does not duplicate the original body or disappear when equipment changes. Choose one supported appearance override, leaving inventory gameplay intact.
5. Import/cook one private test asset with the build-compatible toolchain, preserving the verified package paths and material setup. Record the exact added files and removal steps, back up saves/config, then test on the Windows installation.

## Acceptance checks

- Talion is visible and recognizable during normal exploration, spellcasting and dialogue on the user's Steam build.
- Walk/run, dodge, spell targeting, broom/mount states and interaction animations remain functional; hands meet the wand and mesh bounds do not cause culling.
- Facial/dialogue scenes, hair and clothing show acceptable deformation; limitations are documented rather than concealed.
- Gear changes, save/reload and a full restart preserve the intended appearance. Another character/save is unaffected unless deliberately selected.
- Rival tracking works with the Talion appearance enabled and disabled. Removing the appearance package restores ordinary Hogwarts behavior.

These checks require native game runs and screenshots; the 39 rival-rule tests do not validate any of them.

## Read-only preparation

The updated `tools/probe-hogwarts.ps1` reports Hogwarts package-format counts and looks for Shadow of War via Steam appmanifest `356190` in the same library. When Shadow of War is in another library, supply its existing install path:

```powershell
powershell -NoProfile -File .\tools\probe-hogwarts.ps1 -ShadowOfWarRoot 'D:\SteamLibrary\steamapps\common\ShadowOfWar'
```

The directory in that example must be replaced with the actual source install path. Omit the option to check the Hogwarts library. The probe reads manifests and file metadata only, installs nothing, never launches either game and does not export assets. Return the JSON output to establish the next prerequisites. A missing detection means only that the source was not found in the searched location, not that the user does not own it.
