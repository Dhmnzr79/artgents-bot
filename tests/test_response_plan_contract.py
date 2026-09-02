from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.response_schema import RequestedDisplayPolicy
from contracts.response_plan import (
    ALLOWED_ROUTE_MODE_PAIRS,
    CanonicalContactCandidate,
    CanonicalMultiPriceCandidate,
    CanonicalSinglePriceCandidate,
    CodeOwnedTerminalCandidate,
    CommercialFactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    DeterministicBypassRouteAuthority,
    EXPECTED_TERMINAL_STATE,
    FinalizedCommercialIds,
    PlanDiagnostic,
    PreComposerPlan,
    PricePlan,
    RequiredOfferConditionBlock,
    ResolvedFactBlock,
    ResolvedPriceBlock,
    ResolvedResponsePlan,
    ResolvedServiceValueBlock,
    ResolvedTextualCtaBlock,
    ResolvedUiPlan,
    ResponseCaps,
    ResponsePlanContractError,
    ResponseSessionDelta,
    RouteModePair,
    ServiceValueCandidate,
    SessionKey,
    TextualCtaCandidate,
    UiButtonCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
    UiVideoCandidate,
    UiWidgetCandidate,
    all_allowed_route_mode_pairs,
)
from core.response_plan_resolver import resolve_response_plan


def session(client_id: str = "demo", sid: str = "s1") -> SessionKey:
    return SessionKey(client_id=client_id, sid=sid)


def route_mode(route: str = "ANSWER", mode: str = "standard") -> RouteModePair:
    return RouteModePair(route=route, mode=mode)


def contact(client_id: str = "demo", phone: str = "+7 (495) 000-00-00") -> CanonicalContactCandidate:
    return CanonicalContactCandidate(source_client_id=client_id, phone=phone)


def admin_terminal(
    *,
    client_id: str = "demo",
    mode: str = "standard",
    text: str = "ADMIN TEXT",
    authority: str = "governed_ui",
) -> CodeOwnedTerminalCandidate:
    return CodeOwnedTerminalCandidate(
        source_client_id=client_id,
        route="ADMIN",
        mode=mode,
        authority=authority,
        display_text=text,
        canonical_contact=contact(client_id),
    )


def contacts_terminal(client_id: str = "demo", text: str = "Контакты demo") -> CodeOwnedTerminalCandidate:
    return CodeOwnedTerminalCandidate(
        source_client_id=client_id,
        route="ANSWER",
        mode="contacts",
        authority="contacts",
        display_text=text,
        canonical_contact=contact(client_id),
    )


def default_terminal_candidates(client_id: str = "demo") -> tuple[CodeOwnedTerminalCandidate, ...]:
    return (
        contacts_terminal(client_id=client_id),
        admin_terminal(client_id=client_id),
        admin_terminal(client_id=client_id, mode="medical_terminal", text="MEDICAL TERMINAL"),
    )


def composer_route_authority(
    *,
    allowed_route_modes: tuple[RouteModePair, ...] | None = None,
    terminal_candidates: tuple[CodeOwnedTerminalCandidate, ...] | None = None,
    client_id: str = "demo",
) -> ComposerSelectedRouteAuthority:
    return ComposerSelectedRouteAuthority(
        allowed_route_modes=allowed_route_modes or all_allowed_route_mode_pairs(),
        terminal_candidates=terminal_candidates
        if terminal_candidates is not None
        else default_terminal_candidates(client_id=client_id),
    )


def deterministic_route_authority(
    route: str = "ANSWER",
    mode: str = "contacts",
    *,
    terminal: CodeOwnedTerminalCandidate | None = None,
    client_id: str = "demo",
) -> DeterministicBypassRouteAuthority:
    pair = (route, mode)
    if terminal is None:
        if pair == ("ANSWER", "contacts"):
            terminal = contacts_terminal(client_id=client_id)
        else:
            terminal = admin_terminal(client_id=client_id, mode=mode)
    return DeterministicBypassRouteAuthority(
        route_mode=RouteModePair(route=route, mode=mode),
        terminal_candidate=terminal,
    )


def price_single(
    *,
    client_id: str = "demo",
    offer_id: str = "offer_implant",
    display_text: str = "120 000 ₽ за имплант",
    amount: int = 120_000,
) -> PricePlan:
    return PricePlan(
        kind="single",
        single=CanonicalSinglePriceCandidate(
            source_client_id=client_id,
            offer_id=offer_id,
            display_text=display_text,
            amount=amount,
            currency="RUB",
            billing_unit="tooth_package",
        ),
    )


def price_multi(client_id: str = "demo") -> PricePlan:
    return PricePlan(
        kind="multi",
        multi=CanonicalMultiPriceCandidate(
            source_client_id=client_id,
            offer_ids=("offer_a", "offer_b"),
            display_text="A: 100 000 ₽\nB: 150 000 ₽",
        ),
    )


def fact(
    fact_id: str,
    *,
    client_id: str = "demo",
    text: str | None = None,
    explicit_only: bool = False,
    roles: tuple[str, ...] = ("requested_fact", "promo", "automatic_amplifier"),
    applicability: str = "clinic_wide",
    allowed_topic_ids: tuple[str, ...] = (),
    allowed_service_ids: tuple[str, ...] = (),
    requires_implant_scope: bool = False,
    requested_display_policy: RequestedDisplayPolicy | None = None,
) -> CommercialFactCandidate:
    return CommercialFactCandidate(
        fact_id=fact_id,
        display_text=text or fact_id,
        explicit_only=explicit_only,
        allowed_roles=roles,
        applicability=applicability,
        allowed_topic_ids=allowed_topic_ids,
        allowed_service_ids=allowed_service_ids,
        requires_implant_scope=requires_implant_scope,
        source_client_id=client_id,
        requested_display_policy=requested_display_policy,
    )


def make_plan(**overrides: object) -> PreComposerPlan:
    client_id = overrides.pop("client_id", "demo")
    sid = overrides.pop("sid", "s1")
    payload = {
        "session_key": session(client_id, sid),
        "context_strategy": "full_context",
        "route_authority": composer_route_authority(client_id=client_id),
        "response_scope": "service",
        "selected_service_id": "implantium",
        "price_plan": price_single(client_id=client_id),
        "commercial_facts": (
            fact("installment_12", client_id=client_id),
            fact(
                "implant_warranty",
                client_id=client_id,
                explicit_only=True,
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("implantium",),
                requires_implant_scope=True,
            ),
            fact("clinic_warranty", client_id=client_id, explicit_only=True, roles=("requested_fact",)),
            fact("promo_spring", client_id=client_id, roles=("promo",)),
            fact("amp_painless", client_id=client_id, roles=("automatic_amplifier",)),
        ),
        "promo_candidate_ids": ("promo_spring",),
        "automatic_amplifier_candidate_ids": ("amp_painless", "installment_12"),
        "service_value_candidate": ServiceValueCandidate(
            fact_id="service_value_implant",
            display_text="Имплантация под ключ",
            source_client_id=client_id,
        ),
        "textual_cta_candidate": TextualCtaCandidate(
            source_client_id=client_id,
            text="Записаться на консультацию",
        ),
        "required_offer_conditions": (
            RequiredOfferConditionBlock(
                source_client_id=client_id,
                condition_id="per_jaw",
                display_text="Цена указана за челюсть",
            ),
        ),
        "ui_candidates": UiPlanCandidates(
            widget=UiWidgetCandidate(source_client_id=client_id, widget_offer_id="offer_implant"),
            video=UiVideoCandidate(source_client_id=client_id, video_id="video_implant"),
        ),
    }
    payload.update(overrides)
    return PreComposerPlan(**payload)


def compose(**kwargs: object) -> ComposerResult:
    payload = {"route": "ANSWER", "mode": "standard", "patient_text": "Ответ"}
    payload.update(kwargs)
    return ComposerResult(**payload)


def test_session_key_no_delimiter_collision() -> None:
    assert SessionKey(client_id="a:b", sid="c") != SessionKey(client_id="a", sid="b:c")


def test_models_are_frozen() -> None:
    plan = make_plan()
    with pytest.raises(ValidationError):
        plan.session_key.client_id = "other"


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(unknown_field="x")


def test_route_mode_pair_rejects_forbidden() -> None:
    with pytest.raises(ValidationError):
        RouteModePair(route="ANSWER", mode="medical_terminal")


def test_all_allowed_route_mode_pairs_validate() -> None:
    for route, mode in ALLOWED_ROUTE_MODE_PAIRS:
        RouteModePair(route=route, mode=mode)


def test_admin_composer_invariants() -> None:
    ComposerResult(route="ADMIN", mode="standard", patient_text=None)
    with pytest.raises(ValidationError):
        ComposerResult(route="ADMIN", mode="standard", patient_text="text")


def test_clarify_composer_invariants() -> None:
    ComposerResult(route="CLARIFY", mode="standard", patient_text="Уточните.")
    with pytest.raises(ValidationError):
        ComposerResult(route="CLARIFY", mode="standard", patient_text="")


def test_composer_contacts_mode_allowed() -> None:
    result = ComposerResult(route="ANSWER", mode="contacts", patient_text=None)
    assert result.patient_text is None
    with pytest.raises(ValidationError):
        ComposerResult(route="ANSWER", mode="contacts", patient_text="x")


def test_composer_selected_route_authority_requires_terminal_candidates() -> None:
    with pytest.raises(ValidationError):
        ComposerSelectedRouteAuthority(
            allowed_route_modes=all_allowed_route_mode_pairs(),
            terminal_candidates=(),
        )


def test_composer_selected_route_authority_rejects_duplicate_allowed_pairs() -> None:
    with pytest.raises(ValidationError):
        ComposerSelectedRouteAuthority(
            allowed_route_modes=(
                RouteModePair(route="ANSWER", mode="standard"),
                RouteModePair(route="ANSWER", mode="standard"),
            ),
            terminal_candidates=(),
        )


def test_deterministic_bypass_route_authority_rejects_clarify() -> None:
    with pytest.raises(ValidationError):
        DeterministicBypassRouteAuthority(
            route_mode=RouteModePair(route="CLARIFY", mode="standard"),
            terminal_candidate=admin_terminal(),
        )


def test_deterministic_bypass_terminal_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        DeterministicBypassRouteAuthority(
            route_mode=RouteModePair(route="ANSWER", mode="contacts"),
            terminal_candidate=admin_terminal(),
        )


def test_whitespace_padded_promo_candidate_id_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(promo_candidate_ids=(" promo_spring",))


def test_duplicate_requested_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        compose(requested_fact_ids=("installment_12", "installment_12"))


def test_arbitrary_required_condition_id_rejected() -> None:
    with pytest.raises(ValidationError):
        RequiredOfferConditionBlock(
            source_client_id="demo",
            condition_id="custom_condition",
            display_text="x",
        )


def test_session_delta_contains_session_key() -> None:
    resolved = resolve_response_plan(make_plan(price_plan=PricePlan(kind="none")), compose())
    assert resolved.session_delta.session_key == session()


def test_selected_service_id_none_valid_for_topic_scope() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
    )
    assert plan.selected_service_id is None


def test_selected_service_id_none_valid_for_clinic_scope() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
    )
    assert plan.response_scope == "clinic"


def test_service_scope_requires_service_id() -> None:
    with pytest.raises(ValidationError):
        make_plan(response_scope="service", selected_service_id=None)


def test_blank_service_id_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(selected_service_id="")


def test_active_session_service_separate_from_selected_service() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        active_session_service_id="all_on_4",
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
    )
    assert plan.active_session_service_id == "all_on_4"
    assert plan.selected_service_id is None


def test_clinic_topic_plan_does_not_require_price_offer() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
    )
    assert plan.price_plan.kind == "none"


def test_answer_without_composer_rejected() -> None:
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(make_plan(), None)
    assert exc.value.code == "composer_result_required"


def test_clarify_without_composer_rejected() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, None)
    assert exc.value.code == "composer_result_required"


def test_code_owned_contacts_without_composer_success() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(plan, None)
    assert resolved.terminal_text == "Контакты demo"
    assert resolved.patient_text is None


def test_contacts_with_composer_rejected() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose(patient_text="x"))
    assert exc.value.code == "composer_result_forbidden"


def test_code_owned_admin_without_authority_rejected() -> None:
    with pytest.raises(ValidationError):
        admin_terminal(authority="contacts")


def test_code_owned_admin_success() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(
            route="ADMIN",
            mode="standard",
            terminal=admin_terminal(),
        ),
        price_plan=PricePlan(kind="none"),
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(plan, None)
    assert resolved.terminal_text == "ADMIN TEXT"


def test_forbidden_route_mode_pairs_rejected() -> None:
    forbidden = [
        ("ANSWER", "medical_terminal"),
        ("ADMIN", "contacts"),
        ("CLARIFY", "contacts"),
        ("CLARIFY", "medical_terminal"),
    ]
    for route, mode in forbidden:
        with pytest.raises(ValidationError):
            RouteModePair(route=route, mode=mode)


def test_client_source_mismatch_on_price() -> None:
    plan = make_plan(price_plan=price_single(client_id="nikadent"))
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_unused_promo_candidate() -> None:
    plan = make_plan(
        commercial_facts=(fact("promo_spring", client_id="nikadent", roles=("promo",)),),
        promo_candidate_ids=("promo_spring",),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_required_condition() -> None:
    plan = make_plan(
        required_offer_conditions=(
            RequiredOfferConditionBlock(
                source_client_id="nikadent",
                condition_id="per_jaw",
                display_text="x",
            ),
        ),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_cta() -> None:
    plan = make_plan(
        textual_cta_candidate=TextualCtaCandidate(source_client_id="nikadent", text="CTA"),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_service_value() -> None:
    plan = make_plan(
        service_value_candidate=ServiceValueCandidate(
            fact_id="sv",
            display_text="sv",
            source_client_id="nikadent",
        ),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_terminal_candidate() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(
            terminal=contacts_terminal(client_id="nikadent"),
        ),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, None)
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_multi_price() -> None:
    plan = make_plan(price_plan=price_multi(client_id="nikadent"))
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_quick_reply() -> None:
    plan = make_plan(
        ui_candidates=UiPlanCandidates(
            quick_replies=(
                UiQuickReplyCandidate(
                    source_client_id="nikadent",
                    reply_id="qr",
                    label="QR",
                ),
            )
        ),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_client_source_mismatch_on_video() -> None:
    plan = make_plan(
        ui_candidates=UiPlanCandidates(
            video=UiVideoCandidate(source_client_id="nikadent", video_id="v1"),
        ),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(plan, compose())
    assert exc.value.code == "client_source_mismatch"


def test_duplicate_promo_candidate_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(promo_candidate_ids=("promo_spring", "promo_spring"))


def test_duplicate_amplifier_candidate_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(automatic_amplifier_candidate_ids=("amp_painless", "amp_painless"))


def test_duplicate_commercial_fact_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(
            commercial_facts=(
                fact("dup_fact"),
                fact("dup_fact"),
            ),
            promo_candidate_ids=(),
            automatic_amplifier_candidate_ids=(),
        )


def test_duplicate_required_condition_id_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(
            required_offer_conditions=(
                RequiredOfferConditionBlock(
                    source_client_id="demo",
                    condition_id="per_jaw",
                    display_text="a",
                ),
                RequiredOfferConditionBlock(
                    source_client_id="demo",
                    condition_id="per_jaw",
                    display_text="b",
                ),
            ),
        )


def test_normal_caps_above_absolute_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(normal_caps=ResponseCaps(max_service_value=2))
    with pytest.raises(ValidationError):
        make_plan(normal_caps=ResponseCaps(max_promo=3))
    with pytest.raises(ValidationError):
        make_plan(normal_caps=ResponseCaps(max_automatic_amplifiers=3))


def test_price_caps_above_absolute_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(price_caps=ResponseCaps(max_service_value=1, max_promo=2, max_automatic_amplifiers=4))
    with pytest.raises(ValidationError):
        make_plan(price_caps=ResponseCaps(max_service_value=0, max_promo=3, max_automatic_amplifiers=4))
    with pytest.raises(ValidationError):
        make_plan(price_caps=ResponseCaps(max_service_value=0, max_promo=2, max_automatic_amplifiers=5))


def _minimal_answer_resolved(**overrides: object) -> ResolvedResponsePlan:
    base = {
        "route": "ANSWER",
        "mode": "standard",
        "context_strategy": "full_context",
        "response_scope": "service",
        "transport_kind": "blocking",
        "patient_text": "Ответ",
        "terminal_text": None,
        "ui_plan": ResolvedUiPlan(),
        "finalized_commercial_ids": FinalizedCommercialIds(),
        "session_delta": ResponseSessionDelta(
            session_key=session(),
            active_service_id="implantium",
            terminal_state="none",
            clarify_pending=False,
        ),
    }
    base.update(overrides)
    return ResolvedResponsePlan(**base)


def test_manually_created_resolved_plan_with_mismatched_finalized_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            requested_fact_blocks=(
                ResolvedFactBlock(
                    fact_id="installment_12",
                    display_text="installment_12",
                    role="requested_fact",
                    source_client_id="demo",
                ),
            ),
            finalized_commercial_ids=FinalizedCommercialIds(requested_fact_ids=("other",)),
            session_delta=ResponseSessionDelta(
                session_key=session(),
                shown_requested_fact_ids=("other",),
            ),
        )


def test_manually_created_resolved_plan_with_mismatched_session_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            finalized_commercial_ids=FinalizedCommercialIds(requested_fact_ids=("installment_12",)),
            session_delta=ResponseSessionDelta(
                session_key=session(),
                shown_requested_fact_ids=("other",),
            ),
        )


def test_single_price_with_canonical_multi_owner_rejected() -> None:
    with pytest.raises(ValidationError):
        ResolvedPriceBlock(
            source_client_id="demo",
            offer_ids=("offer_implant",),
            display_text="120 000 ₽",
            owner="canonical_multi",
            amount=120_000,
            currency="RUB",
            billing_unit="tooth_package",
        )


def test_multi_price_with_single_price_owner_rejected() -> None:
    with pytest.raises(ValidationError):
        ResolvedPriceBlock(
            source_client_id="demo",
            offer_ids=("offer_a", "offer_b"),
            display_text="A\nB",
            owner="canonical_single",
        )


def test_terminal_plan_with_commerce_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            route="ADMIN",
            mode="standard",
            patient_text=None,
            terminal_text="ADMIN",
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_service_id="implantium",
                terminal_state="admin",
                clarify_pending=False,
            ),
            price_block=ResolvedPriceBlock(
                source_client_id="demo",
                offer_ids=("offer_implant",),
                display_text="120 000 ₽",
                owner="canonical_single",
                amount=120_000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
        )


def test_clarify_plan_with_commerce_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            route="CLARIFY",
            mode="standard",
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_service_id="implantium",
                terminal_state="clarify",
                clarify_pending=True,
            ),
            service_value_block=ResolvedServiceValueBlock(
                fact_id="sv",
                display_text="sv",
                source_client_id="demo",
            ),
            finalized_commercial_ids=FinalizedCommercialIds(service_value_ids=("sv",)),
        )


def test_topic_scope_with_selected_service_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(
            response_scope="topic",
            selected_topic_id="sterilization",
            selected_service_id="implantium",
        )


def test_clinic_scope_with_selected_service_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(
            response_scope="clinic",
            selected_service_id="implantium",
        )


def test_clinic_scope_with_selected_topic_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(
            response_scope="clinic",
            selected_topic_id="technologies",
        )


def test_topic_scope_without_selected_topic_rejected() -> None:
    with pytest.raises(ValidationError):
        make_plan(response_scope="topic", selected_service_id=None, selected_topic_id=None)


def test_active_historical_service_not_selected_service() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        active_session_service_id="all_on_4",
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Стерилизация."))
    assert plan.selected_service_id is None
    assert resolved.session_delta.active_service_id is None


def test_wrong_terminal_state_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_service_id="implantium",
                terminal_state="admin",
                clarify_pending=False,
            ),
        )


def test_clarify_with_clarify_pending_false_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            route="CLARIFY",
            mode="standard",
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_service_id="implantium",
                terminal_state="clarify",
                clarify_pending=False,
            ),
        )


def test_topic_session_delta_with_active_service_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            response_scope="topic",
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_service_id="implantium",
                active_topic_id="sterilization",
                terminal_state="none",
                clarify_pending=False,
            ),
        )


def test_clinic_session_delta_with_active_topic_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            response_scope="clinic",
            session_delta=ResponseSessionDelta(
                session_key=session(),
                active_topic_id="technologies",
                terminal_state="none",
                clarify_pending=False,
            ),
        )


def test_requested_lane_with_promo_role_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            requested_fact_blocks=(
                ResolvedFactBlock(
                    fact_id="installment_12",
                    display_text="x",
                    role="promo",
                    source_client_id="demo",
                ),
            ),
            finalized_commercial_ids=FinalizedCommercialIds(requested_fact_ids=("installment_12",)),
        )


def test_promo_lane_with_amplifier_role_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            promo_blocks=(
                ResolvedFactBlock(
                    fact_id="promo_spring",
                    display_text="x",
                    role="automatic_amplifier",
                    source_client_id="demo",
                ),
            ),
            finalized_commercial_ids=FinalizedCommercialIds(promo_fact_ids=("promo_spring",)),
        )


def test_amplifier_lane_with_promo_role_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            automatic_amplifier_blocks=(
                ResolvedFactBlock(
                    fact_id="amp_painless",
                    display_text="x",
                    role="promo",
                    source_client_id="demo",
                ),
            ),
            finalized_commercial_ids=FinalizedCommercialIds(amplifier_fact_ids=("amp_painless",)),
        )


def test_cross_client_resolved_price_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            price_block=ResolvedPriceBlock(
                source_client_id="nikadent",
                offer_ids=("offer_implant",),
                display_text="120 000 ₽",
                owner="canonical_single",
                amount=120_000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
            finalized_commercial_ids=FinalizedCommercialIds(price_offer_ids=("offer_implant",)),
        )


def test_cross_client_resolved_fact_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            requested_fact_blocks=(
                ResolvedFactBlock(
                    fact_id="installment_12",
                    display_text="x",
                    role="requested_fact",
                    source_client_id="nikadent",
                ),
            ),
            finalized_commercial_ids=FinalizedCommercialIds(requested_fact_ids=("installment_12",)),
        )


def test_cross_client_resolved_service_value_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            service_value_block=ResolvedServiceValueBlock(
                fact_id="sv",
                display_text="sv",
                source_client_id="nikadent",
            ),
            finalized_commercial_ids=FinalizedCommercialIds(service_value_ids=("sv",)),
        )


def test_cross_client_resolved_cta_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            textual_cta_block=ResolvedTextualCtaBlock(
                source_client_id="nikadent",
                text="CTA",
            ),
        )


def test_cross_client_resolved_ui_contact_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_answer_resolved(
            ui_plan=ResolvedUiPlan(
                contact=CanonicalContactCandidate(source_client_id="nikadent", phone="+7"),
            ),
        )


def test_diagnostic_wrong_explicit_classification_rejected() -> None:
    with pytest.raises(ValidationError):
        PlanDiagnostic(
            code="requested_fact_unknown",
            classification="optional_resolution",
        )


def test_diagnostic_correct_explicit_classification_allowed() -> None:
    diag = PlanDiagnostic(
        code="requested_fact_unknown",
        classification="model_contract_violation",
    )
    assert diag.classification == "model_contract_violation"


def test_diagnostic_auto_classification_without_explicit_value() -> None:
    diag = PlanDiagnostic(code="service_value_out_of_scope")
    assert diag.classification == "optional_resolution"
