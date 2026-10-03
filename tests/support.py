"""Shared fixtures for RhinoDiet tests."""

from pathlib import Path

from rhinodiet.config import Config, load_config
from rhinodiet.creative import CreativeService, LocalCreativeProvider
from rhinodiet.graph import GraphStore
from rhinodiet.supervisor import OfflineModel, Supervisor

ROOT = Path(__file__).resolve().parents[1]

PASSAGE = (
    "It is important to note that the token is validated by the gate at this point in time. "
    "The expired token is rejected by the handler in the event that the exp claim is in the past. "
    "UserToken lives in src/auth/session.py. "
    "On failure the handler raises TokenExpiredError: token exp 1710000000. "
    "Please note that the session check is really just performed by the middleware in order to keep the session safe. "
    "It should be noted that the same session check is basically repeated by the middleware again."
)

FLUFFY = (
    "Please could you kindly just really take a moment in order to add the session check. "
    "It is important to note that this is a very simple change at this point in time. "
    "The handler must reject expired tokens. "
    "Keep the identifier UserToken in src/auth/session.py. "
    "On failure raise TokenExpiredError: token exp 1710000000."
)


def config(**changes) -> Config:
    base = load_config(ROOT / "rhinodiet.config.json")
    data = {**base.__dict__}
    data.update(changes)
    return Config(**data)


def boot(tmp_path: Path, model=None, **changes):
    cfg = config(**changes)
    graph = GraphStore(tmp_path / "memory.db")
    creative = CreativeService(graph, LocalCreativeProvider(), tmp_path / "art")
    supervisor = Supervisor(
        graph=graph,
        config=cfg,
        model=model or OfflineModel(),
        project_root=tmp_path,
        creative=creative,
    )
    return supervisor, graph
