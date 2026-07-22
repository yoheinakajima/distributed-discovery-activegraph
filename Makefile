.PHONY: sync rebuild verify trial-rebuild trial-verify holdout-rebuild holdout-verify test lint typecheck check

sync:
	uv sync --extra dev

rebuild:
	PYTHONPATH=. uv run ddgraph rebuild --source $${DD_SOURCE:-.sources/distributed-discovery} --output exports/current

verify:
	PYTHONPATH=. uv run ddgraph verify --source $${DD_SOURCE:-.sources/distributed-discovery} --exports exports/current

trial-rebuild:
	PYTHONPATH=. uv run ddgraph trial-rebuild --source-root $${DD_SNAPSHOT_ROOT:-.sources/snapshots}

trial-verify:
	PYTHONPATH=. uv run ddgraph trial-verify --source-root $${DD_SNAPSHOT_ROOT:-.sources/snapshots}

holdout-rebuild:
	PYTHONPATH=. uv run ddgraph holdout-rebuild --source $${DD_HOLDOUT_SOURCE:-.sources/holdout/504c9fb9c1039b21bf57f83a794f9f0da3e64afa}

holdout-verify:
	PYTHONPATH=. uv run ddgraph holdout-verify --source $${DD_HOLDOUT_SOURCE:-.sources/holdout/504c9fb9c1039b21bf57f83a794f9f0da3e64afa}

test:
	PYTHONPATH=. uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy dd_activegraph

check: lint typecheck test verify trial-verify holdout-verify
