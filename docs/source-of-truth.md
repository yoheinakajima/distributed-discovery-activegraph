# Source-of-truth boundary

Git is authoritative for scientific definitions, proofs, claims, immutable runs,
papers, public metadata, and decisions after approval. Existing Distributed
Discovery Python and Make targets remain the computation and verification
engine.

ActiveGraph is authoritative only for the operational event sequence, queued
work, and reactive state during a particular pilot run. Its ignored SQLite file
is disposable. A scientific result is never authoritative merely because it
exists in ActiveGraph; an approved deterministic artifact must be merged into
the canonical scientific repository.

This repository is an integration and audit artifact, not the scientific source
of truth. Every useful projection and audit is exported to visible Git files,
and a clean import from the pinned source regenerates them without an LLM.

The multi-snapshot trial does not change this split. Each historical checkout is
clean, commit-pinned, and read-only after setup. Cross-snapshot comparisons and
triage reports are Git-visible advisory evidence about the importer, not new
scientific facts. Performance timestamps are isolated in the explicitly
non-deterministic `exports/comparison/performance.json`; canonical graph content
contains no operational timestamps.
