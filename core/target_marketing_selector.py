"""Deterministic target marketing ingredient selection (S21, offline and unwired)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import (
    MarketingScenario,
    ResponseSchemaBundle,
    TargetAutomaticCommercialRefs,
    TargetMarketingPolicy,
)
from contracts.response_schema_refs import ResponseSchemaExternalIndex


from core.service_value_selection import resolve_service_value_ref


_MARKETING_SCENARIOS = frozenset(get_args(MarketingScenario))

MarketingSelectionMode = Literal[
    "automatic",
    "promotion_general",
    "promotion_service",
    "promotion_shown",
]

MarketingAnswerProfile = Literal["service", "price"]

PROMOTION_GENERAL_OVERVIEW_MAX_FACTS = 3
_PROMO_KINDS = frozenset({"promo"})


@dataclass(frozen=True, slots=True)
class TargetMarketingSelection:
    applied_scenarios: tuple[str, ...]
    selected_refs: tuple[str, ...]
    amplifier_refs: tuple[str, ...]
    cta_key: str
    selection_mode: MarketingSelectionMode = "automatic"
    service_value_ref: str | None = None


class TargetMarketingSelectionError(ValueError):
    """Typed error for invalid explicit selector inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class OptionalMarketingApplicationError(ValueError):
    """Controlled failure while applying optional marketing to a materialized answer."""

    def __init__(self, code: str, value: object = None) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _validated_sequence(
    values: Sequence[str],
    *,
    invalid_code: str,
    duplicate_code: str,
    item_is_valid: Callable[[object], bool],
) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TargetMarketingSelectionError(invalid_code, values)
    copied = tuple(values)
    for value in copied:
        if not item_is_valid(value):
            raise TargetMarketingSelectionError(invalid_code, value)
    if len(copied) != len(set(copied)):
        raise TargetMarketingSelectionError(duplicate_code, copied)
    return copied


def _is_nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_marketing_scenario(value: object) -> bool:
    return isinstance(value, str) and value in _MARKETING_SCENARIOS


def _is_source_ref(value: object) -> bool:
    if not isinstance(value, str) or ":" not in value:
        return False
    prefix, target = value.split(":", 1)
    if prefix not in {"fact", "kb", "doctor"} or not target.strip():
        return False
    if prefix == "kb":
        if target.count("#") != 1:
            return False
        document, chunk = target.split("#", 1)
        if not document.strip() or not chunk.strip():
            return False
    return True


def _marketing_answer_profile(semantic_context: str) -> MarketingAnswerProfile:
    return "price" if semantic_context == "price" else "service"


def _service_profile_block(
    policy: TargetMarketingPolicy,
    *,
    service_id: str | None,
    profile: MarketingAnswerProfile,
) -> TargetAutomaticCommercialRefs | None:
    if not service_id:
        return None
    svc_policy = policy.service_automatic_commercial.get(service_id)
    if svc_policy is None:
        return None
    return svc_policy.price if profile == "price" else svc_policy.service


def _filter_promo_refs(
    bundle: ResponseSchemaBundle,
    refs: Sequence[str],
) -> tuple[str, ...]:
    promo_refs: list[str] = []
    for ref in refs:
        if not ref.startswith("fact:"):
            continue
        fact = bundle.facts.get(ref.removeprefix("fact:"))
        if fact is None or str(fact.kind) not in _PROMO_KINDS:
            continue
        promo_refs.append(ref)
    return tuple(promo_refs)


def _ordered_automatic_promo_refs_for_context(
    bundle: ResponseSchemaBundle,
    *,
    semantic_context: str,
    service_id: str | None = None,
) -> tuple[str, ...]:
    """Automatic promo pool: per-service profile overrides global; empty profile list means none."""

    policy = bundle.marketing
    profile = _marketing_answer_profile(semantic_context)
    profile_block = _service_profile_block(
        policy,
        service_id=service_id,
        profile=profile,
    )
    if profile_block is not None:
        return _filter_promo_refs(bundle, profile_block.ordered_promo_refs)

    block = policy.initial_commercial_blocks.get(semantic_context)
    if block is None and semantic_context == "price":
        block = policy.initial_commercial_blocks.get("service")
    if block is None:
        return ()
    return _filter_promo_refs(bundle, block.ordered_fact_refs)


def _ordered_direct_promo_refs_for_context(
    bundle: ResponseSchemaBundle,
    *,
    semantic_context: str,
) -> tuple[str, ...]:
    """Direct promotion pool: global blocks only, not constrained by auto allowlists."""

    policy = bundle.marketing
    block = policy.initial_commercial_blocks.get(semantic_context)
    if block is None and semantic_context == "price":
        block = policy.initial_commercial_blocks.get("service")
    if block is None:
        return ()
    return _filter_promo_refs(bundle, block.ordered_fact_refs)


def _ordered_promo_refs_for_context(
    bundle: ResponseSchemaBundle,
    *,
    semantic_context: str,
    service_id: str | None = None,
) -> tuple[str, ...]:
    return _ordered_automatic_promo_refs_for_context(
        bundle,
        semantic_context=semantic_context,
        service_id=service_id,
    )


def _ordered_amplifier_refs_for_context(
    bundle: ResponseSchemaBundle,
    *,
    semantic_context: str,
    service_id: str | None = None,
) -> tuple[str, ...]:
    policy = bundle.marketing
    profile = _marketing_answer_profile(semantic_context)
    profile_block = _service_profile_block(
        policy,
        service_id=service_id,
        profile=profile,
    )
    if profile_block is not None:
        return tuple(profile_block.ordered_amplifier_refs)
    return tuple(policy.ordered_amplifier_refs)


def _amplifier_auto_show_allowed(
    *,
    ref: str,
    profile_block: TargetAutomaticCommercialRefs | None,
    global_refs: Sequence[str],
) -> bool:
    if profile_block is not None:
        return ref in profile_block.ordered_amplifier_refs
    return ref in global_refs


def _promo_fact_runtime_eligible(
    bundle: ResponseSchemaBundle,
    fact_ref: str,
    *,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    selected_fact_ids: set[str],
    apply_service_applicability: bool = True,
    apply_topic_applicability: bool = True,
) -> bool:
    if not fact_ref.startswith("fact:"):
        return False
    fact_id = fact_ref.removeprefix("fact:")
    fact = bundle.facts[fact_id]
    if not fact.active:
        return False
    if fact.active_from is not None and today_iso < fact.active_from:
        return False
    if fact.active_until is not None and today_iso > fact.active_until:
        return False
    if apply_service_applicability and fact.allowed_service_ids:
        if service_id is None or service_id not in fact.allowed_service_ids:
            return False
    if apply_topic_applicability and service_id is None and fact.allowed_topics:
        if not turn_topic or turn_topic not in fact.allowed_topics:
            return False
    if (
        apply_service_applicability
        and service_id is not None
        and fact.allowed_topics
        and not fact.allowed_service_ids
    ):
        return False
    if any(selected_id in fact.incompatible_with for selected_id in selected_fact_ids):
        return False
    if any(
        fact_id in bundle.facts[selected_id].incompatible_with
        for selected_id in selected_fact_ids
    ):
        return False
    return True


def _fact_is_eligible(
    bundle: ResponseSchemaBundle,
    fact_ref: str,
    *,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    shown_fact_ids: frozenset[str],
    selected_fact_ids: set[str],
    bypass_shown_fact_id: str | None = None,
) -> bool:
    fact_id = fact_ref.removeprefix("fact:")
    fact = bundle.facts[fact_id]
    if not fact.active or (
        fact_id in shown_fact_ids and fact_id != bypass_shown_fact_id
    ):
        return False
    if fact.active_from is not None and today_iso < fact.active_from:
        return False
    if fact.active_until is not None and today_iso > fact.active_until:
        return False
    if fact.allowed_service_ids and service_id not in fact.allowed_service_ids:
        return False
    if service_id is None and fact.allowed_topics:
        if not turn_topic or turn_topic not in fact.allowed_topics:
            return False
    if (
        service_id is not None
        and fact.allowed_topics
        and not fact.allowed_service_ids
    ):
        return False
    if any(selected_id in fact.incompatible_with for selected_id in selected_fact_ids):
        return False
    if any(
        fact_id in bundle.facts[selected_id].incompatible_with
        for selected_id in selected_fact_ids
    ):
        return False
    return True


def _candidate_is_eligible(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    external_kb_refs: frozenset[str],
    external_doctor_refs: frozenset[str],
    ref: str,
    semantic_context: str,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    shown_fact_ids: frozenset[str],
    shown_amplifier_refs: frozenset[str],
    selected_refs: set[str],
    selected_fact_ids: set[str],
    is_amplifier: bool,
) -> bool:
    if ref in selected_refs:
        return False
    if is_amplifier and ref in shown_amplifier_refs:
        return False
    if ref.startswith("fact:"):
        return _fact_is_eligible(
            bundle,
            ref,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_ids,
            selected_fact_ids=selected_fact_ids,
        )
    if ref.startswith("kb:"):
        return ref in external_kb_refs
    if ref.startswith("doctor:"):
        if ref not in external_doctor_refs:
            return False
        doctor = doctor_catalog.doctors.get(ref.removeprefix("doctor:"))
        if doctor is None:
            return False
        if service_id is None:
            return semantic_context == "doctors"
        return service_id in doctor.service_ids
    return False


def _automatic_commercial_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    external_kb_refs: frozenset[str],
    external_doctor_refs: frozenset[str],
    semantic_context: str,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    shown_fact_ids: frozenset[str],
    shown_amplifier_refs: frozenset[str],
    present_fact_ids: frozenset[str],
    max_promos: int,
    max_amplifiers: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Select automatic promos and amplifiers with independent quotas."""

    if max_promos <= 0 and max_amplifiers <= 0:
        return (), ()

    profile = _marketing_answer_profile(semantic_context)
    profile_block = _service_profile_block(
        bundle.marketing,
        service_id=service_id,
        profile=profile,
    )
    global_amplifier_refs = bundle.marketing.ordered_amplifier_refs

    compatibility_context = {
        fact_id for fact_id in present_fact_ids if fact_id in bundle.facts
    }
    selected_fact_ids: set[str] = set(compatibility_context)
    promo_refs: list[str] = []

    def promo_eligible(ref: str) -> bool:
        if not ref.startswith("fact:"):
            return False
        fact_id = ref.removeprefix("fact:")
        if fact_id in present_fact_ids:
            return False
        return _fact_is_eligible(
            bundle,
            ref,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_ids,
            selected_fact_ids=selected_fact_ids,
        )

    pool_promo_refs = _ordered_automatic_promo_refs_for_context(
        bundle,
        semantic_context=semantic_context,
        service_id=service_id,
    )
    for ref in pool_promo_refs:
        if len(promo_refs) >= max_promos:
            break
        if not promo_eligible(ref):
            continue
        promo_refs.append(ref)
        selected_fact_ids.add(ref.removeprefix("fact:"))

    amplifier_refs: list[str] = []
    selected_ref_set = set(promo_refs)
    amp_pool = _ordered_amplifier_refs_for_context(
        bundle,
        semantic_context=semantic_context,
        service_id=service_id,
    )
    for ref in amp_pool:
        if len(amplifier_refs) >= max_amplifiers:
            break
        if not _amplifier_auto_show_allowed(
            ref=ref,
            profile_block=profile_block,
            global_refs=global_amplifier_refs,
        ):
            continue
        if not _candidate_is_eligible(
            bundle,
            doctor_catalog,
            external_kb_refs=external_kb_refs,
            external_doctor_refs=external_doctor_refs,
            ref=ref,
            semantic_context=semantic_context,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_ids,
            shown_amplifier_refs=shown_amplifier_refs,
            selected_refs=selected_ref_set,
            selected_fact_ids=selected_fact_ids,
            is_amplifier=True,
        ):
            continue
        if ref.startswith("fact:"):
            fact_id = ref.removeprefix("fact:")
            if fact_id in present_fact_ids:
                continue
        amplifier_refs.append(ref)
        selected_ref_set.add(ref)
        if ref.startswith("fact:"):
            selected_fact_ids.add(ref.removeprefix("fact:"))

    return tuple(promo_refs), tuple(amplifier_refs)


def fact_ids_present_in_text(
    patient_text: str,
    bundle: ResponseSchemaBundle,
) -> tuple[str, ...]:
    """Return fact IDs whose canonical ``text_fact`` already appears in patient text."""

    token = str(patient_text or "")
    if not token.strip():
        return ()
    present: list[str] = []
    for fact_id, fact in bundle.facts.items():
        text = str(fact.text_fact).strip()
        if text and text in token:
            present.append(str(fact_id))
    return tuple(present)


def select_target_marketing(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    *,
    semantic_context: str,
    service_id: str | None,
    today: date,
    include_initial_block: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    turn_topic: str | None = None,
) -> TargetMarketingSelection:
    """Select exact automatic refs without reading or mutating product/session state."""

    if not _is_nonblank_string(semantic_context):
        raise TargetMarketingSelectionError(
            "marketing_semantic_context_invalid", semantic_context
        )
    if service_id is not None and not _is_nonblank_string(service_id):
        raise TargetMarketingSelectionError("marketing_service_id_invalid", service_id)
    if service_id is not None and service_id not in bundle.services:
        raise TargetMarketingSelectionError("marketing_service_not_found", service_id)
    if type(today) is not date:
        raise TargetMarketingSelectionError("marketing_today_invalid", today)
    if type(include_initial_block) is not bool:
        raise TargetMarketingSelectionError(
            "marketing_include_initial_block_invalid", include_initial_block
        )

    scenarios = _validated_sequence(
        marketing_scenarios,
        invalid_code="marketing_scenario_invalid",
        duplicate_code="marketing_scenario_duplicate",
        item_is_valid=_is_marketing_scenario,
    )
    shown_facts = _validated_sequence(
        shown_fact_ids,
        invalid_code="marketing_shown_fact_id_invalid",
        duplicate_code="marketing_shown_fact_id_duplicate",
        item_is_valid=_is_nonblank_string,
    )
    shown_amplifiers = _validated_sequence(
        shown_amplifier_refs,
        invalid_code="marketing_shown_amplifier_ref_invalid",
        duplicate_code="marketing_shown_amplifier_ref_duplicate",
        item_is_valid=_is_source_ref,
    )

    policy = bundle.marketing
    normalized_topic = turn_topic.strip() if isinstance(turn_topic, str) and turn_topic.strip() else None
    applicable_scenarios: tuple[str, ...] = ()

    external_kb_refs = frozenset(external_index.kb_refs)
    external_doctor_refs = frozenset(external_index.doctor_refs)
    shown_fact_id_set = frozenset(shown_facts)
    shown_amplifier_ref_set = frozenset(shown_amplifiers)
    today_iso = today.isoformat()
    profile = _marketing_answer_profile(semantic_context)
    max_promos, max_amplifiers = policy.limits.profile_limits(profile)

    selected_refs: list[str] = []
    amplifier_refs: list[str] = []

    if include_initial_block:
        selected_refs_list, amplifier_refs_list = _automatic_commercial_selection(
            bundle,
            doctor_catalog,
            external_kb_refs=external_kb_refs,
            external_doctor_refs=external_doctor_refs,
            semantic_context=semantic_context,
            service_id=service_id,
            turn_topic=normalized_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_id_set,
            shown_amplifier_refs=shown_amplifier_ref_set,
            present_fact_ids=frozenset(),
            max_promos=max_promos,
            max_amplifiers=max_amplifiers,
        )
        selected_refs = list(selected_refs_list)
        amplifier_refs = list(amplifier_refs_list)

    cta_key = policy.cta_contexts.get(
        semantic_context,
        policy.cta_contexts["default"],
    )
    return TargetMarketingSelection(
        applied_scenarios=applicable_scenarios,
        selected_refs=tuple(selected_refs),
        amplifier_refs=tuple(amplifier_refs),
        cta_key=cta_key,
        service_value_ref=None,
    )


_PROMO_AUTHORITY_KINDS = frozenset({"promo"})


@dataclass(frozen=True, slots=True)
class Stage51MarketingOutcome:
    selection: TargetMarketingSelection | None
    fail_closed_reason: str | None = None


def _promo_ref_is_eligible(
    bundle: ResponseSchemaBundle,
    fact_ref: str,
    *,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    shown_fact_ids: frozenset[str],
    selected_fact_ids: set[str],
    bypass_shown_fact_id: str | None,
    ignore_shown_suppression: bool = False,
    skip_service_topic_filter: bool = False,
) -> bool:
    if not fact_ref.startswith("fact:"):
        return False
    fact_id = fact_ref.removeprefix("fact:")
    if not ignore_shown_suppression:
        if fact_id in shown_fact_ids and fact_id != bypass_shown_fact_id:
            return False
    return _promo_fact_runtime_eligible(
        bundle,
        fact_ref,
        service_id=service_id,
        turn_topic=turn_topic,
        today_iso=today_iso,
        selected_fact_ids=selected_fact_ids,
        apply_service_applicability=not skip_service_topic_filter,
        apply_topic_applicability=not skip_service_topic_filter,
    )


def _ordered_service_promotion_candidate_refs(
    bundle: ResponseSchemaBundle,
    *,
    service_id: str,
) -> tuple[str, ...]:
    """Stable promo refs for a service: priority mapping, then service commercial block."""

    policy = bundle.marketing
    ordered: list[str] = []
    seen: set[str] = set()
    mapping = policy.priority_service_promos.get(service_id)
    if mapping is not None:
        for ref in mapping.ordered_fact_refs:
            if ref not in seen:
                ordered.append(ref)
                seen.add(ref)
    for ref in _ordered_direct_promo_refs_for_context(
        bundle,
        semantic_context="service",
    ):
        if ref not in seen:
            ordered.append(ref)
            seen.add(ref)
    return tuple(ordered)


def _eligible_service_promotion_refs(
    bundle: ResponseSchemaBundle,
    *,
    service_id: str,
    turn_topic: str | None,
    today_iso: str,
) -> tuple[str, ...]:
    """All eligible promo refs for a direct service-promotion answer."""

    refs: list[str] = []
    for ref in _ordered_service_promotion_candidate_refs(bundle, service_id=service_id):
        if _promo_ref_is_eligible(
            bundle,
            ref,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=frozenset(),
            selected_fact_ids=set(),
            bypass_shown_fact_id=None,
            ignore_shown_suppression=True,
        ):
            refs.append(ref)
    return tuple(refs)


def _reserve_promo_refs(
    bundle: ResponseSchemaBundle,
    *,
    route: str,
    commercial_intent: str,
    promotion_scope: str,
    service_id: str | None,
    turn_topic: str | None,
    today_iso: str,
    shown_fact_ids: frozenset[str],
    last_rendered_promo_fact_id: str | None,
    last_turn_rendered_promo_fact_ids: Sequence[str] = (),
) -> tuple[tuple[str, ...], str | None]:
    """Reserve direct/priority promo fact refs before amplifiers."""

    if route != "ANSWER":
        return (), None
    policy = bundle.marketing
    selected_fact_ids: set[str] = set()

    if commercial_intent == "promotion":
        if promotion_scope == "general":
            refs: list[str] = []
            for ref in policy.promotion_overview.ordered_fact_refs:
                if len(refs) >= PROMOTION_GENERAL_OVERVIEW_MAX_FACTS:
                    break
                if _promo_ref_is_eligible(
                    bundle,
                    ref,
                    service_id=service_id,
                    turn_topic=turn_topic,
                    today_iso=today_iso,
                    shown_fact_ids=shown_fact_ids,
                    selected_fact_ids=set(),
                    bypass_shown_fact_id=None,
                    ignore_shown_suppression=True,
                    skip_service_topic_filter=True,
                ):
                    refs.append(ref)
            return tuple(refs), None
        if promotion_scope == "service":
            if service_id is None:
                return (), "promotion_service_without_authoritative_service_id"
            refs = _eligible_service_promotion_refs(
                bundle,
                service_id=service_id,
                turn_topic=turn_topic,
                today_iso=today_iso,
            )
            return refs, None if refs else None
        if promotion_scope == "shown":
            turn_promos = _validated_sequence(
                last_turn_rendered_promo_fact_ids,
                invalid_code="marketing_last_turn_promo_id_invalid",
                duplicate_code="marketing_last_turn_promo_id_duplicate",
                item_is_valid=_is_nonblank_string,
            )
            if not turn_promos:
                if not last_rendered_promo_fact_id:
                    return (), "promotion_shown_without_session_promo"
                turn_promos = (last_rendered_promo_fact_id,)
            if len(turn_promos) > 1:
                return (), "promotion_shown_ambiguous"
            last_rendered_promo_fact_id = turn_promos[0]
            ref = f"fact:{last_rendered_promo_fact_id}"
            fact = bundle.facts.get(last_rendered_promo_fact_id)
            if fact is None or not fact.active:
                return (), "promotion_shown_promo_no_longer_eligible"
            if fact.active_from is not None and today_iso < fact.active_from:
                return (), "promotion_shown_promo_no_longer_eligible"
            if fact.active_until is not None and today_iso > fact.active_until:
                return (), "promotion_shown_promo_no_longer_eligible"
            if fact.allowed_service_ids and service_id not in fact.allowed_service_ids:
                return (), "promotion_shown_promo_no_longer_eligible"
            bypass = last_rendered_promo_fact_id
            if _promo_ref_is_eligible(
                bundle,
                ref,
                service_id=service_id,
                turn_topic=turn_topic,
                today_iso=today_iso,
                shown_fact_ids=shown_fact_ids,
                selected_fact_ids=selected_fact_ids,
                bypass_shown_fact_id=bypass,
            ):
                return (ref,), None
            return (), "promotion_shown_promo_no_longer_eligible"

    return (), None


def select_stage51_marketing(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    *,
    route: str,
    commercial_intent: str,
    promotion_scope: str,
    semantic_context: str,
    service_id: str | None,
    today: date,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    last_rendered_promo_fact_id: str | None = None,
    rendered_promo_fact_ids: Sequence[str] = (),
    last_turn_rendered_promo_fact_ids: Sequence[str] = (),
    turn_topic: str | None = None,
    direct_requested_fact_ref: str | None = None,
    shown_service_value_ids: Sequence[str] = (),
    present_fact_ids: Sequence[str] = (),
    include_automatic_block: bool = True,
) -> Stage51MarketingOutcome:
    """Stage 5.1 deterministic marketing selection — promos first, then amplifiers."""

    if route != "ANSWER":
        return Stage51MarketingOutcome(
            selection=TargetMarketingSelection(
                applied_scenarios=(),
                selected_refs=(),
                amplifier_refs=(),
                cta_key=bundle.marketing.cta_contexts.get(
                    semantic_context,
                    bundle.marketing.cta_contexts["default"],
                ),
            )
        )

    if not _is_nonblank_string(semantic_context):
        raise TargetMarketingSelectionError(
            "marketing_semantic_context_invalid", semantic_context
        )
    if service_id is not None and service_id not in bundle.services:
        raise TargetMarketingSelectionError("marketing_service_not_found", service_id)

    _validated_sequence(
        marketing_scenarios,
        invalid_code="marketing_scenario_invalid",
        duplicate_code="marketing_scenario_duplicate",
        item_is_valid=_is_marketing_scenario,
    )
    shown_facts = _validated_sequence(
        shown_fact_ids,
        invalid_code="marketing_shown_fact_id_invalid",
        duplicate_code="marketing_shown_fact_id_duplicate",
        item_is_valid=_is_nonblank_string,
    )
    shown_amplifiers = _validated_sequence(
        shown_amplifier_refs,
        invalid_code="marketing_shown_amplifier_ref_invalid",
        duplicate_code="marketing_shown_amplifier_ref_duplicate",
        item_is_valid=_is_source_ref,
    )
    shown_service_values = _validated_sequence(
        shown_service_value_ids,
        invalid_code="marketing_shown_service_value_id_invalid",
        duplicate_code="marketing_shown_service_value_id_duplicate",
        item_is_valid=_is_nonblank_string,
    )
    present_facts = _validated_sequence(
        present_fact_ids,
        invalid_code="marketing_present_fact_id_invalid",
        duplicate_code="marketing_present_fact_id_duplicate",
        item_is_valid=_is_nonblank_string,
    )

    policy = bundle.marketing
    applicable_scenarios: tuple[str, ...] = ()

    external_kb_refs = frozenset(external_index.kb_refs)
    external_doctor_refs = frozenset(external_index.doctor_refs)
    shown_fact_id_set = frozenset(shown_facts)
    shown_amplifier_ref_set = frozenset(shown_amplifiers)
    shown_service_value_id_set = frozenset(shown_service_values)
    present_fact_id_set = frozenset(present_facts)
    selected_refs: list[str] = []
    amplifier_refs: list[str] = []
    selected_ref_set: set[str] = set()
    selected_fact_ids: set[str] = set()
    profile = _marketing_answer_profile(semantic_context)
    max_promos, max_amplifiers = policy.limits.profile_limits(profile)
    today_iso = today.isoformat()

    service_value_ref: str | None = None
    if profile != "price":
        service_value_ref = resolve_service_value_ref(
            bundle,
            service_id=service_id,
            shown_service_value_ids=shown_service_value_id_set,
        )

    promo_refs, fail_reason = _reserve_promo_refs(
        bundle,
        route=route,
        commercial_intent=commercial_intent,
        promotion_scope=promotion_scope,
        service_id=service_id,
        turn_topic=turn_topic,
        today_iso=today_iso,
        shown_fact_ids=shown_fact_id_set,
        last_rendered_promo_fact_id=last_rendered_promo_fact_id,
        last_turn_rendered_promo_fact_ids=last_turn_rendered_promo_fact_ids,
    )
    if fail_reason is not None:
        return Stage51MarketingOutcome(selection=None, fail_closed_reason=fail_reason)

    if commercial_intent == "promotion":
        if not promo_refs:
            return Stage51MarketingOutcome(
                selection=None,
                fail_closed_reason="promotion_no_eligible_facts",
            )
        cta_key = policy.cta_contexts.get(
            semantic_context,
            policy.cta_contexts["default"],
        )
        promo_mode: MarketingSelectionMode
        if promotion_scope == "general":
            promo_mode = "promotion_general"
        elif promotion_scope == "service":
            promo_mode = "promotion_service"
        else:
            promo_mode = "promotion_shown"
        return Stage51MarketingOutcome(
            selection=TargetMarketingSelection(
                applied_scenarios=(),
                selected_refs=tuple(promo_refs),
                amplifier_refs=(),
                cta_key=cta_key,
                selection_mode=promo_mode,
                service_value_ref=service_value_ref,
            )
        )

    if direct_requested_fact_ref and direct_requested_fact_ref.startswith("fact:"):
        fact_id = direct_requested_fact_ref.removeprefix("fact:")
        if _fact_is_eligible(
            bundle,
            direct_requested_fact_ref,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_id_set,
            selected_fact_ids=selected_fact_ids,
            bypass_shown_fact_id=fact_id,
        ):
            selected_refs.append(direct_requested_fact_ref)
            selected_ref_set.add(direct_requested_fact_ref)
            selected_fact_ids.add(fact_id)

    if include_automatic_block:
        auto_selected, auto_amplifiers = _automatic_commercial_selection(
            bundle,
            doctor_catalog,
            external_kb_refs=external_kb_refs,
            external_doctor_refs=external_doctor_refs,
            semantic_context=semantic_context,
            service_id=service_id,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_id_set,
            shown_amplifier_refs=shown_amplifier_ref_set,
            present_fact_ids=present_fact_id_set,
            max_promos=max_promos,
            max_amplifiers=max_amplifiers,
        )
        for ref in auto_selected:
            if ref in selected_ref_set:
                continue
            selected_refs.append(ref)
            selected_ref_set.add(ref)
            if ref.startswith("fact:"):
                selected_fact_ids.add(ref.removeprefix("fact:"))
        amplifier_refs = list(auto_amplifiers)

    cta_key = policy.cta_contexts.get(
        semantic_context,
        policy.cta_contexts["default"],
    )
    return Stage51MarketingOutcome(
        selection=TargetMarketingSelection(
            applied_scenarios=applicable_scenarios,
            selected_refs=tuple(selected_refs),
            amplifier_refs=tuple(amplifier_refs),
            cta_key=cta_key,
            service_value_ref=service_value_ref,
        )
    )
