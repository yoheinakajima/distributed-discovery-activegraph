"""Domain ontology and deterministic identifiers for the pilot."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "dd-activegraph/v1"
GENERATOR_VERSION = "0.1.0"
SOURCE_REPOSITORY = "https://github.com/yoheinakajima/distributed-discovery"
SOURCE_COMMIT = "a560bb771a8ccaf92958bde8e72280e2c968825f"
ACTIVEGRAPH_REPOSITORY = "https://github.com/yoheinakajima/activegraph"
ACTIVEGRAPH_COMMIT = "8aedb1866cf5dce056af97529152ffd6f468a1ed"
ACTIVEGRAPH_PACKS_REPOSITORY = "https://github.com/yoheinakajima/activegraph-packs"
ACTIVEGRAPH_PACKS_COMMIT = "6639a5385518ad49f74813373c85cf96eff9adc0"

OBJECT_TYPES: tuple[str, ...] = (
    "research_program",
    "theorem_family",
    "study",
    "claim",
    "proof",
    "research_run",
    "configuration",
    "certificate",
    "corruption_test",
    "paper",
    "chapter",
    "lab",
    "benchmark_task",
    "experiment_module",
    "research_question",
    "conjecture",
    "hypothesis",
    "route",
    "artifact",
    "pull_request",
    "decision",
    "approval",
    "roadmap_item",
)

RELATION_TYPES: tuple[str, ...] = (
    "builds_on",
    "tests",
    "supports",
    "contradicts",
    "qualifies",
    "supersedes",
    "generated_by",
    "verified_by",
    "appears_in",
    "implemented_by",
    "blocks",
    "requires",
    "owned_by",
    "belongs_to_program",
    "belongs_to_theorem_family",
    "related_to",
    "published_at",
    "exposed_by_lab",
    "benchmarked_by",
    "motivates_experiment",
    "materialized_as",
    "derived_from_source",
)

AUDIT_BEHAVIORS: tuple[str, ...] = (
    "orphan_claim_detector",
    "unverified_run_detector",
    "dangling_relation_detector",
    "stale_status_detector",
    "reverse_link_detector",
    "paper_admission_gate",
    "study_promotion_gate",
    "public_safety_gate",
    "site_relation_materializer",
    "current_state_reconciliation",
)


def canonical_json(value: Any) -> str:
    """Serialize canonical JSON used by every checksum and stable relation id."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_relation_id(
    relation_type: str, source_key: str, target_key: str, data: dict[str, Any]
) -> str:
    payload = [relation_type, source_key, target_key, data]
    return f"relation:{sha256_text(canonical_json(payload))[:24]}"


def export_metadata(source_commit: str = SOURCE_COMMIT) -> dict[str, str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": source_commit,
        "activegraph_commit": ACTIVEGRAPH_COMMIT,
        "activegraph_packs_commit": ACTIVEGRAPH_PACKS_COMMIT,
        "generator_version": GENERATOR_VERSION,
    }
