# Ask for Cursor, Claude, or Codex, then place the plugin there.
$ErrorActionPreference = "Stop"
$homeDir = if ($env:RHINODIET_HOME) { $env:RHINODIET_HOME } else { $env:USERPROFILE }
$url = if ($env:RHINODIET_ZIP_URL) { $env:RHINODIET_ZIP_URL } else { "https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip" }

function Get-InstallHost {
    if ($env:RHINODIET_HOST) {
        return $env:RHINODIET_HOST.ToLower()
    }
    Write-Host "Install RhinoDiet for:"
    Write-Host "  1  Cursor"
    Write-Host "  2  Claude"
    Write-Host "  3  Codex"
    $choice = Read-Host "Choice"
    switch ($choice) {
        { $_ -in "1", "cursor", "Cursor" } { return "cursor" }
        { $_ -in "2", "claude", "Claude" } { return "claude" }
        { $_ -in "3", "codex", "Codex" } { return "codex" }
        default { throw "Choose 1, 2, or 3." }
    }
}

function Write-CodexMarketplace([string]$root) {
    $path = Join-Path $root ".agents\plugins\marketplace.json"
    New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
    $entry = [pscustomobject]@{
        name = "rhinodiet"
        source = [pscustomobject]@{ source = "local"; path = "./.codex/plugins/rhinodiet" }
        policy = [pscustomobject]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
        category = "Productivity"
    }
    if (Test-Path $path) {
        $data = Get-Content -Raw -Path $path | ConvertFrom-Json
    } else {
        $data = [pscustomobject]@{ name = "personal"; plugins = @() }
    }
    $kept = @()
    if ($data.plugins) {
        $kept = @($data.plugins | Where-Object { $_.name -ne "rhinodiet" })
    }
    $kept += $entry
    if (-not $data.name) {
        $data | Add-Member -NotePropertyName name -NotePropertyValue "personal" -Force
    }
    $data | Add-Member -NotePropertyName plugins -NotePropertyValue $kept -Force
    $data | ConvertTo-Json -Depth 6 | Set-Content -Path $path -Encoding utf8
}

$hostName = Get-InstallHost
switch ($hostName) {
    "cursor" {
        $dest = Join-Path $homeDir ".cursor\plugins\local\rhinodiet"
        $nextStep = "Reload Cursor."
    }
    "claude" {
        $dest = Join-Path $homeDir ".claude\skills\rhinodiet"
        $nextStep = "Restart Claude Code."
    }
    "codex" {
        $dest = Join-Path $homeDir ".codex\plugins\rhinodiet"
        $nextStep = "Restart Codex."
    }
    default { throw "Choose Cursor, Claude, or Codex." }
}

$zip = Join-Path $env:TEMP "rhinodiet-main.zip"
$unpack = Join-Path $env:TEMP "rhinodiet-unpack"
Invoke-WebRequest -Uri $url -OutFile $zip
if (Test-Path $unpack) {
    Remove-Item -Recurse -Force $unpack
}
Expand-Archive -Path $zip -DestinationPath $unpack -Force
$src = Join-Path $unpack "RhinoDiet-main"
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
}
Move-Item $src $dest
$cursorHooks = Join-Path $dest "hooks\hooks.json"
if ($hostName -ne "cursor" -and (Test-Path $cursorHooks)) {
    Move-Item $cursorHooks (Join-Path $dest "hooks\cursor-hooks.json")
}
if ($hostName -eq "codex") {
    Write-CodexMarketplace $homeDir
}
Write-Output $nextStep
Write-Output "Type /rhinodiet."
