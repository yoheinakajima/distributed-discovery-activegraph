from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from dd_activegraph.demo import FORK_RUN_ID, run_fork_demo
from dd_activegraph.engine import build_runtime, close_runtime, replay_projection
from dd_activegraph.exporters import deterministic_files, export_runtime
from dd_activegraph.importers import DistributedDiscoveryImporter, SourceReader
from dd_activegraph.ontology import SOURCE_COMMIT, stable_relation_id
from dd_activegraph.validation import (
    HOST_PATH_RE,
    SECRET_PATTERNS,
    orphan_claim_findings,
    reverse_link_findings,
    stale_status_findings,
)


def test_import_current_repository(bundle):
    assert len(bundle.objects) == 1594
    assert len(bundle.relations) == 2548
    assert len(bundle.source_files) == 658


def test_stable_object_and_relation_ids(bundle):
    assert "claim:DD-C-0001" in bundle.objects
    relation = next(item for item in bundle.relations if item.source_key == "claim:DD-C-0001")
    assert stable_relation_id(
        relation.type, relation.source_key, relation.target_key, relation.data
    ) == stable_relation_id(relation.type, relation.source_key, relation.target_key, relation.data)


def test_claim_run_study_links(bundle):
    triples = {(r.type, r.source_key, r.target_key) for r in bundle.relations}
    assert ("owned_by", "claim:DD-C-0001", "study:DD-000") in triples
    assert any(kind == "supports" and target == "claim:DD-C-0001" for kind, _, target in triples)


def test_paper_lab_route_and_benchmark_links(bundle):
    triples = {(r.type, r.source_key, r.target_key) for r in bundle.relations}
    assert any(
        kind == "appears_in" and source.startswith("study:") and target.startswith("paper:")
        for kind, source, target in triples
    )
    assert any(kind == "exposed_by_lab" for kind, _, _ in triples)
    assert any(
        kind == "published_at" and target.startswith("route:") for kind, _, target in triples
    )
    assert any(
        kind == "tests" and source.startswith("benchmark_task:") and target.startswith("claim:")
        for kind, source, target in triples
    )


def test_current_state_counts_reconcile(bundle):
    program = bundle.objects["research_program:distributed-discovery"]
    assert program.attributes["declared_counts"] == program.attributes["computed_counts"]


def _obj(key: str, object_type: str, attributes: dict | None = None):
    return SimpleNamespace(
        id=key, type=object_type, data={"key": key, "attributes": attributes or {}}
    )


def _rel(relation_id: str, relation_type: str, source: str, target: str):
    return SimpleNamespace(
        id=relation_id, type=relation_type, source=source, target=target, data={}
    )


def test_orphan_stale_and_reverse_detectors():
    claim = _obj("claim:test", "claim")
    assert len(orphan_claim_findings([claim], [])) == 3
    study = _obj("study:test", "study", {"phase": "complete", "status": "planned"})
    assert stale_status_findings([study], [])
    lab = _obj("lab:test", "lab")
    relations = [_rel("r1", "exposed_by_lab", study.id, lab.id)]
    assert reverse_link_findings([study, lab], relations)[0].code == "missing_reverse_relation"


def test_public_safety_rejects_host_path(tmp_path: Path):
    path = tmp_path / "unsafe.yml"
    path.write_text("path: /Users/example/private.txt\n")
    with pytest.raises(ValueError, match="host-specific"):
        SourceReader(tmp_path).yaml("unsafe.yml")


def test_source_commit_pinning(source: Path):
    observed = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert observed == SOURCE_COMMIT


def test_materialize_replay_export_rebuild_and_fork(source: Path, tmp_path: Path):
    store = tmp_path / "graph.sqlite"
    runtime = build_runtime(store, fork_run_ids=(FORK_RUN_ID,))
    DistributedDiscoveryImporter(source).materialize(runtime)
    first = tmp_path / "first"
    export_runtime(runtime, first)
    demo = run_fork_demo(runtime, first)
    assert demo["replay_verified"] is True
    assert demo["new_findings"][0]["code"] == "missing_reverse_relation"
    close_runtime(runtime)
    replayed = replay_projection(store)
    assert len(replayed.graph.all_objects()) == 1656
    close_runtime(replayed)
    second_store = tmp_path / "second.sqlite"
    second = build_runtime(second_store, fork_run_ids=(FORK_RUN_ID,))
    DistributedDiscoveryImporter(source).materialize(second)
    rebuilt = tmp_path / "rebuilt"
    export_runtime(second, rebuilt)
    run_fork_demo(second, rebuilt)
    close_runtime(second)
    assert deterministic_files(first) == deterministic_files(rebuilt)


def test_exports_have_no_secret_or_host_path():
    for path in Path("exports/current").iterdir():
        if path.is_file():
            text = path.read_text()
            assert HOST_PATH_RE.search(text) is None
            assert all(pattern.search(text) is None for _, pattern in SECRET_PATTERNS)


def test_no_database_tracked_and_no_llm_or_network_runtime():
    tracked = subprocess.run(
        ["git", "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any(path.endswith((".sqlite", ".sqlite3", ".db")) for path in tracked)
    settings = Path("dd_activegraph/schemas.py").read_text()
    assert "allow_network: bool = False" in settings
    assert "allow_llm: bool = False" in settings
