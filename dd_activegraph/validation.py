"""Deterministic graph audits used by ActiveGraph behaviors and verification."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from dd_activegraph.model import AuditFinding

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9_]{20,})\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")),
)
HOST_PATH_RE = re.compile(r"(?:/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\Users\\)")


def _object_maps(
    objects: Iterable[Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_id: dict[str, Any] = {}
    by_key: dict[str, Any] = {}
    for obj in objects:
        by_id[obj.id] = obj
        key = obj.data.get("key")
        if isinstance(key, str):
            by_key[key] = obj
    return by_id, by_key


def _relation_keys(
    relations: Iterable[Any], by_id: dict[str, Any]
) -> list[tuple[str, str, str, Any]]:
    out: list[tuple[str, str, str, Any]] = []
    for relation in relations:
        source = by_id.get(relation.source)
        target = by_id.get(relation.target)
        source_key = source.data.get("key") if source is not None else relation.source
        target_key = target.data.get("key") if target is not None else relation.target
        out.append((relation.type, str(source_key), str(target_key), relation))
    return out


def orphan_claim_findings(objects: list[Any], relations: list[Any]) -> list[AuditFinding]:
    by_id, by_key = _object_maps(objects)
    keyed_relations = _relation_keys(relations, by_id)
    findings: list[AuditFinding] = []
    for key, claim in sorted(by_key.items()):
        if claim.type != "claim":
            continue
        has_study = any(
            relation_type == "owned_by" and source == key and target.startswith("study:")
            for relation_type, source, target, _ in keyed_relations
        )
        has_evidence = any(
            relation_type in {"supports", "verified_by"} and target == key
            for relation_type, _, target, _ in keyed_relations
        )
        has_public_role = any(
            source == key and relation_type in {"appears_in", "published_at", "materialized_as"}
            for relation_type, source, _, _ in keyed_relations
        )
        for ok, code, message in (
            (has_study, "claim_without_study", "Claim has no owning study relation."),
            (has_evidence, "claim_without_evidence", "Claim has no proof or passing-run support."),
            (
                has_public_role,
                "claim_without_public_role",
                "Claim has no paper, route, or public artifact role.",
            ),
        ):
            if not ok:
                findings.append(
                    AuditFinding(
                        behavior="orphan_claim_detector",
                        code=code,
                        severity="error",
                        subject_key=key,
                        message=message,
                    )
                )
    return findings


def unverified_run_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for obj in sorted(objects, key=lambda item: str(item.data.get("key", ""))):
        if obj.type != "research_run":
            continue
        key = str(obj.data["key"])
        attrs = obj.data.get("attributes", {})
        checks = (
            (attrs.get("exit_status") == 0, "run_exit_nonzero", "Run exit status is nonzero."),
            (
                attrs.get("validation_status") == "passed",
                "run_validation_not_passed",
                "Run validation status is not passed.",
            ),
            (
                bool(attrs.get("has_output_checksum")),
                "run_missing_output_checksum",
                "Run has no checksummed output.",
            ),
            (
                not attrs.get("verifier_required") or bool(attrs.get("has_verifier")),
                "run_missing_verifier",
                "Run has no verifier required by its visible study plan.",
            ),
            (
                not attrs.get("corruption_required") or bool(attrs.get("has_corruption_test")),
                "run_missing_corruption_test",
                "Substantive computational run has no corruption-test output.",
            ),
        )
        for passed, code, message in checks:
            if not passed:
                findings.append(
                    AuditFinding(
                        behavior="unverified_run_detector",
                        code=code,
                        severity="warning" if not attrs.get("substantive") else "error",
                        subject_key=key,
                        message=message,
                        details={"substantive": bool(attrs.get("substantive"))},
                    )
                )
    return findings


def dangling_relation_findings(objects: list[Any], relations: list[Any]) -> list[AuditFinding]:
    by_id, _ = _object_maps(objects)
    findings: list[AuditFinding] = []
    for relation in sorted(relations, key=lambda item: item.id):
        missing = [
            endpoint for endpoint in (relation.source, relation.target) if endpoint not in by_id
        ]
        if missing:
            findings.append(
                AuditFinding(
                    behavior="dangling_relation_detector",
                    code="dangling_relation",
                    severity="error",
                    subject_key=relation.id,
                    message="Relation has a missing endpoint.",
                    details={"missing_internal_ids": sorted(missing)},
                )
            )
    return findings


def stale_status_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    _by_id, by_key = _object_maps(objects)
    findings: list[AuditFinding] = []
    for key, study in sorted(by_key.items()):
        if study.type != "study":
            continue
        attrs = study.data.get("attributes", {})
        public_phase = attrs.get("phase")
        status = attrs.get("status")
        public_state = str(public_phase).lower()
        status_state = str(status).lower()
        incomplete_markers = ("planned", "pending", "queued", "registered", "not-started")
        completion_contradiction = (
            "complete" in public_state
            and any(marker in status_state for marker in incomplete_markers)
        ) or (
            "complete" in status_state
            and any(marker in public_state for marker in incomplete_markers)
        )
        failure_contradiction = ("failed" in public_state) != ("failed" in status_state)
        if public_phase and status and (completion_contradiction or failure_contradiction):
            findings.append(
                AuditFinding(
                    behavior="stale_status_detector",
                    code="study_status_mismatch",
                    severity="warning",
                    subject_key=key,
                    message="Study public phase and status.yml disagree.",
                    details={"public_phase": public_phase, "status": status},
                )
            )
        if attrs.get("roadmap_state") == "planned" and "complete" in str(status):
            findings.append(
                AuditFinding(
                    behavior="stale_status_detector",
                    code="roadmap_still_planned",
                    severity="warning",
                    subject_key=key,
                    message="Roadmap still presents a completed study as planned.",
                )
            )
    for key, paper in sorted(by_key.items()):
        if paper.type != "paper":
            continue
        attrs = paper.data.get("attributes", {})
        validation = attrs.get("validation", {})
        if attrs.get("status") == "validated" and validation.get("compile_exit_status") != 0:
            findings.append(
                AuditFinding(
                    behavior="stale_status_detector",
                    code="paper_validation_mismatch",
                    severity="error",
                    subject_key=key,
                    message="Paper metadata says validated but compilation did not pass.",
                )
            )
    return findings


def reverse_link_findings(objects: list[Any], relations: list[Any]) -> list[AuditFinding]:
    by_id, by_key = _object_maps(objects)
    keyed = _relation_keys(relations, by_id)
    triples = {(kind, source, target) for kind, source, target, _ in keyed}
    findings: list[AuditFinding] = []
    for kind, source, target, _ in keyed:
        expected: tuple[str, str, str] | None = None
        if kind == "appears_in" and source.startswith("study:") and target.startswith("paper:"):
            expected = ("builds_on", target, source)
        elif kind == "exposed_by_lab" and source.startswith("study:"):
            expected = ("builds_on", target, source)
        if expected is not None and expected not in triples:
            findings.append(
                AuditFinding(
                    behavior="reverse_link_detector",
                    code="missing_reverse_relation",
                    severity="warning",
                    subject_key=source,
                    message=f"Missing reverse relation {expected[0]} from {target}.",
                    details={"expected": list(expected)},
                )
            )

    claim_studies: dict[str, set[str]] = defaultdict(set)
    task_claims: dict[str, set[str]] = defaultdict(set)
    task_studies: dict[str, set[str]] = defaultdict(set)
    for kind, source, target, _ in keyed:
        if kind == "owned_by" and source.startswith("claim:") and target.startswith("study:"):
            claim_studies[source].add(target)
        if kind == "tests" and source.startswith("benchmark_task:") and target.startswith("claim:"):
            task_claims[source].add(target)
        if (
            kind == "builds_on"
            and source.startswith("benchmark_task:")
            and target.startswith("study:")
        ):
            task_studies[source].add(target)
    for task, claims in sorted(task_claims.items()):
        expected_studies = set().union(*(claim_studies.get(claim, set()) for claim in claims))
        if expected_studies and not expected_studies.intersection(task_studies.get(task, set())):
            findings.append(
                AuditFinding(
                    behavior="reverse_link_detector",
                    code="benchmark_missing_study_relation",
                    severity="warning",
                    subject_key=task,
                    message="Benchmark task references a claim without a supporting study relation.",
                    details={"expected_studies": sorted(expected_studies)},
                )
            )
    return findings


def paper_admission_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for obj in sorted(objects, key=lambda item: str(item.data.get("key", ""))):
        if obj.type != "paper":
            continue
        attrs = obj.data.get("attributes", {})
        criteria = {
            "distinct_central_question": bool(attrs.get("central_question")),
            "title_level_result": bool(attrs.get("title")),
            "natural_literature_referee_set": bool(attrs.get("likely_literature")),
            "self_contained_reason": bool(attrs.get("source_runs") or attrs.get("claim_ids")),
            "near_term_non_obsolescence": attrs.get("editorial_disposition") is not None,
        }
        findings.append(
            AuditFinding(
                behavior="paper_admission_gate",
                code="paper_admission_advisory",
                severity="advisory",
                subject_key=str(obj.data["key"]),
                message="Paper admission gate evaluated without changing source metadata.",
                details={"criteria": criteria, "passes_all": all(criteria.values())},
            )
        )
    return findings


def study_promotion_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    required = (
        "precise_model",
        "falsifiable_target",
        "literature_boundary",
        "state_space_audit",
        "verification_plan",
        "independent_verifier",
        "corruption_plan",
        "non_overlap_statement",
        "stop_condition",
    )
    for obj in sorted(objects, key=lambda item: str(item.data.get("key", ""))):
        if obj.type != "study":
            continue
        attrs = obj.data.get("attributes", {})
        criteria = {name: bool(attrs.get("promotion_gate", {}).get(name)) for name in required}
        findings.append(
            AuditFinding(
                behavior="study_promotion_gate",
                code="study_promotion_advisory",
                severity="advisory",
                subject_key=str(obj.data["key"]),
                message="Study promotion gate evaluated from visible source files only.",
                details={"criteria": criteria, "passes_all": all(criteria.values())},
            )
        )
    return findings


def public_safety_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for obj in sorted(objects, key=lambda item: str(item.data.get("key", ""))):
        key = str(obj.data.get("key", obj.id))
        text = json.dumps(obj.data, sort_keys=True, ensure_ascii=False)
        if HOST_PATH_RE.search(text):
            findings.append(
                AuditFinding(
                    behavior="public_safety_gate",
                    code="host_specific_absolute_path",
                    severity="error",
                    subject_key=key,
                    message="Exportable object contains a host-specific absolute path.",
                )
            )
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(
                    AuditFinding(
                        behavior="public_safety_gate",
                        code=f"secret_{name}",
                        severity="error",
                        subject_key=key,
                        message=f"Exportable object matches the {name} secret pattern.",
                    )
                )
        if obj.type == "research_run":
            attrs = obj.data.get("attributes", {})
            if attrs.get("substantive") and attrs.get("validation_status") != "passed":
                findings.append(
                    AuditFinding(
                        behavior="public_safety_gate",
                        code="failed_evidence_presented_as_passed",
                        severity="error",
                        subject_key=key,
                        message="Failed evidence is marked substantive.",
                    )
                )
    return findings


def current_state_findings(objects: list[Any], _: list[Any]) -> list[AuditFinding]:
    _by_id, by_key = _object_maps(objects)
    program = by_key.get("research_program:distributed-discovery")
    if program is None:
        return [
            AuditFinding(
                behavior="current_state_reconciliation",
                code="missing_program_inventory",
                severity="error",
                subject_key="research_program:distributed-discovery",
                message="Program inventory object is missing.",
            )
        ]
    attrs = program.data.get("attributes", {})
    declared = attrs.get("declared_counts", {})
    computed = attrs.get("computed_counts", {})
    findings: list[AuditFinding] = []
    for name in sorted(set(declared) & set(computed)):
        if declared[name] != computed[name]:
            findings.append(
                AuditFinding(
                    behavior="current_state_reconciliation",
                    code="current_state_count_mismatch",
                    severity="warning",
                    subject_key="research_program:distributed-discovery",
                    message=f"Declared and computed {name} counts differ.",
                    details={
                        "measure": name,
                        "declared": declared[name],
                        "computed": computed[name],
                    },
                )
            )
    return findings


def audit_counts(findings: Iterable[AuditFinding]) -> dict[str, int]:
    return dict(sorted(Counter(finding.severity for finding in findings).items()))
