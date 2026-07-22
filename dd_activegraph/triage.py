"""Human-reviewable classification of the original evidence-audit findings."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

BUCKETS = {
    "A": "Current primary-evidence gap",
    "B": "Superseded or historical non-primary run",
    "C": "Intentionally failed or preliminary run",
    "D": "Importer-policy mismatch",
}

# Classification is deliberately explicit. Keys are (run id, finding code), so
# the generator fails if the baseline finding set changes or a row is omitted.
TRIAGE: dict[tuple[str, str], dict[str, Any]] = {
    (
        "20260720T200124Z_DD-001_6eb12861_f9bcf73ec7",
        "run_missing_verifier",
    ): {
        "classification": "B",
        "role": "earlier passing 17-point run; superseded by the 21-point primary run",
        "verifier": None,
        "corruption": None,
    },
    (
        "20260720T200124Z_DD-001_6eb12861_f9bcf73ec7",
        "run_missing_corruption_test",
    ): {
        "classification": "B",
        "role": "earlier passing 17-point run; superseded by the 21-point primary run",
        "verifier": None,
        "corruption": None,
    },
    (
        "20260720T200245Z_DD-001_6eb12861_ba766d1eba",
        "run_missing_verifier",
    ): {
        "classification": "B",
        "role": "earlier passing 21-point run; superseded by the figure-complete primary run",
        "verifier": None,
        "corruption": None,
    },
    (
        "20260720T200245Z_DD-001_6eb12861_ba766d1eba",
        "run_missing_corruption_test",
    ): {
        "classification": "B",
        "role": "earlier passing 21-point run; superseded by the figure-complete primary run",
        "verifier": None,
        "corruption": None,
    },
    (
        "20260721T153110Z_DD-008A_637f2b94_06307caab4",
        "run_missing_verifier",
    ): {
        "classification": "B",
        "role": "earlier non-primary registration run; replaced by the clean primary run",
        "verifier": (
            "results/verified/20260721T163030Z_DD-008A_8b70668b_06307caab4/validation.json"
        ),
        "corruption": None,
    },
    (
        "20260720T225701Z_DD-002_a12ba3e8_e29b1460ae",
        "run_missing_verifier",
    ): {
        "classification": "C",
        "role": "explicit preliminary disclosure run",
        "verifier": (
            "results/verified/20260720T225848Z_DD-002_94607423_e29b1460ae/"
            "outputs/witness-verification.json"
        ),
        "corruption": None,
    },
    (
        "20260720T220911Z_DD-001_6822d4c6_40bf5b06a5",
        "run_missing_corruption_test",
    ): {
        "classification": "C",
        "role": "explicit preliminary signature audit with superseded presentation key",
        "verifier": (
            "results/verified/20260720T220911Z_DD-001_6822d4c6_40bf5b06a5/"
            "outputs/certificate-verification.json"
        ),
        "corruption": None,
    },
    (
        "20260720T200447Z_DD-001_6eb12861_ba766d1eba",
        "run_missing_verifier",
    ): {
        "classification": "D",
        "role": "current primary initial-grid evidence",
        "verifier": (
            "results/verified/20260720T200447Z_DD-001_6eb12861_ba766d1eba/validation.json"
        ),
        "corruption": None,
    },
    (
        "20260720T200447Z_DD-001_6eb12861_ba766d1eba",
        "run_missing_corruption_test",
    ): {
        "classification": "D",
        "role": "current primary initial-grid evidence; corruption requirement belongs to later milestones",
        "verifier": (
            "results/verified/20260720T200447Z_DD-001_6eb12861_ba766d1eba/validation.json"
        ),
        "corruption": None,
    },
    (
        "20260721T022739Z_DD-001_358cb1eb_cd16846ba5",
        "run_missing_corruption_test",
    ): {
        "classification": "D",
        "role": "current primary alignment-bound evidence",
        "verifier": (
            "results/verified/20260721T022739Z_DD-001_358cb1eb_cd16846ba5/"
            "outputs/independent-verification.json"
        ),
        "corruption": (
            "results/verified/20260721T022739Z_DD-001_358cb1eb_cd16846ba5/"
            "outputs/independent-verification.json"
        ),
    },
    (
        "20260720T221139Z_DD-001_b1d8d431_40bf5b06a5",
        "run_missing_corruption_test",
    ): {
        "classification": "D",
        "role": "current primary signature evidence",
        "verifier": (
            "results/verified/20260720T221139Z_DD-001_b1d8d431_40bf5b06a5/"
            "outputs/certificate-verification.json"
        ),
        "corruption": (
            "results/verified/20260720T221139Z_DD-001_b1d8d431_40bf5b06a5/validation.json"
        ),
    },
    (
        "20260720T223829Z_DD-001_b2cc23f4_5e16a90ad1",
        "run_missing_corruption_test",
    ): {
        "classification": "D",
        "role": "current primary threshold evidence; study-wide text was misapplied per run",
        "verifier": (
            "results/verified/20260720T223829Z_DD-001_b2cc23f4_5e16a90ad1/validation.json"
        ),
        "corruption": None,
    },
    (
        "20260722T044453Z_DD-015_34bc4379_33e1da478b",
        "run_missing_verifier",
    ): {
        "classification": "D",
        "role": "current secondary threshold-two extension evidence",
        "verifier": "src/distributed_discovery/dynamic_attention/verification.py",
        "corruption": (
            "results/verified/20260722T044453Z_DD-015_34bc4379_33e1da478b/"
            "outputs/corruption-tests.json"
        ),
    },
}


def _load_content(path: Path) -> Any:
    return json.loads(path.read_text())["content"]


def build_gap_triage(source: Path, baseline_exports: Path) -> list[dict[str, Any]]:
    objects = _load_content(baseline_exports / "graph.json")
    findings = [
        item
        for item in objects
        if item["type"] == "decision"
        and item.get("attributes", {}).get("category") == "audit_finding"
        and item.get("attributes", {}).get("severity") == "error"
    ]
    runs = {item["key"]: item for item in objects if item["type"] == "research_run"}
    claims = [item for item in objects if item["type"] == "claim"]
    rows: list[dict[str, Any]] = []
    observed: set[tuple[str, str]] = set()
    for finding in sorted(findings, key=lambda item: item["key"]):
        attrs = finding["attributes"]
        subject = str(attrs["subject_key"])
        run_id = subject.removeprefix("research_run:")
        key = (run_id, str(attrs["code"]))
        if key not in TRIAGE:
            raise ValueError(f"unclassified substantive finding: {key}")
        observed.add(key)
        rule = TRIAGE[key]
        run = runs[subject]["attributes"]
        claim_ids = sorted(
            item["attributes"]["claim_id"]
            for item in claims
            if run_id in item["attributes"].get("run_ids", [])
        )
        classification = str(rule["classification"])
        if classification == "A":
            canonical_action = "Add or correct canonical evidence for the current primary run."
            importer_action = "None until canonical evidence changes."
            blocks_ci = True
        elif classification == "B":
            canonical_action = "Preserve immutable historical evidence; no source mutation."
            importer_action = "Recognize explicit primary/superseded evidence roles."
            blocks_ci = False
        elif classification == "C":
            canonical_action = "Preserve the explicitly preliminary run and its label."
            importer_action = "Downgrade findings for explicitly preliminary or failed runs."
            blocks_ci = False
        else:
            canonical_action = (
                "No canonical change; the visible evidence already supports the role."
            )
            importer_action = "Scope requirements to the specific run and recognize validation/verifier artifacts."
            blocks_ci = False
        verifier = rule["verifier"]
        corruption = rule["corruption"]
        for candidate in (verifier, corruption):
            if candidate is not None and not (source / str(candidate)).is_file():
                raise FileNotFoundError(f"triage evidence path is missing: {candidate}")
        rows.append(
            {
                "finding_id": finding["key"],
                "finding_code": attrs["code"],
                "subject_run": run_id,
                "study": run["study_id"],
                "current_evidence_role": rule["role"],
                "public_exposure": (
                    f"public claim ledger: {', '.join(claim_ids)}"
                    if claim_ids
                    else "no direct claim-ledger exposure"
                ),
                "claim_ids": claim_ids,
                "actual_verifier_location": verifier,
                "actual_corruption_test_location": corruption,
                "classification": classification,
                "classification_label": BUCKETS[classification],
                "proposed_canonical_action": canonical_action,
                "proposed_importer_action": importer_action,
                "should_block_ci": blocks_ci,
                "review_minutes": 3,
            }
        )
    if observed != set(TRIAGE):
        missing = sorted(set(TRIAGE) - observed)
        raise ValueError(f"triage rows no longer correspond to baseline findings: {missing}")
    if len(rows) != 13:
        raise ValueError(f"expected 13 substantive findings, observed {len(rows)}")
    return rows


def write_gap_triage(
    source: Path, baseline_exports: Path, comparison: Path, reports: Path
) -> dict[str, Any]:
    rows = build_gap_triage(source, baseline_exports)
    counts = Counter(str(item["classification"]) for item in rows)
    metrics = {
        "true_positive_count": counts["A"],
        "false_positive_count": counts["D"],
        "historical_exception_count": counts["B"],
        "expected_failed_or_preliminary_count": counts["C"],
        "reviewed_finding_count": len(rows),
        "review_minutes_total": sum(int(item["review_minutes"]) for item in rows),
        "false_positive_rate": counts["D"] / (counts["A"] + counts["D"]),
    }
    payload = {
        "schema_version": "dd-activegraph-gap-triage/v1",
        "buckets": BUCKETS,
        "metrics": metrics,
        "findings": rows,
    }
    comparison.mkdir(parents=True, exist_ok=True)
    (comparison / "gap-triage.yml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    )
    reports.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Evidence-gap triage",
        "",
        "This report classifies the original 13 substantive ActiveGraph findings. It does not "
        "modify canonical evidence or open per-finding issues.",
        "",
        "## Counts",
        "",
        *(f"- {code}. {BUCKETS[code]}: {counts[code]}" for code in "ABCD"),
        f"- False-positive rate among current-evidence findings: {metrics['false_positive_rate']:.1%}",
        f"- Recorded review time: {metrics['review_minutes_total']} minutes",
        "",
        "## Findings",
        "",
    ]
    for item in rows:
        lines.extend(
            [
                f"### `{item['subject_run']}` / `{item['finding_code']}`",
                "",
                f"- Study: `{item['study']}`",
                f"- Role: {item['current_evidence_role']}",
                f"- Exposure: {item['public_exposure']}",
                f"- Classification: **{item['classification']}. {item['classification_label']}**",
                f"- Verifier: `{item['actual_verifier_location'] or 'not present'}`",
                f"- Corruption test: `{item['actual_corruption_test_location'] or 'not present'}`",
                f"- Canonical action: {item['proposed_canonical_action']}",
                f"- Importer action: {item['proposed_importer_action']}",
                f"- CI blocking: `{str(item['should_block_ci']).lower()}`",
                "",
            ]
        )
    (reports / "evidence-gap-triage.md").write_text("\n".join(lines))
    return metrics
