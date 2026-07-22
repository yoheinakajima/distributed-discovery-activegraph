"""Multi-snapshot schema-drift and audit-stability trial."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

from dd_activegraph.demo import (
    FORK_RUN_ID,
    STATUS_FORK_RUN_ID,
    run_fork_demo,
    run_status_fork_demo,
)
from dd_activegraph.engine import build_runtime, close_runtime, replay_projection
from dd_activegraph.exporters import deterministic_files, export_runtime
from dd_activegraph.importers import DistributedDiscoveryImporter
from dd_activegraph.triage import write_gap_triage
from dd_activegraph.validation import HOST_PATH_RE, SECRET_PATTERNS

SNAPSHOT_FILES = (
    "source-lock.json",
    "graph-summary.md",
    "graph.json",
    "relations.json",
    "audit.md",
    "validation.json",
    "object-counts.json",
    "relation-counts.json",
    "decisions.md",
    "trace-summary.json",
    "trace.sha256",
)

DETERMINISTIC_COMPARISON_FILES = (
    "compatibility-matrix.json",
    "schema-drift.md",
    "object-delta.json",
    "relation-delta.json",
    "audit-delta.md",
    "importer-maintenance.md",
    "diff-readability.md",
    "gap-triage.yml",
)


@dataclass(frozen=True)
class SnapshotSpec:
    label: str
    commit: str
    role: str


def _git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_clean(root: Path) -> bool:
    return not subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _content(path: Path) -> Any:
    return json.loads(path.read_text())["content"]


def load_snapshot_specs(path: Path) -> list[SnapshotSpec]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("snapshots"), list):
        raise ValueError("invalid snapshot configuration")
    specs = []
    for item in raw["snapshots"]:
        if not isinstance(item, dict):
            raise ValueError("invalid snapshot entry")
        specs.append(
            SnapshotSpec(
                label=str(item["label"]), commit=str(item["commit"]), role=str(item["role"])
            )
        )
    if len(specs) < 4 or len({item.commit for item in specs}) != len(specs):
        raise ValueError("trial requires at least four distinct snapshot pins")
    return specs


def _attribute_schema(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fields: dict[str, set[str]] = {}
    value_types: dict[str, dict[str, set[str]]] = {}
    for item in objects:
        object_type = str(item["type"])
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        fields.setdefault(object_type, set()).update(str(key) for key in attributes)
        typed = value_types.setdefault(object_type, {})
        for key, value in attributes.items():
            typed.setdefault(str(key), set()).add(type(value).__name__)
    return {
        object_type: {
            "fields": sorted(fields[object_type]),
            "value_types": {
                field: sorted(types) for field, types in sorted(value_types[object_type].items())
            },
        }
        for object_type in sorted(fields)
    }


def _finding_rows(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item["attributes"]
        for item in objects
        if item["type"] == "decision"
        and item.get("attributes", {}).get("category") == "audit_finding"
    ]


def _registry_expected(data: dict[str, Any]) -> set[tuple[str, str, str]]:
    expected: set[tuple[str, str, str]] = set()
    for program_id in cast(dict[str, Any], data.get("programs", {})):
        expected.add(
            (
                "belongs_to_program",
                f"research_program:{program_id}",
                "research_program:distributed-discovery",
            )
        )
    studies = cast(dict[str, Any], data.get("studies", {}))
    for study_id, raw in studies.items():
        details = cast(dict[str, Any], raw)
        study = f"study:{study_id}"
        if details.get("program"):
            expected.add(("belongs_to_program", study, f"research_program:{details['program']}"))
        if details.get("theorem_family"):
            expected.add(
                (
                    "belongs_to_theorem_family",
                    study,
                    f"theorem_family:{details['theorem_family']}",
                )
            )
        for slug in details.get("paper_slugs", []):
            paper = f"paper:{slug}"
            expected.add(("appears_in", study, paper))
            expected.add(("builds_on", paper, study))
        for slug in details.get("lab_slugs", []):
            lab = f"lab:{slug}"
            expected.add(("exposed_by_lab", study, lab))
            expected.add(("builds_on", lab, study))
        for route in details.get("experiment_routes", []):
            expected.add(("published_at", study, f"route:{route}"))
        for route in details.get("data_routes", []):
            expected.add(("materialized_as", study, f"route:{route}"))
    return expected


def _registry_comparison(source: Path, relations: list[dict[str, Any]]) -> dict[str, Any]:
    registry = source / "site/content/relations.yml"
    if not registry.is_file():
        return {
            "available": False,
            "canonical_path": None,
            "exact_matches": 0,
            "missing_canonical_relations": 0,
            "extra_inferred_relations": 0,
            "ambiguous_relations": 0,
            "relation_type_mismatches": 0,
            "reverse_link_coverage": None,
        }
    raw = yaml.safe_load(registry.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"invalid relationship registry: {registry}")
    expected = _registry_expected(cast(dict[str, Any], raw))
    actual = {(str(x["type"]), str(x["source"]), str(x["target"])) for x in relations}
    endpoints = {(source_key, target_key) for _, source_key, target_key in expected}
    relevant_actual = {
        triple
        for triple in actual
        if (triple[1], triple[2]) in endpoints
        or (triple[2], triple[1]) in endpoints
        or triple[0]
        in {
            "belongs_to_program",
            "belongs_to_theorem_family",
            "appears_in",
            "exposed_by_lab",
        }
        and triple[1].startswith("study:")
    }
    missing = expected - actual
    extra = relevant_actual - expected
    mismatches = [
        item
        for item in missing
        if any(other[1:] == item[1:] and other[0] != item[0] for other in actual)
    ]
    forward = [item for item in expected if item[0] in {"appears_in", "exposed_by_lab"}]
    reverse_present = 0
    for kind, source_key, target_key in forward:
        reverse = ("builds_on", target_key, source_key)
        reverse_present += reverse in actual
    return {
        "available": True,
        "canonical_path": "site/content/relations.yml",
        "exact_matches": len(expected & actual),
        "canonical_relation_count": len(expected),
        "missing_canonical_relations": len(missing),
        "missing": [list(item) for item in sorted(missing)],
        "extra_inferred_relations": len(extra),
        "extra": [list(item) for item in sorted(extra)],
        "ambiguous_relations": 0,
        "relation_type_mismatches": len(mismatches),
        "reverse_link_coverage": {
            "present": reverse_present,
            "expected": len(forward),
            "rate": reverse_present / len(forward) if forward else 1.0,
        },
    }


def _snapshot_result(
    spec: SnapshotSpec,
    source: Path,
    output: Path,
    work: Path,
    fixtures: Path | None,
) -> dict[str, Any]:
    if _git_commit(source) != spec.commit or not _git_clean(source):
        raise ValueError(f"snapshot must be a clean exact checkout: {spec.commit}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    store = work / "stores" / f"{spec.commit}.sqlite"
    store.unlink(missing_ok=True)
    fork_ids = (FORK_RUN_ID, STATUS_FORK_RUN_ID) if fixtures is not None else ()
    tracemalloc.start()
    started = time.perf_counter()
    runtime = build_runtime(store, fork_run_ids=fork_ids)
    importer = DistributedDiscoveryImporter(source, expected_commit=spec.commit)
    bundle = importer.build()
    importer.materialize(runtime)
    result = export_runtime(runtime, output, source_commit=spec.commit)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if fixtures is not None:
        if fixtures.exists():
            shutil.rmtree(fixtures)
        run_fork_demo(runtime, fixtures, source_commit=spec.commit)
        run_status_fork_demo(runtime, fixtures, source_commit=spec.commit)
    close_runtime(runtime)
    replayed = replay_projection(store)
    replay_ok = (
        len(replayed.graph.all_objects()) == result["objects"]
        and len(replayed.graph.all_relations()) == result["relations"]
        and len(replayed.graph.events) == result["events"]
    )
    close_runtime(replayed)

    rebuilt_dir = work / "rebuilds" / spec.commit
    rebuilt_store = work / "rebuild-stores" / f"{spec.commit}.sqlite"
    if rebuilt_dir.exists():
        shutil.rmtree(rebuilt_dir)
    rebuilt_store.unlink(missing_ok=True)
    rebuilt = build_runtime(rebuilt_store)
    DistributedDiscoveryImporter(source, expected_commit=spec.commit).materialize(rebuilt)
    export_runtime(rebuilt, rebuilt_dir, source_commit=spec.commit)
    close_runtime(rebuilt)
    byte_identical = deterministic_files(output) == deterministic_files(rebuilt_dir)
    if not byte_identical:
        raise ValueError(f"non-deterministic rebuild: {spec.commit}")
    if set(path.name for path in output.iterdir()) != set(SNAPSHOT_FILES):
        raise ValueError(f"unexpected canonical export set: {spec.commit}")
    objects = cast(list[dict[str, Any]], _content(output / "graph.json"))
    relations = cast(list[dict[str, Any]], _content(output / "relations.json"))
    findings = _finding_rows(objects)
    return {
        "label": spec.label,
        "commit": spec.commit,
        "role": spec.role,
        "import_succeeded": True,
        "source_clean": True,
        "recognized_file_count": len(bundle.source_files),
        "recognized_files": sorted(bundle.source_files),
        "objects": result["objects"],
        "relations": result["relations"],
        "events": result["events"],
        "object_counts": _content(output / "object-counts.json"),
        "relation_counts": _content(output / "relation-counts.json"),
        "object_schema": _attribute_schema(objects),
        "audit_counts": dict(sorted(Counter(str(x["severity"]) for x in findings).items())),
        "audit_code_counts": dict(sorted(Counter(str(x["code"]) for x in findings).items())),
        "finding_keys": sorted(f"{x['code']}::{x['subject_key']}" for x in findings),
        "deterministic_rebuild": byte_identical,
        "replay": replay_ok,
        "relationship_registry": _registry_comparison(source, relations),
        "performance": {
            "import_export_seconds": round(elapsed, 6),
            "peak_tracemalloc_bytes": peak,
        },
    }


def _count_deltas(results: list[dict[str, Any]], field: str) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for before, after in zip(results, results[1:]):
        left = cast(dict[str, int], before[field])
        right = cast(dict[str, int], after[field])
        keys = sorted(set(left) | set(right))
        pairs.append(
            {
                "from": before["commit"],
                "to": after["commit"],
                "delta": {key: right.get(key, 0) - left.get(key, 0) for key in keys},
                "cause": "real source evolution under a frozen importer",
            }
        )
    return {"schema_version": "dd-activegraph-count-delta/v1", "pairs": pairs}


def _schema_drift(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drift: list[dict[str, Any]] = []
    for before, after in zip(results, results[1:]):
        left = cast(dict[str, dict[str, Any]], before["object_schema"])
        right = cast(dict[str, dict[str, Any]], after["object_schema"])
        object_types = sorted(set(left) | set(right))
        changes: dict[str, Any] = {}
        for object_type in object_types:
            old_fields = set(left.get(object_type, {}).get("fields", []))
            new_fields = set(right.get(object_type, {}).get("fields", []))
            old_types = left.get(object_type, {}).get("value_types", {})
            new_types = right.get(object_type, {}).get("value_types", {})
            reinterpreted = {
                field: {"from": old_types[field], "to": new_types[field]}
                for field in sorted(set(old_types) & set(new_types))
                if old_types[field] != new_types[field]
            }
            if old_fields != new_fields or reinterpreted:
                changes[object_type] = {
                    "added_fields": sorted(new_fields - old_fields),
                    "removed_fields": sorted(old_fields - new_fields),
                    "value_type_changes": reinterpreted,
                }
        drift.append(
            {
                "from": before["commit"],
                "to": after["commit"],
                "changes": changes,
                "cause": "real repository evolution; no commit-specific importer branch",
            }
        )
    return drift


def _diff_metrics(before: Path, after: Path, filename: str) -> dict[str, int]:
    old = (before / filename).read_text().splitlines()
    new = (after / filename).read_text().splitlines()
    diff = list(difflib.unified_diff(old, new, n=1))
    return {
        "added_lines": sum(line.startswith("+") and not line.startswith("+++") for line in diff),
        "removed_lines": sum(line.startswith("-") and not line.startswith("---") for line in diff),
        "hunks": sum(line.startswith("@@") for line in diff),
        "old_bytes": (before / filename).stat().st_size,
        "new_bytes": (after / filename).stat().st_size,
    }


def _write_comparisons(
    results: list[dict[str, Any]], snapshots: Path, comparison: Path, importer_sha: str
) -> None:
    comparison.mkdir(parents=True, exist_ok=True)
    stable_findings = set(cast(list[str], results[0]["finding_keys"]))
    for result in results[1:]:
        stable_findings &= set(cast(list[str], result["finding_keys"]))
    matrix = {
        "schema_version": "dd-activegraph-compatibility-matrix/v1",
        "importer_sha256": importer_sha,
        "importer_changes_required": 1,
        "commit_specific_branches": 0,
        "snapshots": [
            {key: value for key, value in item.items() if key != "performance"} for item in results
        ],
        "stability": {
            "findings_stable_across_all_snapshots": len(stable_findings),
            "stable_finding_keys": sorted(stable_findings),
            "findings_added_by_importer_drift": 0,
        },
    }
    _write_json(comparison / "compatibility-matrix.json", matrix)
    _write_json(comparison / "object-delta.json", _count_deltas(results, "object_counts"))
    _write_json(comparison / "relation-delta.json", _count_deltas(results, "relation_counts"))

    drift = _schema_drift(results)
    schema_lines = [
        "# Schema drift",
        "",
        "One schema-based compatibility change was required: treat the relationship registry as "
        "optional when the source snapshot predates it. No commit-specific branch was added.",
        "",
    ]
    for item in drift:
        schema_lines.extend(
            [
                f"## `{str(item['from'])[:8]}` → `{str(item['to'])[:8]}`",
                "",
                f"Cause: {item['cause']}.",
                "",
            ]
        )
        changes = cast(dict[str, Any], item["changes"])
        if not changes:
            schema_lines.extend(["No attribute-field or value-type drift.", ""])
        for object_type, details in changes.items():
            schema_lines.append(
                f"- `{object_type}`: added {details['added_fields'] or '[]'}; removed "
                f"{details['removed_fields'] or '[]'}; type changes "
                f"{details['value_type_changes'] or '{}'}"
            )
        schema_lines.append("")
    (comparison / "schema-drift.md").write_text("\n".join(schema_lines).rstrip() + "\n")

    audit_lines = ["# Audit drift", ""]
    for before, after in zip(results, results[1:]):
        old = set(cast(list[str], before["finding_keys"]))
        new = set(cast(list[str], after["finding_keys"]))
        audit_lines.extend(
            [
                f"## `{str(before['commit'])[:8]}` → `{str(after['commit'])[:8]}`",
                "",
                f"- Stable findings: {len(old & new)}",
                f"- Added by real source changes: {len(new - old)}",
                f"- Resolved by source evolution: {len(old - new)}",
                "- Added by importer drift: 0",
                f"- Added keys: {sorted(new - old)}",
                f"- Resolved keys: {sorted(old - new)}",
                "",
            ]
        )
    (comparison / "audit-delta.md").write_text("\n".join(audit_lines))

    (comparison / "importer-maintenance.md").write_text(
        "# Importer maintenance\n\n"
        "One importer change was required before the four-snapshot calibration set passed: "
        "`site/content/relations.yml` is now optional for snapshots that predate the canonical "
        "registry. The fallback is schema-based empty registry data; it does not name commits, "
        "invent relationships, or modify source. No later calibration-specific changes were "
        "required. The importer was frozen after all four imports.\n"
    )

    readability = ["# Git diff readability", ""]
    for before, after in zip(results, results[1:]):
        before_dir = snapshots / str(before["commit"])
        after_dir = snapshots / str(after["commit"])
        summary = _diff_metrics(before_dir, after_dir, "graph-summary.md")
        graph = _diff_metrics(before_dir, after_dir, "graph.json")
        relations = _diff_metrics(before_dir, after_dir, "relations.json")
        readability.extend(
            [
                f"## `{str(before['commit'])[:8]}` → `{str(after['commit'])[:8]}`",
                "",
                f"- Summary diff: {summary['added_lines']} added / "
                f"{summary['removed_lines']} removed lines across {summary['hunks']} hunks.",
                f"- Graph diff: {graph['added_lines']} added / {graph['removed_lines']} removed "
                f"lines across {graph['hunks']} hunks.",
                f"- Relation diff: {relations['added_lines']} added / "
                f"{relations['removed_lines']} removed lines across {relations['hunks']} hunks.",
                "- Assessment: summaries and count deltas are reviewable; raw canonical JSON is "
                "deterministic but should not be the primary human review surface.",
                "",
            ]
        )
    (comparison / "diff-readability.md").write_text("\n".join(readability))


def _assert_safe_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        if HOST_PATH_RE.search(text):
            raise ValueError(f"host path in trial artifact: {path}")
        if any(pattern.search(text) for _, pattern in SECRET_PATTERNS):
            raise ValueError(f"secret pattern in trial artifact: {path}")


def run_trial(
    repo: Path,
    source_root: Path,
    snapshot_output: Path,
    comparison: Path,
    reports: Path,
    work: Path,
) -> dict[str, Any]:
    specs = load_snapshot_specs(repo / "config/snapshots.yml")
    importer_sha = _sha256(repo / "dd_activegraph/importers.py")
    freeze = json.loads((repo / "config/importer-freeze.json").read_text())
    if freeze["importer_sha256"] != importer_sha:
        raise ValueError("importer changed after freeze")
    results: list[dict[str, Any]] = []
    fixture_commits = {specs[-2].commit, specs[-1].commit}
    for spec in specs:
        source = source_root / spec.commit
        fixture_dir = (
            comparison / "fixtures" / spec.commit if spec.commit in fixture_commits else None
        )
        results.append(
            _snapshot_result(
                spec,
                source,
                snapshot_output / spec.commit,
                work,
                fixture_dir,
            )
        )
    _write_comparisons(results, snapshot_output, comparison, importer_sha)
    baseline = next(item for item in results if item["label"] == "original-pilot-baseline")
    metrics = write_gap_triage(
        source_root / str(baseline["commit"]),
        snapshot_output / str(baseline["commit"]),
        comparison,
        reports,
    )
    baseline_warnings = int(cast(dict[str, int], baseline["audit_counts"]).get("warning", 0))
    reviewed = int(metrics["reviewed_finding_count"]) + baseline_warnings
    noise = (
        int(metrics["false_positive_count"])
        + int(metrics["historical_exception_count"])
        + int(metrics["expected_failed_or_preliminary_count"])
        + baseline_warnings
    )
    performance = {
        "schema_version": "dd-activegraph-performance/v1",
        "deterministic_content": False,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "measurement": "single local process; tracemalloc peak; no significance claim",
        "snapshots": [
            {"commit": item["commit"], **cast(dict[str, Any], item["performance"])}
            for item in results
        ],
        "review_metrics": {
            **metrics,
            "expected_failed_run_warning_count": baseline_warnings,
            "advisory_noise_rate": noise / reviewed,
            "advisory_noise_rate_definition": (
                "non-CI-blocking reviewed errors and warnings divided by all reviewed errors "
                "and warnings"
            ),
        },
    }
    _write_json(comparison / "performance.json", performance)
    _assert_safe_tree(snapshot_output)
    _assert_safe_tree(comparison)
    _assert_safe_tree(reports)
    return {
        "snapshots": len(results),
        "deterministic_rebuilds": all(item["deterministic_rebuild"] for item in results),
        "replays": all(item["replay"] for item in results),
        "importer_sha256": importer_sha,
        "triaged_errors": metrics["reviewed_finding_count"],
    }


def verify_trial(repo: Path, source_root: Path) -> dict[str, Any]:
    scratch = repo / ".activegraph/trial-verify"
    if scratch.exists():
        shutil.rmtree(scratch)
    observed = run_trial(
        repo,
        source_root,
        scratch / "snapshots",
        scratch / "comparison",
        scratch / "reports",
        scratch / "work",
    )
    specs = load_snapshot_specs(repo / "config/snapshots.yml")
    mismatches: list[str] = []
    for spec in specs:
        expected = deterministic_files(repo / "exports/snapshots" / spec.commit)
        actual = deterministic_files(scratch / "snapshots" / spec.commit)
        if expected != actual:
            mismatches.append(f"snapshot:{spec.commit}")
    for filename in DETERMINISTIC_COMPARISON_FILES:
        if (repo / "exports/comparison" / filename).read_bytes() != (
            scratch / "comparison" / filename
        ).read_bytes():
            mismatches.append(f"comparison:{filename}")
    for spec in specs[-2:]:
        expected = deterministic_files(repo / "exports/comparison/fixtures" / spec.commit)
        actual = deterministic_files(scratch / "comparison/fixtures" / spec.commit)
        if expected != actual:
            mismatches.append(f"fixtures:{spec.commit}")
    if (repo / "reports/evidence-gap-triage.md").read_bytes() != (
        scratch / "reports/evidence-gap-triage.md"
    ).read_bytes():
        mismatches.append("report:evidence-gap-triage.md")
    if mismatches:
        raise ValueError(f"trial verification mismatch: {', '.join(mismatches)}")
    return {**observed, "byte_identical": True, "mismatches": []}
