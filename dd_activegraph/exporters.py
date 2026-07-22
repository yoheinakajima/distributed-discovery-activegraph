"""Canonical Git-visible exports for the disposable ActiveGraph projection."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from activegraph import Runtime

from dd_activegraph.ontology import (
    SOURCE_COMMIT,
    canonical_json,
    export_metadata,
    sha256_text,
    stable_relation_id,
)
from dd_activegraph.validation import HOST_PATH_RE, SECRET_PATTERNS


def _envelope(content: Any, source_commit: str) -> dict[str, Any]:
    return {
        "metadata": export_metadata(source_commit),
        "canonical_content_sha256": sha256_text(canonical_json(content)),
        "content": content,
    }


def _write_json(path: Path, content: Any, source_commit: str) -> None:
    path.write_text(json.dumps(_envelope(content, source_commit), indent=2, sort_keys=True) + "\n")


def projection(runtime: Runtime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = sorted(
        ({"type": obj.type, **obj.data} for obj in runtime.graph.all_objects()),
        key=lambda item: (item["type"], item["key"]),
    )
    keys = {obj.id: str(obj.data["key"]) for obj in runtime.graph.all_objects()}
    relations = []
    for relation in runtime.graph.all_relations():
        source = keys[relation.source]
        target = keys[relation.target]
        relations.append(
            {
                "id": stable_relation_id(relation.type, source, target, relation.data),
                "type": relation.type,
                "source": source,
                "target": target,
                "data": relation.data,
            }
        )
    return objects, sorted(relations, key=lambda item: item["id"])


def audit_records(
    objects: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = [item for item in objects if item["type"] == "decision"]
    findings = [
        item for item in decisions if item.get("attributes", {}).get("category") == "audit_finding"
    ]
    summaries = [
        item for item in decisions if item.get("attributes", {}).get("category") == "audit_summary"
    ]
    return findings, summaries


def trace_projection(runtime: Runtime) -> list[dict[str, Any]]:
    return [
        {"sequence": index, "type": event.type, "actor": event.actor, "payload": event.payload}
        for index, event in enumerate(runtime.graph.events, start=1)
    ]


def export_runtime(
    runtime: Runtime, output: Path, *, source_commit: str = SOURCE_COMMIT
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    objects, relations = projection(runtime)
    findings, summaries = audit_records(objects)
    object_counts = dict(sorted(Counter(item["type"] for item in objects).items()))
    relation_counts = dict(sorted(Counter(item["type"] for item in relations).items()))
    trace = trace_projection(runtime)
    trace_hash = sha256_text(canonical_json(trace))
    errors = sum(item["attributes"]["severity"] == "error" for item in findings)
    validation = {
        "valid": errors == 0,
        "structural_and_safety_valid": all(
            item["attributes"]["status"] == "pass"
            for item in summaries
            if item["attributes"]["behavior"]
            in {"dangling_relation_detector", "public_safety_gate", "current_state_reconciliation"}
        ),
        "audit_error_count": errors,
        "audit_finding_count": len(findings),
        "source_file_count": next(
            item["attributes"].get("source_file_count", 0)
            for item in objects
            if item["key"] == "research_program:distributed-discovery"
        ),
    }
    _write_json(output / "source-lock.json", export_metadata(source_commit), source_commit)
    _write_json(output / "graph.json", objects, source_commit)
    _write_json(output / "relations.json", relations, source_commit)
    _write_json(output / "validation.json", validation, source_commit)
    _write_json(output / "object-counts.json", object_counts, source_commit)
    _write_json(output / "relation-counts.json", relation_counts, source_commit)
    _write_json(
        output / "trace-summary.json",
        {
            "event_count": len(trace),
            "event_counts": dict(sorted(Counter(x["type"] for x in trace).items())),
            "trace_sha256": trace_hash,
        },
        source_commit,
    )
    (output / "trace.sha256").write_text(f"{trace_hash}  canonical-public-trace\n")
    summary_lines = [
        "# Canonical graph summary",
        "",
        f"- Objects: {len(objects)}",
        f"- Relations: {len(relations)}",
        f"- Events: {len(trace)}",
        "",
        "## Object counts",
        "",
    ]
    summary_lines.extend(f"- `{key}`: {value}" for key, value in object_counts.items())
    summary_lines.extend(["", "## Relation counts", ""])
    summary_lines.extend(f"- `{key}`: {value}" for key, value in relation_counts.items())
    (output / "graph-summary.md").write_text("\n".join(summary_lines) + "\n")
    audit_lines = ["# Deterministic audit", "", f"Findings: {len(findings)}; errors: {errors}.", ""]
    for item in sorted(summaries, key=lambda x: x["attributes"]["behavior"]):
        attrs = item["attributes"]
        audit_lines.append(
            f"- `{attrs['behavior']}`: **{attrs['status']}** ({attrs['finding_count']})"
        )
    audit_lines.extend(["", "## Findings", ""])
    for item in sorted(findings, key=lambda x: x["key"]):
        attrs = item["attributes"]
        audit_lines.append(
            f"- **{attrs['severity']}** `{attrs['code']}` — `{attrs['subject_key']}`: {attrs['message']}"
        )
    (output / "audit.md").write_text("\n".join(audit_lines) + "\n")
    decision_lines = ["# Decisions and advisories", ""]
    for item in sorted([x for x in objects if x["type"] == "decision"], key=lambda x: x["key"]):
        attrs = item["attributes"]
        decision_lines.append(
            f"- `{item['key']}` — {item['label']} ({attrs.get('category', 'source')})"
        )
    (output / "decisions.md").write_text("\n".join(decision_lines) + "\n")
    for path in output.iterdir():
        if not path.is_file():
            continue
        text = path.read_text()
        if HOST_PATH_RE.search(text) or any(pattern.search(text) for _, pattern in SECRET_PATTERNS):
            raise ValueError(f"unsafe export content: {path.name}")
    return {
        "objects": len(objects),
        "relations": len(relations),
        "events": len(trace),
        **validation,
    }


def deterministic_files(output: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(output.iterdir()) if path.is_file()}
