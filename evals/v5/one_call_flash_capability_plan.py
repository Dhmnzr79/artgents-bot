"""Frozen capability plan hash and eval message builders (Stage 3B)."""

from __future__ import annotations

import hashlib
import json

from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_runtime_client_context import load_target_runtime_client_context
from evals.v5.one_call_flash_capability_contract import (
    FROZEN_CAPABILITY_CASES,
    MAX_CALLS,
    MEASUREMENT_ID,
    MODEL_SNAPSHOT,
    CapabilityCaseSpec,
)
from evals.v5.one_call_flash_capability_probes import (
    JSON_MODE_CAPABILITY_PROBE_USER,
    LEGACY_CAPABILITY_PROBE_USER,
    build_cache_cold_dynamic_suffix,
    build_cache_repeat_dynamic_suffix,
    probe_template_for_case_id,
)

RESPONSE_EXCERPT_MAX_CHARS = 512


def frozen_capability_plan_document() -> dict[str, object]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "model_snapshot": MODEL_SNAPSHOT,
        "max_calls": MAX_CALLS,
        "cases": [
            {
                "case_id": case.case_id,
                "requested_model": case.requested_model,
                "stream": case.stream,
                "response_format_strategy": case.response_format_strategy,
                "expect_cached_tokens_gt_zero": case.expect_cached_tokens_gt_zero,
                "probe_template": probe_template_for_case_id(case.case_id),
            }
            for case in FROZEN_CAPABILITY_CASES
        ],
    }


def frozen_capability_plan_sha256() -> str:
    payload = json.dumps(
        frozen_capability_plan_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_prefix_sha256(prefix: str) -> str:
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


def build_demo_eval_stable_prefix(attempt_id: str) -> str:
    """Production demo stable FullContext prefix with eval-only attempt nonce prefix."""

    ctx = load_target_runtime_client_context("demo")
    bundle = ctx.bundle
    catalog = ActiveServiceCatalogSnapshot.from_bundle(bundle)
    service_reference_catalog = ServiceReferenceCatalogSnapshot.from_bundle(bundle)
    exact_commercial_catalog = ExactCommercialCatalogSnapshot.from_bundle(bundle)
    base_prefix = build_one_call_stable_prefix(
        identity=ctx.pack_identity,
        cached_full_context=ctx.cached_full_context,
        active_service_catalog=catalog,
        service_reference_catalog=service_reference_catalog,
        exact_commercial_catalog=exact_commercial_catalog,
    )
    nonce_block = (
        "=== EVAL_ATTEMPT_NONCE ===\n"
        f"attempt_id={attempt_id}\n"
        "probe=cache_byte_identical_prefix"
    )
    return f"{nonce_block}\n\n{base_prefix}"


def cache_stable_prefix_sha256(attempt_id: str) -> str:
    return stable_prefix_sha256(build_demo_eval_stable_prefix(attempt_id))


def messages_for_live_case(
    case: CapabilityCaseSpec,
    *,
    attempt_id: str,
    eval_stable_prefix: str | None = None,
) -> list[dict[str, str]]:
    if case.case_id == "cache_cold":
        prefix = eval_stable_prefix or build_demo_eval_stable_prefix(attempt_id)
        return [
            {"role": "system", "content": prefix},
            {"role": "user", "content": build_cache_cold_dynamic_suffix()},
        ]
    if case.case_id == "cache_repeat":
        prefix = eval_stable_prefix or build_demo_eval_stable_prefix(attempt_id)
        return [
            {"role": "system", "content": prefix},
            {"role": "user", "content": build_cache_repeat_dynamic_suffix()},
        ]
    if case.response_format_strategy == "json_mode":
        return [{"role": "user", "content": JSON_MODE_CAPABILITY_PROBE_USER}]
    return [{"role": "user", "content": LEGACY_CAPABILITY_PROBE_USER}]


def excerpt_text(value: str | None, *, max_chars: int = RESPONSE_EXCERPT_MAX_CHARS) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
