# Proposed canonical integration

No write-back or canonical change is authorized by this trial. Because adoption
decision v2 is **continue bounded pilot**, defer integration until the frozen
importer passes a genuinely unseen DD-022 holdout and the evidence-role policy
is re-evaluated.

If those gates pass and optional adoption is later approved, keep the proposal
to exactly this bounded shape:

- `docs/activegraph-audit-boundary.md` documenting advisory status and Git/Make
  authority;
- `config/external-audits/activegraph.yml` containing the external repository,
  frozen importer checksum, and non-blocking policy;
- one infrastructure link to this pilot repository;
- one aggregate evidence-gap triage issue rather than 13 issues;
- optional advisory CI only after a measured precision improvement.

Do not commit SQLite, move claims, proofs, runs, or papers into ActiveGraph,
make the audit immediately required, promote claims automatically, or mutate
scientific files from an ActiveGraph finding.
