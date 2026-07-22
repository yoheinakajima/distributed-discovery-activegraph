from __future__ import annotations

import os
from pathlib import Path

import pytest

from dd_activegraph.importers import DistributedDiscoveryImporter


@pytest.fixture(scope="session")
def source() -> Path:
    return Path(os.environ.get("DD_SOURCE", ".sources/distributed-discovery")).resolve()


@pytest.fixture(scope="session")
def bundle(source: Path):
    return DistributedDiscoveryImporter(source).build()
