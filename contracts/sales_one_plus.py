"""Strict contracts for the isolated one-Plus sales candidate path."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.exact_sales_resolution import ExactSalesResolution

SalesOnePlusDecision = Literal["answer", "admin", "spam"]
SalesOnePlusSource = Literal["local_gate", "model", "backend", "protocol"]


@dataclass(frozen=True, slots=True)
class SalesOnePlusStrictFact:
    """Already-authoritative compact evidence, including scoped offer/package data."""

    id: str
    kind: str
    text: str
    must_preserve_exact: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.kind.strip() or not self.text.strip():
            raise ValueError("sales_one_plus_strict_fact_invalid")


@dataclass(frozen=True, slots=True)
class SalesOnePlusInvocation:
    """One provider invocation; raw user text is allowed here, never in result."""

    system_prompt: str
    user_prompt: str
    model_corpus_text: str
    user_message: str
    exact_sales_resolution: ExactSalesResolution
    current_strict_facts: tuple[SalesOnePlusStrictFact, ...]
    sales_context: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.system_prompt.strip() or not self.user_prompt.strip():
            raise ValueError("sales_one_plus_prompt_empty")
        if not self.model_corpus_text.strip() or not self.user_message.strip():
            raise ValueError("sales_one_plus_input_empty")


class SalesOnePlusResult(BaseModel):
    """No raw user text or model prose is retained for terminal outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    decision: SalesOnePlusDecision
    source: SalesOnePlusSource
    reason: str
    patient_text: str | None = None
    handoff_text: str | None = None
    interrupted: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.reason.strip():
            raise ValueError("sales_one_plus_reason_empty")
        if self.decision == "answer":
            if (
                self.source not in {"model", "backend"}
                or not self.patient_text
                or not self.patient_text.strip()
                or self.handoff_text is not None
                or self.interrupted != (self.source == "backend")
            ):
                raise ValueError("sales_one_plus_answer_inconsistent")
        elif self.decision == "admin":
            if (
                self.patient_text is not None
                or not self.handoff_text
                or not self.handoff_text.strip()
                or self.interrupted
            ):
                raise ValueError("sales_one_plus_admin_inconsistent")
        elif self.patient_text is not None or self.handoff_text is not None or self.interrupted:
            raise ValueError("sales_one_plus_spam_text_forbidden")
        return self
