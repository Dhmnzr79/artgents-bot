from __future__ import annotations

import pytest

from contracts.response_plan import ComposerResult, PricePlan, ResponsePlanContractError, RouteModePair
from core.response_plan_resolver import resolve_response_plan
from core.response_ui_projection import project_response_ui
from tests.test_response_plan_contract import (
    admin_terminal,
    compose,
    contacts_terminal,
    fact,
    make_plan,
    route_mode,
    session,
)


def test_ui_projection_does_not_change_text() -> None:
    plan = make_plan(price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None)
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    from core.response_text_renderer import render_response_text

    render_response_text(resolved)
    project_response_ui(resolved)


def test_commercial_ids_equal_plan_typed_groups() -> None:
    plan = make_plan(price_plan=PricePlan(kind="none"))
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("installment_12",), patient_text="Ответ"),
    )
    ui = project_response_ui(resolved)
    assert ui.projected_commercial_ids == resolved.finalized_commercial_ids


def test_ui_projection_does_not_create_new_fact_ids() -> None:
    plan = make_plan(price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None)
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    ui = project_response_ui(resolved)
    assert ui.projected_commercial_ids.promo_fact_ids == resolved.finalized_commercial_ids.promo_fact_ids


def test_admin_only_contact_action() -> None:
    plan = make_plan(
        execution_kind="composer",
        route_mode=route_mode("ADMIN", "standard"),
        terminal_candidate=admin_terminal(),
        price_plan=PricePlan(kind="none"),
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    ui = project_response_ui(
        resolve_response_plan(plan, ComposerResult(route="ADMIN", mode="standard", patient_text=None))
    )
    assert ui.projected_commercial_ids.price_offer_ids == ()
    assert ui.buttons and ui.buttons[0].action_kind == "contact"


def test_contacts_without_composer() -> None:
    plan = make_plan(
        execution_kind="code_owned_terminal",
        route_mode=route_mode("ANSWER", "contacts"),
        terminal_candidate=contacts_terminal(),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    ui = project_response_ui(resolve_response_plan(plan, None))
    assert ui.contact is not None
    assert ui.contact.source_client_id == "demo"


def test_clarify_quick_replies_only() -> None:
    from contracts.response_plan import UiPlanCandidates, UiQuickReplyCandidate

    plan = make_plan(
        route_mode=route_mode("CLARIFY", "standard"),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        ui_candidates=UiPlanCandidates(
            quick_replies=(
                UiQuickReplyCandidate(
                    source_client_id="demo",
                    reply_id="clarify_service",
                    label="Имплантация",
                ),
            )
        ),
    )
    ui = project_response_ui(
        resolve_response_plan(
            plan,
            ComposerResult(route="CLARIFY", mode="standard", patient_text="Уточните услугу."),
        )
    )
    assert ui.quick_replies
    assert ui.projected_commercial_ids.requested_fact_ids == ()


def test_same_projection_regardless_of_transport_label() -> None:
    blocking = make_plan(transport_kind="blocking", price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None)
    streaming = make_plan(transport_kind="streaming", price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None)
    composer = compose(patient_text="Ответ")
    blocking_ui = project_response_ui(resolve_response_plan(blocking, composer))
    streaming_ui = project_response_ui(resolve_response_plan(streaming, composer))
    assert blocking_ui.projected_commercial_ids == streaming_ui.projected_commercial_ids


def test_general_doctors_ui_uses_current_source_client_id() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="doctors",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    ui = project_response_ui(resolve_response_plan(plan, compose(patient_text="Врачи")))
    assert ui.contact is None or ui.buttons
    assert all(item.source_client_id == "demo" for item in ui.quick_replies)


def test_clinic_topic_ui_does_not_require_offer() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="technologies",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
        ui_candidates=__import__(
            "contracts.response_plan",
            fromlist=["UiPlanCandidates"],
        ).UiPlanCandidates(widget=None, video=None),
    )
    ui = project_response_ui(resolve_response_plan(plan, compose(patient_text="Технологии")))
    assert ui.widget is None


def test_ui_projection_rejects_cross_client_button() -> None:
    from contracts.response_plan import UiButtonCandidate, UiPlanCandidates

    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(
            buttons=(
                UiButtonCandidate(
                    source_client_id="nikadent",
                    button_id="bad",
                    label="Bad",
                    action_kind="cta",
                ),
            )
        ),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert exc.value.code == "client_source_mismatch"


def test_topic_switch_does_not_project_previous_service_widget() -> None:
    from contracts.response_plan import UiPlanCandidates, UiWidgetCandidate

    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        active_session_service_id="implantium",
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(
            widget=UiWidgetCandidate(source_client_id="demo", widget_offer_id="offer_implant")
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    ui = project_response_ui(resolve_response_plan(plan, compose(patient_text="Стерилизация")))
    assert ui.projected_commercial_ids.price_offer_ids == ()
