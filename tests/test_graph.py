from rhinodiet.graph import GraphStore, format_cites


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_traverse_follows_typed_edges(tmp_path):
    graph = GraphStore(tmp_path / "memory.db")
    first = graph.add_node(label="task", name="a", summary="start")
    second = graph.add_node(label="file", name="b", summary="middle")
    third = graph.add_node(label="file", name="c", summary="end")
    side = graph.add_node(label="note", name="d", summary="side")
    graph.link(first.id, second.id, "depends_on")
    graph.link(second.id, third.id, "depends_on")
    graph.link(first.id, side.id, "mentions")

    depth_one = {node.id for node in graph.traverse(first.id, depth=1)}
    assert depth_one == {second.id, side.id}
    depth_two = {node.id for node in graph.traverse(first.id, depth=2)}
    assert third.id in depth_two
    typed = {node.id for node in graph.traverse(first.id, depth=1, edge_types=["depends_on"])}
    assert typed == {second.id}
    assert graph.traverse("missing", depth=2) == []

    graph.delete_node(second.id)
    assert third.id not in {node.id for node in graph.traverse(first.id, depth=2)}


def test_cite_ranks_salient_recent_refs_and_hides_bodies(tmp_path):
    clock = Clock()
    graph = GraphStore(tmp_path / "memory.db", clock=clock)
    old = graph.add_node(
        label="requirement",
        name="token expiry old",
        summary="token expiry old",
        salience=0.1,
        body="SECRET_BLOB_DO_NOT_CITE",
    )
    clock.now = 10_000
    fresh = graph.add_node(
        label="requirement",
        name="token expiry new",
        summary="token expiry new",
        salience=0.95,
        horizon="long",
    )
    cites = graph.cite("token expiry")
    assert cites[0].id == fresh.id
    assert old.id in {item.id for item in cites}
    rendered = format_cites(cites)
    assert "SECRET_BLOB_DO_NOT_CITE" not in rendered
    assert "body" not in cites[0].__dataclass_fields__
    assert graph.get(old.id).body == "SECRET_BLOB_DO_NOT_CITE"


def test_compact_merges_stale_short_term_and_keeps_the_model(tmp_path):
    clock = Clock()
    graph = GraphStore(tmp_path / "memory.db", clock=clock)
    kept = graph.add_node(
        label="requirement",
        name="expiry rule",
        summary="Handler rejects expired tokens.",
        horizon="long",
        salience=0.95,
        body="FULL_REQUIREMENT_BLOB",
    )
    for index in range(8):
        graph.add_node(
            label="task",
            name=f"detail {index}",
            summary=f"Stale detail {index} about tokens.",
            salience=0.1,
        )
    clock.now = 50_000
    report = graph.compact(4)
    assert report.ran
    assert report.after <= 4
    assert report.after < report.before
    nodes = graph.all_nodes()
    assert kept.id in {node.id for node in nodes}
    assert any(node.name == "project-model" and node.horizon == "long" for node in nodes)
    rendered = format_cites(graph.cite("tokens", limit=10))
    assert "FULL_REQUIREMENT_BLOB" not in rendered
    model = next(node for node in nodes if node.name == "project-model")
    assert "Stale detail" in model.summary
    assert len(model.summary) < 400
