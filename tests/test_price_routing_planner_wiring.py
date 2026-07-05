from __future__ import annotations

from contracts.turn_plan import TurnPlan
from query_selector import select_price_service_route


def _plan(
    *,
    service_id: str | None = None,
    patient_situation: str | None = None,
) -> TurnPlan:
    return TurnPlan(
        route="price_lookup",
        aspects=["price"],
        service_id=service_id,
        patient_situation=patient_situation,
        needs_clarify=False,
    )


def test_price_routing_planner_flag_off_does_not_call_mapper(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("price_scope_from_plan must not be called when flag is off")

    monkeypatch.setattr("query_selector.PRICE_ROUTING_FROM_PLANNER", False)
    monkeypatch.setattr("core.price_scope_planner.price_scope_from_plan", _boom)

    route = select_price_service_route(
        "Сколько стоит имплантация?",
        client_id="demo",
        sid="planner-off",
        intent_override="price_lookup",
    )

    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"


def test_price_routing_planner_flag_on_generic_implantation(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("detect_price_scope must not be called when planner has a plan")

    monkeypatch.setattr("query_selector.PRICE_ROUTING_FROM_PLANNER", True)
    monkeypatch.setattr(
        "core.turn_planner_llm.turn_plan_from_ctx",
        lambda: _plan(patient_situation="generic_implant_interest"),
    )
    monkeypatch.setattr("query_selector.detect_price_scope", _boom)

    route = select_price_service_route(
        "Сколько стоит имплантация?",
        client_id="demo",
        sid="planner-generic",
        intent_override="price_lookup",
    )

    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"


def test_price_routing_planner_flag_on_specific_protocol(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("detect_price_scope must not be called when planner has a plan")

    monkeypatch.setattr("query_selector.PRICE_ROUTING_FROM_PLANNER", True)
    monkeypatch.setattr(
        "core.turn_planner_llm.turn_plan_from_ctx",
        lambda: _plan(service_id="all_on_4"),
    )
    monkeypatch.setattr("query_selector.detect_price_scope", _boom)

    route = select_price_service_route(
        "Сколько стоит All-on-4?",
        client_id="demo",
        sid="planner-all-on-4",
        intent_override="price_lookup",
    )

    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "all_on_4"


def test_price_routing_planner_none_fail_opens_to_regex(monkeypatch):
    monkeypatch.setattr("query_selector.PRICE_ROUTING_FROM_PLANNER", True)
    monkeypatch.setattr("core.turn_planner_llm.turn_plan_from_ctx", lambda: None)

    route = select_price_service_route(
        "Сколько стоит имплантация?",
        client_id="demo",
        sid="planner-none",
        intent_override="price_lookup",
    )

    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"
