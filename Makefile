.PHONY: sync rebuild verify trial-rebuild trial-verify test lint typecheck check

sync:
	uv sync --extra dev

rebuild:
	uv run ddgraph rebuild --source $${DD_SOURCE:-.sources/distributed-discovery} --output exports/current

verify:
	uv run ddgraph verify --source $${DD_SOURCE:-.sources/distributed-discovery} --exports exports/current

trial-rebuild:
	uv run ddgraph trial-rebuild --source-root $${DD_SNAPSHOT_ROOT:-.sources/snapshots}

trial-verify:
	uv run ddgraph trial-verify --source-root $${DD_SNAPSHOT_ROOT:-.sources/snapshots}

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy dd_activegraph

check: lint typecheck test verify trial-verify
