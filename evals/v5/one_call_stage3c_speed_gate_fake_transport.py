"""Role-aware fake provider transport for Stage 3C offline harness."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from core.target_composer_output import composer_test_json
from evals.v5.one_call_stage3c_speed_gate_contract import MODEL_SNAPSHOT


@dataclass
class ProviderCallRecord:
    source: str
    model: str
    stream: bool
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int


@dataclass
class SpeedGateFakeTransport:
    """Counts real wrapper invocations; simulates latency without network."""

    answer_text: str
    delay_ms_by_source: dict[str, int] = field(
        default_factory=lambda: {
            "ingress": 40,
            "planner": 180,
            "medical_boundary": 120,
            "composer": 280,
            "verifier": 120,
            "sales_fast": 220,
        }
    )
    calls: list[ProviderCallRecord] = field(default_factory=list)
    _attempts: int = 0

    def chat_completions_create(self, **kwargs: Any) -> Any:
        self._attempts += 1
        source = str(kwargs.get("provider_call_source") or "unknown")
        model = str(kwargs.get("model") or MODEL_SNAPSHOT)
        stream = bool(kwargs.get("stream"))
        delay_ms = int(self.delay_ms_by_source.get(source, 80))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        content = self._content_for_source(source)
        record = ProviderCallRecord(
            source=source,
            model=model,
            stream=stream,
            duration_ms=delay_ms,
            prompt_tokens=256,
            completion_tokens=48,
            cached_tokens=0,
        )
        self.calls.append(record)

        if stream:
            return self._stream(content, model=model, record=record)
        return self._blocking(content, model=model, record=record)

    def reset_calls(self) -> None:
        self.calls.clear()
        self._attempts = 0

    def _content_for_source(self, source: str) -> str:
        if source == "ingress":
            return json.dumps(
                {
                    "route": "normal",
                    "confidence": 0.95,
                    "reason": "stage3c_fake",
                    "policy_key": None,
                    "requested_service": None,
                    "is_urgent": False,
                },
                ensure_ascii=False,
            )
        if source == "planner":
            return json.dumps(
                {
                    "route": "content",
                    "aspects": ["overview"],
                    "service_id": "classic",
                    "followup_of": None,
                    "needs_clarify": False,
                    "patient_situation": None,
                    "brand_filter": None,
                    "topic": "implantation",
                    "topic_confidence": 0.9,
                    "marketing_scenarios": [],
                },
                ensure_ascii=False,
            )
        if source == "medical_boundary":
            return json.dumps({"decision": "none", "confidence": 0.95}, ensure_ascii=False)
        if source == "composer":
            return composer_test_json(self.answer_text)
        if source == "verifier":
            return json.dumps({"issues": []}, ensure_ascii=False)
        if source == "sales_fast":
            return f"@ANSWER\n{self.answer_text}"
        return self.answer_text

    def _blocking(self, content: str, *, model: str, record: ProviderCallRecord) -> Any:
        usage = SimpleNamespace(
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            prompt_tokens_details=SimpleNamespace(cached_tokens=record.cached_tokens),
        )
        return SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=usage,
        )

    def _stream(self, content: str, *, model: str, record: ProviderCallRecord) -> list[Any]:
        chunks: list[Any] = []
        usage = SimpleNamespace(
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            prompt_tokens_details=SimpleNamespace(cached_tokens=record.cached_tokens),
        )

        def _chunk(text: str, with_usage: bool = False) -> Any:
            delta = SimpleNamespace(content=text) if text else None
            choice = SimpleNamespace(delta=delta) if delta is not None else SimpleNamespace(delta=SimpleNamespace(content=None))
            return SimpleNamespace(
                choices=[choice] if delta is not None else [],
                usage=usage if with_usage else None,
                model=model,
            )

        if content.startswith("@ANSWER\n"):
            marker = "@ANSWER\n"
            body = content.split("\n", 1)[1]
            for piece in (marker, body[:1], body[1:]):
                if piece:
                    chunks.append(_chunk(piece))
        elif content.startswith("{") and '"answer"' in content:
            payload = json.loads(content)
            answer = str(payload.get("answer") or "")
            for piece in (answer[:1], answer[1:]):
                if piece:
                    chunks.append(_chunk(piece))
        else:
            for piece in (content[:1], content[1:]):
                if piece:
                    chunks.append(_chunk(piece))

        chunks.append(_chunk("", with_usage=True))
        return chunks
