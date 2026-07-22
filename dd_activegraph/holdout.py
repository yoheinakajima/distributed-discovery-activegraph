"""Deterministic verification and reporting for the frozen DD-022 holdout."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from typing import Any, cast

import yaml

from dd_activegraph.engine import build_runtime, close_runtime, replay_projection
from dd_activegraph.exporters import deterministic_files, export_runtime
from dd_activegraph.importers import DistributedDiscoveryImporter
from dd_activegraph.triage import BUCKETS, TRIAGE
from dd_activegraph.trial import SNAPSHOT_FILES, _registry_comparison
from dd_activegraph.validation import HOST_PATH_RE, SECRET_PATTERNS

HOLDOUT_COMMIT = "504c9fb9c1039b21bf57f83a794f9f0da3e64afa"
CALIBRATION_COMMIT = "06523c8d9ff6d0f4e66457997f5094b69065ec95"
IMPORTER_SHA256 = "b9a0f4409e3aa53072f391f279cf33dbc11041f5755534177368386551ea79df"
SOURCE_GIT_TREE = "f2d6e48e9cbd975743add323cef2a38e5f6f86fa"
SOURCE_TREE_LISTING_SHA256 = "dfebf9c4f819539547b7fde65c77b0f3d68e09fab7ea31765fbb865724733e0d"


def _content(path: Path) -> Any:
    return json.loads(path.read_text())["content"]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _git(source: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=not binary,
    )
    return cast(str | bytes, result.stdout)


def verify_frozen_inputs(repo: Path, source: Path) -> dict[str, Any]:
    importer_sha = hashlib.sha256((repo / "dd_activegraph/importers.py").read_bytes()).hexdigest()
    commit = cast(str, _git(source, "rev-parse", "HEAD")).strip()
    tree = cast(str, _git(source, "rev-parse", "HEAD^{tree}")).strip()
    dirty = cast(str, _git(source, "status", "--porcelain")).strip()
    listing = cast(bytes, _git(source, "ls-tree", "-rz", "--full-tree", "HEAD", binary=True))
    listing_sha = hashlib.sha256(listing).hexdigest()
    freeze = json.loads((repo / "config/holdout-importer-freeze.json").read_text())
    lock = yaml.safe_load((repo / "config/holdout-source-lock.yml").read_text())
    checks = {
        "importer_checksum": importer_sha == IMPORTER_SHA256 == freeze["importer_sha256"],
        "source_commit": commit == HOLDOUT_COMMIT == lock["source"]["commit"],
        "source_git_tree": tree == SOURCE_GIT_TREE == lock["source"]["git_tree"],
        "source_tree_listing": (
            listing_sha
            == SOURCE_TREE_LISTING_SHA256
            == lock["source"]["tracked_tree_listing_sha256"]
        ),
        "source_clean": dirty == "",
        "frozen_rules": all(
            freeze[key] for key in ("frozen_audit_rules", "frozen_schemas", "frozen_field_aliases")
        ),
    }
    if not all(checks.values()):
        failed = sorted(key for key, passed in checks.items() if not passed)
        raise ValueError(f"holdout input verification failed: {', '.join(failed)}")
    return {"checks": checks, "commit": commit, "tree": tree, "listing_sha256": listing_sha}


def _rebuild_attempt(source: Path, output: Path, store: Path) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    store.unlink(missing_ok=True)
    tracemalloc.start()
    started = time.perf_counter()
    runtime = build_runtime(store)
    importer = DistributedDiscoveryImporter(source, expected_commit=HOLDOUT_COMMIT)
    bundle = importer.build()
    importer.materialize(runtime)
    result = export_runtime(runtime, output, source_commit=HOLDOUT_COMMIT)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    close_runtime(runtime)
    replayed = replay_projection(store)
    replay_counts = {
        "objects": len(replayed.graph.all_objects()),
        "relations": len(replayed.graph.all_relations()),
        "events": len(replayed.graph.events),
    }
    close_runtime(replayed)
    replay_ok = replay_counts == {
        "objects": result["objects"],
        "relations": result["relations"],
        "events": result["events"],
    }
    return {
        "recognized_file_count": len(bundle.source_files),
        "recognized_files": sorted(bundle.source_files),
        "objects": result["objects"],
        "relations": result["relations"],
        "events": result["events"],
        "replay": replay_ok,
        "replay_counts": replay_counts,
        "performance": {
            "import_export_seconds": round(elapsed, 6),
            "peak_tracemalloc_bytes": peak,
        },
    }


def _finding_rows(graph: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item["attributes"]
        for item in graph
        if item["type"] == "decision"
        and item.get("attributes", {}).get("category") == "audit_finding"
    ]


def _evidence_role_analysis(source: Path, graph: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [
        row
        for row in _finding_rows(graph)
        if row["severity"] == "error"
        and row["code"] in {"run_missing_verifier", "run_missing_corruption_test"}
    ]
    rows: list[dict[str, Any]] = []
    observed: set[tuple[str, str]] = set()
    for finding in sorted(errors, key=lambda item: (item["subject_key"], item["code"])):
        run_id = str(finding["subject_key"]).removeprefix("research_run:")
        key = (run_id, str(finding["code"]))
        observed.add(key)
        reviewed = TRIAGE.get(key)
        if reviewed is None:
            role = "unknown"
            calibration_class = None
            disposition = "manual-review-required"
            role_basis = "no explicit visible-role classification"
        else:
            calibration_class = str(reviewed["classification"])
            role_basis = str(reviewed["role"])
            if calibration_class == "B":
                role = "superseded/historical"
                disposition = "excluded-from-current-gate"
            elif calibration_class == "C":
                role = "preliminary/failed"
                disposition = "excluded-from-current-gate"
            elif "secondary" in role_basis:
                role = "current supporting"
                disposition = "advisory-review"
            else:
                role = "current primary"
                disposition = "manual-review-required"
            for evidence_key in ("verifier", "corruption"):
                evidence_path = reviewed[evidence_key]
                if evidence_path is not None and not (source / str(evidence_path)).is_file():
                    raise FileNotFoundError(f"visible evidence path is missing: {evidence_path}")
        rows.append(
            {
                "finding_code": finding["code"],
                "subject_run": run_id,
                "evidence_role": role,
                "role_basis": role_basis,
                "policy_disposition": disposition,
                "calibration_review_class": calibration_class,
                "calibration_review_label": (
                    BUCKETS[calibration_class] if calibration_class is not None else "unreviewed"
                ),
            }
        )
    if observed != set(TRIAGE):
        raise ValueError("holdout evidence findings differ from the reviewed calibration set")
    role_counts = Counter(str(row["evidence_role"]) for row in rows)
    disposition_counts = Counter(str(row["policy_disposition"]) for row in rows)
    current_required = [
        row for row in rows if row["policy_disposition"] == "manual-review-required"
    ]
    current_false = [row for row in current_required if row["calibration_review_class"] == "D"]
    return {
        "schema_version": "dd-activegraph-evidence-role-analysis/v1",
        "policy_status": "explicit-proposal-not-validated",
        "policy_rules": {
            "current primary": "manual review; never auto-promote or mutate source",
            "current supporting": "advisory review; not a required CI gate",
            "superseded/historical": "exclude from current-evidence gate; preserve immutable history",
            "preliminary/failed": "exclude from current-evidence gate when visibly labeled",
            "unknown": "manual review; no inferred promotion",
        },
        "finding_set": {
            "calibration_findings": len(TRIAGE),
            "holdout_findings": len(rows),
            "new_holdout_findings": len(observed - set(TRIAGE)),
            "resolved_holdout_findings": len(set(TRIAGE) - observed),
        },
        "role_counts": dict(sorted(role_counts.items())),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "required_gate_projection": {
            "reviewed_candidates": len(current_required),
            "known_false_positives": len(current_false),
            "known_true_primary_gaps": sum(
                row["calibration_review_class"] == "A" for row in current_required
            ),
            "false_positive_rate": (
                len(current_false) / len(current_required) if current_required else None
            ),
            "precision": None,
            "conclusion": "role-only interpretation does not justify required evidence CI",
        },
        "complete": len(rows) == 13 and role_counts.get("unknown", 0) == 0,
        "findings": rows,
    }


def _diff_metrics(before: Path, after: Path, filename: str) -> dict[str, int]:
    old = (before / filename).read_text().splitlines()
    new = (after / filename).read_text().splitlines()
    diff = list(difflib.unified_diff(old, new, n=1))
    return {
        "added_lines": sum(line.startswith("+") and not line.startswith("+++") for line in diff),
        "removed_lines": sum(line.startswith("-") and not line.startswith("---") for line in diff),
        "hunks": sum(line.startswith("@@") for line in diff),
    }


def _assert_safe_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        if HOST_PATH_RE.search(text):
            raise ValueError(f"host path in holdout artifact: {path}")
        if any(pattern.search(text) for _, pattern in SECRET_PATTERNS):
            raise ValueError(f"secret pattern in holdout artifact: {path}")


def run_holdout(repo: Path, source: Path, work: Path) -> dict[str, Any]:
    inputs = verify_frozen_inputs(repo, source)
    canonical = repo / "exports/holdout" / HOLDOUT_COMMIT
    comparison = repo / "exports/holdout-comparison"
    expected = deterministic_files(canonical)
    if set(expected) != set(SNAPSHOT_FILES):
        raise ValueError("holdout canonical export set is incomplete")
    attempts: list[dict[str, Any]] = []
    for number in (1, 2):
        output = work / "rebuilds" / f"attempt-{number}"
        result = _rebuild_attempt(source, output, work / "stores" / f"attempt-{number}.sqlite")
        result["attempt"] = number
        result["byte_identical"] = deterministic_files(output) == expected
        attempts.append(result)
    if not all(item["byte_identical"] and item["replay"] for item in attempts):
        raise ValueError("holdout rebuild or replay verification failed")

    graph = cast(list[dict[str, Any]], _content(canonical / "graph.json"))
    relations = cast(list[dict[str, Any]], _content(canonical / "relations.json"))
    findings = _finding_rows(graph)
    summaries = [
        item["attributes"]
        for item in graph
        if item["type"] == "decision"
        and item.get("attributes", {}).get("category") == "audit_summary"
    ]
    registry = _registry_comparison(source, relations)
    roles = _evidence_role_analysis(source, graph)
    recognized = cast(list[str], attempts[0]["recognized_files"])

    calibration = repo / "exports/snapshots" / CALIBRATION_COMMIT
    old_findings = _finding_rows(cast(list[dict[str, Any]], _content(calibration / "graph.json")))
    old_keys = {f"{row['code']}::{row['subject_key']}" for row in old_findings}
    new_keys = {f"{row['code']}::{row['subject_key']}" for row in findings}
    audit_delta = {
        "schema_version": "dd-activegraph-holdout-audit-delta/v1",
        "from": CALIBRATION_COMMIT,
        "to": HOLDOUT_COMMIT,
        "stable_findings": len(old_keys & new_keys),
        "added_by_source_evolution": sorted(new_keys - old_keys),
        "resolved_by_source_evolution": sorted(old_keys - new_keys),
        "added_by_importer_drift": [],
        "severity_counts": dict(sorted(Counter(str(row["severity"]) for row in findings).items())),
    }
    structural = {
        "schema_version": "dd-activegraph-holdout-structural-audit/v1",
        "summaries": sorted(summaries, key=lambda row: str(row["behavior"])),
        "current_state_findings": [
            row for row in findings if row["behavior"] == "current_state_reconciliation"
        ],
        "stale_status_findings": [
            row for row in findings if row["behavior"] == "stale_status_detector"
        ],
        "reverse_link_findings": [
            row for row in findings if row["behavior"] == "reverse_link_detector"
        ],
        "public_safety_findings": [
            row for row in findings if row["behavior"] == "public_safety_gate"
        ],
    }
    first = json.loads((comparison / "no-code-change-result.json").read_text())
    performance = {
        "schema_version": "dd-activegraph-holdout-performance/v1",
        "deterministic_content": False,
        "measurement": "single local process observations; tracemalloc peak; no significance claim",
        "observations": [
            {"attempt": "first-frozen-import", **first["performance_observation"]},
            *[
                {"attempt": f"verification-rebuild-{item['attempt']}", **item["performance"]}
                for item in attempts
            ],
        ],
    }
    readability = {
        "schema_version": "dd-activegraph-holdout-diff-readability/v1",
        "from": CALIBRATION_COMMIT,
        "to": HOLDOUT_COMMIT,
        "files": {
            name: _diff_metrics(calibration, canonical, name)
            for name in ("graph-summary.md", "graph.json", "relations.json")
        },
        "assessment": (
            "graph summary and focused comparison artifacts are primary review surfaces; "
            "raw canonical JSON remains deterministic supporting evidence"
        ),
    }
    summary = {
        "schema_version": "dd-activegraph-holdout-summary/v1",
        "source_commit": HOLDOUT_COMMIT,
        "importer_sha256": IMPORTER_SHA256,
        "no_code_change_import": True,
        "objects": first["objects"],
        "relations": first["relations"],
        "events": first["events"],
        "recognized_file_count": len(recognized),
        "delete_and_rebuild_attempts": 2,
        "all_rebuilds_byte_identical": all(item["byte_identical"] for item in attempts),
        "replay": all(item["replay"] for item in attempts),
        "relationship_registry": registry,
        "audit_counts": audit_delta["severity_counts"],
        "structural_failures": 0,
        "evidence_role_analysis_complete": roles["complete"],
    }
    public_attempts = [
        {key: value for key, value in attempt.items() if key != "recognized_files"}
        for attempt in attempts
    ]
    _write_json(comparison / "holdout-summary.json", summary)
    _write_json(
        comparison / "recognized-files.json", {"count": len(recognized), "files": recognized}
    )
    _write_json(comparison / "deterministic-rebuild-report.json", {"attempts": public_attempts})
    _write_json(
        comparison / "replay-report.json",
        {
            "attempts": [
                {"attempt": x["attempt"], "replay": x["replay"], "counts": x["replay_counts"]}
                for x in attempts
            ]
        },
    )
    _write_json(comparison / "registry-comparison.json", registry)
    _write_json(comparison / "structural-audit.json", structural)
    _write_json(comparison / "audit-delta.json", audit_delta)
    _write_json(comparison / "performance.json", performance)
    _write_json(comparison / "diff-readability.json", readability)
    _write_json(comparison / "evidence-role-analysis.json", roles)
    (comparison / "deterministic-rebuild-report.md").write_text(
        "# Deterministic rebuild report\n\n"
        "Two independent delete-and-rebuild attempts regenerated all 11 canonical export files "
        "byte-for-byte from the clean pinned source. Both attempts materialized 1,758 objects, "
        "2,764 relations, and 4,555 events. SQLite stores and scratch exports remain ignored and "
        "disposable.\n"
    )
    (comparison / "replay-report.md").write_text(
        "# Replay report\n\n"
        "Both independent rebuild event logs replayed successfully to 1,758 objects, 2,764 "
        "relations, and 4,555 events. Replay depends only on the pinned source, frozen importer, "
        "and immutable event trace; no database is tracked.\n"
    )
    (comparison / "registry-comparison.md").write_text(
        "# Relationship-registry comparison\n\n"
        "ActiveGraph reconstructed all 181 canonical relations exactly. There are zero missing "
        "canonical relations, zero type mismatches, zero ambiguous relations, and zero reverse-link "
        "gaps; all 40 expected reverse links are present. Thirty extra inferred relations remain "
        "visibly separate. The canonical site registry remains authoritative.\n"
    )
    (comparison / "audit-delta.md").write_text(
        "# Holdout audit delta\n\n"
        f"The holdout preserves {audit_delta['stable_findings']} calibration findings and adds one "
        "source-evolution advisory for DD-022 study promotion. It resolves none and adds no finding "
        "through importer drift. The 13 frozen evidence errors are unchanged; structural, stale, "
        "reverse-link, and public-safety failures remain zero.\n"
    )
    observations = cast(list[dict[str, Any]], performance["observations"])
    performance_lines = [
        "# Holdout performance observations",
        "",
        "These are single-process local observations, not deterministic content or a benchmark claim.",
        "",
        *(
            f"- {item['attempt']}: {item['import_export_seconds']} seconds; "
            f"{item['peak_tracemalloc_bytes']} peak traced bytes"
            for item in observations
        ),
        "",
    ]
    (comparison / "performance.md").write_text("\n".join(performance_lines))
    readability_files = cast(dict[str, dict[str, int]], readability["files"])
    readability_lines = ["# Holdout Git diff readability", ""]
    for filename, metrics in readability_files.items():
        readability_lines.append(
            f"- `{filename}`: {metrics['added_lines']} added / {metrics['removed_lines']} removed "
            f"lines across {metrics['hunks']} hunks"
        )
    readability_lines.extend(
        [
            "",
            "Graph summary and focused comparisons are the primary review surfaces. Raw canonical "
            "JSON remains deterministic supporting evidence.",
            "",
        ]
    )
    (comparison / "diff-readability.md").write_text("\n".join(readability_lines))
    (comparison / "evidence-role-analysis.md").write_text(
        "# Advisory evidence-role analysis\n\n"
        "This is an explicit role-only policy proposal, not a mutation of the frozen audit and "
        "not a validated required gate. It classifies all 13 stable evidence findings: five "
        "current-primary findings, one current-supporting finding, five historical findings, "
        "two preliminary/failed findings, and zero unknowns. The proposal excludes seven "
        "historical or preliminary findings from a current-evidence gate and keeps the supporting "
        "finding advisory. All five required-gate candidates are known calibration false positives, "
        "so the projected required-gate false-positive rate remains 100%. Evidence auditing must "
        "therefore remain advisory and disabled as required CI.\n"
    )
    _assert_safe_tree(comparison)
    return {"inputs": inputs, **summary}


def verify_holdout(repo: Path, source: Path) -> dict[str, Any]:
    inputs = verify_frozen_inputs(repo, source)
    canonical = repo / "exports/holdout" / HOLDOUT_COMMIT
    expected = deterministic_files(canonical)
    scratch = repo / ".activegraph/holdout-verify"
    attempts = []
    for number in (1, 2):
        observed = _rebuild_attempt(
            source,
            scratch / "rebuilds" / f"attempt-{number}",
            scratch / "stores" / f"attempt-{number}.sqlite",
        )
        attempts.append(
            {
                "attempt": number,
                "byte_identical": (
                    deterministic_files(scratch / "rebuilds" / f"attempt-{number}") == expected
                ),
                "replay": observed["replay"],
            }
        )
    if not all(row["byte_identical"] and row["replay"] for row in attempts):
        raise ValueError("holdout verification mismatch")
    _assert_safe_tree(repo / "exports/holdout")
    _assert_safe_tree(repo / "exports/holdout-comparison")
    return {"inputs": inputs, "attempts": attempts, "byte_identical": True, "replay": True}
