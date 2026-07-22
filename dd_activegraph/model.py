"""Pure records shared by import, audit, export, and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeRecord:
    key: str
    type: str
    label: str
    source_path: str | None = None
    source_sha256: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def data(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "attributes": self.attributes,
        }


@dataclass(frozen=True)
class RelationRecord:
    type: str
    source_key: str
    target_key: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditFinding:
    behavior: str
    code: str
    severity: str
    subject_key: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        from dd_activegraph.ontology import canonical_json, sha256_text

        digest = sha256_text(
            canonical_json([self.behavior, self.code, self.subject_key, self.message, self.details])
        )[:16]
        return f"decision:audit:{self.behavior}:finding:{digest}"


@dataclass
class ImportBundle:
    objects: dict[str, NodeRecord] = field(default_factory=dict)
    relations: list[RelationRecord] = field(default_factory=list)
    source_files: dict[str, str] = field(default_factory=dict)
    declared_counts: dict[str, int] = field(default_factory=dict)

    def add_object(self, record: NodeRecord) -> None:
        if record.key in self.objects:
            raise ValueError(f"duplicate stable object key: {record.key}")
        self.objects[record.key] = record

    def add_relation(self, record: RelationRecord) -> None:
        if record.source_key not in self.objects:
            raise ValueError(f"missing relation source: {record.source_key}")
        if record.target_key not in self.objects:
            raise ValueError(f"missing relation target: {record.target_key}")
        marker = (record.type, record.source_key, record.target_key, repr(record.data))
        existing = {
            (item.type, item.source_key, item.target_key, repr(item.data))
            for item in self.relations
        }
        if marker not in existing:
            self.relations.append(record)
