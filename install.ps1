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
    Write-Host "  4  All"
    $choice = Read-Host "Choice"
    switch ($choice) {
        { $_ -in "1", "cursor", "Cursor" } { return "cursor" }
        { $_ -in "2", "claude", "Claude" } { return "claude" }
        { $_ -in "3", "codex", "Codex" } { return "codex" }
        { $_ -in "4", "all", "All" } { return "all" }
        default { throw "Choose 1, 2, 3, or 4." }
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

function Install-HostCopy([string]$name, [string]$srcPath) {
    switch ($name) {
        "cursor" { $dest = Join-Path $homeDir ".cursor\plugins\local\rhinodiet" }
        "claude" { $dest = Join-Path $homeDir ".claude\skills\rhinodiet" }
        "codex" { $dest = Join-Path $homeDir ".codex\plugins\rhinodiet" }
        default { throw "Choose Cursor, Claude, Codex, or all." }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
    }
    Copy-Item -Recurse -Path $srcPath -Destination $dest
    $cursorHooks = Join-Path $dest "hooks\hooks.json"
    if ($name -ne "cursor" -and (Test-Path $cursorHooks)) {
        Move-Item $cursorHooks (Join-Path $dest "hooks\cursor-hooks.json")
    }
    if ($name -eq "codex") {
        Write-CodexMarketplace $homeDir
    }
}

if (-not $env:RHINODIET_HOST -and $args.Count -gt 0) {
    $env:RHINODIET_HOST = $args[0]
}
$hostName = Get-InstallHost
if ($hostName -notin "cursor", "claude", "codex", "all", "update", "upgrade") {
    throw "Choose Cursor, Claude, Codex, or all."
}
$zip = Join-Path $env:TEMP "rhinodiet-main.zip"
$unpack = Join-Path $env:TEMP "rhinodiet-unpack"
Invoke-WebRequest -Uri $url -OutFile $zip
if (Test-Path $unpack) {
    Remove-Item -Recurse -Force $unpack
}
Expand-Archive -Path $zip -DestinationPath $unpack -Force
$src = Join-Path $unpack "RhinoDiet-main"
if ($hostName -in "update", "upgrade") {
    $targets = @()
    if (Test-Path (Join-Path $homeDir ".cursor\plugins\local\rhinodiet")) { $targets += "cursor" }
    if (Test-Path (Join-Path $homeDir ".claude\skills\rhinodiet")) { $targets += "claude" }
    if (Test-Path (Join-Path $homeDir ".codex\plugins\rhinodiet")) { $targets += "codex" }
    if ($targets.Count -eq 0) { $targets = @("cursor", "claude", "codex") }
    foreach ($name in $targets) { Install-HostCopy $name $src }
    Write-Output "Updated from GitHub."
    if (Test-Path (Join-Path $homeDir ".cursor\plugins\local\rhinodiet")) { Write-Output "Reload Cursor." }
    if (Test-Path (Join-Path $homeDir ".claude\skills\rhinodiet")) { Write-Output "Restart Claude Code." }
    if (Test-Path (Join-Path $homeDir ".codex\plugins\rhinodiet")) { Write-Output "Restart Codex." }
} elseif ($hostName -eq "all") {
    Install-HostCopy "cursor" $src
    Install-HostCopy "claude" $src
    Install-HostCopy "codex" $src
    Write-Output "Reload Cursor."
    Write-Output "Restart Claude Code."
    Write-Output "Restart Codex."
} else {
    Install-HostCopy $hostName $src
    switch ($hostName) {
        "cursor" { Write-Output "Reload Cursor." }
        "claude" { Write-Output "Restart Claude Code." }
        "codex" { Write-Output "Restart Codex." }
    }
}
Write-Output "Type /rhinodiet."
