# Distributed Discovery ActiveGraph pilot

This separate repository evaluates ActiveGraph as an operational control plane
and auditable workflow runtime for Distributed Discovery. GitHub repository
files remain the canonical scientific, public, and reviewable record;
ActiveGraph stores only disposable operational workflow state and audit history.

This is an integration pilot, not a migration. It imports an isolated,
commit-pinned clone of Distributed Discovery read-only. It does not modify or
push to `distributed-discovery`, `activegraph`, or `activegraph-packs`, and it
creates no research result, claim, study, paper, or immutable research run. The
pilot uses deterministic fixtures and makes no LLM or paid API calls.

## Exact source pins

- ActiveGraph: `8aedb1866cf5dce056af97529152ffd6f468a1ed`
- activegraph-packs: `6639a5385518ad49f74813373c85cf96eff9adc0`
- Distributed Discovery: `a560bb771a8ccaf92958bde8e72280e2c968825f`

The machine-readable lock is `config/source-lock.yml`. Local source clones and
the default SQLite database live under ignored directories in this repository.

## Source-of-truth split

- Git files: scientific definitions, proofs, claims, runs, papers, public
  metadata, approved decisions, deterministic graph projections, and audits.
- ActiveGraph event store: operational event ordering and reactive workflow
  state for a pilot execution.
- Existing Distributed Discovery Python and Make targets: exact computation and
  scientific verification. This pilot does not invoke timestamp-producing
  research targets.

Implementation is developed on `pilot/distributed-discovery-activegraph` and
reviewed through a single pull request.

## Rebuild and inspect

With the pinned source checked out at `.sources/distributed-discovery`:

```sh
uv sync --extra dev
uv run ddgraph rebuild --source .sources/distributed-discovery --output exports/current
uv run ddgraph audit --store .activegraph/distributed-discovery.sqlite
uv run ddgraph verify --source .sources/distributed-discovery --exports exports/current
make check
```

`rebuild` deletes only the ignored pilot database, imports the pinned checkout,
runs all ten reactive behaviors to idle, exports the canonical projection, and
creates the deterministic fork/diff demonstration. The committed trace is a
canonical public summary and checksum rather than the full 4,237-event trace:
the complete trace would add little review value beyond `graph.json` and
`audit.md` and would materially inflate the repository.

The source-of-truth boundary is documented in `docs/source-of-truth.md`; the
bounded recommendation is in `docs/adoption-decision.md`.
