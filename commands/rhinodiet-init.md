---
name: rhinodiet-init
description: RhinoDiet: Install the plugin for Cursor, Claude, or Codex
---

# Init

Run one command and show the output. The installer shows a menu. Pick Cursor, Claude, or Codex. Do not print a checklist and stop.

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex
```

On Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh
```

`rhinodiet init` installs the console script inside a checkout. Loading the plugin does not need it.
