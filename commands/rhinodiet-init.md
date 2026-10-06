---
name: rhinodiet-init
description: RhinoDiet: Install the plugin into Cursor
---

# Init

Run one command and show the output. Do not print a checklist and stop.

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex
```

On Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh
```

`rhinodiet init` installs the console script inside a checkout. Loading the plugin does not need it.
