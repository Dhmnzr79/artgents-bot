"""Patient situation routing — unit-based soft scope (Slice 2)."""

from __future__ import annotations

import pytest

from contracts.patient_situation import PatientSituationResult
from core.candidate_builder import MetadataRetrievalContext, apply_metadata_candidate_boosts
from core.patient_situation import detect_patient_situation
from core.patient_situation_routing import (
    merge_price_scope,
    price_scope_from_situation,
    situation_routing_eligible,
    unit_bias_for_situation,
)
from core.price_scope import PriceScopeResult, detect_price_scope
from query_selector import select_price_service_route


def _situation(q: str) -> PatientSituationResult:
    return detect_patient_situation(q)


def test_one_tooth_choose_solution_eligible():
    s = _situation("Что мне подойдет, если нет одного зуба?")
    assert s.kind == "one_tooth_missing"
    assert situation_routing_eligible(s) is True
    bias = unit_bias_for_situation(s)
    assert bias is not None
    assert bias.preferred_units == frozenset({"one_tooth"})
    assert "jaw" in bias.penalized_units


def test_unknown_not_eligible():
    s = _situation("пустое место сбоку")
    assert situation_routing_eligible(s) is False


def test_merge_price_scope_supplements_when_regex_missed():
    q = "Сколько стоит имплантация если нет одного зуба?"
    primary = detect_price_scope(q, client_id="demo")
    situation = _situation(q)
    merged = merge_price_scope(primary, situation, client_id="demo")
    assert merged.kind == "one_tooth"
    assert "all_on_4" in merged.blocked_service_ids


def test_price_scope_from_situation_not_from_contract_hints():
    s = _situation("Что мне подойдет, если нет одного зуба?")
    assert price_scope_from_situation(s, client_id="demo") is None
    s_price = _situation("Сколько стоит восстановить один зуб?")
    scope = price_scope_from_situation(s_price, client_id="demo")
    assert scope is None or scope.kind == "one_tooth"


def test_one_tooth_content_bias_demotes_jaw_service_chunk():
    s = _situation("Что мне подойдет, если нет одного зуба?")
    bias = unit_bias_for_situation(s)
    assert bias is not None
    cands = [
        {"file": "all_on_4.md", "service_id": "all_on_4", "_score": 0.9},
        {"file": "classic.md", "service_id": "classic", "_score": 0.85},
    ]
    ctx = MetadataRetrievalContext(
        query_mode="overview",
        service_topic="implantation",
        service_topic_confidence=0.9,
    )
    out, tel = apply_metadata_candidate_boosts(
        cands,
        ctx=ctx,
        client_id="demo",
        patient_scope_bias=bias,
    )
    assert tel.get("patient_scope_unit_bias_applied") is True
    assert out[0]["service_id"] == "classic"


def test_one_tooth_price_not_all_on_4():
    question = "А сколько будет стоить имплантация если нет одного зуба?"
    route = select_price_service_route(question, client_id="demo", sid="ps-routing-price")
    assert route.get("matched_service_id") in {"classic", "one_stage"}
    assert route.get("matched_service_id") != "all_on_4"
