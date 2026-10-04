"""Local history of game-test runs. Stills stay under .rhinodiet/tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

PAGE_PORT = 8797
METRICS = (
    ("pellets_eaten", "Pellets eaten"),
    ("time_survived", "Time survived"),
    ("ghosts_hit", "Ghosts hit"),
    ("board_cleared", "Board cleared"),
)


def tests_dir(root: Path) -> Path:
    path = root / ".rhinodiet" / "tests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_path(root: Path) -> Path:
    return tests_dir(root) / "history.json"


def load_history(root: Path) -> dict:
    path = history_path(root)
    if not path.is_file():
        return {"runs": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        return {"runs": []}
    return data


def compare_metrics(current: dict, previous: dict) -> str:
    parts = []
    for key, label in METRICS:
        now = current[key]
        then = previous[key]
        if isinstance(now, bool):
            parts.append(f"{label} {'yes' if now else 'no'} versus {'yes' if then else 'no'}.")
            continue
        diff = round(float(now) - float(then), 1)
        if key == "time_survived":
            if diff == 0:
                parts.append(f"{label} {now} seconds versus {then} seconds, unchanged.")
            else:
                direction = "up" if diff > 0 else "down"
                parts.append(
                    f"{label} {now} seconds versus {then} seconds, {direction} {abs(diff)}."
                )
            continue
        if diff == 0:
            parts.append(f"{label} {now} versus {then}, unchanged.")
        else:
            direction = "up" if diff > 0 else "down"
            amount = int(abs(diff)) if float(abs(diff)).is_integer() else abs(diff)
            parts.append(f"{label} {now} versus {then}, {direction} {amount}.")
    return " ".join(parts)


def record_run(
    root: Path,
    *,
    mode: str,
    area: str,
    passed: bool,
    result: str,
    metrics: dict,
    frames: list[bytes],
) -> dict:
    folder_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + area
    base = tests_dir(root)
    folder = base / folder_name
    suffix = 2
    while folder.exists():
        folder = base / f"{folder_name}-{suffix}"
        suffix += 1
    folder.mkdir(parents=True)
    images = []
    for index, blob in enumerate(frames):
        name = f"frame-{index:03d}.png"
        (folder / name).write_bytes(blob)
        images.append(name)
    data = load_history(root)
    previous = next((item for item in reversed(data["runs"]) if item.get("area") == area), None)
    versus = compare_metrics(metrics, previous["metrics"]) if previous else ""
    entry = {
        "id": folder.name,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "area": area,
        "passed": passed,
        "result": result,
        "metrics": metrics,
        "images": images,
        "versus": versus,
    }
    data["runs"].append(entry)
    history_path(root).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return entry


def page_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RhinoDiet test history</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font: 16px/1.45 ui-sans-serif, system-ui, sans-serif; background: #12160f; color: #f3f0e6; }
  header, main { max-width: 980px; margin: 0 auto; padding: 24px 20px; }
  h1 { font-size: 28px; margin: 0 0 8px; }
  p { margin: 0 0 12px; }
  .muted { color: #b7b29f; }
  .layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
  button.run { display: block; width: 100%; text-align: left; margin: 0 0 8px; padding: 10px 12px; border: 1px solid #3a4030; border-radius: 10px; background: #1b2116; color: inherit; cursor: pointer; }
  button.run.active { border-color: #ffd56a; }
  .pass { color: #b6e38a; }
  .fail { color: #ff8d7a; }
  .frames { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; }
  .frames img { height: 180px; background: #070910; border-radius: 8px; image-rendering: pixelated; }
  label { display: block; margin: 12px 0 6px; color: #b7b29f; }
  select { font: inherit; padding: 8px; background: #1b2116; color: inherit; border: 1px solid #3a4030; border-radius: 8px; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>Test history</h1>
  <p class="muted">Each run keeps the time, the mode, the area, pass or fail, a short result, and stills from the driver.</p>
</header>
<main>
  <p id="empty" class="muted" hidden>No test runs yet. Run rhinodiet test, or rhinodiet test --focus "avoid ghosts", then refresh.</p>
  <div class="layout" id="layout" hidden>
    <div id="list"></div>
    <section id="detail"></section>
  </div>
</main>
<script>
const empty = document.getElementById("empty");
const layout = document.getElementById("layout");
const list = document.getElementById("list");
const detail = document.getElementById("detail");
let runs = [];
let selected = "";

function earlier(run) {
  return runs.filter((item) => item.area === run.area && item.at < run.at);
}

function sentence(label, now, then) {
  if (typeof now === "boolean") {
    const left = now ? "yes" : "no";
    const right = then ? "yes" : "no";
    return label + " " + left + " versus " + right + ".";
  }
  const diff = Math.round((Number(now) - Number(then)) * 10) / 10;
  if (label === "Time survived") {
    if (diff === 0) return label + " " + now + " seconds versus " + then + " seconds, unchanged.";
    const direction = diff > 0 ? "up" : "down";
    return label + " " + now + " seconds versus " + then + " seconds, " + direction + " " + Math.abs(diff) + ".";
  }
  if (diff === 0) return label + " " + now + " versus " + then + ", unchanged.";
  const direction = diff > 0 ? "up" : "down";
  return label + " " + now + " versus " + then + ", " + direction + " " + Math.abs(diff) + ".";
}

function show(id) {
  selected = id;
  const run = runs.find((item) => item.id === id);
  if (!run) return;
  for (const button of list.querySelectorAll("button.run")) {
    button.classList.toggle("active", button.dataset.id === id);
  }
  const prior = earlier(run);
  const images = (run.images || []).map((name) => {
    return '<img alt="Still from ' + run.area + '" src="/runs/' + run.id + '/' + name + '">';
  }).join("");
  const options = prior.map((item) => {
    return '<option value="' + item.id + '">' + item.at + " " + (item.passed ? "pass" : "fail") + "</option>";
  }).join("");
  detail.innerHTML = `
    <h2>${run.area}</h2>
    <p class="${run.passed ? "pass" : "fail"}">${run.passed ? "Pass" : "Fail"}. ${run.mode} at ${run.at}.</p>
    <p>${run.result}</p>
    <div class="frames">${images || "<p class='muted'>No stills.</p>"}</div>
    <label for="prior">Compare with an earlier run of this area</label>
    <select id="prior" ${prior.length ? "" : "disabled"}>
      ${options || "<option>No earlier run</option>"}
    </select>
    <div id="versus"></div>
  `;
  const select = document.getElementById("prior");
  const versus = document.getElementById("versus");
  function paint() {
    if (!prior.length) {
      versus.innerHTML = "<p class='muted'>No earlier run of this area.</p>";
      return;
    }
    const other = runs.find((item) => item.id === select.value) || prior[prior.length - 1];
    const lines = [
      ["Pellets eaten", run.metrics.pellets_eaten, other.metrics.pellets_eaten],
      ["Time survived", run.metrics.time_survived, other.metrics.time_survived],
      ["Ghosts hit", run.metrics.ghosts_hit, other.metrics.ghosts_hit],
      ["Board cleared", run.metrics.board_cleared, other.metrics.board_cleared],
    ].map((row) => "<p>" + sentence(row[0], row[1], row[2]) + "</p>").join("");
    versus.innerHTML = lines;
  }
  if (select) select.addEventListener("change", paint);
  paint();
}

fetch("/api/history").then((response) => response.json()).then((data) => {
  runs = data.runs || [];
  if (!runs.length) {
    empty.hidden = false;
    return;
  }
  layout.hidden = false;
  const ordered = runs.slice().reverse();
  list.innerHTML = ordered.map((run) => {
    const mark = run.passed ? "pass" : "fail";
    return '<button class="run" data-id="' + run.id + '"><strong>' + run.area + '</strong><br><span class="muted">' + run.mode + " · " + run.at + '</span><br><span class="' + mark + '">' + mark + "</span></button>";
  }).join("");
  for (const button of list.querySelectorAll("button.run")) {
    button.addEventListener("click", () => show(button.dataset.id));
  }
  show(ordered[0].id);
});
</script>
</body>
</html>
"""


def serve(root: Path, port: int = PAGE_PORT) -> None:
    base = tests_dir(root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = unquote(self.path.split("?", 1)[0])
            if path in {"/", "/index.html"}:
                self._send(200, page_html().encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/history":
                payload = json.dumps(load_history(root)).encode("utf-8")
                self._send(200, payload, "application/json")
                return
            if path.startswith("/runs/"):
                target = (base / path[len("/runs/") :]).resolve()
                if base not in target.parents or not target.is_file():
                    self._send(404, b"Missing still.", "text/plain; charset=utf-8")
                    return
                mime = "image/png" if target.suffix == ".png" else "application/octet-stream"
                self._send(200, target.read_bytes(), mime)
                return
            self._send(404, b"Not found.", "text/plain; charset=utf-8")

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Test history at http://127.0.0.1:{port}/")
    server.serve_forever()
