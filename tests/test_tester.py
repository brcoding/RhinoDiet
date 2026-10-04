"""Game tester assignment, focus, Pac-Man play, and history stills."""

from rhinodiet.pacman_play import run_avoid, run_clear, run_restart
from rhinodiet.supervisor import wants_dev, wants_godot, wants_tester
from rhinodiet.tester import Area, GameSpec, TesterService, choose_area
from rhinodiet.testhistory import compare_metrics, load_history, page_html, record_run

from support import ROOT, boot


def _pacman_game() -> GameSpec:
    from rhinodiet.tester import PACMAN

    return PACMAN


def test_focus_maps_phrases_to_areas():
    areas = _pacman_game().areas
    assert choose_area("avoid ghosts", areas).name == "avoid-ghosts"
    assert choose_area("restart", areas).name == "restart"
    assert choose_area("reach the end while avoiding ghosts", areas).name == "clear-board"
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


def test_pacman_driver_meets_each_goal():
    avoid = run_avoid()
    assert avoid.passed
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
    still = tmp_path / ".rhinodiet" / "tests" / run["id"] / run["images"][0]
    assert still.read_bytes().startswith(b"\x89PNG")
    second_metrics = dict(run["metrics"])
    second_metrics["pellets_eaten"] = run["metrics"]["pellets_eaten"] + 3
    second_metrics["time_survived"] = run["metrics"]["time_survived"] + 1
    second_metrics["ghosts_hit"] = 1
    second_metrics["board_cleared"] = True
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
    assert "Board cleared yes versus no." in text
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
