"""Supervisor plans and delegates. It never writes product code."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from rhinodiet.compress import compress, user_visible
from rhinodiet.config import Config
from rhinodiet.creative import CreativeService
from rhinodiet.docs import DocsResult, DocsWriter
from rhinodiet.graph import Citation, GraphStore, format_cites
from rhinodiet.release import ReleaseWriter

DEV_SYSTEM = (
    "You are the dev worker. Return JSON only with keys summary, code_changed, files, tests. "
    "Write simple code and straightforward unit tests. Prefer existing libraries. "
    "Terse comments. US English. No em dashes. No semicolons in prose."
)
REVIEW_SYSTEM = (
    "You are the reviewer. Return JSON only with keys accept and findings. "
    "Findings are instructions for the dev worker. Do not edit code."
)

_DEV = re.compile(
    r"\b(add|implement|fix|build|create|update|refactor|bug|test|function|code|feature|parser)\b",
    re.I,
)
_REVIEW = re.compile(r"\b(review|audit)\b", re.I)
_CREATIVE = re.compile(
    r"\b(image|images|texture|textures|video|logo|icon|illustration|mockup)\b",
    re.I,
)
_RELEASE = re.compile(r"\b(package|release|pull request)\b|\bopen a pr\b", re.I)
_DOCS_WORD = re.compile(
    r"\b(docs|documentation|readme|release notes)\b|\bdocument(?:\s+(?:the|this|how|our))?\b",
    re.I,
)
_REWRITE_TEXT = re.compile(
    r"\b(?:rewrite|shorten|clarify|tighten)\b.{0,48}\b(?:text|section|paragraph|prose|copy|docs|readme|sentence)s?\b",
    re.I,
)
_PASSIVE_BY = re.compile(r"\b(?:is|are|was|were)\s+[A-Za-z]+(?:ed|en)\s+by\b", re.I)
_TECH = re.compile(
    r"\b(?:api|function|module|token|config|handler|endpoint|class|middleware|session)\b"
    r"|[/]|[A-Z][a-z0-9]+[A-Z]",
)


class ModelClient:
    def complete(self, agent: str, model: str, system: str, user: str) -> str:
        raise NotImplementedError


class OfflineModel(ModelClient):
    """No API key. Records the task. Does not invent product code."""

    def complete(self, agent: str, model: str, system: str, user: str) -> str:
        if agent == "supervisor":
            raise RuntimeError("supervisor does not implement")
        if agent == "reviewer":
            return json.dumps({"accept": True, "findings": []})
        if agent == "dev":
            return json.dumps(
                {
                    "summary": "Queued the dev task for a worker model.",
                    "code_changed": False,
                    "files": [],
                    "tests": [],
                }
            )
        raise RuntimeError(f"no model call for {agent}")


class HttpModel(ModelClient):
    def __init__(self, url: str, fallback: ModelClient):
        self.url = url
        self.fallback = fallback

    def complete(self, agent: str, model: str, system: str, user: str) -> str:
        try:
            payload = json.dumps(
                {"agent": agent, "model": model, "system": system, "user": user}
            ).encode()
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            token = os.environ.get("RHINODIET_MODEL_TOKEN")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            if isinstance(data, dict) and "text" in data:
                return str(data["text"])
            return json.dumps(data)
        except Exception:
            return self.fallback.complete(agent, model, system, user)


def default_model() -> ModelClient:
    url = os.environ.get("RHINODIET_MODEL_URL")
    offline = OfflineModel()
    if not url:
        return offline
    return HttpModel(url, offline)


@dataclass
class DevResult:
    summary: str
    code_changed: bool
    files: list[str]
    tests: list[str]


@dataclass
class RunReport:
    reply: str
    agents: list[str]
    cites: list[Citation]
    memory_id: str
    compacted: bool
    accepted: bool
    delegations: list[tuple[str, str]] = field(default_factory=list)
    rewrite: str = ""


def plan(request: str) -> list[str]:
    text = request.strip()
    if not text:
        return []
    tasks: list[str] = []
    docs = wants_docs(text)
    if _CREATIVE.search(text):
        tasks.append("creative")
    if _DEV.search(text):
        tasks.append("dev")
    elif _REVIEW.search(text) and not docs:
        tasks.append("reviewer")
    if docs:
        tasks.append("docs")
    if wants_release(text):
        tasks.append("release")
    return tasks


def wants_docs(text: str) -> bool:
    if _DOCS_WORD.search(text) or _REWRITE_TEXT.search(text):
        return True
    if len(text.split()) < 40:
        return False
    return bool(_PASSIVE_BY.search(text) and _TECH.search(text))


def wants_release(text: str) -> bool:
    if re.search(r"\brelease notes\b", text, re.I):
        return False
    return bool(_RELEASE.search(text))


def local_review(result: DevResult) -> list[str]:
    findings: list[str] = []
    blob = "\n".join([result.summary, *result.files, *result.tests])
    if "\u2014" in blob or "\u2013" in blob:
        findings.append("Remove em dashes. Use commas or periods.")
    if result.code_changed and not result.tests:
        findings.append("Add straightforward unit tests for the change.")
    for line in result.summary.splitlines():
        if line.strip().startswith("#") and len(line.split()) > 12:
            findings.append("Shorten comments. Keep them terse.")
            break
    return findings


def parse_json_object(text: str) -> dict:
    raw = text.strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, dict):
        return {}
    return value


class Supervisor:
    def __init__(
        self,
        graph: GraphStore,
        config: Config,
        model: ModelClient,
        project_root: Path,
        creative: CreativeService | None = None,
        docs: DocsWriter | None = None,
        release: ReleaseWriter | None = None,
    ):
        self.graph = graph
        self.config = config
        self.model = model
        self.project_root = project_root
        self.creative = creative
        self.docs = docs or DocsWriter()
        self.release = release or ReleaseWriter()

    def prepare(self, request: str) -> dict:
        packed = compress(request, self.config.input_mode)
        cites = self.graph.cite(packed.text)
        tasks = plan(request)
        # Wrapper is compressed. Docs keeps the passage whole so voice and facts survive.
        assignments = []
        for agent in tasks:
            task = packed.text
            if agent == "docs":
                task = request.strip()
            assignments.append(
                {
                    "agent": agent,
                    "model": self.config.model_for(agent),
                    "task": task,
                }
            )
        return {
            "compressed": packed.text,
            "cites": [
                {"id": item.id, "label": item.label, "summary": item.summary} for item in cites
            ],
            "assignments": assignments,
            "compact": self.graph.count() > self.config.compact_after_nodes,
        }

    def run(self, request: str) -> RunReport:
        prepared = self.prepare(request)
        cites = self.graph.cite(compress(request, self.config.input_mode).text)
        trace: list[str] = []
        delegations: list[tuple[str, str]] = []
        accepted = True
        docs_result: DocsResult | None = None
        notes: list[str] = []
        for item in prepared["assignments"]:
            agent = item["agent"]
            delegations.append((agent, item["model"]))
            if agent == "dev":
                accepted = self._dev_loop(request, cites, trace)
            elif agent == "reviewer":
                self._review_only(request, cites, trace)
            elif agent == "creative":
                artifact = self._creative(request)
                notes.append(artifact.summary)
                trace.append("creative")
            elif agent == "docs":
                docs_result = self.docs.run(request)
                trace.append("docs")
            elif agent == "release":
                result = self.release.run(request, self.project_root, apply=False)
                notes.append(result.summary)
                trace.append("release")
        memory_id = ""
        if trace:
            memory_id = self._remember(trace, cites, docs_result, notes)
        compact = self.graph.compact(self.config.compact_after_nodes)
        reply = self._reply(trace, accepted, docs_result, memory_id, notes)
        return RunReport(
            reply=reply,
            agents=trace,
            cites=cites,
            memory_id=memory_id,
            compacted=compact.ran,
            accepted=accepted,
            delegations=delegations,
            rewrite=docs_result.text if docs_result else "",
        )

    def _worker_prompt(self, task: str, cites: list[Citation]) -> str:
        packed = compress(task, self.config.inter_agent_mode).text
        return f"TASK {packed}\nREFS {format_cites(cites)}"

    def _dev_loop(self, request: str, cites: list[Citation], trace: list[str]) -> bool:
        result = self._call_dev(self._worker_prompt(request, cites))
        trace.append("dev")
        rounds = 0
        while result.code_changed:
            if rounds >= self.config.max_review_rounds:
                return False
            findings, accept = self._call_review(result, cites)
            trace.append("reviewer")
            rounds += 1
            if accept:
                return True
            fix = "Apply the reviewer instructions.\n" + "\n".join(findings)
            result = self._call_dev(self._worker_prompt(fix, cites))
            trace.append("dev")
        return True

    def _review_only(self, request: str, cites: list[Citation], trace: list[str]) -> None:
        result = DevResult(summary=request, code_changed=True, files=[], tests=[])
        self._call_review(result, cites)
        trace.append("reviewer")

    def _call_dev(self, user: str) -> DevResult:
        raw = self.model.complete("dev", self.config.worker_model, DEV_SYSTEM, user)
        data = parse_json_object(raw)
        files = _str_list(data.get("files"))
        tests = _str_list(data.get("tests"))
        return DevResult(
            summary=str(data.get("summary") or "").strip(),
            code_changed=bool(data.get("code_changed")),
            files=files,
            tests=tests,
        )

    def _call_review(self, result: DevResult, cites: list[Citation]) -> tuple[list[str], bool]:
        payload = "\n".join([result.summary, *result.files, *result.tests])
        raw = self.model.complete(
            "reviewer",
            self.config.worker_model,
            REVIEW_SYSTEM,
            self._worker_prompt(payload, cites),
        )
        data = parse_json_object(raw)
        findings = _str_list(data.get("findings"))
        for item in local_review(result):
            if item not in findings:
                findings.append(item)
        accept = bool(data.get("accept")) and not findings
        return findings, accept

    def _creative(self, request: str):
        if self.creative is None:
            raise RuntimeError("creative worker is not configured")
        return self.creative.run(request)

    def _remember(
        self,
        trace: list[str],
        cites: list[Citation],
        docs_result: DocsResult | None,
        notes: list[str],
    ) -> str:
        if docs_result and trace == ["docs"]:
            summary = docs_result.summary_line
        else:
            summary = "Delegated to " + ", ".join(trace) + "."
            if docs_result:
                summary = f"{summary} {docs_result.summary_line}"
            if notes:
                summary = f"{summary} {' '.join(notes)}"
        summary = summary[:160]
        node = self.graph.add_node(
            label="docs" if docs_result and trace == ["docs"] else "task",
            name=summary[:60],
            horizon="short",
            salience=0.6,
            summary=summary,
            body="",
        )
        for item in cites:
            self.graph.link(node.id, item.id, "cites")
        return node.id

    def _reply(
        self,
        trace: list[str],
        accepted: bool,
        docs_result: DocsResult | None,
        memory_id: str,
        notes: list[str],
    ) -> str:
        if not trace:
            return user_visible("No worker matched.")
        parts = ["Delegated to " + ", ".join(trace) + "."]
        if "reviewer" in trace:
            if accepted:
                parts.append("Review accepted.")
            else:
                parts.append("Review still open. Sent findings back to dev.")
        parts.extend(notes)
        if docs_result:
            parts.append(docs_result.summary_line)
            parts.append(docs_result.text)
        if memory_id:
            parts.append(f"Memory {memory_id}.")
        return user_visible(" ".join(parts))


def open_supervisor(project: Path | None = None) -> Supervisor:
    from rhinodiet.config import load_config, project_dir, resolve_memory_path
    from rhinodiet.creative import make_provider

    root = project or project_dir()
    cfg = load_config()
    graph = GraphStore(resolve_memory_path(cfg, root))
    creative = CreativeService(graph, make_provider(), root / ".rhinodiet" / "artifacts")
    return Supervisor(graph, cfg, default_model(), root, creative=creative)


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
