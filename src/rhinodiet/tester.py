"""Game tester. Areas are short graph refs. Pac-Man is the built-in example."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rhinodiet.graph import GraphStore
from rhinodiet.pacman_play import PlayResult, play_area
from rhinodiet.testhistory import record_run

DEFAULT_LOOPS = 2
LONGER_LOOPS = 4

_FOCUS = re.compile(
    r"--focus\s+[\"']([^\"']+)[\"']"
    r"|\bfocus(?:ed)?(?:\s+test)?\s+on\s+(.+?)(?:\.|$)"
    r"|\btest this area:?\s+(.+?)(?:\.|$)",
    re.I,
)
_LOOPS = re.compile(r"\b(\d+)\s+loops?\b", re.I)
_LONGER = re.compile(r"\blonger\b", re.I)


@dataclass(frozen=True)
class Area:
    name: str
    goal: str
    passed: str
    failed: str


@dataclass(frozen=True)
class GameSpec:
    name: str
    marker: str
    areas: tuple[Area, ...]
    endurance: str
    play: object


@dataclass
class TesterReport:
    passed: bool
    text: str
    cite_ids: list[str]
    area: str = ""
    mode: str = ""


PACMAN_AREAS = (
    Area(
        "avoid-ghosts",
        "Avoid ghosts.",
        "No shared cell with a ghost.",
        "A ghost catches Pac-Man.",
    ),
    Area(
        "restart",
        "Restart.",
        "R restores pellets and the start cell.",
        "The board stays ended.",
    ),
    Area(
        "clear-board",
        "Reach the end while avoiding ghosts.",
        "No pellets left and no ghost hit.",
        "A hit or pellets remain.",
    ),
)

PACMAN = GameSpec(
    name="pac-man",
    marker="benchmarks/godot-pacman/project.godot",
    areas=PACMAN_AREAS,
    endurance="clear-board",
    play=play_area,
)

GAMES = (PACMAN,)


def focus_phrase(request: str, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    match = _FOCUS.search(request.strip())
    if not match:
        return ""
    return next(part.strip() for part in match.groups() if part)


def loop_count(request: str, explicit: int = 0) -> int:
    if explicit:
        return max(1, explicit)
    match = _LOOPS.search(request)
    if match:
        return max(1, int(match.group(1)))
    if _LONGER.search(request):
        return LONGER_LOOPS
    return DEFAULT_LOOPS


def score_area(phrase: str, area: Area) -> float:
    text = _flat(phrase)
    goal = _flat(area.goal)
    name = area.name.replace("-", " ")
    if not text:
        return 0
    if text == goal or text == name:
        return 1000 - len(goal)
    if text in goal:
        return 500 - len(goal)
    if text in name:
        return 400
    phrase_tokens = set(re.findall(r"[a-z0-9]+", text))
    goal_tokens = set(re.findall(r"[a-z0-9]+", f"{goal} {name}"))
    overlap = len(phrase_tokens & goal_tokens)
    if overlap == 0:
        return 0
    return overlap * 10 - len(goal) * 0.01


def choose_area(phrase: str, areas: list[Area] | tuple[Area, ...]) -> Area | None:
    ranked = sorted(areas, key=lambda area: score_area(phrase, area), reverse=True)
    if not ranked or score_area(phrase, ranked[0]) <= 0:
        return None
    return ranked[0]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip().strip("."))


class TesterService:
    __test__ = False

    def __init__(self, graph: GraphStore, games: tuple[GameSpec, ...] | None = None):
        self.graph = graph
        self.games = GAMES if games is None else games

    def ensure(self, root) -> GameSpec | None:
        game = self.game_at(root)
        if game is None:
            return None
        names = ", ".join(area.name for area in game.areas)
        self._upsert("game", game.name, f"Areas: {names}."[:160], 0.66)
        game_node = self._find("game", game.name)
        linked = set()
        if game_node is not None:
            linked = {dst for dst, kind in self.graph.edges_from(game_node.id) if kind == "has"}
        for area in game.areas:
            summary = (
                f"{area.name}. Goal: {area.goal} Pass: {area.passed} Fail: {area.failed}."
            )
            self._upsert("area", area.name, summary[:160], 0.64)
            node = self._find("area", area.name)
            if game_node is not None and node is not None and node.id not in linked:
                self.graph.link(game_node.id, node.id, "has")
                linked.add(node.id)
        return game

    def game_at(self, root) -> GameSpec | None:
        for game in self.games:
            if (root / game.marker).is_file():
                return game
        return None

    def run(self, request: str, root, focus: str = "", loops: int = 0) -> TesterReport:
        game = self.ensure(root)
        if game is None:
            return TesterReport(False, "No registered game in this project.", [])
        phrase = focus_phrase(request, focus)
        if phrase:
            area = choose_area(phrase, game.areas)
            if area is None:
                return TesterReport(False, "No area matches that focus.", self._area_ids())
            return self._play(game, area, "focus", root, 1)
        area = self._endurance_area(game)
        return self._play(game, area, "loop", root, loop_count(request, loops))

    def _endurance_area(self, game: GameSpec) -> Area:
        for area in game.areas:
            if area.name == game.endurance:
                return area
        return game.areas[0]

    def _play(self, game: GameSpec, area: Area, mode: str, root, loops: int) -> TesterReport:
        if game.play is None:
            return TesterReport(False, "This game has no play driver.", self._area_ids(area.name), area.name, mode)
        notes = []
        passed = True
        for _ in range(loops):
            result = game.play(area.name)
            if not isinstance(result, PlayResult):
                return TesterReport(False, "The play driver returned nothing.", self._area_ids(area.name), area.name, mode)
            entry = record_run(
                root,
                mode=mode,
                area=area.name,
                passed=result.passed,
                result=result.result,
                metrics={
                    "pellets_eaten": result.pellets_eaten,
                    "time_survived": result.time_survived,
                    "ghosts_hit": result.ghosts_hit,
                    "board_cleared": result.board_cleared,
                },
                frames=result.frames[:8],
            )
            passed = passed and result.passed
            line = result.result
            if entry["versus"]:
                line = f"{line} {entry['versus']}"
            notes.append(line)
        text = " ".join(notes)
        return TesterReport(passed, text, self._area_ids(area.name), area.name, mode)

    def _area_ids(self, name: str = "") -> list[str]:
        ids = []
        for node in self.graph.by_label("area"):
            if name and node.name != name:
                continue
            if node.body:
                continue
            ids.append(node.id)
        return ids

    def _find(self, label: str, name: str):
        for node in self.graph.by_label(label):
            if node.name == name:
                return node
        return None

    def _upsert(self, label: str, name: str, summary: str, salience: float) -> None:
        node = self._find(label, name)
        if node is None:
            self.graph.add_node(
                label=label,
                name=name,
                horizon="long",
                salience=salience,
                summary=summary,
                body="",
            )
            return
        if node.summary != summary:
            self.graph.update_summary(node.id, summary, salience=salience)
