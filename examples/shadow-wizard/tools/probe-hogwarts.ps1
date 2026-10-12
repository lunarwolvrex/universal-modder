# Read-only: reports version/loader metadata; installs nothing and never launches the game.
param(
    [string]$GameRoot = 'C:\Program Files (x86)\Steam\steamapps\common\Hogwarts Legacy',
    [string]$ShadowOfWarRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $GameRoot -PathType Container)) {
    throw "Game directory not found: $GameRoot"
}
$resolvedRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$exeRelative = @('Phoenix\Binaries\Win64\HogwartsLegacy.exe', 'HogwartsLegacy.exe')
$executables = @()
foreach ($relative in $exeRelative) {
    $path = Join-Path $resolvedRoot $relative
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $file = Get-Item -LiteralPath $path
        $executables += [ordered]@{
            relative_path = $relative
            file_version = $file.VersionInfo.FileVersion
            product_version = $file.VersionInfo.ProductVersion
            bytes = $file.Length
        }
    }
}
$steamapps = Split-Path (Split-Path $resolvedRoot -Parent) -Parent
$manifestPath = Join-Path $steamapps 'appmanifest_990080.acf'
$buildID = $null
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw
    if ($manifest -match '"buildid"\s+"([0-9]+)"') { $buildID = $Matches[1] }
}
$loaderPresence = [ordered]@{}
foreach ($relative in @(
    'Phoenix\Binaries\Win64\ue4ss',
    'Phoenix\Binaries\Win64\UE4SS.dll',
    'Phoenix\Binaries\Win64\ue4ss\UE4SS.dll',
    'Phoenix\Binaries\Win64\dwmapi.dll',
    'Phoenix\Binaries\Win64\xinput1_3.dll',
    'Phoenix\Binaries\Win64\ue4ss\Mods',
    'Phoenix\Binaries\Win64\Mods'
)) {
    $loaderPresence[$relative] = Test-Path -LiteralPath (Join-Path $resolvedRoot $relative)
}
$packageCounts = [ordered]@{ pak = 0; utoc = 0; ucas = 0 }
$paksRoot = Join-Path $resolvedRoot 'Phoenix\Content\Paks'
if (Test-Path -LiteralPath $paksRoot -PathType Container) {
    foreach ($extension in @('pak', 'utoc', 'ucas')) {
        # Only the stock package directory, no recursive asset/mod-file traversal.
        $packageCounts[$extension] = @(Get-ChildItem -LiteralPath $paksRoot -File -Filter ('*.' + $extension)).Count
    }
}

# Look for Shadow of War in the same Steam library, or use the explicit optional path.
# This reads Steam manifest metadata and file properties, never model/save contents.
$shadowManifestPath = Join-Path $steamapps 'appmanifest_356190.acf'
$shadowBuildID = $null
$shadowAutoDetected = $false
if ([string]::IsNullOrWhiteSpace($ShadowOfWarRoot)) {
    if (Test-Path -LiteralPath $shadowManifestPath -PathType Leaf) {
        $shadowManifest = Get-Content -LiteralPath $shadowManifestPath -Raw
        if ($shadowManifest -match '"installdir"\s+"([^"\r\n]+)"') {
            $installDir = $Matches[1]
            # A manifest install directory must be one component, not a parent/absolute path.
            if ($installDir -notmatch '[\\/:*?"<>|]' -and $installDir -ne '.' -and $installDir -ne '..') {
                $candidate = Join-Path (Join-Path $steamapps 'common') $installDir
                if (Test-Path -LiteralPath $candidate -PathType Container) {
                    $ShadowOfWarRoot = $candidate
                    $shadowAutoDetected = $true
                }
            }
        }
    }
}
$shadow = [ordered]@{
    detected = $false
    directory_present = $false
    game_executable_present = $false
    detection_scope = 'Same Steam library as Hogwarts, or explicit -ShadowOfWarRoot'
    auto_detected = $shadowAutoDetected
    steam_build_id = $null
    executable = $null
    top_level_archive_count = 0
    top_level_archive_bytes = 0
    talion_asset_conversion_verified = $false
}
if (-not [string]::IsNullOrWhiteSpace($ShadowOfWarRoot)) {
    if (-not (Test-Path -LiteralPath $ShadowOfWarRoot -PathType Container)) {
        throw "Shadow of War directory not found: $ShadowOfWarRoot"
    }
    $resolvedShadow = (Resolve-Path -LiteralPath $ShadowOfWarRoot).Path
    $shadowSteamapps = Split-Path (Split-Path $resolvedShadow -Parent) -Parent
    $selectedShadowManifest = Join-Path $shadowSteamapps 'appmanifest_356190.acf'
    if (Test-Path -LiteralPath $selectedShadowManifest -PathType Leaf) {
        $shadowManifest = Get-Content -LiteralPath $selectedShadowManifest -Raw
        if ($shadowManifest -match '"buildid"\s+"([0-9]+)"') { $shadowBuildID = $Matches[1] }
    }
    $shadow['directory_present'] = $true
    $shadow['steam_build_id'] = $shadowBuildID
    $shadowExe = Join-Path $resolvedShadow 'x64\ShadowOfWar.exe'
    if (Test-Path -LiteralPath $shadowExe -PathType Leaf) {
        $shadow['detected'] = $true
        $shadow['game_executable_present'] = $true
        $file = Get-Item -LiteralPath $shadowExe
        $shadow['executable'] = [ordered]@{
            relative_path = 'x64\ShadowOfWar.exe'
            file_version = $file.VersionInfo.FileVersion
            product_version = $file.VersionInfo.ProductVersion
            bytes = $file.Length
        }
    }
    $archives = @(Get-ChildItem -LiteralPath $resolvedShadow -File | Where-Object { $_.Extension -match '^\.arch[0-9]+$' })
    $shadow['top_level_archive_count'] = $archives.Count
    foreach ($archive in $archives) { $shadow['top_level_archive_bytes'] += $archive.Length }
}
[ordered]@{
    probe_version = 2
    platform = 'Windows'
    steam_build_id = $buildID
    executables = $executables
    loader_path_presence = $loaderPresence
    content_package_counts = $packageCounts
    shadow_of_war = $shadow
    save_directory_present = Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Hogwarts Legacy\Saved\SaveGames')
    note = 'File presence does not establish loader/model compatibility. No save or model contents or credentials were read; no files were changed.'
} | ConvertTo-Json -Depth 5
