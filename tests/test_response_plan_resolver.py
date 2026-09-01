from __future__ import annotations

import pytest

from contracts.response_plan import (
    CanonicalMultiPriceCandidate,
    ComposerResult,
    EXPECTED_TERMINAL_STATE,
    PricePlan,
    ResponsePlanContractError,
    RouteModePair,
    ServiceValueCandidate,
)
from core.response_plan_resolver import resolve_response_plan
from tests.test_response_plan_contract import (
    admin_terminal,
    compose,
    composer_route_authority,
    contacts_terminal,
    deterministic_route_authority,
    fact,
    make_plan,
    price_multi,
    price_single,
    route_mode,
)


def test_valid_single_canonical_price() -> None:
    resolved = resolve_response_plan(
        make_plan(),
        compose(patient_text="Ответ"),
    )
    assert resolved.price_block is not None
    assert resolved.price_block.owner == "canonical_single"
    assert len(resolved.price_block.offer_ids) == 1


def test_single_price_without_composer_price_text_uses_canonical_single() -> None:
    resolved = resolve_response_plan(make_plan(), compose(patient_text="Ответ"))
    assert resolved.price_block is not None
    assert resolved.price_block.owner == "canonical_single"
    assert resolved.diagnostics == ()


def test_multi_price_one_combined_block() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=price_multi()),
        compose(patient_text="Ответ"),
    )
    assert resolved.price_block is not None
    assert resolved.price_block.owner == "canonical_multi"
    assert resolved.price_block.offer_ids == ("offer_a", "offer_b")
    assert "100 000" in resolved.price_block.display_text


def test_unsafe_offer_has_no_price_and_preserves_patient_text() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="single", single=price_single().single, offer_applicable=False)
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Объяснение без цены"))
    assert resolved.price_block is None
    assert resolved.patient_text == "Объяснение без цены"
    assert resolved.required_offer_conditions == ()


def test_installment_requested_once_not_in_amplifiers() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(requested_fact_ids=("installment_12",), patient_text="Да, есть рассрочка."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)
    assert "installment_12" not in resolved.finalized_commercial_ids.amplifier_fact_ids


def test_warranty_requested_once() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(requested_fact_ids=("implant_warranty",), patient_text="Гарантия."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("implant_warranty",)


def test_ordinary_implant_answer_has_no_warranty() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(patient_text="Имплантация проходит в несколько этапов."),
    )
    assert "implant_warranty" not in resolved.finalized_commercial_ids.requested_fact_ids


def test_explicit_only_suppressed_from_automatic_roles() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        automatic_amplifier_candidate_ids=("implant_warranty",),
        commercial_facts=(fact("implant_warranty", explicit_only=True, roles=("requested_fact",)),),
        promo_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert "implant_warranty" not in resolved.finalized_commercial_ids.amplifier_fact_ids
    assert any(item.code == "explicit_only_automatic_suppressed" for item in resolved.diagnostics)


def test_promo_and_amplifier_caps_independent() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=("promo_spring", "promo_extra"),
        automatic_amplifier_candidate_ids=("amp_painless", "amp_extra"),
        commercial_facts=(
            fact("promo_spring", roles=("promo",)),
            fact("promo_extra", roles=("promo",)),
            fact("amp_painless", roles=("automatic_amplifier",)),
            fact("amp_extra", roles=("automatic_amplifier",)),
        ),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert len(resolved.promo_blocks) == 2
    assert len(resolved.automatic_amplifier_blocks) == 2


def test_normal_service_value_max_one() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(patient_text="Ответ"),
    )
    assert resolved.service_value_block is not None


def test_price_answer_has_no_service_value() -> None:
    resolved = resolve_response_plan(
        make_plan(),
        compose(patient_text="Ответ"),
    )
    assert resolved.service_value_block is None


def test_same_fact_cannot_receive_two_roles() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(requested_fact_ids=("installment_12",), patient_text="Ответ"),
    )
    all_ids = (
        *resolved.finalized_commercial_ids.requested_fact_ids,
        *resolved.finalized_commercial_ids.promo_fact_ids,
        *resolved.finalized_commercial_ids.amplifier_fact_ids,
    )
    assert len(all_ids) == len(set(all_ids))


def test_missing_optional_candidate_preserves_patient_text() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=("missing_promo",),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Основной ответ"))
    assert resolved.patient_text == "Основной ответ"
    assert resolved.promo_blocks == ()


def test_promotion_optional_failure_preserves_patient_text() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=("broken_promo",),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Основной ответ"))
    assert resolved.patient_text == "Основной ответ"
    assert "broken_promo" not in resolved.finalized_commercial_ids.promo_fact_ids


def test_unknown_requested_id_is_model_violation_not_crash() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None),
        compose(requested_fact_ids=("unknown_fact",), patient_text="Ответ"),
    )
    assert resolved.patient_text == "Ответ"
    assert any(item.code == "requested_fact_unknown" for item in resolved.diagnostics)


def test_composer_admin_has_no_commerce() -> None:
    plan = make_plan(
        route_authority=composer_route_authority(),
        price_plan=PricePlan(kind="none"),
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="ADMIN", mode="standard", patient_text=None),
    )
    assert resolved.patient_text is None
    assert resolved.terminal_text == "ADMIN TEXT"
    assert resolved.finalized_commercial_ids.price_offer_ids == ()


def test_code_owned_contacts_has_no_commerce() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(
            terminal=contacts_terminal(client_id="demo"),
        ),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(plan, None)
    assert resolved.ui_plan.contact is not None
    assert resolved.ui_plan.contact.source_client_id == "demo"
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()


def test_clarify_has_no_commerce() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        ui_candidates=__import__(
            "contracts.response_plan",
            fromlist=["UiPlanCandidates", "UiQuickReplyCandidate"],
        ).UiPlanCandidates(
            quick_replies=(
                __import__(
                    "contracts.response_plan",
                    fromlist=["UiQuickReplyCandidate"],
                ).UiQuickReplyCandidate(
                    source_client_id="demo",
                    reply_id="clarify_service",
                    label="Имплантация",
                ),
            )
        ),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="CLARIFY", mode="standard", patient_text="Уточните услугу."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    assert resolved.session_delta.clarify_pending is True
    assert resolved.patient_text == "Уточните услугу."
    assert resolved.terminal_text is None


def test_medical_terminal_inherits_admin_restrictions() -> None:
    plan = make_plan(
        route_authority=composer_route_authority(
            terminal_candidates=(
                contacts_terminal(),
                admin_terminal(),
                admin_terminal(mode="medical_terminal", text="MEDICAL TERMINAL"),
            ),
        ),
        price_plan=PricePlan(kind="none"),
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="ADMIN", mode="medical_terminal", patient_text=None),
    )
    assert resolved.mode == "medical_terminal"
    assert resolved.terminal_text == "MEDICAL TERMINAL"
    assert resolved.patient_text is None


def test_full_context_and_hybrid_resolve_identically() -> None:
    fc = make_plan(context_strategy="full_context", price_plan=PricePlan(kind="none"), textual_cta_candidate=None, service_value_candidate=None)
    hy = make_plan(context_strategy="hybrid", price_plan=PricePlan(kind="none"), textual_cta_candidate=None, service_value_candidate=None)
    composer = compose(patient_text="Ответ")
    fc_res = resolve_response_plan(fc, composer)
    hy_res = resolve_response_plan(hy, composer)
    assert fc_res.finalized_commercial_ids == hy_res.finalized_commercial_ids


def test_finalized_ids_typed_groups_match_blocks() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(requested_fact_ids=("installment_12",), patient_text="Ответ"),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)
    assert resolved.session_delta.shown_requested_fact_ids == ("installment_12",)
    assert "promo_spring" in resolved.finalized_commercial_ids.promo_fact_ids


def test_no_id_from_patient_text_words() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None),
        compose(patient_text="Гарантия и рассрочка упомянуты словами."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()


def test_clinic_wide_installment_without_service_id() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        commercial_facts=(fact("installment_12", applicability="clinic_wide"),),
        automatic_amplifier_candidate_ids=(),
        promo_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("installment_12",), patient_text="Есть рассрочка."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("installment_12",)


def test_service_scoped_fact_not_shown_without_service_id() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="payment",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(
            fact(
                "service_installment",
                applicability="service_scoped",
                allowed_service_ids=("implantium",),
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("service_installment",), patient_text="Ответ"),
    )
    assert resolved.requested_fact_blocks == ()
    assert any(item.code == "requested_fact_inapplicable" for item in resolved.diagnostics)


def test_generic_warranty_does_not_substitute_implant_warranty() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        price_plan=PricePlan(kind="none"),
        commercial_facts=(
            fact("clinic_warranty", explicit_only=True, roles=("requested_fact",)),
            fact(
                "implant_warranty",
                explicit_only=True,
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("implantium",),
                requires_implant_scope=True,
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("clinic_warranty",), patient_text="Гарантия."),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("clinic_warranty",)


def test_topic_scoped_implant_warranty_materialized_with_implantation_topic() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="implantation",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(
            fact(
                "implant_warranty",
                explicit_only=True,
                roles=("requested_fact",),
                applicability="topic_scoped",
                allowed_topic_ids=("implantation",),
                requires_implant_scope=True,
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("implant_warranty",), patient_text="Гарантия?"),
    )
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("implant_warranty",)


def test_topic_scoped_implant_warranty_suppressed_for_unrelated_topic() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(
            fact(
                "implant_warranty",
                explicit_only=True,
                roles=("requested_fact",),
                applicability="topic_scoped",
                allowed_topic_ids=("implantation",),
                requires_implant_scope=True,
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("implant_warranty",), patient_text="Гарантия?"),
    )
    assert resolved.requested_fact_blocks == ()
    assert any(item.code == "requested_fact_inapplicable" for item in resolved.diagnostics)


def test_price_without_service_does_not_create_price_block() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        price_plan=PricePlan(kind="none"),
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Сколько стоит?"))
    assert resolved.price_block is None


def test_topic_switch_clears_current_service_scope() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        active_session_service_id="all_on_4",
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(
            fact(
                "promo_spring",
                roles=("promo",),
                applicability="service_scoped",
                allowed_service_ids=("all_on_4",),
            ),
        ),
        promo_candidate_ids=("promo_spring",),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Стерилизация."))
    assert resolved.promo_blocks == ()


def test_same_question_different_clients_do_not_mix() -> None:
    demo = make_plan(
        client_id="demo",
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="doctors",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    nika = make_plan(
        client_id="nikadent",
        sid="s1",
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="doctors",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(fact("doctor_nika", client_id="nikadent", applicability="clinic_wide"),),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    demo_res = resolve_response_plan(demo, compose(patient_text="Врачи demo"))
    nika_res = resolve_response_plan(nika, compose(patient_text="Врачи nika"))
    assert demo_res.session_delta.session_key.client_id == "demo"
    assert nika_res.session_delta.session_key.client_id == "nikadent"


def test_composer_route_mode_mismatch_rejected() -> None:
    plan = make_plan(
        route_authority=composer_route_authority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
    )
    with pytest.raises(ResponsePlanContractError) as exc:
        resolve_response_plan(
            plan,
            ComposerResult(route="CLARIFY", mode="standard", patient_text="x"),
        )
    assert exc.value.code == "route_mode_conflict"


def test_offer_and_fact_same_string_id_do_not_mix_session_groups() -> None:
    plan = make_plan(
        price_plan=PricePlan(
            kind="single",
            single=__import__(
                "contracts.response_plan",
                fromlist=["CanonicalSinglePriceCandidate"],
            ).CanonicalSinglePriceCandidate(
                source_client_id="demo",
                offer_id="shared_id",
                display_text="120 000 ₽",
                amount=120_000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
        ),
        commercial_facts=(fact("shared_id", roles=("requested_fact",)),),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("shared_id",), patient_text="Ответ"),
    )
    assert resolved.finalized_commercial_ids.price_offer_ids == ("shared_id",)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("shared_id",)
    assert resolved.session_delta.shown_price_offer_ids == ("shared_id",)
    assert resolved.session_delta.shown_requested_fact_ids == ("shared_id",)


def test_same_id_service_value_and_promo_visible_once() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        service_value_candidate=ServiceValueCandidate(
            fact_id="promo_spring",
            display_text="Service promo",
            source_client_id="demo",
        ),
        promo_candidate_ids=("promo_spring",),
        commercial_facts=(fact("promo_spring", roles=("promo",)),),
        automatic_amplifier_candidate_ids=(),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert resolved.service_value_block is not None
    assert resolved.promo_blocks == ()
    assert resolved.finalized_commercial_ids.service_value_ids == ("promo_spring",)
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()


def test_same_id_promo_and_amplifier_promo_wins() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=("shared_fact",),
        automatic_amplifier_candidate_ids=("shared_fact",),
        commercial_facts=(
            fact("shared_fact", roles=("promo", "automatic_amplifier")),
        ),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert len(resolved.promo_blocks) == 1
    assert resolved.automatic_amplifier_blocks == ()
    assert resolved.finalized_commercial_ids.promo_fact_ids == ("shared_fact",)
    assert resolved.finalized_commercial_ids.amplifier_fact_ids == ()


def test_requested_fact_suppresses_service_value_promo_amplifier() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        service_value_candidate=ServiceValueCandidate(
            fact_id="installment_12",
            display_text="sv",
            source_client_id="demo",
        ),
        promo_candidate_ids=("installment_12",),
        automatic_amplifier_candidate_ids=("installment_12",),
        commercial_facts=(
            fact("installment_12", roles=("requested_fact", "promo", "automatic_amplifier")),
        ),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("installment_12",), patient_text="Ответ"),
    )
    assert len(resolved.requested_fact_blocks) == 1
    assert resolved.service_value_block is None
    assert resolved.promo_blocks == ()
    assert resolved.automatic_amplifier_blocks == ()


def test_normal_max_service_value_zero_removes_service_value() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        normal_caps=__import__("contracts.response_plan", fromlist=["ResponseCaps"]).ResponseCaps(
            max_service_value=0,
            max_promo=2,
            max_automatic_amplifiers=2,
        ),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    assert resolved.service_value_block is None
    assert resolved.finalized_commercial_ids.service_value_ids == ()


def test_finalized_required_condition_ids_match_blocks() -> None:
    resolved = resolve_response_plan(
        make_plan(),
        compose(patient_text="Ответ"),
    )
    assert resolved.finalized_commercial_ids.required_offer_condition_ids == ("per_jaw",)
    assert resolved.required_offer_conditions[0].condition_id == "per_jaw"


def test_session_shown_condition_ids_match_finalized() -> None:
    resolved = resolve_response_plan(
        make_plan(),
        compose(patient_text="Ответ"),
    )
    assert (
        resolved.session_delta.shown_required_offer_condition_ids
        == resolved.finalized_commercial_ids.required_offer_condition_ids
    )


def test_without_price_condition_groups_empty() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(patient_text="Ответ"),
    )
    assert resolved.finalized_commercial_ids.required_offer_condition_ids == ()
    assert resolved.session_delta.shown_required_offer_condition_ids == ()


def test_same_string_in_offer_fact_condition_typed_groups() -> None:
    shared = "shared_id"
    plan = make_plan(
        price_plan=PricePlan(
            kind="single",
            single=__import__(
                "contracts.response_plan",
                fromlist=["CanonicalSinglePriceCandidate"],
            ).CanonicalSinglePriceCandidate(
                source_client_id="demo",
                offer_id=shared,
                display_text="120 000 ₽",
                amount=120_000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
        ),
        commercial_facts=(fact(shared, roles=("requested_fact",)),),
        required_offer_conditions=(
            __import__(
                "contracts.response_plan",
                fromlist=["RequiredOfferConditionBlock"],
            ).RequiredOfferConditionBlock(
                source_client_id="demo",
                condition_id="per_jaw",
                display_text="cond",
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=(shared,), patient_text="Ответ"),
    )
    assert shared in resolved.finalized_commercial_ids.price_offer_ids
    assert shared in resolved.finalized_commercial_ids.requested_fact_ids
    assert "per_jaw" in resolved.finalized_commercial_ids.required_offer_condition_ids


def test_unknown_requested_fact_classification_model_contract_violation() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none"), service_value_candidate=None, textual_cta_candidate=None),
        compose(requested_fact_ids=("unknown_fact",), patient_text="Ответ"),
    )
    diag = next(item for item in resolved.diagnostics if item.code == "requested_fact_unknown")
    assert diag.classification == "model_contract_violation"


def test_none_price_plan_has_no_price_block() -> None:
    resolved = resolve_response_plan(
        make_plan(price_plan=PricePlan(kind="none")),
        compose(patient_text="Ответ"),
    )
    assert resolved.price_block is None
    assert resolved.diagnostics == ()


def test_optional_missing_promo_classification_optional_resolution() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=("missing_promo",),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    diag = next(item for item in resolved.diagnostics if item.code == "optional_candidate_unavailable")
    assert diag.classification == "optional_resolution"


def test_topic_scope_suppresses_stale_service_value() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        active_session_service_id="implantium",
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Стерилизация."))
    assert resolved.patient_text == "Стерилизация."
    assert resolved.service_value_block is None
    assert resolved.finalized_commercial_ids.service_value_ids == ()
    assert resolved.session_delta.shown_service_value_ids == ()
    assert any(item.code == "service_value_out_of_scope" for item in resolved.diagnostics)


def test_clinic_scope_suppresses_stale_service_value() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        active_session_service_id="implantium",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="О клинике."))
    assert resolved.patient_text == "О клинике."
    assert resolved.service_value_block is None
    assert resolved.finalized_commercial_ids.service_value_ids == ()
    assert any(item.code == "service_value_out_of_scope" for item in resolved.diagnostics)


def test_out_of_scope_service_value_id_still_reserves_promo() -> None:
    shared = "service_value_implant"
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="sterilization",
        price_plan=PricePlan(kind="none"),
        service_value_candidate=ServiceValueCandidate(
            fact_id=shared,
            display_text="Имплантация под ключ",
            source_client_id="demo",
        ),
        promo_candidate_ids=(shared,),
        commercial_facts=(fact(shared, roles=("promo",)),),
        automatic_amplifier_candidate_ids=(),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Стерилизация."))
    assert resolved.promo_blocks == ()
    assert shared not in resolved.finalized_commercial_ids.promo_fact_ids


def test_requested_fact_same_id_stays_requested_on_topic_scope() -> None:
    shared = "installment_12"
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="payment",
        price_plan=PricePlan(kind="none"),
        service_value_candidate=ServiceValueCandidate(
            fact_id=shared,
            display_text="sv",
            source_client_id="demo",
        ),
        promo_candidate_ids=(shared,),
        automatic_amplifier_candidate_ids=(shared,),
        commercial_facts=(
            fact(shared, roles=("requested_fact", "promo", "automatic_amplifier")),
        ),
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=(shared,), patient_text="Рассрочка."),
    )
    assert len(resolved.requested_fact_blocks) == 1
    assert resolved.service_value_block is None
    assert resolved.promo_blocks == ()
    assert resolved.automatic_amplifier_blocks == ()


@pytest.mark.parametrize(
    ("route", "mode", "composer_kwargs"),
    [
        ("ANSWER", "standard", {"patient_text": "Ответ"}),
        ("ANSWER", "contacts", {"patient_text": None}),
        ("ADMIN", "standard", {"patient_text": None}),
        ("ADMIN", "medical_terminal", {"patient_text": None}),
        ("CLARIFY", "standard", {"patient_text": "Уточните."}),
    ],
)
def test_same_composer_plan_resolves_all_five_pairs(
    route: str,
    mode: str,
    composer_kwargs: dict[str, object],
) -> None:
    plan = make_plan(
        route_authority=composer_route_authority(),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route=route, mode=mode, **composer_kwargs),
    )
    assert resolved.route == route
    assert resolved.mode == mode


def test_composer_contacts_strips_commerce() -> None:
    plan = make_plan(
        route_authority=composer_route_authority(),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="ANSWER", mode="contacts", patient_text=None),
    )
    assert resolved.terminal_text == "Контакты demo"
    assert resolved.patient_text is None
    assert resolved.price_block is None
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert resolved.finalized_commercial_ids.promo_fact_ids == ()


@pytest.mark.parametrize(
    ("route", "mode", "terminal_state", "clarify_pending"),
    [
        (route, mode, EXPECTED_TERMINAL_STATE[(route, mode)][0], EXPECTED_TERMINAL_STATE[(route, mode)][1])
        for route, mode in EXPECTED_TERMINAL_STATE
    ],
)
def test_route_mode_terminal_state_matrix(
    route: str,
    mode: str,
    terminal_state: str,
    clarify_pending: bool,
) -> None:
    if route == "ANSWER" and mode == "standard":
        resolved = resolve_response_plan(
            make_plan(price_plan=PricePlan(kind="none")),
            compose(patient_text="Ответ"),
        )
    elif route == "ANSWER" and mode == "contacts":
        resolved = resolve_response_plan(
            make_plan(
                route_authority=deterministic_route_authority(),
                price_plan=PricePlan(kind="none"),
                response_scope="clinic",
                selected_service_id=None,
                selected_topic_id=None,
                textual_cta_candidate=None,
                service_value_candidate=None,
                promo_candidate_ids=(),
                automatic_amplifier_candidate_ids=(),
            ),
            None,
        )
    elif route == "ADMIN":
        resolved = resolve_response_plan(
            make_plan(
                route_authority=composer_route_authority(
                    terminal_candidates=(
                        contacts_terminal(),
                        admin_terminal(mode="standard", text="TERMINAL"),
                        admin_terminal(mode="medical_terminal", text="TERMINAL"),
                    ),
                ),
                price_plan=PricePlan(kind="none"),
                textual_cta_candidate=None,
                service_value_candidate=None,
                promo_candidate_ids=(),
                automatic_amplifier_candidate_ids=(),
            ),
            ComposerResult(route="ADMIN", mode=mode, patient_text=None),
        )
    else:
        resolved = resolve_response_plan(
            make_plan(
                price_plan=PricePlan(kind="none"),
                response_scope="clinic",
                selected_service_id=None,
                selected_topic_id=None,
                textual_cta_candidate=None,
                service_value_candidate=None,
                promo_candidate_ids=(),
                automatic_amplifier_candidate_ids=(),
            ),
            ComposerResult(route="CLARIFY", mode="standard", patient_text="Уточните."),
        )
    assert resolved.session_delta.terminal_state == terminal_state
    assert resolved.session_delta.clarify_pending is clarify_pending
