"""Reactive deterministic audit behaviors for the custom pack."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from activegraph.packs import behavior

from dd_activegraph.model import AuditFinding
from dd_activegraph.ontology import AUDIT_BEHAVIORS, canonical_json, sha256_text
from dd_activegraph.validation import (
    current_state_findings,
    dangling_relation_findings,
    orphan_claim_findings,
    paper_admission_findings,
    public_safety_findings,
    reverse_link_findings,
    stale_status_findings,
    study_promotion_findings,
    unverified_run_findings,
)

FindingFunction = Callable[[list[Any], list[Any]], list[AuditFinding]]


def _record(
    behavior_name: str,
    finding_function: FindingFunction,
    graph: Any,
    ctx: Any,
) -> None:
    objects = ctx.view.objects()
    relations = ctx.view.relations()
    findings = sorted(finding_function(objects, relations), key=lambda item: item.key)
    severities = {finding.severity for finding in findings}
    status = (
        "fail"
        if "error" in severities
        else "warning"
        if "warning" in severities
        else "advisory"
        if findings
        else "pass"
    )
    finding_keys: list[str] = []
    for finding in findings:
        finding_keys.append(finding.key)
        graph.add_object(
            "decision",
            {
                "key": finding.key,
                "label": f"{finding.code}: {finding.subject_key}",
                "source_path": None,
                "source_sha256": None,
                "attributes": {
                    "category": "audit_finding",
                    "behavior": finding.behavior,
                    "code": finding.code,
                    "severity": finding.severity,
                    "subject_key": finding.subject_key,
                    "message": finding.message,
                    "details": finding.details,
                    "advisory_only": finding.severity == "advisory",
                },
            },
        )
    summary_key = f"decision:audit:{behavior_name}:summary"
    graph.add_object(
        "decision",
        {
            "key": summary_key,
            "label": f"{behavior_name} audit summary",
            "source_path": None,
            "source_sha256": None,
            "attributes": {
                "category": "audit_summary",
                "behavior": behavior_name,
                "status": status,
                "finding_count": len(findings),
                "finding_keys": finding_keys,
                "deterministic": True,
            },
        },
    )
    graph.emit(
        "dd.audit.completed",
        {
            "behavior": behavior_name,
            "status": status,
            "summary_key": summary_key,
            "finding_keys": finding_keys,
        },
    )


@behavior(name="orphan_claim_detector", on=["dd.import.completed"])
def orphan_claim_detector(event: Any, graph: Any, ctx: Any) -> None:
    _record("orphan_claim_detector", orphan_claim_findings, graph, ctx)


@behavior(name="unverified_run_detector", on=["dd.import.completed"])
def unverified_run_detector(event: Any, graph: Any, ctx: Any) -> None:
    _record("unverified_run_detector", unverified_run_findings, graph, ctx)


@behavior(name="dangling_relation_detector", on=["dd.import.completed"])
def dangling_relation_detector(event: Any, graph: Any, ctx: Any) -> None:
    _record("dangling_relation_detector", dangling_relation_findings, graph, ctx)


@behavior(name="stale_status_detector", on=["dd.import.completed"])
def stale_status_detector(event: Any, graph: Any, ctx: Any) -> None:
    _record("stale_status_detector", stale_status_findings, graph, ctx)


@behavior(name="reverse_link_detector", on=["dd.import.completed"])
def reverse_link_detector(event: Any, graph: Any, ctx: Any) -> None:
    _record("reverse_link_detector", reverse_link_findings, graph, ctx)


@behavior(name="paper_admission_gate", on=["dd.import.completed"])
def paper_admission_gate(event: Any, graph: Any, ctx: Any) -> None:
    _record("paper_admission_gate", paper_admission_findings, graph, ctx)


@behavior(name="study_promotion_gate", on=["dd.import.completed"])
def study_promotion_gate(event: Any, graph: Any, ctx: Any) -> None:
    _record("study_promotion_gate", study_promotion_findings, graph, ctx)


@behavior(name="public_safety_gate", on=["dd.import.completed"])
def public_safety_gate(event: Any, graph: Any, ctx: Any) -> None:
    _record("public_safety_gate", public_safety_findings, graph, ctx)


def _site_relation_candidates(objects: list[Any], relations: list[Any]) -> list[dict[str, Any]]:
    by_id = {obj.id: obj for obj in objects}
    allowed = {"published_at", "appears_in", "exposed_by_lab", "materialized_as"}
    candidates: list[dict[str, Any]] = []
    for relation in relations:
        if relation.type not in allowed:
            continue
        source = by_id.get(relation.source)
        target = by_id.get(relation.target)
        if source is None or target is None:
            continue
        candidates.append(
            {
                "type": relation.type,
                "source": source.data["key"],
                "target": target.data["key"],
            }
        )
    return sorted(candidates, key=lambda item: (item["type"], item["source"], item["target"]))


@behavior(name="site_relation_materializer", on=["dd.import.completed"])
def site_relation_materializer(event: Any, graph: Any, ctx: Any) -> None:
    candidates = _site_relation_candidates(ctx.view.objects(), ctx.view.relations())
    content_hash = sha256_text(canonical_json(candidates))
    artifact_key = "artifact:generated:site-relations-candidate"
    graph.add_object(
        "artifact",
        {
            "key": artifact_key,
            "label": "Candidate site relationship map",
            "source_path": None,
            "source_sha256": content_hash,
            "attributes": {
                "category": "generated_candidate",
                "relation_count": len(candidates),
                "relations": candidates,
                "writes_source_repository": False,
            },
        },
    )
    _record("site_relation_materializer", lambda _objects, _relations: [], graph, ctx)


@behavior(name="current_state_reconciliation", on=["dd.import.completed"])
def current_state_reconciliation(event: Any, graph: Any, ctx: Any) -> None:
    _record("current_state_reconciliation", current_state_findings, graph, ctx)


BEHAVIORS = (
    orphan_claim_detector,
    unverified_run_detector,
    dangling_relation_detector,
    stale_status_detector,
    reverse_link_detector,
    paper_admission_gate,
    study_promotion_gate,
    public_safety_gate,
    site_relation_materializer,
    current_state_reconciliation,
)

assert tuple(item.name for item in BEHAVIORS) == AUDIT_BEHAVIORS
