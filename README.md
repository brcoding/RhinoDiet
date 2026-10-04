# RhinoDiet

RhinoDiet is a Cursor plugin that cuts token use. It compresses prompts, delegates work to cheaper models, and stores project memory in a local SQLite graph. Later prompts cite node ids instead of pasting the same context again.

## Install

From this repo:

```bash
python -m pip install -e ".[dev]"
```

Load the plugin in Cursor:

1. Copy this directory to `~/.cursor/plugins/local/rhinodiet`.
2. Reload Cursor.
3. Open Customize and confirm the RhinoDiet rules, agents, and MCP server.

Local plugin imports must be allowed. On Enterprise that setting stays off until an admin enables Allow Local Plugin Imports.

Play the built-in Pac-Man example in a short loop:

```bash
rhinodiet test
```

Play one area:

```bash
rhinodiet test --focus "avoid ghosts"
```

Open the history page:

```bash
rhinodiet test --serve
```

The page is `http://127.0.0.1:8797/`. It reads `.rhinodiet/tests/`, which is gitignored. Stills and `history.json` stay there.

Show the saved runs and the commands that run tests:

```bash
rhinodiet test --show
```

In Cursor, `/showtests` runs that same read.

Cursor skips a symlink in `~/.cursor/plugins/local` when the target sits outside that folder. Copy the directory.

## Run

Headless supervisor, no API key:

```bash
rhinodiet run "add a token expiry check in src/auth/session.py"
```

Compress a prompt:

```bash
rhinodiet compress --mode caveman "Please just really explain the bug"
```

Rewrite technical text:

```bash
rhinodiet docs "The token is validated by the gate."
```

Cite memory:

```bash
rhinodiet cite "token expiry"
```

Compact the graph:

```bash
rhinodiet compact
```

Tests:

```bash
python -m pytest
```

Cursor starts the MCP server from `mcp.json`. You can also run it yourself:

```bash
python -m rhinodiet.mcp_server
```

## Model tiers

`rhinodiet.config.json` sets the tiers.

| Role | Tier | Default model |
| --- | --- | --- |
| Supervisor | supervisor | inherit |
| Dev, reviewer, creative, Godot, docs, release, tester | worker | composer-2.5[fast=true] |

Workers default to the cheaper worker tier. The supervisor model is `inherit`, so it stays on the parent model. No API key is required. If `RHINODIET_MODEL_URL` is unset, dev, Godot, and reviewer use an offline client that records the task and does not invent product code. Creative uses a local SVG or storyboard unless `RHINODIET_CREATIVE_URL` is set. Docs rewrites text locally so facts stay exact without a model call. Godot stores the engine version and conventions as short refs, and it writes the Web export preset the release script already uses.

## Memory

The graph file is `.rhinodiet/memory.db` under the project directory (`CURSOR_PROJECT_DIR`, else the current working directory). It is gitignored.

Nodes have a label, a short summary, salience, and a horizon of `short` or `long`. Edges are typed. `rhinodiet cite` answers what the next prompt should cite. It returns ids, labels, and short summaries. It does not return stored bodies.

Compaction runs when the node count passes `memory.compact_after_nodes` (default 48). It merges stale short-term nodes into a smaller long-term project model and drops the detail.

This is a thin graph API on SQLite. It keeps labeled nodes and typed edges in the project tree, with no separate database server.

## Agents

Invoke an agent with `/name` in Cursor chat, or ask the supervisor to delegate.

| Agent | Invoke | Job |
| --- | --- | --- |
| Supervisor | `/supervisor` or `/rhinodiet` | Plan, delegate, review, send work back. Does not write product code. |
| Dev | `/dev` | Simple code with straightforward unit tests. Prefer existing libraries. |
| Reviewer | `/reviewer` | CodeRabbit-style review. Findings are instructions for the worker that made the change. Godot reviews use a short checklist. |
| Creative | `/creative` | Images, textures, or video. Read style from memory first. |
| Godot | `/godot` | Godot 4 scenes, GDScript, signals, the input map, and the export pipeline. Read engine version from memory first. |
| Tester | `/tester` | Play a registered game in a loop, or focus one area. Read area refs from memory first. |
| Docs | `/docs` | Rewrite technical text. About 30 percent shorter, active voice, facts exact. |
| Release | `/release` | Only for package, release, or a dev test. Write scripts/release.sh and run that script. |

The docs worker runs when the user asks for docs, or when user-facing technical text needs a rewrite. A docs pass stores a short memory ref, not the full text.

Supervisor flow:

1. Compress the incoming request.
2. Load graph references, not full history.
3. Plan and assign tasks to the cheapest fitting agent.
4. Dev work returns to the reviewer when code changed. Godot work and pipeline integration go to the Godot worker, not the generic dev worker. Godot code changes return to the reviewer with the short checklist.
5. The supervisor accepts or sends the review back to the worker that made the change. It does not patch the code.
6. Creative, Godot, docs, release, and the tester run only when the request needs them. Creative makes the art. Godot places it. The tester plays. Release still serves, starts cloudflared when it is on PATH, commits, and opens pull requests.
7. Write a short memory update of refs plus a compact summary.
8. Compact when over the size threshold.

Inter-agent traffic uses caveman compression. The docs worker still sees the technical passage so it can fix voice without dropping facts. User-visible supervisor replies stay tight US English.

## Hard rules

Comments stay terse. Prose is US English. Use commas and periods. Do not use em dashes. Do not use semicolons in prose. Pass memory ids and short labels, not full blobs, unless a task truly needs the blob.

## Packaging gaps

This repo uses the Cursor plugin manifest at `.cursor-plugin/plugin.json`. Rules, agents, a skill, commands, hooks, and `mcp.json` follow the current plugin docs.

Cursor cannot express the whole product inside the manifest:

- `beforeSubmitPrompt` can block a prompt. It cannot replace the prompt text. Input compression runs in the supervisor and the MCP tools.
- `afterAgentResponse` cannot rewrite the assistant message. Output compression applies to inter-agent traffic inside the runtime. User-visible text is tightened by the supervisor reply path. Technical rewrites go through the docs worker.
- Plugin agent docs list `name` and `description`. Worker model ids live in `rhinodiet.config.json`. The same ids are set on agent frontmatter `model`, which the subagent docs support. If a build ignores `model` on plugin agents, the Python supervisor still passes the worker model when it dispatches.
- A plugin cannot force the parent model to spawn subagents. The supervisor prompt and `rhinodiet_prepare` tell it the assignments. `rhinodiet_run` runs the same loop against a model client for tests and headless use.
- Video generation without credentials writes a storyboard file. Images write an SVG. Set `RHINODIET_CREATIVE_URL` to plug in another provider.

## MCP tools

- `rhinodiet_prepare` compresses, cites, and returns assignments.
- `rhinodiet_run` runs the full loop.
- `rhinodiet_compress` compresses text.
- `rhinodiet_cite` returns references.
- `rhinodiet_docs` rewrites technical text and stores a short ref.
- `rhinodiet_creative` reads or defines style and writes a local artifact.
- `rhinodiet_godot` reads or defines Godot refs and prepares the shared export preset. It does not serve.
- `rhinodiet_test` plays a registered game in a loop, or focuses one area. It records stills under `.rhinodiet/tests/`.
- `rhinodiet_release` writes `scripts/release.sh`.
- `rhinodiet_remember` stores a short update and compacts when needed.
- `rhinodiet_get` returns one node body when a task truly needs the blob.

## Game tests

Two modes use the same tester path. `rhinodiet test` is endurance. It plays to clear the board, twice by default, so a run can finish. `rhinodiet test --loops 4` or a request that asks for a longer run raises the cap. `rhinodiet test --focus "avoid ghosts"` plays one area and ignores the rest.

Focus maps the phrase to a stored area. The score prefers an exact goal, name, or alias, then a phrase contained in the shorter goal. "avoid ghosts" selects `avoid-ghosts`. "restart" selects `restart`. "reach the end while avoiding ghosts" and "beat the level" select `clear-board`.

The default run and "beat the level" mean clear the board. The driver reads the player, the ghosts, and the pellets. It eats pellets and flees ghosts until the board is clear, a ghost hits, or the safety cap. It does not stop on a 4 second timer. Four seconds alive with pellets left is a fail. A death records how far that attempt got. The endurance loop then tries again until the loop cap. Avoid ghosts uses the same chase. It passes only when the board is clear and no ghost caught Pac-Man. Restart is the only area that does not try to clear the board.

Pac-Man in `benchmarks/godot-pacman` is the built-in example. The headless driver simulates input. It does not rebuild the export on port 8741. Areas:

| Area | Goal | Pass | Fail |
| --- | --- | --- | --- |
| avoid-ghosts | Avoid ghosts. | Board clear and no ghost hit. | Pellets remain or a ghost catches Pac-Man. |
| restart | Restart. | R restores pellets and the start cell. | The board stays ended. |
| clear-board | Reach the end while avoiding ghosts. | No pellets left and no ghost hit. | A hit or pellets remain. |

A game with no areas yet gets short refs from the tester: name, goal, and how to tell pass from fail. Later runs cite those ids. New games register areas the same way. The supervisor does not special-case Pac-Man.

Each run records the time, the mode (`loop` or `focus`), the area name, pass or fail, a short result, and stills spread across the attempt. For Pac-Man the page also compares pellets eaten, time survived, ghosts hit, and whether the board was cleared with the previous run of that area. You can pick an earlier run of the same area on the page.

`/showtests` reads `.rhinodiet/tests/history.json` and lists the commands that run tests. `rhinodiet test --show` is the same read. It does not start a new run.

Godot still owns scenes and the export pipeline. The tester drives play. Release still serves, commits, and opens pull requests.

## Token comparison

This comparison uses the Godot 4 Pac-Man clone in `benchmarks/godot-pacman`. The task stays the same across three turns. Without the plugin, each turn sends the prompt again with the spec and the file tree. With RhinoDiet, each turn calls prepare, compress, cite, and the supervisor. Inter-agent text uses caveman compression. Memory passes ids and short labels. Stored bodies stay in the graph. From the second turn the baseline also sends the review notes and earlier replies. The last turn also runs the docs rewriter on one technical passage.

Headline counts use tiktoken `o200k_base`. Output tokens are harness fixtures, counted raw on the baseline and after caveman compression on the plugin path. The last turn counts the original technical passage on the baseline and the docs rewriter output on the plugin path. No live model call was made.

| Condition | Input | Output | Total |
| --- | --- | --- | --- |
| Without plugin | 3890 | 354 | 4244 |
| With RhinoDiet | 1914 | 287 | 2201 |
| Saved | 1976 | 67 | 2043 (48.1%) |

The later turn is the long-context case. Input on that turn is 1535 tokens without the plugin and 267 tokens with RhinoDiet, an 82.6 percent reduction. Without the plugin that turn resends the spec, the file tree, the review notes, and earlier replies. With RhinoDiet that turn cites stored node ids and short labels.

The first turn still sends the spec. Caveman compression and the reviewer pass put that turn's input at 1191 tokens with the plugin and 1061 without it. Output is 67 tokens lower with the plugin on these harness fixtures and the docs rewrite.

Compression kept the maze size (19 columns by 21 rows), the controls (arrow keys and WASD), the win rule (win when every pellet is eaten), the lose rule (lose when a ghost touches the player), and the file names (scripts/player.gd, scripts/ghost.gd, scripts/maze.gd, scripts/hud.gd, scripts/main.gd).

The plugin counter, a local whitespace split, totals 4531 without the plugin and 2217 with it. The table uses tiktoken o200k_base. That count is the headline.

Illustration only, from public list prices. At the OpenAI GPT-4o standard list price of $2.50 per 1M input tokens and $10 per 1M output tokens, published 2 Oct 2026, these counts come to $0.0133 without the plugin and $0.0077 with it. Per 1,000 runs the illustration is $13.30 versus $7.70. The configured worker model is composer-2.5 fast. This sketch uses the GPT-4o list, which is a different price.

Godot 4.3 ran headless on benchmarks/godot-pacman. The main scene loaded, reported 201 pellets and 2 ghosts, and exited cleanly.

Install the dev extra so tiktoken is available. Then rerun the count.

```bash
python -m pip install -e ".[dev]"
python benchmarks/token_compare.py
```

## Measured agent runs

The table above is a synthetic harness. It does not call a live model.

The build and the dev-test release were separate cloud agent runs. The totals below are reconstructed from the exported transcripts with tiktoken `o200k_base`. Each prompt and output string is counted once. This is not a provider bill. The export had no usage field. The system prompt was not in the export. Arguments for edit, search, and web tools were not in the export, so output is a lower bound. Edit diffs are counted as input. The record is `benchmarks/measured/pacman-agents.json`.

| Run | Input | Output | Total |
| --- | --- | --- | --- |
| Build `bc-01b54d90-3b71-589a-a51d-966be7a5b6f3` | 48472 | 41838 | 90310 |
| Dev-test release `bc-fb2e8e48-a482-5978-ac16-31d7c59e648e` | 46373 | 50793 | 97166 |

The release transcript has three user turns. Counted once, the launch is 71746 tokens, the IPv6 follow-up is 7071, and the tunnel follow-up is 18349. The first reply published a localhost URL. The next turn fixed an IPv4-only bind. A later turn started a tunnel by hand. `scripts/release.sh` was not what served the game.

Resending prior transcript text on each generation reconstructs 3921856 tokens for the build and 4690453 tokens for the release. That replay figure is not a bill.

Record another transcript with the same counter. Serve a dev test, or publish, from the same script.

```bash
rhinodiet tokens record transcript.json
scripts/release.sh dev-test
scripts/release.sh publish
```

`scripts/release.sh dev-test` exports the Godot HTML5 build when Godot is on PATH, serves it on IPv4 and IPv6, and prints both local URLs. When cloudflared is on PATH, that same command starts the tunnel and prints the public URL. `scripts/release.sh publish` commits, pushes, and opens a draft pull request when the branch does not already have an open one.

## License

MIT
