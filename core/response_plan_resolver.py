"""Pure resolver for the isolated response-plan lower path."""

from __future__ import annotations

from contracts.response_plan import (
    ALLOWED_ROUTE_MODE_PAIRS,
    CODE_OWNED_ROUTE_MODE_PAIRS,
    CodeOwnedTerminalCandidate,
    CommercialFactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    DeterministicBypassRouteAuthority,
    FinalizedCommercialIds,
    PlanDiagnostic,
    PreComposerPlan,
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
    TerminalState,
    UiButtonCandidate,
)


def resolve_response_plan(
    precomposer_plan: PreComposerPlan,
    composer_result: ComposerResult | None,
) -> ResolvedResponsePlan:
    """Resolve a frozen response plan from normalized precomposer input and Composer output."""

    _validate_plan_structure(precomposer_plan)
    _validate_client_ownership(precomposer_plan)

    authority = precomposer_plan.route_authority
    if isinstance(authority, DeterministicBypassRouteAuthority):
        if composer_result is not None:
            raise ResponsePlanContractError("composer_result_forbidden")
        return _resolve_code_owned_terminal(precomposer_plan, authority.terminal_candidate)

    if composer_result is None:
        raise ResponsePlanContractError("composer_result_required")

    selected_pair = (composer_result.route, composer_result.mode)
    allowed_pairs = {(item.route, item.mode) for item in authority.allowed_route_modes}
    if selected_pair not in allowed_pairs:
        raise ResponsePlanContractError("route_mode_conflict")

    if selected_pair == ("ANSWER", "standard"):
        return _resolve_composer_answer(precomposer_plan, composer_result)
    if selected_pair == ("ANSWER", "contacts"):
        terminal = _require_terminal_candidate(authority, selected_pair)
        return _resolve_composer_contacts(precomposer_plan, composer_result, terminal)
    if selected_pair in {("ADMIN", "standard"), ("ADMIN", "medical_terminal")}:
        terminal = _require_terminal_candidate(authority, selected_pair)
        return _resolve_composer_admin(precomposer_plan, composer_result, terminal)
    if selected_pair == ("CLARIFY", "standard"):
        return _resolve_composer_clarify(precomposer_plan, composer_result)
    raise ResponsePlanContractError("route_mode_conflict")


def _require_terminal_candidate(
    authority: ComposerSelectedRouteAuthority,
    pair: tuple[str, str],
) -> CodeOwnedTerminalCandidate:
    for terminal in authority.terminal_candidates:
        if (terminal.route, terminal.mode) == pair:
            return terminal
    raise ResponsePlanContractError("plan_structure_invalid")


def _validate_plan_structure(plan: PreComposerPlan) -> None:
    authority = plan.route_authority
    if isinstance(authority, DeterministicBypassRouteAuthority):
        pair = (authority.route_mode.route, authority.route_mode.mode)
        if pair not in CODE_OWNED_ROUTE_MODE_PAIRS:
            raise ResponsePlanContractError("plan_structure_invalid")
        terminal = authority.terminal_candidate
        if (terminal.route, terminal.mode) != pair:
            raise ResponsePlanContractError("plan_structure_invalid")
        if pair == ("ANSWER", "contacts") and terminal.authority != "contacts":
            raise ResponsePlanContractError("terminal_authority_invalid")
        if pair[0] == "ADMIN" and terminal.authority not in {
            "governed_ui",
            "deterministic_policy_terminal",
        }:
            raise ResponsePlanContractError("terminal_authority_invalid")
        return

    allowed_pairs = {(item.route, item.mode) for item in authority.allowed_route_modes}
    if not allowed_pairs:
        raise ResponsePlanContractError("plan_structure_invalid")
    for pair in allowed_pairs:
        if pair not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ResponsePlanContractError("plan_structure_invalid")
    for terminal in authority.terminal_candidates:
        pair = (terminal.route, terminal.mode)
        if pair == ("ANSWER", "contacts") and terminal.authority != "contacts":
            raise ResponsePlanContractError("terminal_authority_invalid")
        if pair[0] == "ADMIN" and terminal.authority not in {
            "governed_ui",
            "deterministic_policy_terminal",
        }:
            raise ResponsePlanContractError("terminal_authority_invalid")


def _validate_client_ownership(plan: PreComposerPlan) -> None:
    client_id = plan.session_key.client_id
    owned = _collect_owned_candidates(plan)
    for candidate in owned:
        source_client_id = getattr(candidate, "source_client_id", None)
        if source_client_id != client_id:
            raise ResponsePlanContractError("client_source_mismatch")


def _collect_owned_candidates(plan: PreComposerPlan) -> list[object]:
    items: list[object] = []
    authority = plan.route_authority
    if isinstance(authority, DeterministicBypassRouteAuthority):
        items.append(authority.terminal_candidate)
        if authority.terminal_candidate.canonical_contact is not None:
            items.append(authority.terminal_candidate.canonical_contact)
    else:
        for terminal in authority.terminal_candidates:
            items.append(terminal)
            if terminal.canonical_contact is not None:
                items.append(terminal.canonical_contact)
    if plan.price_plan.single is not None:
        items.append(plan.price_plan.single)
    if plan.price_plan.multi is not None:
        items.append(plan.price_plan.multi)
    items.extend(plan.required_offer_conditions)
    items.extend(plan.commercial_facts)
    if plan.service_value_candidate is not None:
        items.append(plan.service_value_candidate)
    if plan.textual_cta_candidate is not None:
        items.append(plan.textual_cta_candidate)
    items.extend(plan.ui_candidates.quick_replies)
    items.extend(plan.ui_candidates.buttons)
    if plan.ui_candidates.widget is not None:
        items.append(plan.ui_candidates.widget)
    if plan.ui_candidates.video is not None:
        items.append(plan.ui_candidates.video)
    return items


def _reserved_service_value_fact_id(plan: PreComposerPlan) -> str | None:
    if plan.service_value_candidate is None:
        return None
    return plan.service_value_candidate.fact_id


def _session_scope_ids(plan: PreComposerPlan) -> tuple[str | None, str | None]:
    if plan.response_scope == "service":
        return plan.selected_service_id, plan.selected_topic_id
    if plan.response_scope == "topic":
        return None, plan.selected_topic_id
    return None, None


def _resolve_code_owned_terminal(
    plan: PreComposerPlan,
    terminal: CodeOwnedTerminalCandidate,
) -> ResolvedResponsePlan:
    terminal_state: TerminalState
    if terminal.route == "ANSWER" and terminal.mode == "contacts":
        terminal_state = "contacts"
    elif terminal.mode == "medical_terminal":
        terminal_state = "medical_terminal"
    else:
        terminal_state = "admin"
    ui_plan = _resolve_terminal_ui(plan, terminal)
    finalized = FinalizedCommercialIds()
    session_delta = _build_session_delta(plan, finalized, terminal_state=terminal_state)
    return ResolvedResponsePlan(
        route=terminal.route,
        mode=terminal.mode,
        context_strategy=plan.context_strategy,
        response_scope=plan.response_scope,
        transport_kind=plan.transport_kind,
        patient_text=None,
        terminal_text=terminal.display_text,
        ui_plan=ui_plan,
        finalized_commercial_ids=finalized,
        session_delta=session_delta,
    )


def _resolve_composer_contacts(
    plan: PreComposerPlan,
    composer: ComposerResult,
    terminal: CodeOwnedTerminalCandidate,
) -> ResolvedResponsePlan:
    ui_plan = _resolve_terminal_ui(plan, terminal)
    finalized = FinalizedCommercialIds()
    session_delta = _build_session_delta(plan, finalized, terminal_state="contacts")
    return ResolvedResponsePlan(
        route=composer.route,
        mode=composer.mode,
        context_strategy=plan.context_strategy,
        response_scope=plan.response_scope,
        transport_kind=plan.transport_kind,
        patient_text=None,
        terminal_text=terminal.display_text,
        ui_plan=ui_plan,
        finalized_commercial_ids=finalized,
        session_delta=session_delta,
    )


def _resolve_composer_admin(
    plan: PreComposerPlan,
    composer: ComposerResult,
    terminal: CodeOwnedTerminalCandidate,
) -> ResolvedResponsePlan:
    terminal_state: TerminalState = (
        "medical_terminal" if composer.mode == "medical_terminal" else "admin"
    )
    ui_plan = _resolve_terminal_ui(plan, terminal)
    finalized = FinalizedCommercialIds()
    session_delta = _build_session_delta(plan, finalized, terminal_state=terminal_state)
    return ResolvedResponsePlan(
        route=composer.route,
        mode=composer.mode,
        context_strategy=plan.context_strategy,
        response_scope=plan.response_scope,
        transport_kind=plan.transport_kind,
        patient_text=None,
        terminal_text=terminal.display_text,
        ui_plan=ui_plan,
        finalized_commercial_ids=finalized,
        session_delta=session_delta,
    )


def _resolve_composer_clarify(
    plan: PreComposerPlan,
    composer: ComposerResult,
) -> ResolvedResponsePlan:
    ui_plan = _resolve_clarify_ui(plan)
    finalized = FinalizedCommercialIds()
    session_delta = _build_session_delta(
        plan,
        finalized,
        terminal_state="clarify",
        clarify_pending=True,
    )
    return ResolvedResponsePlan(
        route=composer.route,
        mode=composer.mode,
        context_strategy=plan.context_strategy,
        response_scope=plan.response_scope,
        transport_kind=plan.transport_kind,
        patient_text=composer.patient_text,
        terminal_text=None,
        ui_plan=ui_plan,
        finalized_commercial_ids=finalized,
        session_delta=session_delta,
    )


def _resolve_composer_answer(
    plan: PreComposerPlan,
    composer: ComposerResult,
) -> ResolvedResponsePlan:
    diagnostics: list[PlanDiagnostic] = []
    price_block, price_diag = _resolve_price(plan, composer)
    diagnostics.extend(price_diag)
    required_conditions = _resolve_required_conditions(plan, price_block is not None)
    facts_by_id = {fact.fact_id: fact for fact in plan.commercial_facts}

    requested_blocks, requested_diag = _resolve_requested_facts(plan, composer, facts_by_id)
    diagnostics.extend(requested_diag)
    requested_ids = {block.fact_id for block in requested_blocks}

    is_price_answer = price_block is not None
    caps = plan.price_caps if is_price_answer else plan.normal_caps
    reserved_service_value_id = _reserved_service_value_fact_id(plan)

    service_value_block, service_value_diag = _resolve_service_value(
        plan,
        requested_ids,
        is_price_answer,
        caps,
    )
    diagnostics.extend(service_value_diag)
    promo_blocks, promo_diag = _resolve_promo_blocks(
        plan,
        facts_by_id,
        requested_ids,
        reserved_service_value_id,
        caps.max_promo,
    )
    diagnostics.extend(promo_diag)
    amplifier_blocks, amplifier_diag = _resolve_amplifier_blocks(
        plan,
        facts_by_id,
        requested_ids,
        reserved_service_value_id,
        promo_blocks,
        caps.max_automatic_amplifiers,
    )
    diagnostics.extend(amplifier_diag)
    textual_cta_block = _resolve_textual_cta(plan)
    ui_plan = _resolve_commerce_ui(plan)
    finalized = _build_finalized_ids(
        price_block,
        required_conditions,
        requested_blocks,
        service_value_block,
        promo_blocks,
        amplifier_blocks,
    )
    session_delta = _build_session_delta(plan, finalized, terminal_state="none")
    return ResolvedResponsePlan(
        route=composer.route,
        mode=composer.mode,
        context_strategy=plan.context_strategy,
        response_scope=plan.response_scope,
        transport_kind=plan.transport_kind,
        patient_text=composer.patient_text,
        terminal_text=None,
        price_block=price_block,
        required_offer_conditions=required_conditions,
        requested_fact_blocks=tuple(requested_blocks),
        service_value_block=service_value_block,
        promo_blocks=tuple(promo_blocks),
        automatic_amplifier_blocks=tuple(amplifier_blocks),
        textual_cta_block=textual_cta_block,
        ui_plan=ui_plan,
        diagnostics=tuple(diagnostics),
        finalized_commercial_ids=finalized,
        session_delta=session_delta,
    )


def _resolve_price(
    plan: PreComposerPlan,
    composer: ComposerResult,
) -> tuple[ResolvedPriceBlock | None, list[PlanDiagnostic]]:
    del composer
    price_plan = plan.price_plan
    if price_plan.kind == "none" or not price_plan.offer_applicable:
        return None, []

    if price_plan.kind == "multi":
        assert price_plan.multi is not None
        multi = price_plan.multi
        return (
            ResolvedPriceBlock(
                source_client_id=multi.source_client_id,
                offer_ids=multi.offer_ids,
                display_text=multi.display_text,
                owner="canonical_multi",
            ),
            [],
        )

    assert price_plan.single is not None
    single = price_plan.single
    return (
        ResolvedPriceBlock(
            source_client_id=single.source_client_id,
            offer_ids=(single.offer_id,),
            display_text=single.display_text,
            owner="canonical_single",
            amount=single.amount,
            currency=single.currency,
            billing_unit=single.billing_unit,
        ),
        [],
    )


def _resolve_required_conditions(
    plan: PreComposerPlan,
    has_price_block: bool,
) -> tuple[RequiredOfferConditionBlock, ...]:
    if not has_price_block:
        return ()
    return plan.required_offer_conditions


def _fact_applicable(plan: PreComposerPlan, fact: CommercialFactCandidate) -> bool:
    if fact.applicability == "clinic_wide":
        return True
    if fact.applicability == "topic_scoped":
        return (
            plan.response_scope == "topic"
            and plan.selected_topic_id is not None
            and plan.selected_topic_id in fact.allowed_topic_ids
        )
    if fact.applicability == "service_scoped":
        return (
            plan.response_scope == "service"
            and plan.selected_service_id is not None
            and plan.selected_service_id in fact.allowed_service_ids
        )
    return False


def _implant_scope_ok(plan: PreComposerPlan, fact: CommercialFactCandidate) -> bool:
    if not fact.requires_implant_scope and fact.fact_id != "implant_warranty":
        return True
    if plan.response_scope == "service":
        return (
            plan.selected_service_id is not None
            and plan.selected_service_id in fact.allowed_service_ids
        )
    if plan.response_scope == "topic":
        return (
            plan.selected_topic_id is not None
            and plan.selected_topic_id in fact.allowed_topic_ids
        )
    return False


def _resolve_requested_facts(
    plan: PreComposerPlan,
    composer: ComposerResult,
    facts_by_id: dict[str, CommercialFactCandidate],
) -> tuple[list[ResolvedFactBlock], list[PlanDiagnostic]]:
    diagnostics: list[PlanDiagnostic] = []
    blocks: list[ResolvedFactBlock] = []
    for fact_id in composer.requested_fact_ids:
        fact = facts_by_id.get(fact_id)
        if fact is None or "requested_fact" not in fact.allowed_roles:
            diagnostics.append(PlanDiagnostic(code="requested_fact_unknown", detail=fact_id))
            continue
        if not _fact_applicable(plan, fact):
            diagnostics.append(PlanDiagnostic(code="requested_fact_inapplicable", detail=fact_id))
            continue
        if not _implant_scope_ok(plan, fact):
            diagnostics.append(PlanDiagnostic(code="requested_fact_inapplicable", detail=fact_id))
            continue
        blocks.append(
            ResolvedFactBlock(
                fact_id=fact.fact_id,
                display_text=fact.display_text,
                role="requested_fact",
                source_client_id=fact.source_client_id,
            )
        )
    return blocks, diagnostics


def _resolve_service_value(
    plan: PreComposerPlan,
    requested_ids: set[str],
    is_price_answer: bool,
    caps: ResponseCaps,
) -> tuple[ResolvedServiceValueBlock | None, list[PlanDiagnostic]]:
    candidate = plan.service_value_candidate
    if candidate is None:
        return None, []
    if candidate.fact_id in requested_ids:
        return None, []
    if is_price_answer or caps.max_service_value == 0:
        return None, []
    if plan.response_scope != "service" or plan.selected_service_id is None:
        return None, [
            PlanDiagnostic(
                code="service_value_out_of_scope",
                detail=candidate.fact_id,
            )
        ]
    return (
        ResolvedServiceValueBlock(
            fact_id=candidate.fact_id,
            display_text=candidate.display_text,
            source_client_id=candidate.source_client_id,
        ),
        [],
    )


def _resolve_promo_blocks(
    plan: PreComposerPlan,
    facts_by_id: dict[str, CommercialFactCandidate],
    requested_ids: set[str],
    reserved_service_value_id: str | None,
    max_promo: int,
) -> tuple[list[ResolvedFactBlock], list[PlanDiagnostic]]:
    diagnostics: list[PlanDiagnostic] = []
    blocks: list[ResolvedFactBlock] = []
    for fact_id in plan.promo_candidate_ids:
        if len(blocks) >= max_promo:
            break
        if fact_id in requested_ids or fact_id == reserved_service_value_id:
            continue
        fact = facts_by_id.get(fact_id)
        if fact is None or "promo" not in fact.allowed_roles:
            diagnostics.append(PlanDiagnostic(code="optional_candidate_unavailable", detail=fact_id))
            continue
        if fact.explicit_only:
            diagnostics.append(
                PlanDiagnostic(code="explicit_only_automatic_suppressed", detail=fact_id)
            )
            continue
        if not _fact_applicable(plan, fact):
            diagnostics.append(PlanDiagnostic(code="optional_candidate_unavailable", detail=fact_id))
            continue
        blocks.append(
            ResolvedFactBlock(
                fact_id=fact.fact_id,
                display_text=fact.display_text,
                role="promo",
                source_client_id=fact.source_client_id,
            )
        )
    return blocks, diagnostics


def _resolve_amplifier_blocks(
    plan: PreComposerPlan,
    facts_by_id: dict[str, CommercialFactCandidate],
    requested_ids: set[str],
    reserved_service_value_id: str | None,
    promo_blocks: list[ResolvedFactBlock],
    max_amplifiers: int,
) -> tuple[list[ResolvedFactBlock], list[PlanDiagnostic]]:
    diagnostics: list[PlanDiagnostic] = []
    blocks: list[ResolvedFactBlock] = []
    promo_ids = {block.fact_id for block in promo_blocks}
    for fact_id in plan.automatic_amplifier_candidate_ids:
        if len(blocks) >= max_amplifiers:
            break
        if fact_id in requested_ids or fact_id in promo_ids or fact_id == reserved_service_value_id:
            continue
        fact = facts_by_id.get(fact_id)
        if fact is None:
            diagnostics.append(PlanDiagnostic(code="optional_candidate_unavailable", detail=fact_id))
            continue
        if fact.explicit_only or fact.fact_id == "implant_warranty":
            diagnostics.append(
                PlanDiagnostic(code="explicit_only_automatic_suppressed", detail=fact_id)
            )
            continue
        if "automatic_amplifier" not in fact.allowed_roles:
            diagnostics.append(PlanDiagnostic(code="optional_candidate_unavailable", detail=fact_id))
            continue
        if not _fact_applicable(plan, fact):
            diagnostics.append(PlanDiagnostic(code="optional_candidate_unavailable", detail=fact_id))
            continue
        blocks.append(
            ResolvedFactBlock(
                fact_id=fact.fact_id,
                display_text=fact.display_text,
                role="automatic_amplifier",
                source_client_id=fact.source_client_id,
            )
        )
    return blocks, diagnostics


def _resolve_textual_cta(plan: PreComposerPlan) -> ResolvedTextualCtaBlock | None:
    candidate = plan.textual_cta_candidate
    if candidate is None:
        return None
    return ResolvedTextualCtaBlock(
        source_client_id=candidate.source_client_id,
        text=candidate.text,
    )


def _resolve_terminal_ui(
    plan: PreComposerPlan,
    terminal: CodeOwnedTerminalCandidate,
) -> ResolvedUiPlan:
    buttons: tuple[UiButtonCandidate, ...] = ()
    if terminal.canonical_contact is not None:
        buttons = (
            UiButtonCandidate(
                source_client_id=terminal.canonical_contact.source_client_id,
                button_id="contact_call",
                label="Позвонить",
                action_kind="contact",
            ),
        )
    return ResolvedUiPlan(buttons=buttons, contact=terminal.canonical_contact)


def _resolve_clarify_ui(plan: PreComposerPlan) -> ResolvedUiPlan:
    return ResolvedUiPlan(quick_replies=plan.ui_candidates.quick_replies)


def _resolve_commerce_ui(plan: PreComposerPlan) -> ResolvedUiPlan:
    return ResolvedUiPlan(
        quick_replies=plan.ui_candidates.quick_replies,
        buttons=plan.ui_candidates.buttons,
        widget=plan.ui_candidates.widget,
        video=plan.ui_candidates.video,
    )


def _build_finalized_ids(
    price_block: ResolvedPriceBlock | None,
    required_conditions: tuple[RequiredOfferConditionBlock, ...],
    requested_blocks: list[ResolvedFactBlock],
    service_value_block: ResolvedServiceValueBlock | None,
    promo_blocks: list[ResolvedFactBlock],
    amplifier_blocks: list[ResolvedFactBlock],
) -> FinalizedCommercialIds:
    return FinalizedCommercialIds(
        requested_fact_ids=tuple(block.fact_id for block in requested_blocks),
        promo_fact_ids=tuple(block.fact_id for block in promo_blocks),
        amplifier_fact_ids=tuple(block.fact_id for block in amplifier_blocks),
        service_value_ids=(
            (service_value_block.fact_id,) if service_value_block is not None else ()
        ),
        price_offer_ids=tuple(price_block.offer_ids) if price_block is not None else (),
        required_offer_condition_ids=tuple(
            block.condition_id for block in required_conditions
        ),
    )


def _build_session_delta(
    plan: PreComposerPlan,
    finalized: FinalizedCommercialIds,
    *,
    terminal_state: TerminalState,
    clarify_pending: bool = False,
) -> ResponseSessionDelta:
    active_service_id, active_topic_id = _session_scope_ids(plan)
    return ResponseSessionDelta(
        session_key=plan.session_key,
        active_service_id=active_service_id,
        active_topic_id=active_topic_id,
        shown_requested_fact_ids=finalized.requested_fact_ids,
        shown_promo_ids=finalized.promo_fact_ids,
        shown_amplifier_ids=finalized.amplifier_fact_ids,
        shown_service_value_ids=finalized.service_value_ids,
        shown_price_offer_ids=finalized.price_offer_ids,
        shown_required_offer_condition_ids=finalized.required_offer_condition_ids,
        terminal_state=terminal_state,
        clarify_pending=clarify_pending,
    )
