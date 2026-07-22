"""Deterministic ActiveGraph fork-and-diff demonstration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from activegraph import Runtime

from dd_activegraph.ontology import SOURCE_COMMIT, canonical_json, export_metadata, sha256_text
from dd_activegraph.validation import reverse_link_findings, stale_status_findings

FORK_RUN_ID = "run_dd_activegraph_reverse_link_fork_v1"
STATUS_FORK_RUN_ID = "run_dd_activegraph_status_fork_v1"


def run_fork_demo(
    parent: Runtime, output: Path, *, source_commit: str = SOURCE_COMMIT
) -> dict[str, Any]:
    target = next(
        relation
        for relation in parent.graph.all_relations()
        if relation.type == "builds_on"
        and parent.graph.get_object(relation.source).type == "lab"
        and parent.graph.get_object(relation.target).type == "study"
    )
    fork = parent.fork(at_event=parent.graph.events[-1].id, label="missing-lab-reverse-link")
    fork.graph.remove_relation(target.id, actor="dd.fixture")
    findings = reverse_link_findings(fork.graph.all_objects(), fork.graph.all_relations())
    fixture_findings = [item for item in findings if item.code == "missing_reverse_relation"]
    if not fixture_findings:
        raise RuntimeError("fork fixture did not trigger the reverse-link detector")
    for finding in fixture_findings:
        fork.graph.add_object(
            "decision",
            {
                "key": finding.key,
                "label": f"{finding.code}: {finding.subject_key}",
                "source_path": None,
                "source_sha256": None,
                "attributes": {
                    "category": "fork_demo_finding",
                    "behavior": finding.behavior,
                    "code": finding.code,
                    "severity": finding.severity,
                    "subject_key": finding.subject_key,
                    "message": finding.message,
                    "details": finding.details,
                },
            },
            actor="dd.fixture",
        )
    fork.save_state()
    diff = parent.diff(fork)
    payload = {
        "metadata": export_metadata(source_commit),
        "parent_run_id": parent.run_id,
        "fork_run_id": fork.run_id,
        "removed_relation": {
            "type": target.type,
            "source_key": parent.graph.get_object(target.source).data["key"],
            "target_key": parent.graph.get_object(target.target).data["key"],
        },
        "new_findings": [
            {"code": item.code, "subject_key": item.subject_key, "message": item.message}
            for item in fixture_findings
        ],
        "activegraph_diff": {
            "shared_events": len(diff.shared_events),
            "parent_only_events": len(diff.parent_only_events),
            "fork_only_events": len(diff.fork_only_events),
            "divergent_objects": len(diff.divergent_objects),
            "divergent_relations": len(diff.divergent_relations),
        },
    }
    replayed = Runtime.load(str(parent.graph.store.path), run_id=fork.run_id)
    replay_ok = len(replayed.graph.all_objects()) == len(fork.graph.all_objects()) and len(
        replayed.graph.all_relations()
    ) == len(fork.graph.all_relations())
    replayed.graph.close_sinks()
    if replayed.graph.store is not None:
        replayed.graph.store.close()
    payload["replay_verified"] = replay_ok
    payload["canonical_content_sha256"] = sha256_text(canonical_json(payload))
    output.mkdir(parents=True, exist_ok=True)
    (output / "fork-diff.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    (output / "fork-demo.md").write_text(
        "# ActiveGraph fork-and-diff demonstration\n\n"
        f"Parent `{parent.run_id}` was forked as `{fork.run_id}` at a quiescent event. "
        "The deterministic fixture removed one Lab-to-study reverse relation.\n\n"
        f"The reverse-link audit produced {len(fixture_findings)} new finding(s), while "
        f"ActiveGraph reported {len(diff.divergent_relations)} divergent relation(s) and "
        f"{len(diff.divergent_objects)} divergent object(s). Replay verification was "
        f"`{str(replay_ok).lower()}`. The scientific source checkout was not changed.\n"
    )
    return payload


def run_status_fork_demo(
    parent: Runtime, output: Path, *, source_commit: str = SOURCE_COMMIT
) -> dict[str, Any]:
    study = next(
        obj
        for obj in sorted(parent.graph.all_objects(), key=lambda item: str(item.data.get("key")))
        if obj.type == "study" and "complete" in str(obj.data.get("attributes", {}).get("phase"))
    )
    fork = parent.fork(at_event=parent.graph.events[-1].id, label="stale-study-status")
    attributes = dict(study.data.get("attributes", {}))
    attributes["status"] = "planned"
    fork.graph.patch_object(study.id, {"attributes": attributes}, actor="dd.fixture")
    findings = stale_status_findings(fork.graph.all_objects(), fork.graph.all_relations())
    fixture_findings = [
        item
        for item in findings
        if item.code == "study_status_mismatch" and item.subject_key == study.data["key"]
    ]
    if not fixture_findings:
        raise RuntimeError("status fork fixture did not trigger the stale-status detector")
    for finding in fixture_findings:
        fork.graph.add_object(
            "decision",
            {
                "key": finding.key,
                "label": f"{finding.code}: {finding.subject_key}",
                "source_path": None,
                "source_sha256": None,
                "attributes": {
                    "category": "fork_demo_finding",
                    "behavior": finding.behavior,
                    "code": finding.code,
                    "severity": finding.severity,
                    "subject_key": finding.subject_key,
                    "message": finding.message,
                    "details": finding.details,
                },
            },
            actor="dd.fixture",
        )
    fork.save_state()
    diff = parent.diff(fork)
    replayed = Runtime.load(str(parent.graph.store.path), run_id=fork.run_id)
    replay_ok = len(replayed.graph.all_objects()) == len(fork.graph.all_objects()) and len(
        replayed.graph.all_relations()
    ) == len(fork.graph.all_relations())
    replayed.graph.close_sinks()
    if replayed.graph.store is not None:
        replayed.graph.store.close()
    payload = {
        "metadata": export_metadata(source_commit),
        "parent_run_id": parent.run_id,
        "fork_run_id": fork.run_id,
        "changed_study": study.data["key"],
        "changed_field": "attributes.status",
        "new_value": "planned",
        "new_findings": [
            {"code": item.code, "subject_key": item.subject_key, "message": item.message}
            for item in fixture_findings
        ],
        "activegraph_diff": {
            "shared_events": len(diff.shared_events),
            "parent_only_events": len(diff.parent_only_events),
            "fork_only_events": len(diff.fork_only_events),
            "divergent_objects": len(diff.divergent_objects),
            "divergent_relations": len(diff.divergent_relations),
        },
        "replay_verified": replay_ok,
        "scientific_source_changed": False,
    }
    payload["canonical_content_sha256"] = sha256_text(canonical_json(payload))
    output.mkdir(parents=True, exist_ok=True)
    (output / "status-fork-diff.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    return payload
