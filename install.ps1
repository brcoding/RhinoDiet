# Ask for Cursor, Claude, or ChatGPT, then place the plugin there.
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
    Write-Host "  3  ChatGPT"
    Write-Host "  4  All"
    $choice = Read-Host "Choice"
    switch ($choice) {
        { $_ -in "1", "cursor", "Cursor" } { return "cursor" }
        { $_ -in "2", "claude", "Claude" } { return "claude" }
        { $_ -in "3", "codex", "Codex", "chatgpt", "ChatGPT" } { return "codex" }
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
        policy = [pscustomobject]@{ installation = "INSTALLED_BY_DEFAULT"; authentication = "ON_INSTALL" }
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
    if (-not $data.interface) {
        $data | Add-Member -NotePropertyName interface -NotePropertyValue ([pscustomobject]@{ displayName = "Personal" }) -Force
    }
    $data | Add-Member -NotePropertyName plugins -NotePropertyValue $kept -Force
    $data | ConvertTo-Json -Depth 6 | Set-Content -Path $path -Encoding utf8
}

function Install-HostCopy([string]$name, [string]$srcPath) {
    switch ($name) {
        "cursor" { $dest = Join-Path $homeDir ".cursor\plugins\local\rhinodiet" }
        "claude" { $dest = Join-Path $homeDir ".claude\skills\rhinodiet" }
        "codex" { $dest = Join-Path $homeDir ".codex\plugins\rhinodiet" }
        default { throw "Choose Cursor, Claude, ChatGPT, or all." }
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
        Enable-ChatGptPlugin $dest
    }
}

function Enable-ChatGptPlugin([string]$pluginRoot) {
    $marketPath = Join-Path $homeDir ".agents\plugins\marketplace.json"
    $marketName = "personal"
    if (Test-Path $marketPath) {
        $market = Get-Content -Raw -Path $marketPath | ConvertFrom-Json
        if ($market.name) { $marketName = $market.name }
    }
    $configDir = Join-Path $homeDir ".codex"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $config = Join-Path $configDir "config.toml"
    $marker = "[plugins.`"rhinodiet@$marketName`"]"
    $existing = ""
    if (Test-Path $config) { $existing = Get-Content -Raw -Path $config }
    if (-not $existing.Contains($marker)) {
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::AppendAllText($config, "`r`n$marker`r`nenabled = true`r`n", $utf8)
    }
    $skillSrc = Join-Path $pluginRoot "skills\rhinodiet"
    if (Test-Path $skillSrc) {
        $skillDest = Join-Path $homeDir ".agents\skills\rhinodiet"
        if (Test-Path $skillDest) { Remove-Item -Recurse -Force $skillDest }
        New-Item -ItemType Directory -Force -Path (Split-Path $skillDest) | Out-Null
        Copy-Item -Recurse -Path $skillSrc -Destination $skillDest
    }
    $cache = Join-Path $homeDir ".codex\plugins\cache\$marketName\rhinodiet\local"
    if (Test-Path $cache) { Remove-Item -Recurse -Force $cache }
    New-Item -ItemType Directory -Force -Path (Split-Path $cache) | Out-Null
    Copy-Item -Recurse -Path $pluginRoot -Destination $cache
}

if (-not $env:RHINODIET_HOST -and $args.Count -gt 0) {
    $env:RHINODIET_HOST = $args[0]
}
$hostName = Get-InstallHost
if ($hostName -eq "chatgpt") { $hostName = "codex" }
if ($hostName -notin "cursor", "claude", "codex", "all", "update", "upgrade") {
    throw "Choose Cursor, Claude, ChatGPT, or all."
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
    if (Test-Path (Join-Path $homeDir ".codex\plugins\rhinodiet")) { Write-Output "Restart ChatGPT." }
    if ((Test-Path (Join-Path $homeDir ".cursor\plugins\local\rhinodiet")) -or (Test-Path (Join-Path $homeDir ".claude\skills\rhinodiet"))) {
        Write-Output "Type /rhinodiet."
    }
    if (Test-Path (Join-Path $homeDir ".codex\plugins\rhinodiet")) { Write-Output "In ChatGPT, type @rhinodiet." }
} elseif ($hostName -eq "all") {
    Install-HostCopy "cursor" $src
    Install-HostCopy "claude" $src
    Install-HostCopy "codex" $src
    Write-Output "Reload Cursor."
    Write-Output "Restart Claude Code."
    Write-Output "Restart ChatGPT."
    Write-Output "Type /rhinodiet."
    Write-Output "In ChatGPT, type @rhinodiet."
} else {
    Install-HostCopy $hostName $src
    switch ($hostName) {
        "cursor" {
            Write-Output "Reload Cursor."
            Write-Output "Type /rhinodiet."
        }
        "claude" {
            Write-Output "Restart Claude Code."
            Write-Output "Type /rhinodiet."
        }
        "codex" {
            Write-Output "Restart ChatGPT."
            Write-Output "In ChatGPT, type @rhinodiet."
        }
    }
}
