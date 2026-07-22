"""Local command-line interface for import, audit, export, and verification."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from dd_activegraph.demo import FORK_RUN_ID, run_fork_demo
from dd_activegraph.engine import build_runtime, close_runtime, replay_projection
from dd_activegraph.exporters import deterministic_files, export_runtime
from dd_activegraph.importers import DistributedDiscoveryImporter
from dd_activegraph.holdout import run_holdout, verify_holdout
from dd_activegraph.trial import run_trial, verify_trial

DEFAULT_STORE = Path(".activegraph/distributed-discovery.sqlite")


def _result(value: object) -> None:
    click.echo(json.dumps(value, indent=2, sort_keys=True))


@click.group()
def main() -> None:
    """Operate the deterministic Distributed Discovery graph pilot."""


@main.command("import")
@click.option("--source", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
def import_command(source: Path, store: Path) -> None:
    runtime = build_runtime(store)
    bundle = DistributedDiscoveryImporter(source).build()
    DistributedDiscoveryImporter(source).materialize(runtime)
    _result(
        {"objects": len(bundle.objects), "relations": len(bundle.relations), "store": str(store)}
    )
    close_runtime(runtime)


@main.command()
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
def inspect(store: Path) -> None:
    runtime = replay_projection(store)
    _result(
        {
            "objects": len(runtime.graph.all_objects()),
            "relations": len(runtime.graph.all_relations()),
            "events": len(runtime.graph.events),
        }
    )
    close_runtime(runtime)


@main.command()
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
def audit(store: Path) -> None:
    runtime = replay_projection(store)
    summaries = [
        o.data
        for o in runtime.graph.all_objects()
        if o.type == "decision" and o.data.get("attributes", {}).get("category") == "audit_summary"
    ]
    _result(sorted(summaries, key=lambda item: item["attributes"]["behavior"]))
    close_runtime(runtime)


@main.command()
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def export(store: Path, output: Path) -> None:
    runtime = replay_projection(store)
    _result(export_runtime(runtime, output))
    close_runtime(runtime)


def _rebuild(source: Path, output: Path, store: Path, *, demo: bool = True) -> dict[str, object]:
    store.unlink(missing_ok=True)
    runtime = build_runtime(store, fork_run_ids=(FORK_RUN_ID,))
    DistributedDiscoveryImporter(source).materialize(runtime)
    result: dict[str, object] = export_runtime(runtime, output)
    if demo:
        result["fork_demo"] = run_fork_demo(runtime, output)
    close_runtime(runtime)
    return result


@main.command()
@click.option("--source", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
def rebuild(source: Path, output: Path, store: Path) -> None:
    _result(_rebuild(source, output, store))


@main.command("fork-demo")
@click.option("--store", type=click.Path(path_type=Path), default=DEFAULT_STORE)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def fork_demo_command(store: Path, output: Path) -> None:
    runtime = replay_projection(store)
    _result(run_fork_demo(runtime, output))
    close_runtime(runtime)


@main.command("diff-demo")
@click.option("--output", type=click.Path(path_type=Path), required=True)
def diff_demo_command(output: Path) -> None:
    _result(json.loads((output / "fork-diff.json").read_text()))


@main.command()
@click.option("--source", type=click.Path(path_type=Path, exists=True), required=True)
@click.option(
    "--exports", "exports_path", type=click.Path(path_type=Path, exists=True), required=True
)
def verify(source: Path, exports_path: Path) -> None:
    scratch = Path(".activegraph/verify-exports")
    store = Path(".activegraph/verify.sqlite")
    if scratch.exists():
        shutil.rmtree(scratch)
    _rebuild(source, scratch, store)
    expected = deterministic_files(exports_path)
    observed = deterministic_files(scratch)
    mismatches = sorted(
        name for name in set(expected) | set(observed) if expected.get(name) != observed.get(name)
    )
    if mismatches:
        raise click.ClickException(f"deterministic export mismatch: {', '.join(mismatches)}")
    _result({"byte_identical": True, "files": sorted(observed), "replay": True, "source_pin": True})


@main.command("trial-rebuild")
@click.option(
    "--source-root",
    type=click.Path(path_type=Path, exists=True),
    default=Path(".sources/snapshots"),
)
def trial_rebuild(source_root: Path) -> None:
    repo = Path.cwd()
    _result(
        run_trial(
            repo,
            source_root.resolve(),
            repo / "exports/snapshots",
            repo / "exports/comparison",
            repo / "reports",
            repo / ".activegraph/trial",
        )
    )


@main.command("trial-verify")
@click.option(
    "--source-root",
    type=click.Path(path_type=Path, exists=True),
    default=Path(".sources/snapshots"),
)
def trial_verify(source_root: Path) -> None:
    _result(verify_trial(Path.cwd(), source_root.resolve()))


@main.command("holdout-rebuild")
@click.option(
    "--source",
    type=click.Path(path_type=Path, exists=True),
    default=Path(".sources/holdout/504c9fb9c1039b21bf57f83a794f9f0da3e64afa"),
)
def holdout_rebuild(source: Path) -> None:
    repo = Path.cwd()
    _result(run_holdout(repo, source.resolve(), repo / ".activegraph/holdout"))


@main.command("holdout-verify")
@click.option(
    "--source",
    type=click.Path(path_type=Path, exists=True),
    default=Path(".sources/holdout/504c9fb9c1039b21bf57f83a794f9f0da3e64afa"),
)
def holdout_verify(source: Path) -> None:
    _result(verify_holdout(Path.cwd(), source.resolve()))
