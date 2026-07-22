"""Read-only importer for a commit-pinned Distributed Discovery checkout."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, cast
from urllib.parse import urlparse

import yaml
from activegraph import Event, Runtime

from dd_activegraph.model import ImportBundle, NodeRecord, RelationRecord
from dd_activegraph.ontology import (
    OBJECT_TYPES,
    RELATION_TYPES,
    SOURCE_COMMIT,
    SOURCE_REPOSITORY,
)
from dd_activegraph.validation import HOST_PATH_RE

CLAIM_ID_RE = re.compile(r"^DD-C-\d{4}$")
STUDY_ID_RE = re.compile(r"^DD-\d{3}[A-Z]?$")
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z_DD-\d{3}[A-Z]?_[0-9a-f]{8}_[0-9a-f]{10}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ROUTE_LITERAL_RE = re.compile(r"[\"']([a-z0-9][a-z0-9_./-]*\.(?:html|json))[\"']")


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: DuplicateKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)  # type: ignore[no-untyped-call]
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(  # type: ignore[no-untyped-call]
            value_node, deep=deep
        )
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


class SourceReader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.source_files: dict[str, str] = {}

    def _path(self, relative: str) -> Path:
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError(f"unsafe source path: {relative}")
        path = self.root.joinpath(*posix.parts)
        if path.is_symlink():
            raise ValueError(f"source path must not be a symlink: {relative}")
        try:
            path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"source path escapes checkout: {relative}") from exc
        if not path.is_file():
            raise FileNotFoundError(f"missing imported source file: {relative}")
        return path

    def bytes(self, relative: str) -> bytes:
        path = self._path(relative)
        payload = path.read_bytes()
        self.source_files[relative] = hashlib.sha256(payload).hexdigest()
        return payload

    def text(self, relative: str) -> str:
        return self.bytes(relative).decode("utf-8")

    def yaml(self, relative: str) -> Any:
        try:
            value = yaml.load(self.text(relative), Loader=DuplicateKeySafeLoader)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML: {relative}: {exc}") from exc
        _reject_host_paths(value, relative)
        return value

    def json(self, relative: str) -> Any:
        try:
            value = json.loads(self.text(relative))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {relative}: {exc}") from exc
        _reject_host_paths(value, relative)
        return value


def _reject_host_paths(value: Any, relative: str) -> None:
    if isinstance(value, str) and HOST_PATH_RE.search(value):
        raise ValueError(f"host-specific absolute path in imported data: {relative}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_host_paths(key, relative)
            _reject_host_paths(item, relative)
    elif isinstance(value, list):
        for item in value:
            _reject_host_paths(item, relative)


def _git_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _as_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {context}")
    return cast(dict[str, Any], value)


def _as_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"expected list in {context}")
    return value


def _safe_identifier(value: Any, pattern: re.Pattern[str], context: str) -> str:
    text = str(value)
    if pattern.fullmatch(text) is None:
        raise ValueError(f"invalid stable id in {context}: {text!r}")
    return text


def _relative_files(root: Path, pattern: str) -> Iterator[str]:
    for path in sorted(root.glob(pattern)):
        if path.is_file() and not path.is_symlink():
            yield path.relative_to(root).as_posix()


class DistributedDiscoveryImporter:
    """Build and materialize a canonical projection without writing source."""

    def __init__(self, source: Path, *, expected_commit: str | None = SOURCE_COMMIT) -> None:
        self.source = source.resolve()
        self.expected_commit = expected_commit
        self.reader = SourceReader(self.source)
        self.bundle = ImportBundle()
        self.pending_relations: list[RelationRecord] = []
        self.study_public: dict[str, dict[str, Any]] = {}
        self.study_status: dict[str, dict[str, Any]] = {}
        self.manifests: dict[str, dict[str, Any]] = {}
        self.manifest_paths: dict[str, str] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.site_relations: dict[str, Any] = {}
        self.paper_family_map: dict[str, Any] = {}
        self.routes: set[str] = set()

    def build(self) -> ImportBundle:
        if not self.source.is_dir():
            raise FileNotFoundError(f"source checkout does not exist: {self.source}")
        commit = _git_commit(self.source)
        if self.expected_commit is not None and commit != self.expected_commit:
            raise ValueError(
                f"source commit mismatch: expected {self.expected_commit}, observed {commit}"
            )

        self._read_required_documents()
        self._read_manifests()
        self._read_site_relations()
        self._read_paper_family_map()
        self._import_programs_and_families()
        self._import_studies()
        self._import_runs()
        self._import_claims()
        self._import_papers()
        self._import_labs_and_routes()
        self._import_benchmark()
        self._import_experiment_modules()
        self._import_synthesis()
        self._import_configurations_and_questions()
        self._finalize_routes()
        self._finalize_source_artifacts()
        self._add_program_inventory(commit)
        self._add_source_relations()
        for relation in sorted(
            self.pending_relations,
            key=lambda item: (item.type, item.source_key, item.target_key, repr(item.data)),
        ):
            if relation.type not in RELATION_TYPES:
                raise ValueError(f"undeclared relation type: {relation.type}")
            self.bundle.add_relation(relation)
        self.bundle.source_files = dict(sorted(self.reader.source_files.items()))
        return self.bundle

    def _node(
        self,
        object_type: str,
        key: str,
        label: str,
        *,
        source_path: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        if object_type not in OBJECT_TYPES:
            raise ValueError(f"undeclared object type: {object_type}")
        if key in self.bundle.objects:
            return
        source_sha = self.reader.source_files.get(source_path) if source_path else None
        self.bundle.add_object(
            NodeRecord(
                key=key,
                type=object_type,
                label=label,
                source_path=source_path,
                source_sha256=source_sha,
                attributes=attributes or {},
            )
        )

    def _relation(
        self,
        relation_type: str,
        source_key: str,
        target_key: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.pending_relations.append(
            RelationRecord(relation_type, source_key, target_key, data or {})
        )

    def _artifact(
        self, relative: str, *, label: str | None = None, attributes: dict[str, Any] | None = None
    ) -> str:
        if relative not in self.reader.source_files:
            self.reader.bytes(relative)
        key = f"artifact:{relative}"
        merged = {"category": "source_file", **(attributes or {})}
        self._node(
            "artifact",
            key,
            label or relative,
            source_path=relative,
            attributes=merged,
        )
        return key

    def _read_required_documents(self) -> None:
        required = (
            "docs/current-state.md",
            "docs/current-roadmap.md",
            "docs/theorem-roadmap.md",
        )
        optional = (
            "docs/research-output-architecture.md",
            "docs/research-governance.md",
            "docs/publication-architecture.md",
            "site/README.md",
        )
        for relative in required:
            self.reader.text(relative)
        for relative in optional:
            if (self.source / relative).is_file():
                self.reader.text(relative)

    def _read_manifests(self) -> None:
        for relative in _relative_files(self.source, "results/**/manifest.json"):
            data = _as_dict(self.reader.json(relative), relative)
            run_id = _safe_identifier(data.get("run_id"), RUN_ID_RE, relative)
            if run_id in self.manifests:
                raise ValueError(f"duplicate run id: {run_id}")
            self.manifests[run_id] = data
            self.manifest_paths[run_id] = relative

    def _read_site_relations(self) -> None:
        relative = "site/content/relations.yml"
        self.site_relations = _as_dict(self.reader.yaml(relative), relative)

    def _read_paper_family_map(self) -> None:
        relative = "docs/paper-family-map.yml"
        if (self.source / relative).is_file():
            self.paper_family_map = _as_dict(self.reader.yaml(relative), relative)

    def _import_programs_and_families(self) -> None:
        source_path = "site/content/relations.yml"
        programs = _as_dict(self.site_relations.get("programs", {}), source_path)
        for program_id, raw in sorted(programs.items()):
            data = _as_dict(raw, f"{source_path}:programs.{program_id}")
            key = f"research_program:{program_id}"
            self._node(
                "research_program",
                key,
                str(data.get("label", program_id)),
                source_path=source_path,
                attributes={"program_id": program_id},
            )
            self._relation("belongs_to_program", key, "research_program:distributed-discovery")

        families = _as_dict(self.site_relations.get("theorem_families", {}), source_path)
        for family_id, raw in sorted(families.items()):
            data = _as_dict(raw, f"{source_path}:theorem_families.{family_id}")
            self._node(
                "theorem_family",
                f"theorem_family:{family_id}",
                str(data.get("label", family_id)),
                source_path=source_path,
                attributes={"family_id": family_id},
            )

        for raw in _as_list(self.paper_family_map.get("families", []), "paper-family-map"):
            family = _as_dict(raw, "paper-family-map family")
            family_id = str(family.get("family_id"))
            key = f"theorem_family:{family_id}"
            self._node(
                "theorem_family",
                key,
                str(family.get("provisional_title", family_id)),
                source_path="docs/paper-family-map.yml",
                attributes={
                    "family_id": family_id,
                    "central_question": family.get("central_question"),
                    "likely_literature": family.get("likely_literature", []),
                    "editorial_disposition": family.get("editorial_disposition"),
                },
            )
            disposition = family.get("editorial_disposition")
            if disposition:
                decision_key = f"decision:editorial:{family_id}"
                self._node(
                    "decision",
                    decision_key,
                    f"Editorial disposition for {family_id}",
                    source_path="docs/paper-family-map.yml",
                    attributes={
                        "category": "source_decision",
                        "decision": disposition,
                        "admission_gate": family.get("admission_gate"),
                    },
                )
                self._relation("owned_by", decision_key, key)
            for index, target in enumerate(family.get("open_theorem_targets", []), start=1):
                item_key = f"roadmap_item:{family_id}:{index:02d}"
                self._node(
                    "roadmap_item",
                    item_key,
                    str(target),
                    source_path="docs/paper-family-map.yml",
                    attributes={"state": "open", "family_id": family_id},
                )
                self._relation("belongs_to_theorem_family", item_key, key)

    def _import_studies(self) -> None:
        relation_studies = _as_dict(
            self.site_relations.get("studies", {}), "site/content/relations.yml:studies"
        )
        for relative in _relative_files(self.source, "studies/*/public.yml"):
            public = _as_dict(self.reader.yaml(relative), relative)
            study_id = _safe_identifier(public.get("study_id"), STUDY_ID_RE, relative)
            if study_id in self.study_public:
                raise ValueError(f"duplicate study id: {study_id}")
            status_relative = f"{Path(relative).parent.as_posix()}/status.yml"
            status = (
                _as_dict(self.reader.yaml(status_relative), status_relative)
                if (self.source / status_relative).is_file()
                else {}
            )
            self.study_public[study_id] = public
            self.study_public[study_id]["_source_path"] = relative
            self.study_status[study_id] = status
            study_root = Path(relative).parent
            plan_relative = f"{study_root.as_posix()}/plan.md"
            plan_text = (
                self.reader.text(plan_relative) if (self.source / plan_relative).is_file() else ""
            )
            run_ids = [str(item) for item in public.get("run_ids", [])]
            run_data = [self.manifests[item] for item in run_ids if item in self.manifests]
            promotion_gate = {
                "precise_model": (self.source / study_root / "model.md").is_file(),
                "falsifiable_target": (self.source / study_root / "question.md").is_file(),
                "literature_boundary": (self.source / study_root / "literature.md").is_file(),
                "state_space_audit": "state" in plan_text.lower()
                or "enumerat" in plan_text.lower(),
                "verification_plan": "verif" in plan_text.lower(),
                "independent_verifier": any(
                    any(
                        "verification" in name
                        for name in _as_dict(run.get("outputs", {}), "outputs")
                    )
                    for run in run_data
                ),
                "corruption_plan": "corruption" in plan_text.lower()
                or any(
                    any(
                        "corruption" in name for name in _as_dict(run.get("outputs", {}), "outputs")
                    )
                    for run in run_data
                ),
                "non_overlap_statement": "overlap" in plan_text.lower(),
                "stop_condition": "stop" in plan_text.lower(),
            }
            attrs = {
                "study_id": study_id,
                "slug": public.get("slug"),
                "phase": public.get("phase"),
                "summary": public.get("summary"),
                "status": status.get("status"),
                "evidence_status": status.get("evidence_status"),
                "run_ids": run_ids,
                "claim_ids": [str(item) for item in public.get("claim_ids", [])],
                "promotion_gate": promotion_gate,
                "roadmap_state": self._roadmap_state(study_id),
            }
            self._node(
                "study",
                f"study:{study_id}",
                str(public.get("title", study_id)),
                source_path=relative,
                attributes=attrs,
            )
            configured = _as_dict(relation_studies.get(study_id, {}), f"relations:{study_id}")
            program = configured.get("program")
            family = configured.get("theorem_family")
            if program:
                self._relation(
                    "belongs_to_program",
                    f"study:{study_id}",
                    f"research_program:{program}",
                )
            if family:
                self._relation(
                    "belongs_to_theorem_family",
                    f"study:{study_id}",
                    f"theorem_family:{family}",
                )
            for raw_artifact in public.get("public_artifacts", []):
                item = _as_dict(raw_artifact, f"{relative}:public_artifacts")
                artifact_path = str(item.get("path"))
                artifact_key = self._artifact(
                    artifact_path,
                    label=str(item.get("description", artifact_path)),
                    attributes={"public": True},
                )
                self._relation("materialized_as", f"study:{study_id}", artifact_key)

    def _roadmap_state(self, study_id: str) -> str | None:
        text = self.reader.text("docs/current-roadmap.md")
        for line in text.splitlines():
            if study_id in line and re.search(r"\b(planned|pending|queued)\b", line, re.I):
                return "planned"
        return None

    def _import_runs(self) -> None:
        for run_id, manifest in sorted(self.manifests.items()):
            path = self.manifest_paths[run_id]
            study_id = _safe_identifier(manifest.get("study_id"), STUDY_ID_RE, path)
            if study_id not in self.study_public:
                raise ValueError(f"run references missing study {study_id}: {run_id}")
            outputs = _as_dict(manifest.get("outputs", {}), f"{path}:outputs")
            inputs = _as_dict(manifest.get("input_hashes", {}), f"{path}:input_hashes")
            has_output_checksum = bool(outputs) and all(
                isinstance(checksum, str) and SHA256_RE.fullmatch(checksum)
                for checksum in outputs.values()
            )
            passed = (
                manifest.get("exit_status") == 0 and manifest.get("validation_status") == "passed"
            )
            substantive = bool(passed and "/verified/" in f"/{path}")
            evidence_paths = tuple(outputs) + tuple(inputs)
            has_verifier = any(
                token in name.lower()
                for name in evidence_paths
                for token in ("verification", "verifier", "certificate")
            )
            has_corruption = any("corruption" in name.lower() for name in evidence_paths)
            study_root = Path(self.study_public[study_id]["_source_path"]).parent
            plan_path = f"{study_root.as_posix()}/plan.md"
            plan_text = self.reader.text(plan_path) if (self.source / plan_path).is_file() else ""
            attrs = {
                "run_id": run_id,
                "study_id": study_id,
                "exit_status": manifest.get("exit_status"),
                "validation_status": manifest.get("validation_status"),
                "git_commit": manifest.get("git_commit"),
                "git_dirty": manifest.get("git_dirty"),
                "has_output_checksum": has_output_checksum,
                "has_verifier": has_verifier,
                "has_corruption_test": has_corruption,
                "verifier_required": "verif" in plan_text.lower(),
                "corruption_required": "corruption" in plan_text.lower(),
                "substantive": substantive,
                "output_count": len(outputs),
            }
            run_key = f"research_run:{run_id}"
            self._node("research_run", run_key, run_id, source_path=path, attributes=attrs)
            self._relation("owned_by", run_key, f"study:{study_id}")
            for output_path, checksum in sorted(outputs.items()):
                relative = f"{Path(path).parent.as_posix()}/{output_path}"
                if not (self.source / relative).is_file():
                    raise FileNotFoundError(f"manifest output is missing: {relative}")
                actual = hashlib.sha256((self.source / relative).read_bytes()).hexdigest()
                if actual != checksum:
                    raise ValueError(f"manifest checksum mismatch: {relative}")
                category = (
                    "corruption_test"
                    if "corruption" in output_path
                    else "certificate"
                    if any(token in output_path for token in ("verification", "certificate"))
                    else "artifact"
                )
                output_key = f"{category}:{run_id}:{PurePosixPath(output_path).name}"
                self.reader.bytes(relative)
                self._node(
                    category,
                    output_key,
                    PurePosixPath(output_path).name,
                    source_path=relative,
                    attributes={"run_id": run_id, "manifest_checksum": checksum},
                )
                relation = (
                    "requires"
                    if category == "corruption_test"
                    else "verified_by"
                    if category == "certificate"
                    else "generated_by"
                )
                if category == "artifact":
                    self._relation(relation, output_key, run_key)
                else:
                    self._relation(relation, run_key, output_key)

    def _import_claims(self) -> None:
        relative = "claims/claims.yml"
        raw = _as_dict(self.reader.yaml(relative), relative)
        self.routes.add("claims.html")
        for item in _as_list(raw.get("claims"), f"{relative}:claims"):
            claim = _as_dict(item, f"{relative}:claim")
            claim_id = _safe_identifier(claim.get("id"), CLAIM_ID_RE, relative)
            if claim_id in self.claims:
                raise ValueError(f"duplicate claim id: {claim_id}")
            study_id = _safe_identifier(claim.get("study_id"), STUDY_ID_RE, claim_id)
            if study_id not in self.study_public:
                raise ValueError(f"claim references missing study: {claim_id}/{study_id}")
            run_ids = [str(value) for value in claim.get("run_ids", [])]
            for run_id in run_ids:
                if run_id not in self.manifests:
                    raise ValueError(f"claim references missing run: {claim_id}/{run_id}")
                if claim.get("status") in {"verified", "independently-reproduced"}:
                    run = self.manifests[run_id]
                    if run.get("exit_status") != 0 or run.get("validation_status") != "passed":
                        raise ValueError(
                            f"failed or preliminary run presented as substantive evidence: {claim_id}/{run_id}"
                        )
            self.claims[claim_id] = claim
            claim_key = f"claim:{claim_id}"
            self._node(
                "claim",
                claim_key,
                str(claim.get("short_name", claim_id)),
                source_path=relative,
                attributes={
                    "claim_id": claim_id,
                    "statement": claim.get("statement"),
                    "scope": claim.get("scope"),
                    "claim_type": claim.get("claim_type"),
                    "status": claim.get("status"),
                    "source_type": claim.get("source_type"),
                    "run_ids": run_ids,
                },
            )
            self._relation("owned_by", claim_key, f"study:{study_id}")
            self._relation("published_at", claim_key, "route:claims.html")
            for run_id in run_ids:
                self._relation("supports", f"research_run:{run_id}", claim_key)
            proof_path = claim.get("proof_path")
            if isinstance(proof_path, str) and proof_path:
                proof_key = f"proof:{claim_id}"
                self.reader.text(proof_path)
                self._node(
                    "proof",
                    proof_key,
                    f"Proof for {claim_id}",
                    source_path=proof_path,
                    attributes={"claim_id": claim_id},
                )
                self._relation("supports", proof_key, claim_key)
            source_reference = claim.get("source_reference")
            if isinstance(source_reference, str) and (self.source / source_reference).is_file():
                artifact_key = self._artifact(source_reference)
                self._relation("supports", artifact_key, claim_key)
            for dependency in claim.get("dependencies", []):
                self._relation("builds_on", claim_key, f"claim:{dependency}")
            for contradiction in claim.get("contradicts", []):
                self._relation("contradicts", claim_key, f"claim:{contradiction}")
            for superseded in claim.get("supersedes", []):
                self._relation("supersedes", claim_key, f"claim:{superseded}")

    def _import_papers(self) -> None:
        paper_studies: dict[str, set[str]] = defaultdict(set)
        relation_studies = _as_dict(self.site_relations.get("studies", {}), "relations:studies")
        for study_id, raw in relation_studies.items():
            details = _as_dict(raw, f"relations:{study_id}")
            for slug in details.get("paper_slugs", []):
                paper_studies[str(slug)].add(str(study_id))

        family_entries = [
            _as_dict(item, "paper-family-map family")
            for item in _as_list(self.paper_family_map.get("families", []), "paper-family-map")
        ]
        paper_roots = sorted(
            {path.parent for path in self.source.glob("papers/*/validation.json") if path.is_file()}
            | {path.parent for path in self.source.glob("papers/*/metadata.yml") if path.is_file()}
        )
        for paper_root in paper_roots:
            slug = paper_root.name
            metadata_relative = f"papers/{slug}/metadata.yml"
            validation_relative = f"papers/{slug}/validation.json"
            metadata = (
                _as_dict(self.reader.yaml(metadata_relative), metadata_relative)
                if (self.source / metadata_relative).is_file()
                else {}
            )
            validation = (
                _as_dict(self.reader.json(validation_relative), validation_relative)
                if (self.source / validation_relative).is_file()
                else {}
            )
            claim_ids: set[str] = set()
            for path in sorted(paper_root.rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix in {".tex", ".md"}:
                    relative = path.relative_to(self.source).as_posix()
                    text = self.reader.text(relative)
                    claim_ids.update(re.findall(r"DD-C-\d{4}", text))
            studies = paper_studies.get(slug, set())
            family = self._best_family(studies, family_entries)
            source_runs = validation.get("source_runs", {})
            paper_key = f"paper:{slug}"
            self._node(
                "paper",
                paper_key,
                str(metadata.get("title", slug.replace("-", " ").title())),
                source_path=metadata_relative if metadata else validation_relative,
                attributes={
                    "slug": slug,
                    "title": metadata.get("title", slug.replace("-", " ").title()),
                    "status": metadata.get(
                        "status",
                        "validated" if validation.get("compile_exit_status") == 0 else "unknown",
                    ),
                    "submitted": metadata.get("submitted", False),
                    "peer_reviewed": metadata.get("peer_reviewed", False),
                    "validation": validation,
                    "source_runs": source_runs,
                    "claim_ids": sorted(claim_ids),
                    "central_question": family.get("central_question") if family else None,
                    "likely_literature": family.get("likely_literature", []) if family else [],
                    "editorial_disposition": family.get("editorial_disposition")
                    if family
                    else None,
                },
            )
            if metadata:
                self._relation("materialized_as", paper_key, self._artifact(metadata_relative))
            if validation:
                self._relation("materialized_as", paper_key, self._artifact(validation_relative))
            for study_id in sorted(studies):
                if study_id not in self.study_public:
                    raise ValueError(f"paper relation references missing study: {slug}/{study_id}")
                self._relation("appears_in", f"study:{study_id}", paper_key)
                self._relation("builds_on", paper_key, f"study:{study_id}")
            for claim_id in sorted(claim_ids):
                if claim_id in self.claims:
                    self._relation("appears_in", f"claim:{claim_id}", paper_key)
            for run_id in self._flatten_strings(source_runs):
                if run_id in self.manifests:
                    self._relation("appears_in", f"research_run:{run_id}", paper_key)
            if family:
                family_key = f"theorem_family:{family.get('family_id')}"
                if family_key in self.bundle.objects:
                    self._relation("belongs_to_theorem_family", paper_key, family_key)
            public_url = metadata.get("public_url")
            route = (
                urlparse(str(public_url)).path.lstrip("/")
                if public_url
                else f"publications/{slug}.html"
            )
            if route.startswith("distributed-discovery/"):
                route = route.removeprefix("distributed-discovery/")
            self.routes.add(route)
            self._relation("published_at", paper_key, f"route:{route}")

    @staticmethod
    def _best_family(studies: set[str], families: list[dict[str, Any]]) -> dict[str, Any]:
        if not studies:
            return {}
        ranked = sorted(
            families,
            key=lambda item: (
                -len(
                    studies.intersection({str(value) for value in item.get("source_studies", [])})
                ),
                str(item.get("family_id", "")),
            ),
        )
        return (
            ranked[0]
            if ranked
            and studies.intersection({str(value) for value in ranked[0].get("source_studies", [])})
            else {}
        )

    @staticmethod
    def _flatten_strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            out: list[str] = []
            for item in value.values():
                out.extend(DistributedDiscoveryImporter._flatten_strings(item))
            return out
        if isinstance(value, list):
            out = []
            for item in value:
                out.extend(DistributedDiscoveryImporter._flatten_strings(item))
            return out
        return []

    def _import_labs_and_routes(self) -> None:
        relation_studies = _as_dict(self.site_relations.get("studies", {}), "relations:studies")
        for study_id, raw in sorted(relation_studies.items()):
            details = _as_dict(raw, f"relations:{study_id}")
            if study_id not in self.study_public:
                raise ValueError(f"site relation references missing study: {study_id}")
            study = self.study_public[study_id]
            study_route = f"research/{study.get('slug')}.html"
            self.routes.add(study_route)
            self._relation("published_at", f"study:{study_id}", f"route:{study_route}")
            for claim_id in study.get("claim_ids", []):
                if str(claim_id) in self.claims:
                    self._relation("published_at", f"claim:{claim_id}", f"route:{study_route}")
            for slug in details.get("lab_slugs", []):
                lab_key = f"lab:{slug}"
                self._node(
                    "lab",
                    lab_key,
                    f"{str(slug).replace('-', ' ').title()} Lab",
                    source_path="site/content/relations.yml",
                    attributes={"slug": slug, "output_connected": True},
                )
                lab_route = f"labs/{slug}.html"
                self.routes.add(lab_route)
                self._relation("exposed_by_lab", f"study:{study_id}", lab_key)
                self._relation("builds_on", lab_key, f"study:{study_id}")
                self._relation("published_at", lab_key, f"route:{lab_route}")
            for route in details.get("experiment_routes", []):
                self.routes.add(str(route))
                self._relation("published_at", f"study:{study_id}", f"route:{route}")
            for route in details.get("data_routes", []):
                self.routes.add(str(route))
                self._relation("materialized_as", f"study:{study_id}", f"route:{route}")

    def _latest_output(self, study_id: str, basename: str) -> tuple[str, str] | None:
        candidates: list[tuple[str, str]] = []
        for run_id, manifest in self.manifests.items():
            if (
                manifest.get("study_id") != study_id
                or manifest.get("validation_status") != "passed"
            ):
                continue
            for output in _as_dict(manifest.get("outputs", {}), f"{run_id}:outputs"):
                if PurePosixPath(output).name == basename:
                    relative = f"{Path(self.manifest_paths[run_id]).parent.as_posix()}/{output}"
                    candidates.append((run_id, relative))
        return sorted(candidates)[-1] if candidates else None

    def _import_benchmark(self) -> None:
        selected = self._latest_output("DD-010", "task-registry.json")
        if selected is None:
            return
        run_id, relative = selected
        tasks = _as_list(self.reader.json(relative), relative)
        registry_artifact = self._artifact(relative, attributes={"registry": "DiscoveryBench"})
        for raw in tasks:
            task = _as_dict(raw, relative)
            task_id = str(task.get("task_id"))
            key = f"benchmark_task:{task_id}"
            self._node(
                "benchmark_task",
                key,
                task_id,
                source_path=relative,
                attributes=task,
            )
            self._relation("generated_by", key, f"research_run:{run_id}")
            self._relation("derived_from_source", key, registry_artifact)
            studies: set[str] = set()
            for claim_id in task.get("reference_claims", []):
                claim_text = str(claim_id)
                if claim_text not in self.claims:
                    raise ValueError(
                        f"benchmark task references missing claim: {task_id}/{claim_text}"
                    )
                self._relation("tests", key, f"claim:{claim_text}")
                studies.add(str(self.claims[claim_text]["study_id"]))
            for study_id in sorted(studies):
                self._relation("builds_on", key, f"study:{study_id}")
            for reference_run in task.get("reference_runs", []):
                if str(reference_run) not in self.manifests:
                    raise ValueError(
                        f"benchmark task references missing run: {task_id}/{reference_run}"
                    )
                self._relation("benchmarked_by", f"research_run:{reference_run}", key)

    def _import_experiment_modules(self) -> None:
        outputs = (
            ("design-registry.json", "design"),
            ("hypotheses.json", "hypothesis"),
            ("outcomes.json", "outcome"),
            ("treatment-matrix.json", "treatment"),
        )
        for basename, category in outputs:
            selected = self._latest_output("DD-011", basename)
            if selected is None:
                continue
            run_id, relative = selected
            data = self.reader.json(relative)
            artifact_key = self._artifact(relative, attributes={"registry": "Experiment Kit"})
            rows: list[dict[str, Any]] = []
            if isinstance(data, list):
                rows = [_as_dict(item, relative) for item in data]
            elif isinstance(data, dict):
                if basename == "design-registry.json":
                    rows = [_as_dict(item, relative) for item in data.get("alternatives", [])]
                elif isinstance(data.get("rows"), list):
                    rows = [_as_dict(item, relative) for item in data["rows"]]
            for index, row in enumerate(rows, start=1):
                identity = next(
                    (
                        str(row[field])
                        for field in (
                            "design_id",
                            "hypothesis_id",
                            "outcome_id",
                            "cell_id",
                            "treatment_id",
                        )
                        if field in row
                    ),
                    f"row-{index:04d}",
                )
                if category == "hypothesis":
                    object_type = "hypothesis"
                    key = f"hypothesis:DD-011:{identity}"
                else:
                    object_type = "experiment_module"
                    key = f"experiment_module:{category}:{identity}"
                self._node(object_type, key, identity, source_path=relative, attributes=row)
                self._relation("generated_by", key, f"research_run:{run_id}")
                self._relation("derived_from_source", key, artifact_key)
                self._relation("owned_by", key, "study:DD-011")
                for claim_id in self.study_public["DD-011"].get("claim_ids", []):
                    if str(claim_id) in self.claims:
                        self._relation("motivates_experiment", f"claim:{claim_id}", key)

    def _import_synthesis(self) -> None:
        for relative in _relative_files(
            self.source, "synthesis/architecture-of-distributed-discovery/*"
        ):
            if relative.endswith((".yml", ".md")):
                if relative.endswith(".yml"):
                    self.reader.yaml(relative)
                else:
                    self.reader.text(relative)
                self._artifact(relative, attributes={"category": "living_synthesis_source"})
        chapter_relative = "synthesis/architecture-of-distributed-discovery/chapter-map.yml"
        if not (self.source / chapter_relative).is_file():
            return
        chapter_map = _as_dict(self.reader.yaml(chapter_relative), chapter_relative)
        for raw in _as_list(chapter_map.get("chapters", []), f"{chapter_relative}:chapters"):
            chapter = _as_dict(raw, chapter_relative)
            chapter_id = str(chapter.get("chapter"))
            chapter_key = f"chapter:{chapter_id}"
            self._node(
                "chapter",
                chapter_key,
                chapter_id.replace("-", " ").title(),
                source_path=chapter_relative,
                attributes={
                    "maturity": chapter.get("maturity"),
                    "missing_theorem_gate": chapter.get("missing_theorem_gate"),
                    "duplication_risk": chapter.get("duplication_risk"),
                },
            )
            for study_id in chapter.get("source_studies", []):
                if str(study_id) in self.study_public:
                    self._relation("appears_in", f"study:{study_id}", chapter_key)
            for claim_id in chapter.get("source_claims", []):
                if str(claim_id) in self.claims:
                    self._relation("appears_in", f"claim:{claim_id}", chapter_key)
            for slug in chapter.get("source_papers", []):
                paper_key = f"paper:{slug}"
                if paper_key in self.bundle.objects:
                    self._relation("appears_in", paper_key, chapter_key)

    def _import_configurations_and_questions(self) -> None:
        for relative in _relative_files(self.source, "studies/*/configs/*.yml"):
            data = self.reader.yaml(relative)
            study_dir = Path(relative).parts[1]
            study_id = study_dir.split("-", 2)[0] + "-" + study_dir.split("-", 2)[1]
            if study_id not in self.study_public:
                continue
            key = f"configuration:{relative}"
            self._node(
                "configuration",
                key,
                Path(relative).name,
                source_path=relative,
                attributes={
                    "study_id": study_id,
                    "schema_version": _as_dict(data, relative).get("schema_version")
                    if isinstance(data, dict)
                    else None,
                },
            )
            self._relation("owned_by", key, f"study:{study_id}")
        for relative in _relative_files(self.source, "studies/*/question.md"):
            text = self.reader.text(relative)
            study_dir = Path(relative).parts[1]
            match = re.match(r"(DD-\d{3}[A-Z]?)", study_dir)
            if match is None or match.group(1) not in self.study_public:
                continue
            study_id = match.group(1)
            title = next(
                (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")),
                f"{study_id} research question",
            )
            key = f"research_question:{study_id}"
            self._node(
                "research_question",
                key,
                title,
                source_path=relative,
                attributes={"study_id": study_id},
            )
            self._relation("owned_by", key, f"study:{study_id}")

    def _finalize_routes(self) -> None:
        for relative in _relative_files(self.source, "site/src/*.html"):
            self.reader.text(relative)
            self.routes.add(Path(relative).name)
        for source_relative in (
            "src/distributed_discovery/site/build.py",
            "src/distributed_discovery/site/core_labs.py",
        ):
            if (self.source / source_relative).is_file():
                text = self.reader.text(source_relative)
                self.routes.update(ROUTE_LITERAL_RE.findall(text))
        self.routes.add("data/routes.json")
        for route in sorted(self.routes):
            path = PurePosixPath(route)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe public route: {route}")
            if len(path.parts) == 2 and path.parts[0] == "labs" and path.suffix == ".html":
                slug = path.stem
                lab_key = f"lab:{slug}"
                if lab_key not in self.bundle.objects:
                    self._node(
                        "lab",
                        lab_key,
                        f"{slug.replace('-', ' ').title()} Lab",
                        source_path="src/distributed_discovery/site/build.py",
                        attributes={"slug": slug, "legacy_route": slug == "audience"},
                    )
                    if slug == "audience":
                        self._relation("exposed_by_lab", "study:DD-013", lab_key)
                        self._relation("builds_on", lab_key, "study:DD-013")
                        self._relation("published_at", lab_key, f"route:{route}")
            self._node(
                "route",
                f"route:{route}",
                route,
                source_path="site/content/relations.yml",
                attributes={"path": route, "kind": path.suffix.lstrip(".")},
            )

    def _finalize_source_artifacts(self) -> None:
        for relative in sorted(self.reader.source_files):
            self._artifact(relative)

    def _add_program_inventory(self, commit: str) -> None:
        declared = self._declared_counts()
        counts = Counter(record.type for record in self.bundle.objects.values())
        passing = sum(
            manifest.get("exit_status") == 0 and manifest.get("validation_status") == "passed"
            for manifest in self.manifests.values()
        )
        computed = {
            "ledger_claims": counts["claim"],
            "passing_immutable_runs": passing,
            "total_manifests": len(self.manifests),
            "registered_studies": counts["study"],
            "validated_project_papers": sum(
                record.type == "paper"
                and record.attributes.get("validation", {}).get("compile_exit_status") == 0
                for record in self.bundle.objects.values()
            ),
            "laboratory_routes": counts["lab"],
            "public_html_routes": sum(
                record.type == "route" and record.attributes.get("kind") == "html"
                for record in self.bundle.objects.values()
            ),
        }
        self.bundle.declared_counts = declared
        self._node(
            "research_program",
            "research_program:distributed-discovery",
            "Distributed Discovery",
            source_path="docs/current-state.md",
            attributes={
                "repository": SOURCE_REPOSITORY,
                "source_commit": commit,
                "source_file_count": len(self.reader.source_files),
                "declared_counts": declared,
                "computed_counts": computed,
            },
        )

    def _declared_counts(self) -> dict[str, int]:
        text = self.reader.text("docs/current-state.md")
        mapping = {
            "Ledger claims": "ledger_claims",
            "Registered studies": "registered_studies",
            "Public HTML routes": "public_html_routes",
            "Laboratory routes": "laboratory_routes",
            "Validated project papers": "validated_project_papers",
        }
        out: dict[str, int] = {}
        for label, key in mapping.items():
            match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*(\d+)", text)
            if match:
                out[key] = int(match.group(1))
        run_match = re.search(r"\|\s*Passing immutable runs\s*\|\s*(\d+)\s+of\s+(\d+)", text)
        if run_match:
            out["passing_immutable_runs"] = int(run_match.group(1))
            out["total_manifests"] = int(run_match.group(2))
        return out

    def _add_source_relations(self) -> None:
        for record in list(self.bundle.objects.values()):
            if not record.source_path or record.type == "artifact":
                continue
            artifact_key = f"artifact:{record.source_path}"
            if artifact_key in self.bundle.objects:
                self._relation("derived_from_source", record.key, artifact_key)

    def materialize(self, runtime: Runtime) -> dict[str, str]:
        if not self.bundle.objects:
            self.build()
        object_ids: dict[str, str] = {}
        for record in sorted(self.bundle.objects.values(), key=lambda item: item.key):
            obj = runtime.graph.add_object(record.type, record.data(), actor="dd.importer")
            object_ids[record.key] = obj.id
        for relation in sorted(
            self.bundle.relations,
            key=lambda item: (item.type, item.source_key, item.target_key, repr(item.data)),
        ):
            runtime.graph.add_relation(
                object_ids[relation.source_key],
                object_ids[relation.target_key],
                relation.type,
                relation.data,
                actor="dd.importer",
            )
        runtime.graph.emit(
            Event(
                id=runtime.graph.ids.event(),
                type="dd.import.completed",
                payload={
                    "source_repository": SOURCE_REPOSITORY,
                    "source_commit": self.bundle.objects[
                        "research_program:distributed-discovery"
                    ].attributes["source_commit"],
                    "object_count": len(self.bundle.objects),
                    "relation_count": len(self.bundle.relations),
                    "source_file_count": len(self.bundle.source_files),
                },
                actor="dd.importer",
                timestamp=runtime.graph.clock.now(),
            )
        )
        runtime.run_until_idle()
        if runtime.errors:
            messages = "; ".join(f"{item.behavior}: {item.message}" for item in runtime.errors)
            raise RuntimeError(f"ActiveGraph audit behavior failed: {messages}")
        return object_ids


def import_source(source: Path, runtime: Runtime) -> ImportBundle:
    importer = DistributedDiscoveryImporter(source)
    bundle = importer.build()
    importer.materialize(runtime)
    return bundle
