"""Thin labeled graph on SQLite. Memgraph-like nodes, typed edges, traversal."""

from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

_WORD = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    name: str
    horizon: str
    salience: float
    summary: str
    body: str
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class Citation:
    id: str
    label: str
    summary: str
    score: float


@dataclass(frozen=True)
class CompactReport:
    ran: bool
    before: int
    after: int
    dropped: int
    model_id: str | None


def format_cites(cites: list[Citation]) -> str:
    if not cites:
        return "none"
    return "\n".join(f"{item.id} [{item.label}] {item.summary}" for item in cites)


class GraphStore:
    def __init__(self, path: str | Path, clock=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    def _migrate(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                name TEXT NOT NULL,
                horizon TEXT NOT NULL CHECK (horizon IN ('short', 'long')),
                salience REAL NOT NULL DEFAULT 0.5,
                summary TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                src TEXT NOT NULL,
                dst TEXT NOT NULL,
                type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1,
                FOREIGN KEY (src) REFERENCES nodes(id),
                FOREIGN KEY (dst) REFERENCES nodes(id)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
            CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
            CREATE INDEX IF NOT EXISTS idx_nodes_label ON nodes(label);
            """
        )
        self._db.commit()

    def add_node(
        self,
        *,
        label: str,
        name: str,
        horizon: str = "short",
        salience: float = 0.5,
        summary: str = "",
        body: str = "",
    ) -> Node:
        if horizon not in {"short", "long"}:
            raise ValueError("horizon must be short or long")
        now = float(self.clock())
        node_id = f"n{uuid.uuid4().hex[:8]}"
        self._db.execute(
            """
            INSERT INTO nodes
                (id, label, name, horizon, salience, summary, body, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (node_id, label, name, horizon, salience, summary, body, now, now),
        )
        self._db.commit()
        return self.get(node_id)

    def get(self, node_id: str) -> Node:
        row = self._db.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise KeyError(node_id)
        return _node(row)

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])

    def all_nodes(self) -> list[Node]:
        rows = self._db.execute("SELECT * FROM nodes").fetchall()
        return [_node(row) for row in rows]

    def by_label(self, label: str) -> list[Node]:
        rows = self._db.execute(
            "SELECT * FROM nodes WHERE label = ? ORDER BY updated_at DESC",
            (label,),
        ).fetchall()
        return [_node(row) for row in rows]

    def link(self, src: str, dst: str, edge_type: str, weight: float = 1.0) -> str:
        edge_id = f"e{uuid.uuid4().hex[:8]}"
        self._db.execute(
            "INSERT INTO edges (id, src, dst, type, weight) VALUES (?, ?, ?, ?, ?)",
            (edge_id, src, dst, edge_type, weight),
        )
        self._db.commit()
        return edge_id

    def update_summary(self, node_id: str, summary: str, salience: float | None = None) -> None:
        now = float(self.clock())
        if salience is None:
            self._db.execute(
                "UPDATE nodes SET summary = ?, updated_at = ? WHERE id = ?",
                (summary, now, node_id),
            )
        else:
            self._db.execute(
                "UPDATE nodes SET summary = ?, salience = ?, updated_at = ? WHERE id = ?",
                (summary, salience, now, node_id),
            )
        self._db.commit()

    def edges_from(self, src: str) -> list[tuple[str, str]]:
        rows = self._db.execute(
            "SELECT dst, type FROM edges WHERE src = ?",
            (src,),
        ).fetchall()
        return [(row["dst"], row["type"]) for row in rows]

    def delete_node(self, node_id: str) -> None:
        self._db.execute("DELETE FROM edges WHERE src = ? OR dst = ?", (node_id, node_id))
        self._db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._db.commit()

    def traverse(
        self,
        start: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> list[Node]:
        if depth < 1 or self._db.execute("SELECT 1 FROM nodes WHERE id = ?", (start,)).fetchone() is None:
            return []
        seen: dict[str, Node] = {}
        frontier = [start]
        for _ in range(depth):
            if not frontier:
                break
            nxt: list[str] = []
            for node_id in frontier:
                query = "SELECT dst, type FROM edges WHERE src = ?"
                params: list[object] = [node_id]
                if edge_types:
                    marks = ",".join("?" for _ in edge_types)
                    query += f" AND type IN ({marks})"
                    params.extend(edge_types)
                for row in self._db.execute(query, params):
                    dst = row["dst"]
                    if dst in seen or dst == start:
                        continue
                    seen[dst] = self.get(dst)
                    nxt.append(dst)
            frontier = nxt
        return list(seen.values())

    def cite(self, query: str, limit: int = 5) -> list[Citation]:
        """What the next prompt should cite. Ids and short summaries, never bodies."""
        wanted = _tokens(query)
        now = float(self.clock())
        scored: list[tuple[float, Node]] = []
        for node in self.all_nodes():
            age_hours = max(0.0, now - node.updated_at) / 3600
            recency = 1 / (1 + age_hours)
            overlap = len(wanted & _tokens(f"{node.label} {node.name} {node.summary}"))
            if not wanted:
                overlap = 0
            score = (0.4 + node.salience) * recency * (1 + overlap)
            scored.append((score, node))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Citation(node.id, node.label, node.summary, score)
            for score, node in scored[:limit]
        ]

    def compact(self, threshold: int) -> CompactReport:
        before = self.count()
        if before <= threshold:
            return CompactReport(False, before, before, 0, None)
        nodes = self.all_nodes()
        short = [node for node in nodes if node.horizon == "short"]
        now = float(self.clock())

        def stale_key(node: Node) -> float:
            age_hours = max(0.0, now - node.updated_at) / 3600
            recency = 1 / (1 + age_hours)
            return node.salience * recency

        short.sort(key=stale_key)
        model = next((node for node in nodes if node.label == "project" and node.name == "project-model"), None)
        extra = 0 if model else 1
        drop_n = min(len(short), before - threshold + extra)
        drop = short[:drop_n]
        if not drop:
            return CompactReport(False, before, before, 0, model.id if model else None)
        merged = _merge_summaries([node.summary for node in drop])
        if model is None:
            model = self.add_node(
                label="project",
                name="project-model",
                horizon="long",
                salience=0.85,
                summary=merged,
                body="",
            )
        else:
            merged = _merge_summaries([model.summary, *[node.summary for node in drop]])
            self.update_summary(model.id, merged, salience=max(model.salience, 0.85))
        for node in drop:
            if node.id == model.id:
                continue
            self.delete_node(node.id)
        after = self.count()
        return CompactReport(True, before, after, len(drop), model.id)


def _node(row: sqlite3.Row) -> Node:
    return Node(
        id=row["id"],
        label=row["label"],
        name=row["name"],
        horizon=row["horizon"],
        salience=float(row["salience"]),
        summary=row["summary"],
        body=row["body"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def _tokens(text: str) -> set[str]:
    return {item.lower() for item in _WORD.findall(text)}


def _merge_summaries(parts: list[str], limit: int = 360) -> str:
    seen: list[str] = []
    for part in parts:
        for chunk in re.split(r"(?<=[.])\s+", part.strip()):
            fact = chunk.strip()
            if not fact:
                continue
            key = fact.lower()
            if key in {item.lower() for item in seen}:
                continue
            seen.append(fact)
    text = " ".join(seen)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
