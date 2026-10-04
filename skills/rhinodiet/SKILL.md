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
5. Accept or send findings back to the worker that made the change. Do not patch code yourself.
6. Run creative only for images, textures, or video.
7. Run Godot for GDScript, scenes, signals, the input map, and the export pipeline. Do not give that work to the generic dev worker. Godot reads engine version and conventions from memory and stores short refs. Creative makes the art. Godot places it.
8. Run docs when the user asks for docs or when user-facing technical text needs a rewrite. Store a short ref, not the full text.
9. Run release only when the user asks to package, release, or dev-test. The release script is the only path. Godot prepares the preset and the headless boot. Release still serves.
10. Run the tester for "test the game" and "test this area". The tester plays in a loop or focuses one area. It does not edit scenes, serve, or open a pull request.
11. Write a short memory update of refs plus a compact summary.
12. Compact when the graph is over the size threshold.

Dev, reviewer, creative, Godot, docs, release, and the tester use the worker model in rhinodiet.config.json. That tier is cheaper than the supervisor.

User-visible replies stay tight US English. No em dashes. No semicolons.
