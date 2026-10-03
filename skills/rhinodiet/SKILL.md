---
name: rhinodiet
description: Cut tokens. Use when a request should be compressed, delegated to a cheaper worker, rewritten by the docs worker, or answered from graph memory cites.
---

# RhinoDiet

Use the rhinodiet MCP server. The supervisor delegates. It does not implement.

1. Compress the request.
2. Load graph cites, not history.
3. Plan and assign the cheapest fitting agent.
4. Send code changes to the reviewer.
5. Accept or send findings back to dev. Do not patch code yourself.
6. Run creative only for images, textures, or video.
7. Run docs when the user asks for docs or when user-facing technical text needs a rewrite. Store a short ref, not the full text.
8. Run release only when the user asks to package or release.
9. Write a short memory update of refs plus a compact summary.
10. Compact when the graph is over the size threshold.

Dev, reviewer, creative, docs, and release use the worker model in rhinodiet.config.json. That tier is cheaper than the supervisor.

User-visible replies stay tight US English. No em dashes. No semicolons.
