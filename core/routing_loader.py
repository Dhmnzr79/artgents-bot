from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class IngressMinConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hard_stop_non_target: float = Field(..., ge=0.0, le=1.0)
    manual_contact: float = Field(..., ge=0.0, le=1.0)
    service_not_offered: float = Field(..., ge=0.0, le=1.0)


class IngressThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: IngressMinConfidence


class ResolverMinConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: float = Field(..., ge=0.0, le=1.0)
    topic: float = Field(..., ge=0.0, le=1.0)
    service: Literal["ignored"]
    query_mode: float = Field(..., ge=0.0, le=1.0)


class ResolverThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: ResolverMinConfidence


class ArbiterThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(..., ge=0.0, le=1.0)


class VerifierThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(..., ge=0.0, le=1.0)
    timeout_sec: float = Field(..., ge=1.0, le=120.0)
    max_concurrent_shadow: int = Field(..., ge=1, le=32)
    shadow_backlog_max: int = Field(..., ge=0, le=256)


class RetrievalThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_topic_min_confidence: float = Field(..., ge=0.0, le=1.0)
    low_score_threshold: float = Field(..., ge=0.0, le=1.0)
    alias_scope_guard_min: float = Field(..., ge=0.0, le=1.0)


class MetadataFirstThresholds(BaseModel):
    """Metadata-First v1 retrieval boosts (see docs/METADATA_FIRST_V1.md)."""

    model_config = ConfigDict(extra="forbid")

    comparison_doc_type_boost: float = Field(..., ge=0.0, le=0.5)
    pricing_doc_type_boost: float = Field(..., ge=0.0, le=0.5)
    service_topic_match_boost: float = Field(..., ge=0.0, le=0.5)
    aspect_match_boost: float = Field(..., ge=0.0, le=0.5)
    service_id_match_boost: float = Field(..., ge=0.0, le=0.5)
    service_id_min_confidence: float = Field(..., ge=0.0, le=1.0)
    metadata_soft_filter_enabled: bool = True
    alias_boost_max_delta: float = Field(..., ge=0.0, le=0.5)
    comparison_miss_exclude_comparison: bool = True
    price_lookup_exclude_service_when_pricing_present: bool = True
    alias_topic_guard_enabled: bool = True
    soft_scope_enabled: bool = True


class CatalogMatchThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    containment_min: float = Field(..., ge=0.0, le=1.0)
    tie_score_margin: float = Field(..., ge=0.0, le=0.25)
    typo_support_min: float = Field(..., ge=0.0, le=1.0)
    lemma_weak_phrase_recall_min: float = Field(..., ge=0.0, le=1.0)
    topic_tiebreak_boost: float = Field(..., ge=0.0, le=0.25)
    topic_tiebreak_min_confidence: float = Field(..., ge=0.0, le=1.0)


class AliasThresholds(BaseModel):
    """PR #1.10 alias pipeline thresholds (see core/routing.yaml)."""

    model_config = ConfigDict(extra="forbid")

    strong_effective_min: float = Field(..., ge=0.0, le=1.0)
    soft_assist_min: float = Field(..., ge=0.0, le=1.0)
    near_exact_score: float = Field(..., ge=0.0, le=1.0)
    near_exact_length_ratio_min: float = Field(..., ge=0.0, le=1.0)
    embedding_high_min: float = Field(..., ge=0.0, le=1.0)
    embedding_strong_cosine_min: float = Field(..., ge=0.0, le=1.0)
    embedding_medium_min: float = Field(..., ge=0.0, le=1.0)
    embedding_medium_max: float = Field(..., ge=0.0, le=1.0)
    embedding_medium_score_cap: float = Field(..., ge=0.0, le=1.0)
    rescue_max_query_chars: int = Field(..., ge=1, le=256)
    rescue_max_core_tokens: int = Field(..., ge=1, le=32)
    rescue_min_sim: float = Field(..., ge=0.0, le=1.0)
    rescue_margin_min: float = Field(..., ge=0.0, le=1.0)
    rescue_effective_cap: float = Field(..., ge=0.0, le=1.0)
    scope_guard_min: float = Field(..., ge=0.0, le=1.0)
    embed_matrix_top_chunks: int = Field(..., ge=8, le=512)


class AnswerSlotsThresholds(BaseModel):
    """Answer slot assembly (see docs/CURRENT_ARCHITECTURE.md, PRODUCT_WORK_PLAN stage 2)."""

    model_config = ConfigDict(extra="forbid")

    cooldown_turns: int = Field(..., ge=1, le=32)
    clinic_note_max_chars: int = Field(..., ge=40, le=2000)
    consult_value_max_chars: int = Field(..., ge=40, le=2000)
    promo_note_max_chars: int = Field(..., ge=20, le=1000)


class LeadTurnThresholds(BaseModel):
    """Gray-zone lead turn LLM classifier (see docs/CURRENT_ARCHITECTURE.md § Lead flow v2)."""

    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(..., ge=0.0, le=1.0)


class FollowUpThresholds(BaseModel):
    """Short follow-up rewrite + compatibility guard (PRODUCT_WORK_PLAN stage 4a)."""

    model_config = ConfigDict(extra="forbid")

    max_subject_turn_age: int = Field(..., ge=1, le=16)
    min_compat_score: float = Field(..., ge=0.0, le=1.0)
    doc_type_boost: float = Field(..., ge=0.0, le=0.25)


class NumericFactGateThresholds(BaseModel):
    """Deterministic ₽ / % / installment gate (PRODUCT_WORK_PLAN stage 5a)."""

    model_config = ConfigDict(extra="forbid")

    min_answer_chars_after_remove: int = Field(..., ge=0, le=2000)


class FacetArbitrationThresholds(BaseModel):
    """Aspect-aware catalog suppression in A5 arbiter (Retrieval 2.0)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    aspects: list[str] = Field(default_factory=lambda: ["pain"])
    min_facet_score: float = Field(..., ge=0.0, le=1.0)


class Thresholds(BaseModel):
    """Validated representation of `core/routing.yaml` (see docs/CURRENT_ARCHITECTURE.md)."""

    model_config = ConfigDict(extra="forbid")

    ingress: IngressThresholds
    resolver: ResolverThresholds
    arbiter: ArbiterThresholds
    verifier: VerifierThresholds
    retrieval: RetrievalThresholds
    catalog_match: CatalogMatchThresholds
    alias: AliasThresholds
    metadata_first: MetadataFirstThresholds
    answer_slots: AnswerSlotsThresholds
    lead_turn: LeadTurnThresholds
    follow_up: FollowUpThresholds
    numeric_fact_gate: NumericFactGateThresholds
    facet_arbitration: FacetArbitrationThresholds


_LOCK = threading.Lock()
_CACHED: Thresholds | None = None
_CACHED_MTIME: float | None = None


def _routing_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), "routing.yaml")


def _load_yaml(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"routing thresholds file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"routing thresholds must be a YAML mapping at top-level: {path}")
    return data


def load_thresholds(*, force_reload: bool = False) -> Thresholds:
    """Load and validate thresholds from `core/routing.yaml` with a simple mtime cache."""
    global _CACHED, _CACHED_MTIME
    path = _routing_yaml_path()
    mtime = None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    with _LOCK:
        if not force_reload and _CACHED is not None and _CACHED_MTIME == mtime:
            return _CACHED
        raw = _load_yaml(path)
        try:
            parsed = Thresholds.model_validate(raw)
        except ValidationError as e:
            raise ValueError(f"invalid routing thresholds schema in {path}: {e}") from e
        _CACHED = parsed
        _CACHED_MTIME = mtime
        return parsed


@dataclass(frozen=True)
class _ThresholdsProxy:
    """Proxy to keep `THRESHOLDS` as a module-level singleton-like value."""

    def __getattr__(self, item: str):
        return getattr(load_thresholds(), item)


THRESHOLDS = _ThresholdsProxy()

