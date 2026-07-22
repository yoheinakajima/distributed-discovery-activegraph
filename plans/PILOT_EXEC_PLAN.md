# ActiveGraph control-plane pilot ExecPlan

## Purpose and intended outcome

Prove or refute, with deterministic visible artifacts, that ActiveGraph can be
a disposable operational control plane for Distributed Discovery while Git
remains the canonical scientific record.

## Current state

The original pilot and the multi-snapshot schema-drift trial are complete. The
baseline snapshot materializes to 1,656 objects, 2,548 relations, and 4,237
events. Four calibration snapshots import, rebuild byte-for-byte, and replay;
the importer is frozen, the 13 original errors are triaged, relationship
registries are compared, and adoption decision v2 is to continue bounded pilot.

## Scope

Read-only import of an isolated pinned Distributed Discovery clone; a custom
ActiveGraph pack; deterministic reactive audits, exports, replay, rebuild, and
fork/diff demonstration; documentation; tests; CI; one issue, branch, and PR.

## Non-goals

No migration, source-repository mutation, research result, claim, study, paper,
immutable research run, LLM call, paid API call, or production deployment.

## Assumptions

Python 3.11+ and `uv` are available. GitHub remains authoritative. The local
SQLite store is disposable and ignored. Imported schemas may evolve, so the
importer must fail safely and preserve source checksums.

## Milestones

- **M0 (complete):** establish isolated repository, source locks, issue, branch,
  and early draft PR.
- **M1 (complete):** implement domain pack, importer, audit behaviors, CLI, and
  canonical exporters.
- **M2 (complete):** import the pinned source and produce deterministic exports.
- **M3 (complete):** prove rebuild, replay, fork/diff, no-hidden-state, and
  public-safety properties.
- **M4 (complete):** complete docs, full validation, CI, merge, and adoption
  recommendation.

## Progress checklist

- [x] Inspect live source repository heads without modifying source checkouts.
- [x] Create the separate public pilot repository.
- [x] Record exact dependency and source pins.
- [x] Open the single pilot issue and branch; open the draft PR after this
  checkpoint commit is pushed.
- [x] Implement and validate M1.
- [x] Generate and validate M2 artifacts.
- [x] Complete M3 determinism and safety proofs.
- [x] Merge after CI passes.

## Discoveries and surprises

- The local ActiveGraph checkout is behind the live default branch, so the
  pilot will use an isolated clone at the recorded live commit.
- GitHub CLI OAuth is unavailable, but SSH and the connected GitHub app are
  authenticated; repository creation used the explicitly authorized signed-in
  browser session.
- The first `uv sync --extra dev` stopped before installing the pilot because
  Hatchling rejects direct Git references unless
  `tool.hatch.metadata.allow-direct-references = true` is explicit. The exact
  commit pins were preserved and the packaging opt-in was added before retry.
- The first importer pass rejected `site/build.py` because the source code
  contains `/Users/` inside its own public-safety regex. Raw code and prose are
  now checksum-recorded but safety rejection applies to parsed/exportable data,
  avoiding a false positive without weakening the export gate.
- The first persisted materialization reached the import-complete signal but
  called raw `Graph.emit` with the behavior-wrapper signature. ActiveGraph's
  raw graph requires an explicit immutable `Event`; the importer now constructs
  that event with deterministic id, actor, payload, and frozen timestamp.
- Literal public/study status strings use compatible but different vocabulary;
  stale-state checks now flag semantic completion/failure contradictions rather
  than harmless label differences.
- The pinned source passes structural, orphan, reverse-link, stale-state,
  current-count, and public-safety audits. The unverified-run detector preserves
  13 substantive verifier/corruption gaps and eight warnings associated with
  failed or preliminary manifests; advisory gates produce 30 review records.

## Decision log

- `2026-07-22`: use ignored `.sources/` clones pinned by commit; never import
  from the concurrently advancing local Distributed Discovery checkout.
- `2026-07-22`: initialize `main` with only the pilot contract and locks, then
  perform all implementation on `pilot/distributed-discovery-activegraph`.
- `2026-07-22`: issue #1 owns the bounded pilot. The implementation branch is
  the only active substantive branch and M1 is the only active milestone.
- `2026-07-22`: retain the initial Hatchling direct-reference failure as a
  packaging-gate observation; authorize direct references only because every
  Git dependency is pinned to a full commit in both `pyproject.toml` and the
  source lock.
- `2026-07-22`: scan parsed YAML/JSON and exported graph payloads for host
  paths; do not interpret literal scanner patterns inside source code as leaked
  local paths.
- `2026-07-22`: treat the public claims index as a public role for every ledger
  claim, and infer verifier/corruption requirements only from visible study
  plans and manifest evidence rather than imposing a policy absent from source.
- `2026-07-22`: recommend adoption only for relationship/audit tooling; retain
  Git and existing exact-computation workflows as authoritative.

## Validation strategy

Use deterministic fixtures, schema validation, importer rejection cases,
object/relation link tests, behavior tests, byte-for-byte export comparison,
delete-and-rebuild, replay, fork/diff, source-pin, Git tracking, host-path,
secret, and no-network/no-LLM tests. Run lint, strict typing, tests, and a clean
clone validation before merge.

## Commands and expected observations

- `uv sync --extra dev`: installs exact Git commits and locked Python packages.
- `ddgraph rebuild --source .sources/distributed-discovery --output exports/current`:
  produces the required canonical export set and an ignored SQLite store.
- `ddgraph verify --source .sources/distributed-discovery --exports exports/current`:
  reports byte-identical rebuilding, replay, schema, and safety success.

## Artifacts produced

Repository contract, source lock, domain pack, importer, behaviors, CLI,
canonical exports, tests, fork/diff fixture, source-of-truth record, adoption
decision, and this living plan.

## Blockers

None.

## Recovery and restart instructions

Work only in this repository. Inspect `git status --short --branch`, read this
plan, verify `config/source-lock.yml`, and resume the only active milestone.
Never repoint an existing source clone to a moving branch.

## Outcome and retrospective

PR #2 passed local and GitHub validation and was squash-merged to `main` as
`88e491a3cd48b035ec0a64c420c81492c5913d24`. A post-merge push workflow also
passed. The pilot met the rebuild, replay, export, safety, and fork/diff gates
without modifying any source repository. Its bounded recommendation is to use
ActiveGraph only for relationship and audit tooling while Git remains the
scientific authority. The next adoption gate is a multi-snapshot schema-drift
trial; no broader migration is authorized by this outcome.

## DD-022 unseen holdout trial

Issue #5 owns the decisive unseen-snapshot trial on the single branch
`pilot/dd022-unseen-holdout`. The input is the isolated, clean, detached
Distributed Discovery snapshot
`504c9fb9c1039b21bf57f83a794f9f0da3e64afa`; no moving source checkout is used.
Before the first import, the frozen importer was verified at SHA-256
`b9a0f4409e3aa53072f391f279cf33dbc11041f5755534177368386551ea79df`.
The source Git tree is `f2d6e48e9cbd975743add323cef2a38e5f6f86fa`, and the SHA-256 of its complete
tracked-tree listing is
`dfebf9c4f819539547b7fde65c77b0f3d68e09fab7ea31765fbb865724733e0d`.

### Holdout progress

- [x] Verify pilot main, importer checksum, and the unseen source commit.
- [x] Create issue #5 and branch `pilot/dd022-unseen-holdout`.
- [x] Record the holdout source lock and pre-import freeze checkpoint.
- [x] Open the early draft PR (#6).
- [x] Attempt and preserve the first no-code-change import.
- [ ] Run two delete-and-rebuild checks and replay.
- [ ] Compare the holdout relationship registry and structural audits.
- [ ] Complete the explicit advisory evidence-role analysis.
- [ ] Write adoption decision v3 and the bounded integration proposal.
- [ ] Run full local and GitHub validation, merge, and close issue #5.

### Holdout decision log

- `2026-07-22`: treat `504c9fb9` as genuinely unseen because it was not present
  during calibration or importer freeze; pin its exact tree before import.
- `2026-07-22`: preserve all baseline and calibration exports unchanged and
  write only under `exports/holdout/` and `exports/holdout-comparison/`.
- `2026-07-22`: the first frozen import succeeded with 1,758 objects, 2,764
  relations, and 4,555 events. The first delete-and-rebuild was byte-identical,
  replay passed, and all 181 canonical relations matched. Preserve the 13
  unchanged evidence-heuristic errors separately from the passing structural
  result.

## Multi-snapshot schema-drift and audit-stability trial

Issue #3 owns a second bounded evaluation on the single branch
`pilot/multi-snapshot-schema-drift`. The trial preserves `exports/current` as
the original result and imports four exact Distributed Discovery commits from
isolated, read-only snapshot clones. It will measure deterministic rebuilds,
schema and audit drift, canonical relationship-registry agreement, performance,
the original 13 evidence gaps, and two fork/diff fixtures. After the four
calibration snapshots import, the importer checksum will be frozen; a merged
DD-022 commit will be attempted only as a no-code-change holdout if one exists.

### Trial progress

- [x] Verify pilot `main` and live Distributed Discovery `main`.
- [x] Create issue #3 and record the four exact source pins.
- [x] Create the trial branch and early draft PR (#4).
- [x] Import, export, rebuild, replay, and compare four calibration snapshots.
- [x] Triage all 13 original substantive findings and compare registries.
- [x] Freeze the importer and attempt a DD-022 holdout if available.
- [x] Complete reports, adoption decision v2, validation, CI, merge, and closure.

### Trial decision log

- `2026-07-22`: treat `06523c8d9ff6d0f4e66457997f5094b69065ec95`
  as the fourth calibration snapshot because it remains live `main`; no DD-022
  final commit exists before importer work begins.
- `2026-07-22`: create one immutable ignored clone per snapshot rather than
  repointing the existing baseline source checkout.
- `2026-07-22`: freeze the importer after one schema-based maintenance change
  at SHA-256 `b9a0f4409e3aa53072f391f279cf33dbc11041f5755534177368386551ea79df`;
  the change treats a missing relationship registry as an earlier valid schema,
  without naming a commit or inventing relations.
- `2026-07-22`: no DD-022 final commit was available before or immediately after
  freeze; live `main` remained `06523c8d`. Record the unavailable holdout rather
  than tuning to concurrent unmerged work.
- `2026-07-22`: choose adoption decision v2 option 2, continue bounded pilot.
  Relationship reconstruction exactly covers the two available registries, but
  the evidence heuristic's bounded false-positive and advisory-noise rates are
  both 100%, and no unseen holdout exists.

### Trial discoveries

- All four snapshots import with 1,473/1,868, 1,602/2,130, 1,656/2,548,
  and 1,713/2,659 materialized objects/relations respectively; every rebuild is
  byte-identical and every event log replays.
- The relationship registry first appears between the second and third
  snapshots. ActiveGraph exactly reconstructs all 166 baseline and 174 DD-021
  canonical relations, misses none, has no type mismatch, and supplies full
  reverse-link coverage. Thirty additional inferred synthesis/legacy relations
  remain visibly separate.
- The original 13 errors classify as A=0, B=5, C=2, D=6. The eight baseline
  warnings are expected historical/preliminary conditions. None should block
  CI under the reviewed policy.
- Deterministic summary/count artifacts are readable; raw graph/relation diffs
  span hundreds of hunks and are supporting rather than primary review surfaces.
- The captured single-process local import/export observations remain below 13
  seconds and 27.0 MB peak traced memory. No statistical claim is made; exact
  operational measurements remain isolated from deterministic content.

### Trial outcome and retrospective

PR #4 passed GitHub Actions run `29957486211` and was squash-merged to `main` as
`086a220e6b0eeab0a61acd48ac7c6189fb8e4b26`; issue #3 closed automatically as
completed. The post-merge push workflow for this closeout also passed. The trial
met every normal completion floor except an unavailable DD-022 holdout, which
was correctly recorded rather than simulated. The exact next gate is to test
the frozen importer, without code changes, against the first merged DD-022 final
commit and then reconsider audit policy precision. No canonical integration or
broader adoption is authorized before that gate.
