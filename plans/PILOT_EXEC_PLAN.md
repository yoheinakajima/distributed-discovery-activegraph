# ActiveGraph control-plane pilot ExecPlan

## Purpose and intended outcome

Prove or refute, with deterministic visible artifacts, that ActiveGraph can be
a disposable operational control plane for Distributed Discovery while Git
remains the canonical scientific record.

## Current state

The public pilot repository, issue #1, implementation branch, and exact source
pins have been established. No generated graph, audit, or database exists yet.

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
- **M1 (active):** implement domain pack, importer, audit behaviors, CLI, and
  canonical exporters.
- **M2 (pending):** import the pinned source and produce deterministic exports.
- **M3 (pending):** prove rebuild, replay, fork/diff, no-hidden-state, and
  public-safety properties.
- **M4 (pending):** complete docs, full validation, CI, merge, and adoption
  recommendation.

## Progress checklist

- [x] Inspect live source repository heads without modifying source checkouts.
- [x] Create the separate public pilot repository.
- [x] Record exact dependency and source pins.
- [x] Open the single pilot issue and branch; open the draft PR after this
  checkpoint commit is pushed.
- [ ] Implement and validate M1.
- [ ] Generate and validate M2 artifacts.
- [ ] Complete M3 determinism and safety proofs.
- [ ] Merge after CI passes.

## Discoveries and surprises

- The local ActiveGraph checkout is behind the live default branch, so the
  pilot will use an isolated clone at the recorded live commit.
- GitHub CLI OAuth is unavailable, but SSH and the connected GitHub app are
  authenticated; repository creation used the explicitly authorized signed-in
  browser session.

## Decision log

- `2026-07-22`: use ignored `.sources/` clones pinned by commit; never import
  from the concurrently advancing local Distributed Discovery checkout.
- `2026-07-22`: initialize `main` with only the pilot contract and locks, then
  perform all implementation on `pilot/distributed-discovery-activegraph`.
- `2026-07-22`: issue #1 owns the bounded pilot. The implementation branch is
  the only active substantive branch and M1 is the only active milestone.

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

Repository contract, source lock, packaging scaffold, and this living plan.

## Blockers

None.

## Recovery and restart instructions

Work only in this repository. Inspect `git status --short --branch`, read this
plan, verify `config/source-lock.yml`, and resume the only active milestone.
Never repoint an existing source clone to a moving branch.

## Outcome and retrospective

Pending.
