# Official Creator Kit appearance slice

**Status: authoring tools implemented; native avatar assets, cloud cooking and Hogwarts gameplay are not yet verified.** No Windows probe output or private reference FBX has been supplied to this cloud session. There is no game-installable package in GitHub. Do not mark this mod complete until the in-game checklist below has passed on the actual build.

The smallest slice is **SWPlaceholderHair**, a selectable original, rust-colored hair-slot marker. It is generated around one explicitly mapped head deform bone. It retains the reference skeleton but copies no reference geometry, textures, weights or animations. The existing face/body, controller, movement, animation system, combat, spells and progression remain native. This proves a supported appearance extension before attempting Talion's character assets. It does not implement Talion, rival combat, sword fighting or wraith powers.

## Evaluated official workflow

The following primary pages were read during implementation:

- [Customizations & Assets](https://support.curseforge.com/support/solutions/articles/9000259715-hogwarts-legacy-creators-customizations-assets): **How To: Mod Player Avatar**, **Importing Skeletal Mesh Info**, and **How To: Create a new Avatar Preset**.
- [Getting Started](https://support.curseforge.com/support/solutions/articles/9000258592-hogwarts-legacy-creators-getting-started): upload widget performs **cloud cooking**.
- [Upload and onboarding](https://support.curseforge.com/support/solutions/articles/9000259765-hogwarts-legacy-creators-phx-ux-upload-and-onboarding-for-creator-kit): Create/Set Mod, linked accounts, upload form and content location.
- [Testing before publishing](https://support.curseforge.com/support/solutions/articles/9000258593-hogwarts-legacy-creators-testing-your-mod-before-publishing-it): private author/tester installation and mod-enabled saves.

The avatar guide supports a new HairStyle through `CharacterPiece` and `AvatarPresetDefinition`; it automatically creates the mod's table extension when the part is added in CharacterCreator. It also explicitly warns that **Set Character Look Override** persists a look across all save files. This project does not use that node, actor replacement, possession, input hooks or player Blueprint edits.

The guide's example skeleton and physics asset are `Biped_Skeleton` and `Biped_PhysicsAsset`, but it says to verify the actual reference mesh. Full asset paths and bone names are deliberately not hardcoded. Screenshot-only export settings could not be read from the image host; Blender's explicit FBX settings are checked by roundtrip tests and still require acceptance in the user's Kit.

## Get the files on Windows

In GitHub Desktop, **Fetch origin**, then select **Current branch → codex/shadow-wizard-creator-kit-appearance**. The draft PR targets `main`; the files will not appear on `main` until merged.

The project is `examples\shadow-wizard`; the diagnostic script is `examples\shadow-wizard\tools\probe-hogwarts.ps1`.

Open PowerShell at the repository root:

```powershell
Set-Location .\examples\shadow-wizard
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force .\.local | Out-Null
powershell -NoProfile -File .\tools\probe-hogwarts.ps1 |
    Out-File -Encoding utf8 -NoClobber .\.local\windows-probe.json
if ($LASTEXITCODE -ne 0) { throw 'Probe failed; inspect its error before proceeding.' }
```

If the Kit is installed elsewhere, pass `-CreatorKitRoot 'D:\Actual\HogwartsLegacyCreatorKit'`. The probe searches only two conventional Kit folders when that option is absent; a missing result is not proof the Kit is uninstalled. It reports metadata, installs nothing and launches neither game. Keep its JSON local and return it for build-specific review.

Install Python 3.10+, [uv](https://docs.astral.sh/uv/getting-started/installation/) and Blender 4.3+ on this PC. Record the actual Kit/game builds; a generic Unreal installation is not the Hogwarts Creator Kit. Launch the official Kit through the signed-in Epic launcher, and use its account-linking flow rather than copying authentication values into scripts.

```powershell
uv sync --locked --group dev
uv run python tools/appearance.py probe-summary `
    --probe .\.local\windows-probe.json --output .\.local\probe-summary.json
```

The helper requires a real reported Steam build and positive executable size. It does not infer compatibility or a successful game run from those fields.

## Manual Creator Kit and Blender reference setup

1. In the Kit click **Create Mod**, name it **ShadowWizardAppearance**, then **Set** that mod. Select a content/customization template available in your installed dialog; the avatar tutorial does not prescribe an exact template label. Record the selected label. Keep only the avatar/icon table extensions in this slice, with no actor replacements, gameplay graphs or map changes. The Kit owns its generated descriptor/account metadata; do not replace it with a guessed manifest.
2. Enable **View Options → Show Plugin Content**. Open and play **CustomizableCharacter Content/CharacterCreator**.
3. Set **Editor Mode = Avatar Preset**, **Type = Student**, optionally **Scene = NeutralBasic**.
4. Choose an existing compatible student HairStyle and inspect its referenced SkeletalMesh. Record that mesh's actual Skeleton and Physics Asset using **Copy Reference**. Confirm the reference head bone and current rig in the mesh/animation preview.
5. Export that reference mesh through **Asset Actions → Export**, as FBX, to a private directory outside the project, for example `Documents\ShadowWizardPrivate\reference-hair.fbx`. Do not commit it. The official skinned body templates are also private references; their clothing-limits geometry must not become the placeholder.

Inspect the private rig and generate a local mapping template:

```powershell
$reference = Join-Path $env:USERPROFILE 'Documents\ShadowWizardPrivate\reference-hair.fbx'
blender --background --factory-startup --python-exit-code 7 `
    --python .\tools\blender_avatar.py -- inspect `
    --reference-fbx $reference --report .\.local\rig-report.json
if ($LASTEXITCODE -ne 0) { throw 'Rig inspection failed.' }
(Get-Content .\.local\rig-report.json -Raw | ConvertFrom-Json).mapping_template |
    ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 -NoClobber .\.local\rig-map.json
```

**Manual Blender fitting:** inspect the exported reference in Blender, identify its real deform head bone, and fill the null bone/radius values in `.local\rig-map.json`. Use `configs/hair-marker.example.json` as the schema example, not as a completed mapping. Radii are fractions of that bone's length. Optional `length_start_ratio`/`length_end_ratio` place the marker along the bone; fit it above the scalp without covering eyes. The generator handles no humanoid inference. Use `--armature` with the observed object name if multiple armatures are present.

On reruns choose fresh report/probe filenames. The template command refuses to replace an existing rig mapping, preserving your manual edits. Readers accept the UTF-8 BOM produced by Windows PowerShell 5.1.

Do not rename/reparent bones, apply new rest poses, prune unweighted bones, add leaf bones or change reference armature transforms. The marker uses original procedural geometry and one normalized bone influence per vertex. It is intentionally crude. This first slice has no facial morphs, hair simulation or cloth.

## Automated candidate build, validation and private handoff

```powershell
blender --background --factory-startup --python-exit-code 7 `
    --python .\tools\blender_avatar.py -- build `
    --reference-fbx $reference --mapping .\.local\rig-map.json `
    --output-dir .\.local\avatar-candidate
if ($LASTEXITCODE -ne 0) { throw 'Candidate build failed.' }
blender --background --factory-startup --python-exit-code 7 `
    --python .\tools\blender_avatar.py -- validate `
    --blend .\.local\avatar-candidate\generated.blend `
    --roundtrip-fbx .\.local\avatar-candidate\candidate.fbx `
    --report .\.local\avatar-roundtrip.json
if ($LASTEXITCODE -ne 0) { throw 'FBX roundtrip failed.' }
```

Open `generated.blend` manually and verify fit. If you edit it, the old hashes are stale: export and validate a fresh candidate, or adjust the mapping and rebuild into a new empty output directory. Existing outputs are never overwritten. Validation compares names, parents, bind/world transforms, geometry, vertex-to-bone bindings, triangle winding and hashes; it checks UV/material validity rather than exact UV/color equality. It is a Blender check, not native animation compatibility.

Optional private transfer bundle:

```powershell
uv run python tools/appearance.py bundle-candidate `
    --candidate-dir .\.local\avatar-candidate `
    --validation-report .\.local\avatar-roundtrip.json `
    --output .\.local\private-avatar-import.zip
```

This ZIP contains the candidate FBX, validation evidence and manifest. It embeds a private reference skeleton. It is **not** a cooked mod, must not be uploaded to GitHub, and is not the Creator Kit upload input. Source scripts and FBX files stay outside the Kit mod's packaged Content folder.

## Import the mesh in the Creator Kit

Replace the two variables below with **Copy Reference** values from the actual reference asset. The example script accepts the class-wrapped strings the Kit copies; it does not supply guessed paths.

```powershell
$skeletonAsset = Read-Host 'Paste the reference Skeleton Copy Reference'
$physicsAsset = Read-Host 'Paste the reference Physics Asset Copy Reference'
uv run python tools/appearance.py prepare-import `
    --probe .\.local\windows-probe.json `
    --candidate-dir .\.local\avatar-candidate `
    --validation-report .\.local\avatar-roundtrip.json `
    --skeleton-asset $skeletonAsset --physics-asset $physicsAsset `
    --output .\.local\appearance-job.json `
    --import-report .\.local\kit-import-result.json
```

With **ShadowWizardAppearance** created/mounted and selected in the authenticated Kit, run the helper from its Python console, replacing the checkout path:

```text
py "C:/YourCheckout/universal-modder/examples/shadow-wizard/tools/creator_kit_import.py"
```

It reads the local job, checks the plugin and generic Unreal 4.27 APIs, then imports a new `SK_SWPlaceholderHair` and original solid-color material into the owned namespace. It requests no animation, texture or new physics import, disables reference-pose updates, and never overwrites existing assets. If the Kit dirties native/unrelated packages, it fails before saving them and records review instructions. Preserve any pre-existing user edits when reviewing/restarting. Imported partial outputs are not automatically deleted. Missing APIs or failed guards require manual import, not disabling the guards.

**Manual supported fallback:** import the candidate FBX into this mod's own folder, selecting the actual reference Skeleton and Physics Asset. Morph targets are unnecessary for this marker. The official guide also describes duplicating the reference SkeletalMesh into the mod and using **`>> Custom Control → Reimport Base Mesh With New File`**; if using that method, replace/remove every inherited lower LOD so all shipped geometry is your own. Never save changes to the original reference asset. Preview the mesh with native animations and check scale, axes, bounds and material. Importer tests here use fake APIs; actual Kit execution remains pending.

## Manual avatar registration and icons

These steps are deliberately done through the official CharacterCreator tooling, which owns its native data/table schema:

1. Return to the CharacterCreator level in **Avatar Preset / Student** mode. Click **+ beside HairStyle**, enter **SWPlaceholderHair** (no spaces/special characters), and confirm.
2. The tool generates `BP_ModMutator`, `Data/AvatarPresets`, `DT_AddAvatarPresetPieceDefinitions` and the new `AvatarPresetDefinition`, with the required avatar table extension. Keep the registration scoped to these new mod-owned records. Review Gender/Sort Order in the new table if needed; do not edit base-game records.
3. Inside the new part's mod folder create **Miscellaneous → Data Asset → CharacterPiece**, named **DA_SWPlaceholderHairPiece**. Set **Character Classification = Human**, **Character Piece Type = Hair**, **Gender = Any**, **Default Mesh = SK_SWPlaceholderHair**. Do not configure a head facial pose or replace the body for this hair-only slice.
4. In the generated `AvatarPresetDefinition`, replace its **Character Piece** reference with this new piece. Save only your mod-owned assets.
5. Play CharacterCreator again, choose **SWPlaceholderHair** in HairStyle, and preview native poses. The marker must follow the head while the existing face/body remain visible. Correct fitting/LOD/material issues before uploading.
6. For an icon, use **Enter Icon edit Mode → Save**. This creates `Content/UI/Icons/Character Creator/UI_T_SWPlaceholderHair`. For alpha issues check **Min Alpha = 1**.
7. Create **Miscellaneous → Data Table → IconInfo**, named **DT_AddAvatarPresetIconDefinitions**. Add row **SWPlaceholderHair** (without `UI_T_`), assigning the generated icon.
8. In `BP_ModMutator → UGC Data Table Extensions`, add **Additional Data = DT_AddAvatarPresetIconDefinitions**, **Table To Add To = UI_DT_Icons**. Compile and save. Do not add **Set Character Look Override**, actor-spawn gameplay callbacks or controller overrides.

The new style is opt-in. It does not automatically change an existing character. Character-creation selection is documented; availability of the added style in the barber UI still needs testing. If an existing save cannot select it through native UI, use a disposable mod-enabled character rather than forcing a persistent look override.

## Official packaging and exact private installation

1. Finish account linking through the Kit: WB Games/Epic and CurseForge. Save all mod-owned assets and run the Kit's validation/preview checks. Use the real mod's generated metadata; `configs/mod-description.json` is text for the UI, not a registration manifest.
2. Click **Upload Mod**. In **Mod Upload Window**, choose the current **ShadowWizardAppearance** mod and provide its original logo, summary and description. The Kit uploads native content for **cloud cooking**. Wait for that process to succeed. Do not upload the private ZIP, source FBX, Blender files or Python scripts as mod Content. No `UnrealPak`, stock-UE cook or guessed `~mods` installation is implemented here.
3. Keep the mod unpublished for author testing. The author can test it after upload; up to five collaborators can be granted **Cross Platform Testing** through the author console, if needed.
4. Close the game before backing up the actual saves/config. From this example directory, the toolkit commands are:

```powershell
uv run --project ..\.. um backup create "$env:LOCALAPPDATA\Hogwarts Legacy\Saved\SaveGames" --name sw-appearance-before
uv run --project ..\.. um backup create "$env:LOCALAPPDATA\Hogwarts Legacy\Saved\Config" --name sw-config-before
```

Record the snapshot IDs and restore commands. Verify these directories exist on your installation; an empty or failed backup is not protection. The toolkit supports `um backup restore <name> --snapshot <id>` and creates undo snapshots; do not use destructive clean-up options for this test.

5. Link the same CurseForge account to WB Games, launch the Steam game, then click **MODS → Library → Uploaded**. Choose the uploaded mod and click **Install**.
6. Open **Enable mods**. Left-click a disposable unmodded save to copy it into **Mod saves**; select that copy. Enable only **ShadowWizardAppearance** by moving it from **Disabled mods** to **Enabled mods**.
7. Choose **Apply changes (E) → Apply and continue**. Hover the modded save, press **Enter**, and confirm the modded-save popup. Select the new HairStyle through the applicable native appearance UI and run the checklist below. No game-folder file copy is required by this official path.
8. To stop testing, disable the mod for the test save and return to an untouched unmodded save. Confirm its original appearance/progression. Use the recorded snapshot restore procedure only if a regression requires it.

## In-game acceptance record

For each check record **PASS / FAIL / NOT RUN**, game Steam build, Kit build, source commit, cooked mod version, save ID, screenshot/log evidence and any issue. Locked or unavailable features are **NOT RUN**, not pass. Keep evidence private until reviewed. These checks have not run in this cloud session.

| Check | Expected behavior | Current outcome |
| --- | --- | --- |
| Install/load | The uploaded private version installs and loads without errors | NOT RUN |
| Avatar choice | SWPlaceholderHair appears/selects in native avatar UI | NOT RUN |
| Visible mesh | Marker follows the head; face/body remain intact; no T-pose/culling | NOT RUN |
| Movement | Walk/run/jump/dodge and camera retain normal behavior | NOT RUN |
| Animation | Turns, interactions, combat and dialogue poses remain native | NOT RUN |
| Combat/spells | Available attack, defense and spell actions work as in baseline | NOT RUN |
| Progression | Quests, gear, inventory and unlocked abilities retain their state | NOT RUN |
| Gear states | Changing robes/headwear does not duplicate/remove body parts unexpectedly | NOT RUN |
| Mount states | Available broom/mount poses and return to walking remain functional | NOT RUN |
| Save/restart | The chosen style and native progress persist after save, quit and relaunch | NOT RUN |
| Isolation | An untouched unmodded save keeps its original look and progression | NOT RUN |
| Disable | Disabled-mod behavior and ordinary save access are documented and safe | NOT RUN |

A successful import, editor preview, fake-API test or Blender roundtrip does not substitute for this record. The first required proof is the installed HairStyle running in Hogwarts Legacy. Talion conversion and automatic rival integration remain later work.
