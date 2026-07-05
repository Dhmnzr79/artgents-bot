from __future__ import annotations

from types import SimpleNamespace

from contracts.patient_playbook import PatientOption, PatientOptionsResult
from contracts.patient_situation import PatientSituationCues, PatientSituationResult
from orchestration import patient_playbook_flow


def _situation(*, cue_intent: str = "price") -> PatientSituationResult:
    return PatientSituationResult(
        kind="full_arch_missing",
        confidence=0.95,
        source="rule_based",
        evidence=["нет всех зубов"],
        patient_scope="full_jaw",
        problem="missing_teeth",
        extent="full_arch",
        jaw="unknown",
        cues=PatientSituationCues(quantity="all", intent=cue_intent),
    )


def _options_result() -> PatientOptionsResult:
    return PatientOptionsResult(
        situation_kind="full_arch_missing",
        patient_scope="full_jaw",
        options=[
            PatientOption(
                service_id="all_on_4",
                display_name="All-on-4",
                role="main_fixed_solution",
                positioning="fixed option",
                priority=100,
            ),
            PatientOption(
                service_id="all_on_6",
                display_name="All-on-6",
                role="stronger_fixed_solution",
                positioning="stronger fixed option",
                priority=90,
            ),
            PatientOption(
                service_id="removable_dentures",
                display_name="Removable dentures",
                role="budget_alternative",
                positioning="budget option",
                priority=60,
            ),
        ],
        primary_cta="consult",
        strategy="compare_fixed_and_budget_options",
    )


def _try_route(*, intent: str = "price_lookup", decision_route: str = "price_lookup"):
    return patient_playbook_flow.try_patient_options_price_overview(
        q="Нет всех зубов, сколько стоит?",
        sid="situation-price-test",
        client_id="demo",
        intent=intent,
        decision=SimpleNamespace(route_intent=decision_route),
        situation=_situation(cue_intent="price" if intent == "price_lookup" else "choose_solution"),
        decision_frame={"route_intent": decision_route},
    )


def test_situation_price_overview_flag_on_returns_hero_price_and_buttons(monkeypatch):
    monkeypatch.setattr(patient_playbook_flow, "SITUATION_PRICE_ON", True)
    monkeypatch.setattr(
        patient_playbook_flow,
        "select_patient_options",
        lambda *_args, **_kwargs: _options_result(),
    )

    result = _try_route()

    assert result is not None
    assert result.kind == "service_reply"
    assert result.service_route == "situation_price_overview"
    payload = result.service_payload or {}
    answer = payload.get("answer") or ""
    assert "318 000" in answer
    assert "All-on-4" in answer
    assert answer.count("₽") == 1
    assert "368 000" not in answer
    assert "428 000" not in answer
    assert [item["ref"] for item in payload.get("quick_replies") or []] == [
        "price:all_on_4",
        "price:all_on_6",
        "price:removable_dentures",
    ]


def test_situation_price_overview_flag_off_returns_none(monkeypatch):
    monkeypatch.setattr(patient_playbook_flow, "SITUATION_PRICE_ON", False)
    monkeypatch.setattr(
        patient_playbook_flow,
        "select_patient_options",
        lambda *_args, **_kwargs: _options_result(),
    )

    assert _try_route() is None


def test_situation_price_overview_non_price_intent_returns_none(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("select_patient_options must not be called")

    monkeypatch.setattr(patient_playbook_flow, "SITUATION_PRICE_ON", True)
    monkeypatch.setattr(patient_playbook_flow, "select_patient_options", _boom)

    assert _try_route(intent="content", decision_route="content") is None


def test_situation_price_overview_no_options_returns_none(monkeypatch):
    monkeypatch.setattr(patient_playbook_flow, "SITUATION_PRICE_ON", True)
    monkeypatch.setattr(
        patient_playbook_flow,
        "select_patient_options",
        lambda *_args, **_kwargs: None,
    )

    assert _try_route() is None


def test_situation_price_overview_exception_fail_opens(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise RuntimeError("lens failed")

    monkeypatch.setattr(patient_playbook_flow, "SITUATION_PRICE_ON", True)
    monkeypatch.setattr(
        patient_playbook_flow,
        "select_patient_options",
        lambda *_args, **_kwargs: _options_result(),
    )
    monkeypatch.setattr(patient_playbook_flow.answer_lens, "situation_view", _raise)

    assert _try_route() is None
