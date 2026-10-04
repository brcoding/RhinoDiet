---
name: rhinodiet
description: Open the local RhinoDiet walkthrough page
---

# RhinoDiet

If the user asked to init, run `PYTHONPATH=src python3 -m rhinodiet init` in the project directory and show the output. Do not print a checklist and stop. Otherwise serve the local walkthrough. Do not run the supervisor from this command.

Run `rhinodiet guide` in the project directory. If the page is already up, share its URL and do not start another server. If it is not up, start `rhinodiet guide` in the background, then share the URL.

The page is `http://127.0.0.1:8813/`.

Use `/supervisor` when the user wants the supervisor to plan and delegate.
