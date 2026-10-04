"""Game tester assignment, focus, Pac-Man play, and history stills."""

import json

from rhinodiet.cli import main
from rhinodiet.pacman_play import PlayResult, World, attempt_passed, run_avoid, run_clear, run_restart
from rhinodiet.supervisor import wants_dev, wants_godot, wants_tester
from rhinodiet.tester import Area, GameSpec, TesterService, choose_area
from rhinodiet.testhistory import TEST_COMMANDS, compare_metrics, load_history, page_html, record_run, show_tests

from support import ROOT, boot


def _pacman_game() -> GameSpec:
    from rhinodiet.tester import PACMAN

    return PACMAN


def test_focus_maps_phrases_to_areas():
    areas = _pacman_game().areas
    assert choose_area("avoid ghosts", areas).name == "avoid-ghosts"
    assert choose_area("restart", areas).name == "restart"
    assert choose_area("reach the end while avoiding ghosts", areas).name == "clear-board"
    assert choose_area("beat the level", areas).name == "clear-board"
    clear = choose_area("avoid ghosts", areas)
    assert clear.name != "clear-board"


def test_supervisor_sends_game_tests_to_the_tester(tmp_path):
    supervisor, _graph = boot(tmp_path)
    report = supervisor.run("test the game")
    assert report.agents == ["tester"]
    assert "dev" not in report.agents
    assert "godot" not in report.agents
    focused = supervisor.run('test this area: avoid ghosts')
    assert focused.agents == ["tester"]
    code = supervisor.run("add a unit test for the parser")
    assert code.agents == ["dev"]
    assert wants_tester("test the game")
    assert wants_tester("test this area: restart")
    assert not wants_tester("add a unit test for the parser")
    assert not wants_godot("test the game")
    assert wants_dev("add a unit test for the parser")
    text = (ROOT / "src" / "rhinodiet" / "supervisor.py").read_text(encoding="utf-8")
    assert "pacman" not in text.lower()
    assert "pac-man" not in text.lower()


def test_four_second_survival_with_pellets_left_does_not_pass():
    assert attempt_passed(183, 0, False, 4.0) is False
    assert attempt_passed(0, 0, True, 4.0) is True


def test_avoid_keeps_chasing_pellets_past_four_seconds():
    seen = {}

    def observe(world, ticks):
        if ticks == 240:
            seen["eaten"] = world.initial - len(world.pellets)
            seen["left"] = len(world.pellets)
            seen["over"] = world.over
            seen["cell"] = world.player.cell

    avoid = run_avoid(observe=observe)
    assert avoid.time_survived > 4
    assert seen["over"] is False
    assert seen["eaten"] > 0
    assert seen["left"] > 0
    assert seen["cell"] != World().player_start
    assert avoid.pellets_eaten > seen["eaten"]
    assert attempt_passed(seen["left"], 0, False, 4.0) is False
    assert avoid.passed
    assert avoid.board_cleared
    assert avoid.pellets_eaten == 201
    assert avoid.ghosts_hit == 0
    assert len(avoid.frames) >= 4
    assert avoid.frames[0].startswith(b"\x89PNG")
    assert avoid.frames[0] != avoid.frames[-1]


def test_pacman_driver_meets_each_goal():
    avoid = run_avoid()
    assert avoid.passed
    assert avoid.time_survived > 4
    assert avoid.board_cleared
    assert avoid.pellets_eaten == 201
    assert avoid.ghosts_hit == 0
    assert avoid.frames and avoid.frames[0].startswith(b"\x89PNG")
    restart = run_restart()
    assert restart.passed
    assert restart.ghosts_hit == 1
    assert restart.board_cleared is False
    cleared = run_clear()
    assert cleared.passed
    assert cleared.board_cleared
    assert cleared.pellets_eaten == 201
    assert cleared.ghosts_hit == 0


def test_endurance_loop_is_capped_and_records_runs(tmp_path):
    supervisor, graph = boot(tmp_path)
    marker = tmp_path / "benchmarks" / "godot-pacman" / "project.godot"
    marker.parent.mkdir(parents=True)
    marker.write_text('config_version=5\nconfig/features=PackedStringArray("4.3")\n', encoding="utf-8")
    report = supervisor.tester.run("test the game", tmp_path)
    assert report.passed
    assert report.mode == "loop"
    assert report.area == "clear-board"
    history = load_history(tmp_path)
    assert len(history["runs"]) == 2
    assert {item["mode"] for item in history["runs"]} == {"loop"}
    assert all(item["passed"] for item in history["runs"])
    assert all(item["metrics"]["board_cleared"] for item in history["runs"])
    image = tmp_path / ".rhinodiet" / "tests" / history["runs"][0]["id"] / history["runs"][0]["images"][0]
    assert image.is_file()
    assert image.read_bytes().startswith(b"\x89PNG")
    areas = graph.by_label("area")
    assert {node.name for node in areas} == {"avoid-ghosts", "restart", "clear-board"}
    assert all(node.body == "" for node in areas)
    again = supervisor.run('test this area: avoid ghosts')
    cited = {item.id for item in again.cites}
    assert any(node.id in cited for node in areas)


def test_focus_records_a_still_and_compares_with_the_previous_run(tmp_path):
    _supervisor, graph = boot(tmp_path)
    marker = tmp_path / "benchmarks" / "godot-pacman" / "project.godot"
    marker.parent.mkdir(parents=True)
    marker.write_text("config_version=5\n", encoding="utf-8")
    service = TesterService(graph)
    first = service.run('focus on avoid ghosts', tmp_path, focus="avoid ghosts")
    assert first.passed
    assert first.mode == "focus"
    assert first.area == "avoid-ghosts"
    history = load_history(tmp_path)
    run = history["runs"][-1]
    assert run["images"]
    assert len(run["images"]) >= 4
    assert run["metrics"]["time_survived"] > 4
    assert run["metrics"]["pellets_eaten"] == 201
    assert run["metrics"]["board_cleared"] is True
    still = tmp_path / ".rhinodiet" / "tests" / run["id"] / run["images"][0]
    assert still.read_bytes().startswith(b"\x89PNG")
    second_metrics = dict(run["metrics"])
    second_metrics["pellets_eaten"] = run["metrics"]["pellets_eaten"] + 3
    second_metrics["time_survived"] = run["metrics"]["time_survived"] + 1
    second_metrics["ghosts_hit"] = 1
    second_metrics["board_cleared"] = False
    entry = record_run(
        tmp_path,
        mode="focus",
        area="avoid-ghosts",
        passed=False,
        result="A ghost caught Pac-Man.",
        metrics=second_metrics,
        frames=[still.read_bytes()],
    )
    text = entry["versus"]
    assert "Pellets eaten" in text and "up" in text
    assert "Time survived" in text
    assert "Ghosts hit 1 versus 0, up 1." in text
    assert "Board cleared no versus yes." in text
    assert compare_metrics(second_metrics, run["metrics"]) == text
    assert "No test runs yet" in page_html()


def test_a_new_game_registers_areas_the_same_way(tmp_path):
    _supervisor, graph = boot(tmp_path)
    marker = tmp_path / "games" / "blocks" / "project.godot"
    marker.parent.mkdir(parents=True)
    marker.write_text("config_version=5\n", encoding="utf-8")
    blocks = GameSpec(
        name="blocks",
        marker="games/blocks/project.godot",
        endurance="stack",
        play=None,
        areas=(
            Area("stack", "Stack blocks.", "The stack stands.", "The stack falls."),
        ),
    )
    service = TesterService(graph, games=(blocks,))
    service.ensure(tmp_path)
    nodes = graph.by_label("area")
    assert len(nodes) == 1
    assert nodes[0].name == "stack"
    assert nodes[0].body == ""
    assert "Stack blocks." in nodes[0].summary
    assert choose_area("stack blocks", blocks.areas).name == "stack"
    report = service.run("test the game", tmp_path)
    assert report.passed is False
    assert "no play driver" in report.text


def test_a_death_is_recorded_and_the_loop_tries_again(tmp_path):
    _supervisor, graph = boot(tmp_path)
    marker = tmp_path / "bench" / "game.marker"
    marker.parent.mkdir(parents=True)
    marker.write_text("marker", encoding="utf-8")
    calls = []

    def play(name):
        calls.append(name)
        eaten = 25 * len(calls)
        return PlayResult(
            False,
            f"A ghost caught Pac-Man after {eaten} pellets and 12.0 seconds.",
            eaten,
            12.0,
            1,
            False,
            [b"\x89PNG"],
        )

    game = GameSpec(
        name="maze",
        marker="bench/game.marker",
        endurance="clear-board",
        play=play,
        areas=(Area("clear-board", "Beat the level.", "Board clear.", "Pellets remain."),),
    )
    service = TesterService(graph, games=(game,))
    report = service.run("test the game", tmp_path, loops=2)
    assert calls == ["clear-board", "clear-board"]
    assert report.passed is False
    history = load_history(tmp_path)
    assert [item["metrics"]["pellets_eaten"] for item in history["runs"]] == [25, 50]
    assert [item["metrics"]["time_survived"] for item in history["runs"]] == [12.0, 12.0]
    assert all(item["metrics"]["ghosts_hit"] == 1 for item in history["runs"])
    assert all(item["metrics"]["board_cleared"] is False for item in history["runs"])
    assert all(item["passed"] is False for item in history["runs"])


def test_showtests_command_reads_history_json(tmp_path):
    command = (ROOT / "commands" / "showtests.md").read_text(encoding="utf-8")
    assert command.startswith("---\n")
    assert "name: showtests" in command
    assert "rhinodiet test --show" in command
    assert "history.json" in command
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/showtests" in readme
    folder = tmp_path / ".rhinodiet" / "tests" / "run-1"
    folder.mkdir(parents=True)
    (folder / "frame-000.png").write_bytes(b"\x89PNG")
    payload = {
        "runs": [
            {
                "id": "run-1",
                "at": "2026-10-04T22:08:00Z",
                "mode": "focus",
                "area": "avoid-ghosts",
                "passed": False,
                "result": "Stopped after 4.0 seconds with pellets left.",
                "metrics": {
                    "pellets_eaten": 177,
                    "time_survived": 4.0,
                    "ghosts_hit": 0,
                    "board_cleared": False,
                },
                "images": ["frame-000.png"],
                "versus": "",
            }
        ]
    }
    history = tmp_path / ".rhinodiet" / "tests" / "history.json"
    history.write_text(json.dumps(payload), encoding="utf-8")
    text = show_tests(tmp_path, probe=lambda _port: True)
    assert "2026-10-04T22:08:00Z" in text
    assert "focus" in text
    assert "avoid-ghosts" in text
    assert "fail." in text
    assert "Pellets eaten 177." in text
    assert "Time survived 4.0 seconds." in text
    assert "Ghosts hit 0." in text
    assert "Board cleared no." in text
    assert ".rhinodiet/tests/run-1/frame-000.png" in text
    assert "http://127.0.0.1:8797/" in text
    for line in TEST_COMMANDS:
        assert line in text.splitlines()
    missing = show_tests(tmp_path / "empty", probe=lambda _port: False)
    assert "No test runs yet." in missing
    assert "History page is not running. Start it with rhinodiet test --serve." in missing
    assert "http://127.0.0.1:8797/" not in missing


def test_show_cli_reads_history_without_playing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RHINODIET_PROJECT", str(tmp_path))
    monkeypatch.setattr("rhinodiet.testhistory.port_open", lambda _port: False)
    assert main(["test", "--show"]) == 0
    empty = capsys.readouterr().out
    assert "No test runs yet." in empty
    assert "History page is not running. Start it with rhinodiet test --serve." in empty
    for line in TEST_COMMANDS:
        assert line in empty.splitlines()
    record_run(
        tmp_path,
        mode="loop",
        area="clear-board",
        passed=True,
        result="Cleared the board.",
        metrics={
            "pellets_eaten": 201,
            "time_survived": 217.1,
            "ghosts_hit": 0,
            "board_cleared": True,
        },
        frames=[b"\x89PNG"],
    )
    monkeypatch.setattr("rhinodiet.testhistory.port_open", lambda _port: True)
    assert main(["test", "--show"]) == 0
    shown = capsys.readouterr().out
    assert "clear-board" in shown
    assert "pass." in shown
    assert "Pellets eaten 201." in shown
    assert "Time survived 217.1 seconds." in shown
    assert "Ghosts hit 0." in shown
    assert "Board cleared yes." in shown
    assert "frame-000.png" in shown
    assert "History page is already up at http://127.0.0.1:8797/." in shown
    assert "No registered game" not in shown
