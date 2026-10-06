---
name: rhinodiet-update
description: RhinoDiet: Update the plugin to the latest on GitHub
---

# Update

Download the latest RhinoDiet from GitHub and refresh every host that is already installed. `/rhinodiet-upgrade` and `/rhinodiet upgrade` are the same command. Show the output. Do not print a checklist and stop.

On Windows, in PowerShell:

```powershell
$env:RHINODIET_HOST = "update"
irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex
```

On Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh -s update
```

Inside a checkout, `rhinodiet update` does the same thing.
