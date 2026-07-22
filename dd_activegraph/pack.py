"""Custom ActiveGraph pack for Distributed Discovery."""

from __future__ import annotations

from activegraph.packs import ObjectType, Pack, RelationType

from dd_activegraph.behaviors import BEHAVIORS
from dd_activegraph.ontology import OBJECT_TYPES, RELATION_TYPES
from dd_activegraph.schemas import DomainObject, PackSettings

pack = Pack(
    name="distributed_discovery",
    version="0.1.0",
    description="Read-only Distributed Discovery relationship and audit control plane",
    object_types=tuple(
        ObjectType(name=name, schema=DomainObject, description=f"Distributed Discovery {name}")
        for name in OBJECT_TYPES
    ),
    relation_types=tuple(RelationType(name=name) for name in RELATION_TYPES),
    behaviors=BEHAVIORS,
    settings_schema=PackSettings,
)
