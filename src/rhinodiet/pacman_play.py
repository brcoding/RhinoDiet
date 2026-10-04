"""Headless Pac-Man driver. Mirrors benchmarks/godot-pacman without launching Godot."""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

LEFT, RIGHT, UP, DOWN = (-1, 0), (1, 0), (0, -1), (0, 1)
DIRS = (LEFT, RIGHT, UP, DOWN)
DT = 1 / 60
AVOID_TICKS = 240
RESTART_PLAY_TICKS = 180
CLEAR_TICKS = 40000
_MAZE = Path(__file__).resolve().parents[2] / "benchmarks" / "godot-pacman" / "scripts" / "maze.gd"


def load_rows(path: Path | None = None) -> list[str]:
    text = (path or _MAZE).read_text(encoding="utf-8")
    return [row for row in re.findall(r'"([#.PG]+)"', text) if len(row) == 19]


ROWS = load_rows()


def walkable(cell: tuple[int, int]) -> bool:
    x, y = cell
    if x < 0 or y < 0 or y >= len(ROWS) or x >= 19:
        return False
    return ROWS[y][x] != "#"


def add(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    return (a[0] + b[0], a[1] + b[1])


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Actor:
    __slots__ = (
        "cell",
        "from_cell",
        "to_cell",
        "direction",
        "progress",
        "speed",
        "active",
        "queued",
        "prefer_h",
    )

    def __init__(self, cell: tuple[int, int], speed: float, direction: tuple[int, int] = (0, 0)):
        self.cell = cell
        self.from_cell = cell
        self.to_cell = cell
        self.direction = direction
        self.progress = 1.0
        self.speed = speed
        self.active = True
        self.queued = direction
        self.prefer_h = False

    def copy(self) -> "Actor":
        other = Actor(self.cell, self.speed, self.direction)
        other.from_cell = self.from_cell
        other.to_cell = self.to_cell
        other.progress = self.progress
        other.active = self.active
        other.queued = self.queued
        other.prefer_h = self.prefer_h
        return other

    def occupied(self) -> tuple[int, int]:
        if self.progress > 0.5:
            return self.to_cell
        return self.from_cell

    def moving(self) -> bool:
        return self.from_cell != self.to_cell and self.progress < 1.0


class World:
    def __init__(self) -> None:
        self.pellets: set[tuple[int, int]] = set()
        self.ghost_starts: list[tuple[int, int]] = []
        player = (0, 0)
        for y, line in enumerate(ROWS):
            for x, ch in enumerate(line):
                if ch == ".":
                    self.pellets.add((x, y))
                elif ch == "P":
                    player = (x, y)
                elif ch == "G":
                    self.ghost_starts.append((x, y))
        self.initial = len(self.pellets)
        self.player_start = player
        self.player = Actor(player, 6.0, LEFT)
        self.player.queued = LEFT
        self.ghosts = [Actor(self.ghost_starts[0], 4.2), Actor(self.ghost_starts[1], 3.6)]
        self.ghosts[0].prefer_h = True
        self.ghosts[1].prefer_h = False
        self.score = 0
        self.over = False
        self.won = False
        self.hit = False
        self.hits = 0
        self.restarts = 0

    def clone(self) -> "World":
        other = World.__new__(World)
        other.pellets = set(self.pellets)
        other.initial = self.initial
        other.ghost_starts = self.ghost_starts
        other.player_start = self.player_start
        other.player = self.player.copy()
        other.ghosts = [ghost.copy() for ghost in self.ghosts]
        other.score = self.score
        other.over = self.over
        other.won = self.won
        other.hit = self.hit
        other.hits = self.hits
        other.restarts = self.restarts
        return other

    def reset(self) -> None:
        fresh = World()
        fresh.restarts = self.restarts + 1
        self.__dict__.update(fresh.__dict__)

    def tick(self, queued: tuple[int, int]) -> None:
        if self.over:
            return
        self.player.queued = queued
        if self._player_advance() and self.player.cell in self.pellets:
            self.pellets.remove(self.player.cell)
            self.score += 10
        for ghost in self.ghosts:
            self._ghost_advance(ghost, self.player.cell)
        if self._hit():
            self.hit = True
            self.hits += 1
            self.over = True
            self.won = False
            self.player.active = False
            for ghost in self.ghosts:
                ghost.active = False
        elif not self.pellets:
            self.over = True
            self.won = True
            self.player.active = False
            for ghost in self.ghosts:
                ghost.active = False

    def _player_advance(self) -> bool:
        player = self.player
        if not player.active:
            return False
        arrived = False
        if player.progress >= 1.0:
            step = player.direction
            if walkable(add(player.cell, player.queued)):
                step = player.queued
                player.direction = player.queued
            if not walkable(add(player.cell, step)):
                return False
            player.from_cell = player.cell
            player.to_cell = add(player.cell, step)
            player.progress = 0.0
        player.progress += player.speed * DT
        if player.progress >= 1.0:
            player.progress = 1.0
            player.cell = player.to_cell
            player.from_cell = player.cell
            player.to_cell = player.cell
            arrived = True
        return arrived

    def _ghost_advance(self, ghost: Actor, target: tuple[int, int]) -> None:
        if not ghost.active:
            return
        if ghost.progress >= 1.0:
            step = self._choose(ghost, target)
            if step == (0, 0):
                return
            ghost.direction = step
            ghost.from_cell = ghost.cell
            ghost.to_cell = add(ghost.cell, step)
            ghost.progress = 0.0
        ghost.progress += ghost.speed * DT
        if ghost.progress >= 1.0:
            ghost.progress = 1.0
            ghost.cell = ghost.to_cell
            ghost.from_cell = ghost.cell
            ghost.to_cell = ghost.cell

    def _choose(self, ghost: Actor, target: tuple[int, int]) -> tuple[int, int]:
        reverse = (0, 0)
        if ghost.direction != (0, 0):
            reverse = (-ghost.direction[0], -ghost.direction[1])
        best = (0, 0)
        best_score = 1000000
        only = (0, 0)
        for direction in DIRS:
            nxt = add(ghost.cell, direction)
            if not walkable(nxt):
                continue
            only = direction
            if direction == reverse:
                continue
            score = manhattan(nxt, target)
            if ghost.prefer_h:
                score += abs(nxt[1] - target[1])
            else:
                score += abs(nxt[0] - target[0])
            if score < best_score:
                best_score = score
                best = direction
        return best if best != (0, 0) else only

    def _hit(self) -> bool:
        for ghost in self.ghosts:
            if ghost.occupied() == self.player.occupied():
                return True
            if self.player.moving() and ghost.moving():
                swapped = (
                    self.player.from_cell == ghost.to_cell
                    and self.player.to_cell == ghost.from_cell
                )
                if swapped:
                    return True
        return False


def neighbors(cell: tuple[int, int]) -> list[tuple[int, int]]:
    return [add(cell, direction) for direction in DIRS if walkable(add(cell, direction))]


def decision_cell(world: World) -> tuple[int, int]:
    player = world.player
    if player.progress < 1.0 and player.from_cell != player.to_cell:
        return player.to_cell
    return player.cell


def dir_into(src: tuple[int, int], dst: tuple[int, int]) -> tuple[int, int]:
    return (dst[0] - src[0], dst[1] - src[1])


_DIST: dict[tuple[int, int], dict[tuple[int, int], int]] = {}


def bfs_from(start: tuple[int, int]) -> dict[tuple[int, int], int]:
    cached = _DIST.get(start)
    if cached is not None:
        return cached
    dist = {start: 0}
    queue = [start]
    index = 0
    while index < len(queue):
        cell = queue[index]
        index += 1
        for nxt in neighbors(cell):
            if nxt not in dist:
                dist[nxt] = dist[cell] + 1
                queue.append(nxt)
    _DIST[start] = dist
    return dist


def gap_of(world: World) -> int:
    dist = bfs_from(world.player.cell)
    best = 99
    for ghost in world.ghosts:
        best = min(best, dist.get(ghost.occupied(), 99))
    return best


def step_until(world: World, direction: tuple[int, int]) -> None:
    start = world.player.cell
    for _ in range(40):
        world.tick(direction)
        if world.over or (world.player.cell != start and world.player.progress >= 1.0):
            return


def path_to(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    if start == goal:
        return [start]
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue = [start]
    index = 0
    while index < len(queue):
        cell = queue[index]
        index += 1
        for nxt in neighbors(cell):
            if nxt in parent:
                continue
            parent[nxt] = cell
            if nxt == goal:
                path = [goal]
                while path[-1] != start:
                    previous = parent[path[-1]]
                    if previous is None:
                        break
                    path.append(previous)
                path.reverse()
                return path
            queue.append(nxt)
    return [start]


def trip_clear(world: World, cells: list[tuple[int, int]]) -> bool:
    sim = world.clone()
    for nxt in cells:
        here = decision_cell(sim)
        if manhattan(here, nxt) != 1:
            return False
        step_until(sim, dir_into(here, nxt))
        if sim.hit or sim.player.cell != nxt:
            return False
    return True


def cells_to_dirs(here: tuple[int, int], cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    dirs: list[tuple[int, int]] = []
    cursor = here
    for nxt in cells:
        dirs.append(dir_into(cursor, nxt))
        cursor = nxt
    return dirs


def find_trip(world: World) -> list[tuple[int, int]] | None:
    here = decision_cell(world)
    if not world.pellets:
        return None
    dist = bfs_from(here)
    pellets = sorted(world.pellets, key=lambda cell: dist.get(cell, 99))
    for pellet in pellets[:12]:
        path = path_to(here, pellet)
        if len(path) < 2:
            continue
        cells = path[1:] + path[-2::-1]
        if len(cells) > 22 or not trip_clear(world, cells):
            continue
        dirs = cells_to_dirs(here, cells)
        sim = world.clone()
        if any(_replay_hits(sim, direction) for direction in dirs):
            continue
        return dirs
    return None


def _replay_hits(sim: World, direction: tuple[int, int]) -> bool:
    step_until(sim, direction)
    return sim.hit


def greedy_step(world: World) -> tuple[int, int]:
    here = decision_cell(world)
    best = world.player.direction or LEFT
    best_key = None
    for opt in neighbors(here):
        direction = dir_into(here, opt)
        sim = world.clone()
        step_until(sim, direction)
        if sim.hit:
            continue
        dist = bfs_from(sim.player.cell)
        food = min((dist.get(cell, 99) for cell in sim.pellets), default=0)
        gap = gap_of(sim)
        key = (gap >= 3, -food if gap >= 3 else 0, gap)
        if best_key is None or key > best_key:
            best_key = key
            best = direction
    return best


def safe_choose(world: World) -> tuple[int, int]:
    here = decision_cell(world)
    best = None
    best_key = None
    start_pellets = len(world.pellets)
    for opt in neighbors(here):
        direction = dir_into(here, opt)
        sim = world.clone()
        step_until(sim, direction)
        if sim.hit:
            continue
        horizon = 20 if start_pellets <= 50 else 11
        for _ in range(horizon):
            if sim.over:
                break
            step_until(sim, greedy_step(sim))
            if sim.hit:
                break
        if sim.hit:
            continue
        eaten = start_pellets - len(sim.pellets)
        gap = gap_of(sim)
        if sim.won:
            key = (3, eaten, gap)
        elif start_pellets <= 45:
            key = (1 if gap >= 6 else 0, eaten if gap >= 6 else 0, gap)
        else:
            key = (2, eaten, gap)
        if best_key is None or key > best_key:
            best_key = key
            best = direction
    if best is not None:
        return best
    return greedy_step(world)


def chase_direction(world: World) -> tuple[int, int]:
    here = decision_cell(world)
    target = min((ghost.occupied() for ghost in world.ghosts), key=lambda cell: manhattan(here, cell))
    path = path_to(here, target)
    if len(path) < 2:
        return world.player.direction or LEFT
    return dir_into(here, path[1])


@dataclass
class PlayResult:
    passed: bool
    result: str
    pellets_eaten: int
    time_survived: float
    ghosts_hit: int
    board_cleared: bool
    frames: list[bytes] = field(default_factory=list)


def _seconds(ticks: int) -> float:
    return round(ticks / 60, 1)


def _snap(frames: list[bytes], world: World, tick: int, every: int) -> None:
    if tick == 0 or tick % every == 0:
        frames.append(render_png(world))


def _finish(frames: list[bytes], world: World) -> None:
    frames.append(render_png(world))
    if not frames:
        frames.append(render_png(world))


def run_avoid() -> PlayResult:
    world = World()
    frames: list[bytes] = []
    queued = LEFT
    ticks = 0
    for tick in range(AVOID_TICKS):
        if world.player.progress >= 1.0:
            queued = safe_choose(world)
        _snap(frames, world, tick, 80)
        world.tick(queued)
        ticks = tick + 1
        if world.over:
            break
    _finish(frames, world)
    passed = not world.hit
    eaten = world.initial - len(world.pellets)
    result = (
        f"Avoided ghosts for {_seconds(ticks)} seconds."
        if passed
        else "A ghost caught Pac-Man."
    )
    return PlayResult(passed, result, eaten, _seconds(ticks), world.hits, world.won, frames)


def run_restart() -> PlayResult:
    world = World()
    frames: list[bytes] = []
    queued = LEFT
    caught = False
    for tick in range(4000):
        if world.player.progress >= 1.0:
            queued = chase_direction(world)
        _snap(frames, world, tick, 40)
        world.tick(queued)
        if world.hit:
            caught = True
            break
    if not caught:
        _finish(frames, world)
        return PlayResult(False, "Pac-Man never met a ghost, so restart did not run.", 0, 0.0, 0, False, frames)
    world.reset()
    restored = (
        not world.over
        and not world.hit
        and world.player.cell == world.player_start
        and len(world.pellets) == world.initial
        and world.restarts == 1
    )
    queued = LEFT
    played = 0
    for tick in range(RESTART_PLAY_TICKS):
        if world.over:
            break
        if world.player.progress >= 1.0:
            queued = safe_choose(world)
        if tick % 60 == 0:
            frames.append(render_png(world))
        world.tick(queued)
        played = tick + 1
        if world.hit:
            break
    _finish(frames, world)
    continued = not world.hit and not world.over and len(world.pellets) < world.initial
    passed = restored and continued
    if passed:
        result = "R restored the pellets and the start cell, then play continued."
    elif not restored:
        result = "Restart left the board ended."
    else:
        result = "Play did not continue after restart."
    return PlayResult(
        passed,
        result,
        world.initial - len(world.pellets),
        _seconds(played),
        1,
        False,
        frames,
    )


def run_clear(max_ticks: int = CLEAR_TICKS) -> PlayResult:
    world = World()
    frames: list[bytes] = []
    queued = LEFT
    follow: list[tuple[int, int]] = []
    ticks = 0
    for tick in range(max_ticks):
        if world.player.progress >= 1.0:
            if follow:
                queued = follow.pop(0)
            else:
                trip = find_trip(world) if len(world.pellets) <= 45 else None
                if trip:
                    queued = trip[0]
                    follow = trip[1:]
                else:
                    queued = safe_choose(world)
        _snap(frames, world, tick, 3000)
        world.tick(queued)
        ticks = tick + 1
        if world.over:
            break
    _finish(frames, world)
    passed = world.won and world.hits == 0
    eaten = world.initial - len(world.pellets)
    if passed:
        result = f"Cleared the board in {_seconds(ticks)} seconds without a ghost hit."
    elif world.hit:
        result = "A ghost hit before the board was clear."
    else:
        result = "Pellets were still on the board when the run stopped."
    return PlayResult(passed, result, eaten, _seconds(ticks), world.hits, world.won, frames)


def play_area(name: str) -> PlayResult:
    if name == "avoid-ghosts":
        return run_avoid()
    if name == "restart":
        return run_restart()
    if name == "clear-board":
        return run_clear()
    raise KeyError(name)


def render_png(world: World) -> bytes:
    scale = 6
    width = 19 * scale
    height = len(ROWS) * scale
    floor = (11, 14, 20)
    wall = (47, 78, 196)
    pellet = (255, 213, 106)
    player = (255, 216, 74)
    ghost_colors = ((255, 75, 75), (255, 122, 209))
    grid = [[floor for _ in range(width)] for _ in range(height)]
    for y, line in enumerate(ROWS):
        for x, ch in enumerate(line):
            color = wall if ch == "#" else floor
            _fill(grid, x, y, scale, color)
            if (x, y) in world.pellets:
                _fill(grid, x, y, scale, pellet, inset=2)
    for index, ghost in enumerate(world.ghosts):
        cell = ghost.occupied()
        _fill(grid, cell[0], cell[1], scale, ghost_colors[index % 2], inset=1)
    cell = world.player.occupied()
    _fill(grid, cell[0], cell[1], scale, player, inset=1)
    rows = [bytes(channel for pixel in row for channel in pixel) for row in grid]
    return _png(width, height, rows)


def _fill(
    grid: list[list[tuple[int, int, int]]],
    x: int,
    y: int,
    scale: int,
    color: tuple[int, int, int],
    inset: int = 0,
) -> None:
    for py in range(y * scale + inset, (y + 1) * scale - inset):
        if py < 0 or py >= len(grid):
            continue
        row = grid[py]
        for px in range(x * scale + inset, (x + 1) * scale - inset):
            if 0 <= px < len(row):
                row[px] = color


def _png(width: int, height: int, rows: list[bytes]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + row for row in rows)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
