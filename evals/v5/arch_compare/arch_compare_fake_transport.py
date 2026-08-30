"""Deterministic fake provider transport for arch_compare wiring checks (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from core.one_call_envelope_protocol import dumps_production_envelope
from evals.v5.arch_compare.arch_compare_contract import FAKE_PATIENT_TEXT_PREFIX


@dataclass
class ArchCompareFakeTransport:
    """Returns one scripted envelope per prepared turn; counts local invocations only."""

    calls: list[dict[str, object]] = field(default_factory=list)
    _turn_envelopes: list[str] = field(default_factory=list, repr=False)

    def prepare_turn_envelopes(self, envelopes: tuple[str, ...]) -> None:
        if len(envelopes) > 1:
            raise RuntimeError("arch_compare_fake_single_envelope_per_turn")
        self._turn_envelopes = list(envelopes)

    def clear_turn_envelopes(self) -> None:
        self._turn_envelopes.clear()

    def chat_completions_create(self, **kwargs: Any) -> Any:
        if not self._turn_envelopes:
            raise RuntimeError("arch_compare_fake_queue_empty")
        content = self._turn_envelopes[0]
        self._turn_envelopes.clear()
        model = str(kwargs.get("model") or "arch_compare_fake")
        stream = bool(kwargs.get("stream"))
        self.calls.append({"model": model, "stream": stream})
        if stream:
            return self._stream(content, model=model)
        return self._blocking(content, model=model)

    def reset_calls(self) -> None:
        self.calls.clear()

    @staticmethod
    def _blocking(content: str, *, model: str) -> SimpleNamespace:
        return SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(
                prompt_tokens=0,
                completion_tokens=0,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )

    @staticmethod
    def _stream(content: str, *, model: str):
        yield SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
        )
        yield SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=""))],
            usage=SimpleNamespace(
                prompt_tokens=0,
                completion_tokens=0,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


def build_fake_envelope_json(
    *,
    scenario_id: str,
    turn_id: str,
    route: str = "ANSWER",
    service_id: str | None = None,
    commercial_intent: str = "none",
    promotion_scope: str = "none",
) -> str:
    patient_text = f"{FAKE_PATIENT_TEXT_PREFIX}:{scenario_id}:{turn_id}"
    return dumps_production_envelope(
        patient_text=patient_text,
        route=route,
        service_id=service_id,
        commercial_intent=commercial_intent,
        promotion_scope=promotion_scope,
    )


def fake_patient_text_for_turn(*, scenario_id: str, turn_id: str) -> str:
    return f"{FAKE_PATIENT_TEXT_PREFIX}:{scenario_id}:{turn_id}"
