"""Creative worker. Reads style from memory. Local fallback needs no credentials."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from rhinodiet.graph import GraphStore

@dataclass(frozen=True)
class Style:
    name: str
    palette: list[str]
    shape: str
    mood: str


DEFAULT_STYLE = Style(
    name="ink-and-paper",
    palette=["#1c1917", "#f5f0e8", "#c2410c"],
    shape="flat geometric marks, high contrast, no letters",
    mood="dry, precise, warm paper and ink",
)


@dataclass(frozen=True)
class Artifact:
    path: Path
    kind: str
    summary: str


def style_summary(style: Style) -> str:
    return json.dumps(
        {
            "name": style.name,
            "palette": style.palette,
            "shape": style.shape,
            "mood": style.mood,
        },
        separators=(",", ":"),
    )


def style_from_summary(summary: str) -> Style | None:
    try:
        data = json.loads(summary)
        return Style(
            name=data["name"],
            palette=list(data["palette"]),
            shape=data["shape"],
            mood=data["mood"],
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


class LocalCreativeProvider:
    def generate(self, request: str, style: Style, dest: Path) -> Artifact:
        dest.mkdir(parents=True, exist_ok=True)
        if re.search(r"\bvideo\b", request, re.I):
            path = dest / "storyboard.md"
            text = "\n".join(
                [
                    f"Frame 1. {style.mood}. Palette {style.palette[0]}.",
                    f"Frame 2. {style.shape}.",
                    "Frame 3. Hold on the mark.",
                ]
            )
            path.write_text(text + "\n", encoding="utf-8")
            return Artifact(path, "video", f"video {style.name}")
        path = dest / "mark.svg"
        ink, paper, accent = style.palette[0], style.palette[1], style.palette[2]
        path.write_text(
            "\n".join(
                [
                    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">',
                    f'  <rect width="128" height="128" fill="{paper}"/>',
                    f'  <circle cx="64" cy="64" r="28" fill="{accent}"/>',
                    f'  <rect x="58" y="36" width="12" height="56" fill="{ink}"/>',
                    "</svg>",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return Artifact(path, "image", f"image {style.name}")


class HttpCreativeProvider:
    """Optional provider. Any failure uses the local fallback."""

    def __init__(self, url: str, fallback: LocalCreativeProvider):
        self.url = url
        self.fallback = fallback

    def generate(self, request: str, style: Style, dest: Path) -> Artifact:
        try:
            payload = json.dumps({"request": request, "style": style.name}).encode()
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / str(data.get("filename") or "remote.txt")
            path.write_text(str(data.get("text") or ""), encoding="utf-8")
            return Artifact(path, str(data.get("kind") or "image"), f"remote {style.name}")
        except Exception:
            return self.fallback.generate(request, style, dest)


def make_provider() -> LocalCreativeProvider | HttpCreativeProvider:
    local = LocalCreativeProvider()
    url = os.environ.get("RHINODIET_CREATIVE_URL")
    if not url:
        return local
    return HttpCreativeProvider(url, local)


class CreativeService:
    def __init__(self, graph: GraphStore, provider, dest: Path):
        self.graph = graph
        self.provider = provider
        self.dest = dest

    def load_style(self) -> Style | None:
        nodes = self.graph.by_label("style")
        if not nodes:
            return None
        return style_from_summary(nodes[0].summary)

    def run(self, request: str) -> Artifact:
        style = self.load_style()
        if style is None:
            style = DEFAULT_STYLE
            self.graph.add_node(
                label="style",
                name=style.name,
                horizon="long",
                salience=0.9,
                summary=style_summary(style),
                body="",
            )
        return self.provider.generate(request, style, self.dest)
