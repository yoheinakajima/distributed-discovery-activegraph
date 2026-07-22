# Adoption decision

## Recommendation: adopt only for relationship/audit tooling

The pilot demonstrates useful deterministic relationship materialization,
reactive integrity checks, replay, and fork/diff analysis. Git diffs remain
reviewable because the complete projection and audit are ordinary files. The
site relationship graph, claim/run links, and editorial gates are a good fit.

The cost is a second ontology, importer maintenance, an event-store runtime,
and risk that operators mistake workflow state for scientific truth. Exact
research computation itself gains little from migration and must stay in the
existing reproducible Python/Make workflow. SQLite adds operator burden but is
disposable; deterministic materialization and clean rebuild prevent it from
becoming a duplicate authority.

Use ActiveGraph only as an optional control plane for cross-cutting
relationship audits and candidate workflow decisions. Keep Git authoritative,
require deterministic exports in review, and do not migrate claims, proofs,
runs, papers, or numerical verification into the event store. Before broader
adoption, run the importer against several future source commits and measure
schema-drift maintenance and review usefulness.
