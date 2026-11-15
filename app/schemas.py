"""Request bodies and shared response models (they also generate the OpenAPI schema at /docs)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HabitatId = Literal["spacecraft", "station", "moonbase", "rover", "marsbase", "spacesuit"]
Pillar = Literal["prevention", "detection", "suppression"]


class Error(BaseModel):
    error: str
    message: str


class Weights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    atmosphere: float | None = Field(None, ge=0, le=5)
    gravity: float | None = Field(None, ge=0, le=5)
    ventilation: float | None = Field(None, ge=0, le=5)
    scale: float | None = Field(None, ge=0, le=5)
    topic: float | None = Field(None, ge=0, le=5)
    data: float | None = Field(None, ge=0, le=5)


class RankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"habitat": "moonbase", "limit": 5}]})
    habitat: HabitatId | None = Field(None, description="Crew environment to rank for; omit for a general spacecraft fire-safety ranking")
    weights: Weights | None = Field(None, description="Override rubric weights (they are normalized)")
    query: str | None = Field(None, max_length=300, description="Custom topic query for the topical-relevance component")
    pillar: Pillar | None = None
    min_tests: int = Field(0, ge=0, le=10000, description="Only investigations with at least this many normalized test points")
    limit: int = Field(25, ge=1, le=100)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"question": "How does oxygen concentration affect flame spread over thin solids in microgravity?", "habitat": "moonbase"}]})
    question: str = Field(..., min_length=3, max_length=500)
    habitat: HabitatId | None = Field(None, description="Boost passages from investigations relevant to this habitat")
    accessions: list[str] | None = Field(None, max_length=24, description="Restrict retrieval to these PSI investigations, e.g. [\"PSI-69\"]")
    k: int = Field(6, ge=1, le=12, description="Passages to retrieve")
    mode: Literal["auto", "extractive", "claude"] = Field("auto", description="auto uses Claude when configured, else extractive")


class DocumentIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accessions: list[str] | None = Field(None, max_length=24)
    categories: list[Literal["Reports", "Science Documents", "Engineering Documents", "Presentations", "Reference Data", "Analyzed Data"]] | None = None
    max_mb: float = Field(40, gt=0, le=200)
    limit: int | None = Field(None, ge=1, le=1000)
