# ActiveGraph control-plane pilot ExecPlan

## Purpose and intended outcome

Prove or refute, with deterministic visible artifacts, that ActiveGraph can be
a disposable operational control plane for Distributed Discovery while Git
remains the canonical scientific record.

## Current state

The public pilot repository, issue #1, implementation branch, draft PR #2, and
exact source pins are established. The pinned snapshot materializes to 1,656
objects, 2,548 relations, and 4,237 events; all required exports reproduce
byte-for-byte and the deterministic fork replays successfully.

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
- **M4 (active):** complete docs, full validation, CI, merge, and adoption
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
- [ ] Merge after CI passes.

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
  13 substantive verifier/corruption gaps and nine warnings associated with
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

Pending.
