from rhinodiet.docs import rewrite_technical

from support import PASSAGE, boot


FACTS = (
    "UserToken",
    "src/auth/session.py",
    "TokenExpiredError: token exp 1710000000",
)


def test_rewrite_is_shorter_active_and_exact():
    result = rewrite_technical(PASSAGE)
    assert 0.25 <= result.saved_ratio <= 0.45
    lowered = result.text.lower()
    assert "is validated by" not in lowered
    assert "is rejected by" not in lowered
    assert "is performed by" not in lowered
    assert "gate validates" in lowered
    assert "handler rejects" in lowered
    assert "middleware performs" in lowered
    for fact in FACTS:
        assert fact in result.text
    assert "it is important to note that" not in lowered
    assert "in order to" not in lowered
    assert "\u2014" not in result.text
    assert ";" not in result.text
    assert result.summary_line.startswith("Docs pass.")
    assert PASSAGE not in result.summary_line


def test_past_passive_becomes_active():
    result = rewrite_technical("The blob was stored by the cache.")
    assert "was stored by" not in result.text.lower()
    assert "cache stored" in result.text.lower()
    assert "blob" in result.text.lower()


def test_docs_pass_stores_a_short_ref(tmp_path):
    supervisor, graph = boot(tmp_path)
    prior = graph.add_node(
        label="requirement",
        name="UserToken",
        summary="UserToken stays exact",
        horizon="long",
        salience=0.9,
        body="FULL_HISTORY_BLOB",
    )
    report = supervisor.run(PASSAGE)
    assert report.agents == ["docs"]
    assert report.delegations == [("docs", supervisor.config.worker_model)]
    assert supervisor.config.worker_model != supervisor.config.supervisor_model
    node = graph.get(report.memory_id)
    stored = f"{node.summary}\n{node.body}"
    assert node.body == ""
    assert len(node.summary) < 80
    assert node.summary.startswith("Docs pass.")
    assert PASSAGE not in stored
    assert report.rewrite not in stored
    assert "FULL_HISTORY_BLOB" not in report.reply
    assert "FULL_HISTORY_BLOB" not in stored
    assert (prior.id, "cites") in graph.edges_from(report.memory_id)
    for fact in FACTS:
        assert fact in report.rewrite
    assert "gate validates" in report.rewrite.lower()
