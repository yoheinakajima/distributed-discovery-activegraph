# Proposed future canonical integration

No write to Distributed Discovery is part of this pilot. Adoption decision v3
supports a future, separately reviewed canonical PR containing only:

- `docs/activegraph-audit-boundary.md`, documenting advisory status and the
  authority of Git, the canonical relationship registry, and existing Make and
  Python verification workflows;
- `config/external-audits/activegraph.yml`, pinning this external auditor,
  importer checksum, and non-blocking policy;
- one infrastructure link to this pilot repository;
- optional documentation for an advisory workflow.

That future PR must not commit SQLite, move scientific artifacts into
ActiveGraph, promote claims automatically, mutate source automatically, require
the evidence heuristic in CI, or replace the canonical relationship registry.
The first exact next step is an independent human review of PR #6 and its
holdout artifacts before drafting any canonical change.
