---
name: rhinodiet-init
description: RhinoDiet: Create the venv, install the plugin, and copy it into Cursor
---

# Init

Run the setup in the project directory. Do not print a checklist and stop. Show the command output.

From a fresh clone, before the console script exists:

```bash
PYTHONPATH=src python3 -m rhinodiet init
```

`rhinodiet init` is the same command once that script is on PATH. Run it in WSL, not PowerShell.
