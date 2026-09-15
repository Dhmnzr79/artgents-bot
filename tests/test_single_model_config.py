"""Offline contract for the single production LLM configuration."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


_LEGACY_ROLE_ENV_NAMES = (
    "MODEL_CHAT",
    "MODEL_RESOLVER",
    "MODEL_LEAD_NAME",
    "DIALOG_FOCUS_LLM_MODEL",
    "PATIENT_SITUATION_LLM_MODEL",
    "ASPECT_PLANNER_LLM_MODEL",
    "SALES_ONE_PLUS_MODEL",
    "TURN_PLANNER_LLM_MODEL",
    "LEAD_TURN_LLM_MODEL",
    "BOOKING_INTENT_LLM_MODEL",
    "PRICE_INTENT_LLM_MODEL",
    "MODEL_SAFETY_CLASSIFY",
    "MODEL_COMPLAINT_CLASSIFY",
    "MODEL_INGRESS_CLASSIFY",
    "MODEL_VERIFIER",
    "TARGET_FULLCONTEXT_COMPOSER_MODEL",
    "TARGET_FULLCONTEXT_VERIFIER_MODEL",
    "TARGET_FULLCONTEXT_BOUNDARY_MODEL",
    "FULLCONTEXT_RESPONSE_EVAL_LLM_MODEL",
    "MEDICAL_BOUNDARY_EVAL_LLM_MODEL",
)


def test_all_production_roles_use_default_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config
    import core.target_runtime_llm_backends as target_backends
    import verifier

    with monkeypatch.context() as scoped:
        scoped.setenv("DEFAULT_LLM_MODEL", "qwen3.8-flash")
        for name in _LEGACY_ROLE_ENV_NAMES:
            scoped.setenv(name, "stale-role-model")

        importlib.reload(config)
        importlib.reload(target_backends)
        importlib.reload(verifier)

        production_models = {
            config.CHAT_MODEL,
            config.RESOLVER_MODEL,
            config.LEAD_NAME_CLASSIFY_MODEL,
            config.DIALOG_FOCUS_LLM_MODEL,
            config.PATIENT_SITUATION_LLM_MODEL,
            config.ASPECT_PLANNER_LLM_MODEL,
            config.SALES_ONE_PLUS_MODEL,
            config.TURN_PLANNER_LLM_MODEL,
            config.LEAD_TURN_LLM_MODEL,
            config.BOOKING_INTENT_LLM_MODEL,
            config.PRICE_INTENT_LLM_MODEL,
            config.SAFETY_CLASSIFY_MODEL,
            config.COMPLAINT_CLASSIFY_MODEL,
            config.INGRESS_CLASSIFY_MODEL,
            target_backends.target_fullcontext_composer_model(),
            target_backends.target_fullcontext_verifier_model(),
            target_backends.target_fullcontext_boundary_model(),
            verifier._MODEL,
        }
        assert production_models == {"qwen3.8-flash"}

    importlib.reload(config)
    importlib.reload(target_backends)
    importlib.reload(verifier)


def test_thinking_flag_is_only_sent_to_qwen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import llm

    monkeypatch.setattr(llm, "QWEN_ENABLE_THINKING", False)
    assert llm._qwen_disable_thinking(model="qwen3.8-flash", kwargs={}) == {
        "extra_body": {"enable_thinking": False}
    }
    assert llm._qwen_disable_thinking(model="deepseek-flash", kwargs={}) == {}


def test_production_compose_passes_single_model_setting() -> None:
    repo = Path(__file__).resolve().parents[1]
    compose = (repo / "deploy" / "production" / "compose.yml").read_text(encoding="utf-8")
    env_example = (repo / "deploy" / "production" / "env.production.example").read_text(
        encoding="utf-8"
    )
    assert "DEFAULT_LLM_MODEL: ${DEFAULT_LLM_MODEL:-qwen3.8-flash}" in compose
    assert "DEFAULT_LLM_MODEL=qwen3.8-flash" in env_example
    assert "QWEN_ENABLE_THINKING=0" in env_example
