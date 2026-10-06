---
name: rhinodiet-init
description: RhinoDiet: Create the venv, install the plugin, and copy it into Cursor
---

# Init

Run the setup in the project directory. Do not print a checklist and stop. Show the command output.

From a fresh clone, on Windows:

```bat
py -3 install.py
```

If `py` is not on PATH, run `python install.py`. On Linux and macOS:

```bash
python3 install.py
```

`rhinodiet init` is the same command once that script is on PATH.
