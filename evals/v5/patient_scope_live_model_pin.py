"""Planner model-pin bootstrap for patient-scope live eval harnesses."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from contracts.planner_attempt import PlannerAttempt
from evals.v5.fullcontext_response_eval_contract import HarnessConfigError

MODEL_PIN_STALE_CODE = "MODEL_PIN_STALE"
PROVIDER_MODEL_MISMATCH_CODE = "MODEL_MISMATCH"


class PlannerModelPinError(HarnessConfigError):
    """Configured planner model does not match owner-requested pin."""

    def __init__(self, message: str, *, code: str = MODEL_PIN_STALE_CODE) -> None:
        super().__init__(message)
        self.code = code


class ProviderModelMismatchError(HarnessConfigError):
    """Provider response model does not match owner-requested pin."""

    def __init__(
        self,
        message: str,
        *,
        owner_requested_model: str,
        configured_model: str,
        observed_model: str,
    ) -> None:
        super().__init__(message)
        self.code = PROVIDER_MODEL_MISMATCH_CODE
        self.owner_requested_model = owner_requested_model
        self.configured_model = configured_model
        self.observed_model = observed_model


def bootstrap_planner_model_env(owner_requested_model: str) -> None:
    """Set planner model env before any config/planner import in a fresh process."""

    os.environ["TURN_PLANNER_LLM_MODEL"] = owner_requested_model


def read_configured_planner_model() -> str:
    import config

    return str(config.TURN_PLANNER_LLM_MODEL)


def build_model_provenance(
    *,
    owner_requested_model: str,
    configured_model: str | None = None,
    provider_observed_models: list[str] | None = None,
) -> dict[str, Any]:
    configured = configured_model or read_configured_planner_model()
    observed = list(provider_observed_models or [])
    return {
        "owner_requested_model": owner_requested_model,
        "configured_model": configured,
        "provider_observed_models": observed,
        "provider_model_verified": bool(
            observed and all(model == owner_requested_model for model in observed)
        ),
    }


def assert_planner_model_pin_before_marker(owner_requested_model: str) -> dict[str, Any]:
    """Fail closed before attempt marker if env/config disagree with owner pin."""

    env_model = (os.environ.get("TURN_PLANNER_LLM_MODEL") or "").strip()
    if env_model != owner_requested_model:
        raise PlannerModelPinError(
            "TURN_PLANNER_LLM_MODEL env mismatch before attempt marker: "
            f"env={env_model!r} expected={owner_requested_model!r}",
        )
    configured_model = read_configured_planner_model()
    if configured_model != owner_requested_model:
        raise PlannerModelPinError(
            "config.TURN_PLANNER_LLM_MODEL stale before attempt marker: "
            f"configured={configured_model!r} expected={owner_requested_model!r}. "
            "Set env before first config import.",
        )
    return build_model_provenance(
        owner_requested_model=owner_requested_model,
        configured_model=configured_model,
    )


def assert_provider_model_matches(
    *,
    owner_requested_model: str,
    configured_model: str,
    observed_model: str,
) -> None:
    if observed_model != owner_requested_model:
        raise ProviderModelMismatchError(
            "provider model mismatch after first planner call: "
            f"observed={observed_model!r} expected={owner_requested_model!r}",
            owner_requested_model=owner_requested_model,
            configured_model=configured_model,
            observed_model=observed_model,
        )


def extract_provider_model_from_response(response: Any, *, fallback: str | None = None) -> str:
    observed = getattr(response, "model", None)
    if observed:
        return str(observed)
    if fallback:
        return fallback
    raise ProviderModelMismatchError(
        "provider response missing model field",
        owner_requested_model=fallback or "",
        configured_model=fallback or "",
        observed_model="",
    )


def make_model_tracked_planner(
    planner_fn: Callable[[str, str | None, str | None], PlannerAttempt],
    observed_models: list[str],
) -> Callable[[str, str | None, str | None], PlannerAttempt]:
    def _wrapped(q: str, sid: str | None, client_id: str | None) -> PlannerAttempt:
        from core import turn_planner_llm

        original = turn_planner_llm._planner_chat_completions_create

        def _tracking_create(**kwargs: Any) -> Any:
            response = original(**kwargs)
            observed = getattr(response, "model", None) or kwargs.get("model")
            if observed:
                observed_models.append(str(observed))
            return response

        turn_planner_llm._planner_chat_completions_create = _tracking_create
        try:
            return planner_fn(q, sid, client_id)
        finally:
            turn_planner_llm._planner_chat_completions_create = original

    return _wrapped


__all__ = [
    "MODEL_PIN_STALE_CODE",
    "PROVIDER_MODEL_MISMATCH_CODE",
    "PlannerModelPinError",
    "ProviderModelMismatchError",
    "assert_planner_model_pin_before_marker",
    "assert_provider_model_matches",
    "bootstrap_planner_model_env",
    "build_model_provenance",
    "extract_provider_model_from_response",
    "make_model_tracked_planner",
    "read_configured_planner_model",
]
