import json

from rhinodiet.creative import HttpCreativeProvider, LocalCreativeProvider, style_from_summary
from rhinodiet.supervisor import HttpModel, OfflineModel

from support import FLUFFY, PASSAGE, boot


class RecordingModel:
    def __init__(self, inner=None):
        self.inner = inner or OfflineModel()
        self.calls = []

    def complete(self, agent, model, system, user):
        self.calls.append({"agent": agent, "model": model, "user": user})
        return self.inner.complete(agent, model, system, user)


class ScriptedModel:
    def __init__(self):
        self.calls = []
        self.dev_rounds = 0

    def complete(self, agent, model, system, user):
        self.calls.append({"agent": agent, "model": model, "user": user})
        assert agent in {"dev", "reviewer"}
        assert model == "composer-2.5[fast=true]"
        if agent == "reviewer":
            if self.dev_rounds >= 2:
                return json.dumps({"accept": True, "findings": []})
            return json.dumps(
                {
                    "accept": False,
                    "findings": ["Cover the expired token branch in tests/test_session.py."],
                }
            )
        self.dev_rounds += 1
        if self.dev_rounds == 1:
            return json.dumps(
                {
                    "summary": "Added expiry check in src/auth/session.py.",
                    "code_changed": True,
                    "files": ["src/auth/session.py"],
                    "tests": [],
                }
            )
        return json.dumps(
            {
                "summary": "Covered expired token branch.",
                "code_changed": True,
                "files": ["src/auth/session.py"],
                "tests": ["tests/test_session.py"],
            }
        )


def test_workers_are_the_cheaper_tier():
    from support import config

    cfg = config()
    assert cfg.supervisor_model == "inherit"
    assert cfg.worker_model != cfg.supervisor_model
    assert "fast=true" in cfg.worker_model
    for name in ("dev", "reviewer", "creative", "godot", "release", "docs", "tester"):
        assert cfg.agent_tiers[name] == "worker"
        assert cfg.model_for(name) == cfg.worker_model
    assert cfg.model_for("supervisor") == cfg.supervisor_model


def test_dev_review_loop_sends_findings_back(tmp_path):
    model = ScriptedModel()
    supervisor, graph = boot(tmp_path, model)
    report = supervisor.run(FLUFFY)
    assert report.agents == ["dev", "reviewer", "dev", "reviewer"]
    assert report.accepted
    assert [call["agent"] for call in model.calls] == ["dev", "reviewer", "dev", "reviewer"]
    assert "it is important to note that" not in model.calls[0]["user"].lower()
    assert "UserToken" in model.calls[0]["user"]
    assert "must reject expired tokens" in model.calls[0]["user"]
    assert "TokenExpiredError: token exp 1710000000" in model.calls[0]["user"]
    assert "tests/test_session.py" in model.calls[2]["user"]
    assert "def " not in report.reply
    assert "```" not in report.reply
    assert "creative" not in report.agents
    assert "release" not in report.agents
    assert "docs" not in report.agents
    node = graph.get(report.memory_id)
    assert node.body == ""
    assert FLUFFY not in node.summary


def test_open_review_does_not_get_a_supervisor_patch(tmp_path):
    class AlwaysReject:
        def complete(self, agent, model, system, user):
            assert agent != "supervisor"
            if agent == "reviewer":
                return json.dumps(
                    {"accept": False, "findings": ["Cover tests/test_session.py."]}
                )
            return json.dumps(
                {
                    "summary": "Touched src/auth/session.py.",
                    "code_changed": True,
                    "files": ["src/auth/session.py"],
                    "tests": ["tests/test_session.py"],
                }
            )

    supervisor, _graph = boot(tmp_path, AlwaysReject())
    report = supervisor.run("fix the bug in src/auth/session.py")
    assert report.accepted is False
    assert report.agents.count("reviewer") == 2
    assert "Sent findings back to dev." in report.reply
    assert "```" not in report.reply


def test_creative_and_release_stay_off_the_code_path(tmp_path):
    model = RecordingModel()
    supervisor, graph = boot(tmp_path, model)
    code = supervisor.run("add a parser in src/app.py")
    assert code.agents == ["dev"]
    assert model.calls[0]["agent"] == "dev"
    assert "creative" not in code.agents
    assert "docs" not in code.agents
    assert "release" not in code.agents

    logo = supervisor.run("draw a logo texture")
    assert logo.agents == ["creative"]
    styles = graph.by_label("style")
    assert len(styles) == 1
    style = style_from_summary(styles[0].summary)
    assert style is not None
    svg = (tmp_path / "art" / "mark.svg").read_text(encoding="utf-8")
    assert style.palette[2] in svg
    assert "<svg" not in graph.get(logo.memory_id).body

    again = supervisor.run("draw a logo")
    assert again.agents == ["creative"]
    assert len(graph.by_label("style")) == 1

    video = supervisor.run("make a video")
    assert (tmp_path / "art" / "storyboard.md").exists()
    assert video.agents == ["creative"]


def test_release_writes_a_script_and_does_not_run_it(tmp_path):
    model = RecordingModel()
    supervisor, graph = boot(tmp_path, model)
    before = len(model.calls)
    report = supervisor.run("package the release and open a pull request")
    script = tmp_path / "scripts" / "release.sh"
    text = script.read_text(encoding="utf-8")
    assert report.agents == ["release"]
    assert len(model.calls) == before
    assert "python -m pytest" in text
    assert "python -m build" in text
    assert 'git commit -m "Release"' in text
    assert "git push -u origin HEAD" in text
    stored = graph.get(report.memory_id)
    assert "python -m pytest" not in stored.body
    assert "python -m pytest" not in stored.summary
    assert not (tmp_path / "dist").exists()


def test_docs_keyword_and_mixed_plan(tmp_path):
    model = RecordingModel()
    supervisor, _graph = boot(tmp_path, model)
    docs_only = supervisor.run("document the API for UserToken")
    assert docs_only.agents == ["docs"]
    assert docs_only.delegations[0][1] == supervisor.config.worker_model
    assert model.calls == []

    mixed = supervisor.run("add a parser and document the API")
    assert mixed.agents == ["dev", "docs"]
    assert "creative" not in mixed.agents
    assert "release" not in mixed.agents
    node = _graph.get(mixed.memory_id)
    assert "document the API" not in node.body
    assert node.body == ""


def test_review_only_and_no_match(tmp_path):
    model = RecordingModel()
    supervisor, graph = boot(tmp_path, model)
    review = supervisor.run("review the auth changes")
    assert review.agents == ["reviewer"]
    assert model.calls[0]["agent"] == "reviewer"
    quiet = supervisor.run("thanks")
    assert quiet.agents == []
    assert quiet.memory_id == ""
    assert "No worker matched." in quiet.reply
    assert graph.count() >= 1


def test_compact_runs_when_over_threshold(tmp_path):
    supervisor, graph = boot(tmp_path, compact_after_nodes=3)
    for index in range(3):
        graph.add_node(label="task", name=f"old {index}", summary=f"Old note {index}.", salience=0.1)
    report = supervisor.run("add a parser")
    assert report.compacted
    assert graph.count() <= 3


def test_http_clients_fall_back_without_credentials(tmp_path):
    model = HttpModel("http://127.0.0.1:9", OfflineModel())
    raw = model.complete("dev", "composer-2.5[fast=true]", "system", "add a parser")
    assert json.loads(raw)["code_changed"] is False
    provider = HttpCreativeProvider("http://127.0.0.1:9", LocalCreativeProvider())
    from rhinodiet.creative import DEFAULT_STYLE

    artifact = provider.generate("draw a logo", DEFAULT_STYLE, tmp_path / "art")
    assert artifact.path.name == "mark.svg"
    assert artifact.path.exists()


def test_prepare_assigns_docs_on_the_worker_tier(tmp_path):
    supervisor, _graph = boot(tmp_path)
    prepared = supervisor.prepare(PASSAGE)
    agents = [item["agent"] for item in prepared["assignments"]]
    assert agents == ["docs"]
    assert prepared["assignments"][0]["model"] == supervisor.config.worker_model
    assert "FULL" not in json.dumps(prepared["cites"])
