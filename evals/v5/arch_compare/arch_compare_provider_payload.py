"""Outbound Composer provider payload builder for architecture comparison (eval-only)."""

from __future__ import annotations

from typing import Any

from llm import LLM_REQUEST_TIMEOUT_SEC

from evals.v5.arch_compare.arch_compare_configs import (
    ARCH_COMPARE_INFERENCE_SETTINGS,
    ArchCompareConfig,
    ArchCompareInferenceSettings,
)


def build_composer_provider_payload(
    *,
    config: ArchCompareConfig,
    messages: tuple[dict[str, str], ...],
    stream: bool,
) -> dict[str, Any]:
    settings = config.inference_settings
    payload: dict[str, Any] = {
        "model": config.provider_model_id,
        "temperature": settings.temperature,
        "max_completion_tokens": settings.max_completion_tokens,
        "timeout": settings.timeout_sec or LLM_REQUEST_TIMEOUT_SEC,
        "messages": list(messages),
        "response_format": {"type": settings.response_format_type},
        "stream": stream,
        "provider_call_source": settings.provider_call_source,
        "extra_body": {"enable_thinking": settings.enable_thinking},
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def payload_diff_keys(
    *,
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[str, ...]:
  allowed = {"model"}
  diffs: list[str] = []
  keys = set(left) | set(right)
  for key in sorted(keys):
      if key in allowed:
          if left.get(key) != right.get(key):
              diffs.append(key)
          continue
      if left.get(key) != right.get(key):
          diffs.append(key)
  return tuple(diffs)


def assert_flash_plus_payload_parity(
    *,
    flash_config: ArchCompareConfig,
    plus_config: ArchCompareConfig,
    messages: tuple[dict[str, str], ...],
) -> None:
    flash_payload = build_composer_provider_payload(
        config=flash_config,
        messages=messages,
        stream=False,
    )
    plus_payload = build_composer_provider_payload(
        config=plus_config,
        messages=messages,
        stream=False,
    )
    diffs = payload_diff_keys(left=flash_payload, right=plus_payload)
    if diffs != ("model",):
        raise RuntimeError(f"arch_compare_payload_parity_mismatch diffs={diffs}")


def assert_context_payload_parity(
    *,
    full_config: ArchCompareConfig,
    curated_config: ArchCompareConfig,
    full_messages: tuple[dict[str, str], ...],
    curated_messages: tuple[dict[str, str], ...],
) -> None:
    if full_config.provider_model_id != curated_config.provider_model_id:
        raise RuntimeError("arch_compare_context_payload_model_mismatch")
    full_payload = build_composer_provider_payload(
        config=full_config,
        messages=full_messages,
        stream=False,
    )
    curated_payload = build_composer_provider_payload(
        config=curated_config,
        messages=curated_messages,
        stream=False,
    )
    full_settings = dict(full_payload)
    curated_settings = dict(curated_payload)
    full_settings.pop("messages", None)
    curated_settings.pop("messages", None)
    if full_settings != curated_settings:
        raise RuntimeError("arch_compare_context_inference_settings_mismatch")
    if full_payload["messages"] == curated_payload["messages"]:
        raise RuntimeError("arch_compare_context_messages_must_differ")


def inference_settings_document() -> dict[str, Any]:
    return ARCH_COMPARE_INFERENCE_SETTINGS.to_dict()
