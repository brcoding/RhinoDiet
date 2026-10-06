---
name: rhinodiet-upgrade
description: RhinoDiet: Update the plugin to the latest on GitHub
---

# Upgrade

Download the latest RhinoDiet from GitHub and refresh every host that is already installed. `/rhinodiet-update` and `/rhinodiet update` are the same command. Show the output. Do not print a checklist and stop.

On Windows, in PowerShell:

```powershell
$env:RHINODIET_HOST = "upgrade"
irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex
```

On Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh -s upgrade
```

Inside a checkout, `rhinodiet upgrade` does the same thing.
