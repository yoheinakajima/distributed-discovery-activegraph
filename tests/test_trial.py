from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

from dd_activegraph.importers import DistributedDiscoveryImporter
from dd_activegraph.trial import SNAPSHOT_FILES, load_snapshot_specs
from dd_activegraph.validation import HOST_PATH_RE, SECRET_PATTERNS

REPO = Path(__file__).parents[1]
SOURCE_ROOT = REPO / ".sources/snapshots"


def _content(path: Path):
    return json.loads(path.read_text())["content"]


def test_every_snapshot_pin_exists_is_clean_and_imports() -> None:
    specs = load_snapshot_specs(REPO / "config/snapshots.yml")
    assert len(specs) == 4
    for spec in specs:
        source = SOURCE_ROOT / spec.commit
        observed = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert observed == spec.commit
        assert dirty == ""
        assert DistributedDiscoveryImporter(source, expected_commit=spec.commit).build().objects


def test_importer_freeze_checksum_and_no_commit_branches() -> None:
    freeze = json.loads((REPO / "config/importer-freeze.json").read_text())
    importer = (REPO / freeze["importer_path"]).read_bytes()
    assert hashlib.sha256(importer).hexdigest() == freeze["importer_sha256"]
    assert freeze["importer_changes_required"] == 1
    assert freeze["commit_specific_branches"] == 0


def test_snapshot_exports_are_complete_and_pinned() -> None:
    specs = load_snapshot_specs(REPO / "config/snapshots.yml")
    for spec in specs:
        output = REPO / "exports/snapshots" / spec.commit
        assert {path.name for path in output.iterdir()} == set(SNAPSHOT_FILES)
        lock = _content(output / "source-lock.json")
        assert lock["source_commit"] == spec.commit
        objects = _content(output / "graph.json")
        blocking_codes = {
            item["attributes"]["code"]
            for item in objects
            if item["type"] == "decision"
            and item.get("attributes", {}).get("category") == "audit_finding"
            and item["attributes"]["behavior"]
            in {"dangling_relation_detector", "public_safety_gate"}
        }
        assert blocking_codes == set()


def test_compatibility_matrix_and_registry_comparison() -> None:
    matrix = json.loads((REPO / "exports/comparison/compatibility-matrix.json").read_text())
    assert len(matrix["snapshots"]) == 4
    assert matrix["importer_changes_required"] == 1
    assert matrix["commit_specific_branches"] == 0
    assert all(item["deterministic_rebuild"] and item["replay"] for item in matrix["snapshots"])
    registry_results = [
        item["relationship_registry"]
        for item in matrix["snapshots"]
        if item["relationship_registry"]["available"]
    ]
    assert len(registry_results) == 2
    assert all(item["missing_canonical_relations"] == 0 for item in registry_results)
    assert all(item["relation_type_mismatches"] == 0 for item in registry_results)
    assert all(item["reverse_link_coverage"]["rate"] == 1.0 for item in registry_results)


def test_gap_triage_is_complete_and_exclusive() -> None:
    triage = yaml.safe_load((REPO / "exports/comparison/gap-triage.yml").read_text())
    findings = triage["findings"]
    assert len(findings) == 13
    assert all(item["classification"] in {"A", "B", "C", "D"} for item in findings)
    count_keys = (
        "true_positive_count",
        "false_positive_count",
        "historical_exception_count",
        "expected_failed_or_preliminary_count",
    )
    assert sum(triage["metrics"][key] for key in count_keys) == 13
    assert not any(item["should_block_ci"] for item in findings)


def test_two_snapshot_fork_fixtures_are_stable_and_replay() -> None:
    fixture_roots = sorted((REPO / "exports/comparison/fixtures").iterdir())
    assert len(fixture_roots) == 2
    reverse_shapes = []
    status_shapes = []
    for root in fixture_roots:
        reverse = json.loads((root / "fork-diff.json").read_text())
        status = json.loads((root / "status-fork-diff.json").read_text())
        assert reverse["activegraph_diff"]["divergent_relations"] == 1
        assert reverse["new_findings"][0]["code"] == "missing_reverse_relation"
        assert reverse["replay_verified"] is True
        assert status["new_findings"][0]["code"] == "study_status_mismatch"
        assert status["scientific_source_changed"] is False
        assert status["replay_verified"] is True
        reverse_shapes.append(set(reverse) - {"canonical_content_sha256", "metadata"})
        status_shapes.append(set(status) - {"canonical_content_sha256", "metadata"})
    assert reverse_shapes[0] == reverse_shapes[1]
    assert status_shapes[0] == status_shapes[1]


def test_trial_exports_have_no_secret_or_host_path() -> None:
    roots = (REPO / "exports/snapshots", REPO / "exports/comparison", REPO / "reports")
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text()
                assert HOST_PATH_RE.search(text) is None
                assert all(pattern.search(text) is None for _, pattern in SECRET_PATTERNS)


def test_no_database_or_source_snapshot_is_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any(path.endswith((".sqlite", ".sqlite3", ".db")) for path in tracked)
    assert not any(path.startswith(".sources/") for path in tracked)
