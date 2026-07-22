# Adoption decision v3

## Decision: Adopt optional structural relationship auditing only

The genuinely unseen DD-022 snapshot
`504c9fb9c1039b21bf57f83a794f9f0da3e64afa` passed the frozen importer without
code, schema, alias, behavior, or audit-rule changes. It materialized 1,758
objects, 2,764 relations, and 4,555 events from 694 recognized files. The first
rebuild and two independent delete-and-rebuild verification attempts were
byte-identical, and every event log replayed to the expected counts.

Structural relationship auditing passed the decisive holdout. ActiveGraph
reconstructed all 181 canonical registry relations exactly, with no omissions,
type mismatches, reverse-link gaps, or ambiguities. All 40 required reverse
links were present. Thirty extra inferred synthesis relations remain visibly
separate and advisory; they do not replace or modify the canonical registry.
Dangling-relation, orphan-claim, stale-status, reverse-link, and public-safety
checks passed. Current-state reconciliation produced one reviewable warning for
the declared versus computed laboratory-route count and no automatic mutation.

The evidence heuristic did not improve. Its 13 error-severity findings are the
same reviewed set seen during calibration: zero current primary gaps, five
historical exceptions, two preliminary or failed runs, and six policy
mismatches. The explicit role-only interpretation classifies five findings as
current primary, one as current supporting, five as superseded/historical, two
as preliminary/failed, and none as unknown. It removes historical and
preliminary findings from a current gate but leaves five required-gate
candidates, all known false positives. The projected required-gate
false-positive rate therefore remains 100 percent, and precision is undefined
because there are no true positive gaps in the reviewed set. This proposal is
explicit and tested for completeness, but it is not independently validated;
required evidence-audit CI remains disabled.

Optional adoption is limited to structural relationship reconstruction,
reverse-link audit, stale-state reconciliation, public-safety audit, and
fork/diff for workflow plans. ActiveGraph remains independent, disposable, and
advisory. Git, the canonical relationship registry, and existing exact
computation/verification workflows remain authoritative. No SQLite, scientific
artifact, or ActiveGraph-only fact may become canonical state.

