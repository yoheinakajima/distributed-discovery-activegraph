# Adoption decision v2

## Decision: continue bounded pilot

The multi-snapshot trial supports ActiveGraph's relationship reconstruction but
does not yet justify declaring the optional audit layer adopted. All four
calibration snapshots imported with one schema-based maintenance change and no
commit-specific branches. Every snapshot rebuilt byte-for-byte and replayed.
The two snapshots containing the canonical relationship registry reproduced all
166 and 174 expected relations respectively, with no omissions or type
mismatches and complete reverse-link coverage. Thirty additional inferred
relations were visible and reviewable rather than silently replacing the
registry.

Audit precision is the limiting factor. The original 13 errors classify as zero
current primary-evidence gaps, five historical exceptions, two explicitly
preliminary runs, and six importer-policy mismatches. The false-positive rate
among current-evidence findings is therefore 100%, and the defined advisory-noise
rate across reviewed errors and warnings is also 100%. These rates describe this
bounded review only and make no statistical-significance claim. They show that
the current study-wide verifier/corruption heuristic is unsuitable for required
CI even though the structural audits are stable.

Raw graph and relation diffs are deterministic but large. Count summaries,
schema drift, audit deltas, and registry comparisons are readable review
surfaces. The captured local import/export observations stayed below 13 seconds
and 27.0 MB peak traced memory; these single-process measurements are
operational observations, not benchmarks, and the exact capture remains isolated
in `exports/comparison/performance.json`.

The strongest adoption test remains unavailable: Distributed Discovery had no
merged DD-022 final commit when the importer froze. A no-code-change holdout was
therefore not attempted. Continue the bounded pilot until a genuinely unseen
holdout imports under checksum
`b9a0f4409e3aa53072f391f279cf33dbc11041f5755534177368386551ea79df` and the
proposed per-run evidence-role policy reduces audit noise without weakening
structural or public-safety gates.

Git remains authoritative for science. Existing Python and Make workflows
remain authoritative for computation and verification. ActiveGraph remains an
independent, disposable, advisory auditor and may not mutate canonical source.
