from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

from dd_activegraph.holdout import (
    HOLDOUT_COMMIT,
    IMPORTER_SHA256,
    SOURCE_GIT_TREE,
    SOURCE_TREE_LISTING_SHA256,
    verify_frozen_inputs,
)
from dd_activegraph.trial import SNAPSHOT_FILES
from dd_activegraph.validation import HOST_PATH_RE, SECRET_PATTERNS

REPO = Path(__file__).parents[1]
SOURCE = REPO / ".sources/holdout" / HOLDOUT_COMMIT
COMPARISON = REPO / "exports/holdout-comparison"
CANONICAL = REPO / "exports/holdout" / HOLDOUT_COMMIT


def _json(name: str):
    return json.loads((COMPARISON / name).read_text())


def test_holdout_source_and_importer_are_exactly_frozen() -> None:
    result = verify_frozen_inputs(REPO, SOURCE)
    assert all(result["checks"].values())
    assert result["commit"] == HOLDOUT_COMMIT
    assert result["tree"] == SOURCE_GIT_TREE
    assert result["listing_sha256"] == SOURCE_TREE_LISTING_SHA256
    assert hashlib.sha256((REPO / "dd_activegraph/importers.py").read_bytes()).hexdigest() == (
        IMPORTER_SHA256
    )


def test_first_no_code_change_result_is_preserved() -> None:
    result = _json("no-code-change-result.json")
    assert result["importer_or_policy_changes_before_attempt"] == []
    assert result["import_succeeded"] is True
    assert result["first_delete_and_rebuild_byte_identical"] is True
    assert result["replay_succeeded"] is True
    assert (result["objects"], result["relations"], result["events"]) == (1758, 2764, 4555)
    assert {path.name for path in CANONICAL.iterdir()} == set(SNAPSHOT_FILES)


def test_two_rebuilds_replay_and_registry_agreement() -> None:
    rebuild = _json("deterministic-rebuild-report.json")
    assert len(rebuild["attempts"]) == 2
    assert all(row["byte_identical"] and row["replay"] for row in rebuild["attempts"])
    registry = _json("registry-comparison.json")
    assert registry["canonical_relation_count"] == 181
    assert registry["exact_matches"] == 181
    assert registry["missing_canonical_relations"] == 0
    assert registry["relation_type_mismatches"] == 0
    assert registry["reverse_link_coverage"] == {"expected": 40, "present": 40, "rate": 1.0}
    assert registry["extra_inferred_relations"] == 30
    assert registry["ambiguous_relations"] == 0


def test_structural_current_state_stale_and_public_safety_results() -> None:
    audit = _json("structural-audit.json")
    assert len(audit["current_state_findings"]) == 1
    assert audit["current_state_findings"][0]["code"] == "current_state_count_mismatch"
    assert audit["stale_status_findings"] == []
    assert audit["reverse_link_findings"] == []
    assert audit["public_safety_findings"] == []
    summaries = {row["behavior"]: row for row in audit["summaries"]}
    for behavior in (
        "dangling_relation_detector",
        "orphan_claim_detector",
        "public_safety_gate",
        "reverse_link_detector",
        "site_relation_materializer",
        "stale_status_detector",
    ):
        assert summaries[behavior]["status"] == "pass"


def test_evidence_role_policy_is_complete_explicit_and_not_overclaimed() -> None:
    analysis = _json("evidence-role-analysis.json")
    assert analysis["policy_status"] == "explicit-proposal-not-validated"
    assert analysis["complete"] is True
    assert analysis["finding_set"] == {
        "calibration_findings": 13,
        "holdout_findings": 13,
        "new_holdout_findings": 0,
        "resolved_holdout_findings": 0,
    }
    assert analysis["role_counts"] == {
        "current primary": 5,
        "current supporting": 1,
        "preliminary/failed": 2,
        "superseded/historical": 5,
    }
    assert analysis["required_gate_projection"]["false_positive_rate"] == 1.0
    assert analysis["required_gate_projection"]["precision"] is None


def test_holdout_artifacts_are_safe_and_no_database_or_source_is_tracked() -> None:
    for root in (CANONICAL, COMPARISON):
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text()
                assert HOST_PATH_RE.search(text) is None
                assert all(pattern.search(text) is None for _, pattern in SECRET_PATTERNS)
    tracked = subprocess.run(
        ["git", "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any(path.endswith((".sqlite", ".sqlite3", ".db")) for path in tracked)
    assert not any(path.startswith(".sources/") for path in tracked)


def test_holdout_layer_has_no_network_or_llm_dependency() -> None:
    modules = set()
    for filename in ("holdout.py", "importers.py", "behaviors.py"):
        tree = ast.parse((REPO / "dd_activegraph" / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
    assert modules.isdisjoint({"anthropic", "httpx", "openai", "requests", "socket"})


def test_adoption_decision_is_consistent_with_holdout_results() -> None:
    decision = (REPO / "docs/adoption-decision-v3.md").read_text()
    assert "Adopt optional structural relationship auditing only" in decision
    assert "required evidence-audit CI remains disabled" in decision
    assert "504c9fb9c1039b21bf57f83a794f9f0da3e64afa" in decision


def test_required_holdout_report_set_is_git_visible() -> None:
    required = {
        "audit-delta.json",
        "audit-delta.md",
        "deterministic-rebuild-report.json",
        "deterministic-rebuild-report.md",
        "diff-readability.json",
        "diff-readability.md",
        "evidence-role-analysis.json",
        "evidence-role-analysis.md",
        "holdout-summary.json",
        "performance.json",
        "performance.md",
        "recognized-files.json",
        "registry-comparison.json",
        "registry-comparison.md",
        "replay-report.json",
        "replay-report.md",
        "structural-audit.json",
    }
    assert required <= {path.name for path in COMPARISON.iterdir()}
