"""Non-PII cache observability for ONE_CALL path (Stage 3A)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core import turn_timing


@dataclass(frozen=True, slots=True)
class OneCallCacheObservability:
    local_prefix_cache_hit: bool
    provider_cache_hit: bool
    cached_tokens: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    client_pack_hash: str
    prompt_contract_version: int
    requested_model: str
    observed_model: str | None
    provider_model_verified: bool
    prefix_build_ms: int | None
    provider_ms: int | None
    total_ms: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "local_prefix_cache_hit": self.local_prefix_cache_hit,
            "provider_cache_hit": self.provider_cache_hit,
            "cached_tokens": self.cached_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "client_pack_hash": self.client_pack_hash,
            "prompt_contract_version": self.prompt_contract_version,
            "requested_model": self.requested_model,
            "observed_model": self.observed_model,
            "provider_model_verified": self.provider_model_verified,
            "timings_ms": {
                "prefix_build": self.prefix_build_ms,
                "provider": self.provider_ms,
                "total": self.total_ms,
            },
        }


def record_one_call_cache_observability(obs: OneCallCacheObservability) -> None:
    turn_timing.set_flag("one_call_cache_observability", obs.as_dict())


def merge_into_sales_fast_observability(obs: OneCallCacheObservability) -> dict[str, Any]:
    payload = obs.as_dict()
    record_one_call_cache_observability(obs)
    return payload
