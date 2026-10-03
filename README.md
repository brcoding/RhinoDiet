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
| Dev, reviewer, creative, docs, release | worker | composer-2.5[fast=true] |

Workers default to the cheaper worker tier. The supervisor model is `inherit`, so it stays on the parent model. No API key is required. If `RHINODIET_MODEL_URL` is unset, dev and reviewer use an offline client that records the task and does not invent product code. Creative uses a local SVG or storyboard unless `RHINODIET_CREATIVE_URL` is set. Docs rewrites text locally so facts stay exact without a model call.

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
| Reviewer | `/reviewer` | CodeRabbit-style review. Findings are instructions for dev. |
| Creative | `/creative` | Images, textures, or video. Read style from memory first. |
| Docs | `/docs` | Rewrite technical text. About 30 percent shorter, active voice, facts exact. |
| Release | `/release` | Only for package or release. Write a repeatable script. Commit and open a pull request when asked. |

The docs worker runs when the user asks for docs, or when user-facing technical text needs a rewrite. A docs pass stores a short memory ref, not the full text.

Supervisor flow:

1. Compress the incoming request.
2. Load graph references, not full history.
3. Plan and assign tasks to the cheapest fitting agent.
4. Dev work returns to the reviewer when code changed.
5. The supervisor accepts or sends the review back to dev. It does not patch the code.
6. Creative, docs, and release run only when the request needs them.
7. Write a short memory update of refs plus a compact summary.
8. Compact when over the size threshold.

Inter-agent traffic uses caveman compression. The docs worker still sees the technical passage so it can fix voice without dropping facts. User-visible supervisor replies stay tight US English.

## Hard rules

Comments stay terse. Prose is US English. Use commas and periods. Do not use em dashes. Do not use semicolons in prose. Pass memory ids and short labels, not full blobs, unless a task truly needs the blob.

## Packaging gaps

This repo uses the Cursor plugin manifest at `.cursor-plugin/plugin.json`. Rules, agents, a skill, a command, hooks, and `mcp.json` follow the current plugin docs.

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
- `rhinodiet_release` writes `scripts/release.sh`.
- `rhinodiet_remember` stores a short update and compacts when needed.
- `rhinodiet_get` returns one node body when a task truly needs the blob.

## Token comparison

This comparison uses the Godot 4 Pac-Man clone in `benchmarks/godot-pacman`. The task stays the same across three turns. Without the plugin, each turn sends the prompt again with the spec and the file tree. With RhinoDiet, each turn calls prepare, compress, cite, and the supervisor. Inter-agent text uses caveman compression. Memory passes ids and short labels. Stored bodies stay in the graph. From the second turn the baseline also sends the review notes and earlier replies. The last turn also runs the docs rewriter on one technical passage.

Headline counts use tiktoken `o200k_base`. Output tokens are harness fixtures, counted raw on the baseline and after caveman compression on the plugin path. The last turn counts the original technical passage on the baseline and the docs rewriter output on the plugin path. No live model call was made.

| Condition | Input | Output | Total |
| --- | --- | --- | --- |
| Without plugin | 3890 | 354 | 4244 |
| With RhinoDiet | 1855 | 287 | 2142 |
| Saved | 2035 | 67 | 2102 (49.5%) |

The later turn is the long-context case. Input on that turn is 1535 tokens without the plugin and 267 tokens with RhinoDiet, an 82.6 percent reduction. Without the plugin that turn resends the spec, the file tree, the review notes, and earlier replies. With RhinoDiet that turn cites stored node ids and short labels.

The first turn still sends the spec. Caveman compression and the reviewer pass put that turn's input at 1126 tokens with the plugin and 1061 without it. Output is 67 tokens lower with the plugin on these harness fixtures and the docs rewrite.

Compression kept the maze size (19 columns by 21 rows), the controls (arrow keys and WASD), the win rule (win when every pellet is eaten), the lose rule (lose when a ghost touches the player), and the file names (scripts/player.gd, scripts/ghost.gd, scripts/maze.gd, scripts/hud.gd, scripts/main.gd).

The plugin counter, a local whitespace split, totals 4531 without the plugin and 2162 with it. The table uses tiktoken o200k_base. That count is the headline.

Illustration only, from public list prices. At the OpenAI GPT-4o standard list price of $2.50 per 1M input tokens and $10 per 1M output tokens, published 2 Oct 2026, these counts come to $0.0133 without the plugin and $0.0075 with it. Per 1,000 runs the illustration is $13.30 versus $7.50. The configured worker model is composer-2.5 fast. This sketch uses the GPT-4o list, which is a different price.

Godot 4.3 ran headless on benchmarks/godot-pacman. The main scene loaded, reported 201 pellets and 2 ghosts, and exited cleanly.

Install the dev extra so tiktoken is available. Then rerun the count.

```bash
python -m pip install -e ".[dev]"
python benchmarks/token_compare.py
```

## License

MIT
