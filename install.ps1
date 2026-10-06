# Place RhinoDiet where Cursor loads local plugins.
$ErrorActionPreference = "Stop"
$homeDir = if ($env:RHINODIET_HOME) { $env:RHINODIET_HOME } else { $env:USERPROFILE }
$dest = Join-Path $homeDir ".cursor\plugins\local\rhinodiet"
$parent = Split-Path $dest
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$url = if ($env:RHINODIET_ZIP_URL) { $env:RHINODIET_ZIP_URL } else { "https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip" }
$zip = Join-Path $env:TEMP "rhinodiet-main.zip"
$unpack = Join-Path $env:TEMP "rhinodiet-unpack"
Invoke-WebRequest -Uri $url -OutFile $zip
if (Test-Path $unpack) {
    Remove-Item -Recurse -Force $unpack
}
Expand-Archive -Path $zip -DestinationPath $unpack -Force
$src = Join-Path $unpack "RhinoDiet-main"
if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
}
Move-Item $src $dest
Write-Output "Reload Cursor."
Write-Output "Type /rhinodiet."
