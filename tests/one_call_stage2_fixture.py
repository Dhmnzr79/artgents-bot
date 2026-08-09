"""Frozen Stage 0–2 acceptance cases (production-neutral, not eval harness)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "one_call_stage2_cases.json"
_NORMATIVE_BOUNDARY_REF = (
    "docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md § «Нормативная граница ANSWER / ADMIN»"
)


@dataclass(frozen=True, slots=True)
class Stage2ExactSales:
    service_id: str | None = None
    aspect: str | None = None
    extent: str | None = None
    jaw: str | None = None
    stage: str | None = None


@dataclass(frozen=True, slots=True)
class Stage2StrictFact:
    id: str
    kind: str
    text: str
    must_preserve_exact: bool
    source_ref: str | None = None


@dataclass(frozen=True, slots=True)
class Stage2Case:
    case_id: str
    user_message: str
    expected_decision: str
    execution_layer: str
    exact_sales: Stage2ExactSales
    strict_facts: tuple[Stage2StrictFact, ...]
    sales_context: Mapping[str, Any]
    protected_category: str | None = None
    required_all: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()


def normative_boundary_ref() -> str:
    return _NORMATIVE_BOUNDARY_REF


def load_stage2_cases(path: Path | None = None) -> tuple[Stage2Case, ...]:
    fixture_path = path or _FIXTURE_PATH
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases: list[Stage2Case] = []
    for row in raw.get("cases") or []:
        axes = row.get("exact_sales") or {}
        strict_facts = tuple(
            Stage2StrictFact(
                id=str(fact["id"]),
                kind=str(fact["kind"]),
                text=str(fact["text"]),
                must_preserve_exact=bool(fact.get("must_preserve_exact")),
                source_ref=str(fact.get("source_ref") or "") or None,
            )
            for fact in row.get("strict_facts") or []
        )
        cases.append(
            Stage2Case(
                case_id=str(row["case_id"]),
                user_message=str(row["user_message"]),
                expected_decision=str(row["expected_decision"]),
                execution_layer=str(row.get("execution_layer") or "model"),
                exact_sales=Stage2ExactSales(
                    service_id=axes.get("service_id"),
                    aspect=axes.get("aspect"),
                    extent=axes.get("extent"),
                    jaw=axes.get("jaw"),
                    stage=axes.get("stage"),
                ),
                strict_facts=strict_facts,
                sales_context=dict(row.get("sales_context") or {}),
                protected_category=row.get("protected_category"),
                required_all=tuple(str(x) for x in row.get("required_all") or []),
                required_any=tuple(
                    tuple(str(y) for y in group)
                    for group in row.get("required_any") or []
                ),
                forbidden_terms=tuple(str(x) for x in row.get("forbidden_terms") or []),
            )
        )
    return tuple(cases)


def case_by_id(case_id: str, path: Path | None = None) -> Stage2Case:
    for case in load_stage2_cases(path):
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)
