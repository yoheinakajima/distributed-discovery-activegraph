"""Pydantic schemas enforced by the custom ActiveGraph pack."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainObject(BaseModel):
    """Common canonical payload for every domain object type."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    source_path: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attributes: dict[str, Any] = Field(default_factory=dict)


class PackSettings(BaseModel):
    """The pilot has no network or model settings by construction."""

    model_config = ConfigDict(extra="forbid")

    advisory_only: bool = True
    allow_network: bool = False
    allow_llm: bool = False
