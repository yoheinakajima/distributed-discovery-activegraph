"""ActiveGraph runtime construction and deterministic replay helpers."""

from __future__ import annotations

from pathlib import Path

from activegraph import FrozenClock, Graph, IDGen, Runtime

from dd_activegraph.pack import pack
from dd_activegraph.schemas import PackSettings

CANONICAL_RUN_ID = "run_dd_activegraph_import_v1"
CANONICAL_TIMESTAMP = "2026-07-22T00:00:00Z"


class DeterministicIDGen(IDGen):
    """ID generator with fixed fork run IDs while retaining ActiveGraph counters."""

    def __init__(self, fork_run_ids: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._fork_run_ids = list(fork_run_ids)

    def run(self) -> str:
        if not self._fork_run_ids:
            raise RuntimeError("no deterministic fork run id remains")
        return self._fork_run_ids.pop(0)


def normalize_store_path(value: str | Path) -> Path:
    text = str(value)
    if text.startswith("sqlite:///"):
        text = text.removeprefix("sqlite:///")
    path = Path(text)
    return path if path.is_absolute() else Path.cwd() / path


def build_runtime(
    store: str | Path,
    *,
    run_id: str = CANONICAL_RUN_ID,
    fork_run_ids: tuple[str, ...] = (),
) -> Runtime:
    path = normalize_store_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph = Graph(
        ids=DeterministicIDGen(fork_run_ids),
        clock=FrozenClock(CANONICAL_TIMESTAMP),
        run_id=run_id,
    )
    runtime = Runtime(graph, persist_to=str(path), seed=0)
    runtime.load_pack(pack, settings=PackSettings())
    return runtime


def close_runtime(runtime: Runtime) -> None:
    runtime.graph.close_sinks()
    if runtime.graph.store is not None:
        runtime.graph.store.close()


def replay_projection(store: str | Path, run_id: str = CANONICAL_RUN_ID) -> Runtime:
    return Runtime.load(str(normalize_store_path(store)), run_id=run_id)
