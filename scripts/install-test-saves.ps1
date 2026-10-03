<#
.SYNOPSIS
    Copies the DLL test saves into Civ V's modded save folder.

.DESCRIPTION
    Copies python/dlltest/saves/<name>.Civ5Save to
    ModdedSaves/single/dlltest_<name>.Civ5Save, so each one shows up in
    Mods > Next > Load Game. Modded games save under ModdedSaves/, not Saves/;
    a save in Saves/ loads without the mod and turns it off.

.EXAMPLE
    .\scripts\install-test-saves.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $RepoRoot "python\dlltest\saves"
$Dest = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "My Games\Sid Meier's Civilization 5\ModdedSaves\single"

New-Item -ItemType Directory -Force $Dest | Out-Null
Get-ChildItem $Source -Filter "*.Civ5Save" | ForEach-Object {
    $target = Join-Path $Dest ("dlltest_" + $_.Name)
    Copy-Item $_.FullName $target -Force
    Write-Host "Installed: $target" -ForegroundColor Green
}
