---
name: rhinodiet
description: Run the RhinoDiet supervisor on the current request
---

# RhinoDiet

Call the rhinodiet MCP tool rhinodiet_prepare with the user request.

Spawn only the assigned agents on the worker model from rhinodiet.config.json.

Do not implement the work in this turn. Delegate, review, and send work back.

If the assignment includes docs, call rhinodiet_docs. Keep the memory write to a short ref.

If the assignment includes tester, call rhinodiet_test. That plays the game. It does not edit scenes.

Reply in tight US English. Include cite ids. Do not paste memory blobs.
