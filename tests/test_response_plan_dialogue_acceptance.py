"""ONE-CALL-OFFLINE-ACCEPTANCE-1: end-to-end dialogue acceptance via recording backend."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from contracts.response_plan import CanonicalContactCandidate, FinalizedCommercialIds, SessionKey
from contracts.response_plan_adapter import ResponsePlanAdapterTerminalAuthority
from contracts.response_plan_composer_input import ComposerFullContextCorpus, model_visible_session_context
from core.response_plan_composer_executor import ComposerExecutorError, ComposerOutputError
from contracts.response_plan_materialization import OfferConditionEvidence, ResponsePlanMaterializationSources
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_plan_session import (
    PersistedShownCommercialIds,
    SessionCompletionReceipt,
    SessionContinuityPolicy,
)
from contracts.response_schema import RequestedDisplayPolicy, ResponseSchemaBundle, TargetFixedPrice
from core.response_plan_materialization import materialize_pre_composer_payload
from core.response_plan_session import commit_session_update
from core.response_plan_session_store import ResponsePlanSessionStore
from core.response_plan_session_turn import (
    begin_bound_session_turn,
    execute_bound_session_turn,
    prepare_bound_session_turn,
)
from core.response_schema_loader import load_response_schema_bundle
from core.target_cached_full_context import build_target_cached_full_context
from tests.test_response_plan_composer_executor import RecordingBackend, _answer_json
from tests.test_response_plan_composer_input import _demo_corpus
from tests.test_response_plan_materialization import (
    AS_OF,
    SESSION,
    _complete_empty_evidence,
    _complete_with_conditions,
    _sources,
    _synthetic_filter_bundle,
)

TARGET_ROOT = Path("clients/demo/target_response")
NIKADENT_ROOT = Path("clients/nikadent/target_response")
SHARED_SID = "acceptance-shared-sid"

# SYNTHETIC_POLICY_FIXTURE: complete+empty condition evidence is not clinic-authored metadata.
SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE = (
    "OfferConditionEvidence completeness=complete with empty conditions for all_on_4 fixed offers"
)


@dataclass(frozen=True, slots=True)
class TurnSpec:
    patient_message: str
    request_id: str
    composer_json: dict[str, object]


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    prepared: object
    pipeline: object
    backend: RecordingBackend
    bound: object


@dataclass(frozen=True, slots=True)
class DialogueContext:
    label: str
    data_kind: str
    session_key: SessionKey
    material: PostComposerMaterialAuthority
    corpus: ComposerFullContextCorpus
    condition_evidence: dict[str, OfferConditionEvidence]
    condition_evidence_note: str | None = None


def _ordered_union(before: tuple[str, ...], current: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in (*before, *current):
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return tuple(merged)


def _assert_accumulated_group(
    before: PersistedShownCommercialIds,
    finalized: FinalizedCommercialIds,
    after: PersistedShownCommercialIds,
    *,
    group: str,
) -> None:
    expected = _ordered_union(getattr(before, group), getattr(finalized, group))
    assert getattr(after, group) == expected


def _synthetic_warranty_topic_policy_bundle(base: ResponseSchemaBundle) -> ResponseSchemaBundle:
    facts = dict(base.facts)
    facts["implant_warranty"] = facts["implant_warranty"].model_copy(
        update={
            "requested_display_policy": RequestedDisplayPolicy(
                allow_clinic=False,
                allowed_topic_ids=("implantation",),
                canonical_text_is_scope_qualified=True,
            )
        }
    )
    return base.model_copy(update={"facts": facts})


def _policy(**overrides: int) -> SessionContinuityPolicy:
    base = {
        "active_service_max_age_turns": 5,
        "active_topic_max_age_turns": 5,
        "situation_max_age_turns": 5,
        "shown_options_max_age_turns": 5,
        "history_pair_limit": 20,
    }
    base.update(overrides)
    return SessionContinuityPolicy(**base)


def _store(tmp_path: Path) -> ResponsePlanSessionStore:
    import sqlite3

    db_path = tmp_path / "acceptance.db"

    def factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    store = ResponsePlanSessionStore(factory)
    store.ensure_schema()
    return store


def _composer_dict(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = json.loads(_answer_json())
    payload.update(overrides)
    return payload


def _fixed_offer_ids(bundle: ResponseSchemaBundle, service_ids: tuple[str, ...]) -> tuple[str, ...]:
    ids: list[str] = []
    for offer in bundle.offers:
        if offer.service_id not in service_ids or not offer.active:
            continue
        if isinstance(offer.price, TargetFixedPrice):
            ids.append(offer.offer_id)
    return tuple(sorted(ids))


def _offer_by_id(bundle: ResponseSchemaBundle, offer_id: str):
    for offer in bundle.offers:
        if offer.offer_id == offer_id:
            return offer
    raise KeyError(offer_id)


def synthetic_all_on_4_price_evidence(client_id: str = "demo") -> dict[str, OfferConditionEvidence]:
    return _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )


def synthetic_full_arch_price_evidence(bundle: ResponseSchemaBundle, client_id: str = "demo") -> dict[str, OfferConditionEvidence]:
    offer_ids = _fixed_offer_ids(bundle, ("all_on_4", "all_on_6"))
    return _complete_empty_evidence(*offer_ids)


def _demo_context(*, evidence: dict[str, OfferConditionEvidence] | None = None, note: str | None = None) -> DialogueContext:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    return DialogueContext(
        label="demo",
        data_kind="REAL_CATALOG",
        session_key=SESSION,
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence=evidence if evidence is not None else {},
        condition_evidence_note=note,
    )


def _nikadent_context() -> DialogueContext:
    bundle = load_response_schema_bundle(NIKADENT_ROOT)
    cached = build_target_cached_full_context(Path("clients/nikadent/md"))
    corpus = ComposerFullContextCorpus(source_client_id="nikadent", cached_full_context=cached)
    return DialogueContext(
        label="nikadent",
        data_kind="REAL_CATALOG",
        session_key=SessionKey(client_id="nikadent", sid=SHARED_SID),
        material=PostComposerMaterialAuthority(source_client_id="nikadent", bundle=bundle),
        corpus=corpus,
        condition_evidence={},
    )


def _synthetic_installment_policy_bundle(base: ResponseSchemaBundle) -> ResponseSchemaBundle:
    facts = dict(base.facts)
    facts["installment_12"] = facts["installment_12"].model_copy(
        update={
            "requested_display_policy": RequestedDisplayPolicy(
                allow_clinic=True,
                allowed_topic_ids=("implantation",),
                canonical_text_is_scope_qualified=True,
            )
        }
    )
    return base.model_copy(update={"facts": facts})


def _terminal_authorities_for(client_id: str) -> tuple[ResponsePlanAdapterTerminalAuthority, ...]:
    phone = "+7 (495) 000-00-00" if client_id == "demo" else "+7"
    contact = CanonicalContactCandidate(source_client_id=client_id, phone=phone)
    return (
        ResponsePlanAdapterTerminalAuthority(
            source_client_id=client_id,
            route="ANSWER",
            mode="contacts",
            authority="contacts",
            display_text=f"Контакты {client_id}",
            canonical_contact=contact,
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id=client_id,
            route="ADMIN",
            mode="standard",
            authority="governed_ui",
            display_text=f"ADMIN standard {client_id}",
            canonical_contact=contact,
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id=client_id,
            route="ADMIN",
            mode="medical_terminal",
            authority="deterministic_policy_terminal",
            display_text=f"ADMIN medical {client_id}",
            canonical_contact=contact,
        ),
    )


def _materialization_sources(ctx: DialogueContext) -> ResponsePlanMaterializationSources:
    return _sources(
        ctx.material,
        session_key=ctx.session_key,
        condition_evidence_by_offer=ctx.condition_evidence,
        terminal_authorities=_terminal_authorities_for(ctx.material.source_client_id),
    )


class DialogueRunner:
    def __init__(
        self,
        *,
        store: ResponsePlanSessionStore,
        ctx: DialogueContext,
        policy: SessionContinuityPolicy,
    ) -> None:
        self.store = store
        self.ctx = ctx
        self.policy = policy

    def run_turn(self, spec: TurnSpec, *, commit: bool = True) -> TurnOutcome:
        snapshot = self.store.read(self.ctx.session_key)
        bound = begin_bound_session_turn(
            snapshot,
            policy=self.policy,
            source_client_id=self.ctx.material.source_client_id,
            bundle=self.ctx.material.bundle,
            request_id=spec.request_id,
            patient_message=spec.patient_message,
        )
        backend = RecordingBackend(json.dumps(spec.composer_json, ensure_ascii=False))
        pipeline = execute_bound_session_turn(
            bound,
            material=self.ctx.material,
            corpus=self.ctx.corpus,
            allowed_source_refs=tuple(self.ctx.corpus.cached_full_context.document_paths),
            sources=_materialization_sources(self.ctx),
            backend=backend,
            as_of=AS_OF,
        )
        prepared = prepare_bound_session_turn(bound, pipeline)
        if commit:
            commit_session_update(
                self.store,
                prepared,
                SessionCompletionReceipt(
                    session_key=self.ctx.session_key,
                    request_id=spec.request_id,
                    update_fingerprint=prepared.update_fingerprint,
                    transport_kind="blocking",
                ),
                policy=self.policy,
                source_state=snapshot.state,
            )
        return TurnOutcome(prepared=prepared, pipeline=pipeline, backend=backend, bound=bound)

    def read(self):
        return self.store.read(self.ctx.session_key)


def _assert_one_backend_call(outcome: TurnOutcome, *, patient_message: str) -> None:
    assert len(outcome.backend.calls) == 1
    invocation = outcome.backend.calls[0]
    dynamic = json.loads(invocation.user_prompt)  # type: ignore[union-attr]
    assert dynamic["current_user_message"] == patient_message
    assert len(dynamic["recent_dialogue"]) <= 6


def test_a_explicit_service_overview_then_active_session_price(tmp_path: Path) -> None:
    ctx = _demo_context(
        evidence=synthetic_all_on_4_price_evidence(),
        note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE,
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    turn1_text = "All-on-4 — это протокол на 4 имплантах."
    turn1 = runner.run_turn(
        TurnSpec(
            patient_message="Расскажите про All-on-4",
            request_id="a1",
            composer_json=_composer_dict(
                patient_text=turn1_text,
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    _assert_one_backend_call(turn1, patient_message="Расскажите про All-on-4")
    assert turn1.pipeline.materialized.resolved.patient_text == turn1_text
    assert turn1.pipeline.materialized.resolved.service_options_block is None

    snapshot = runner.read()
    bound2 = begin_bound_session_turn(
        snapshot,
        policy=_policy(),
        source_client_id=ctx.material.source_client_id,
        bundle=ctx.material.bundle,
        request_id="a2",
        patient_message="А сколько стоит?",
    )
    assert bound2.read_bundle.active_session_service_id == "all_on_4"

    accumulated_before = runner.read().state.accumulated_shown_ids

    turn2_text = "Сейчас подскажу стоимость обсуждаемого протокола."
    turn2 = runner.run_turn(
        TurnSpec(
            patient_message="А сколько стоит?",
            request_id="a2",
            composer_json=_composer_dict(
                patient_text=turn2_text,
                service_reference_kind="active_session",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["price"],
            ),
        )
    )
    _assert_one_backend_call(turn2, patient_message="А сколько стоит?")
    resolved = turn2.pipeline.materialized.resolved
    assert resolved.patient_text == turn2_text
    assert resolved.price_block is not None
    assert turn2.pipeline.selection.price_candidate_service_ids == ("all_on_4",)
    assert all(offer_id.startswith("all_on_4") for offer_id in resolved.price_block.offer_ids)
    for row in resolved.price_block.offer_rows:
        offer = _offer_by_id(ctx.material.bundle, row.offer_id)
        assert isinstance(offer.price, TargetFixedPrice)
        assert row.amount == offer.price.amount

    turn2_finalized = resolved.finalized_commercial_ids
    assert turn2_finalized.price_offer_ids
    accumulated_after = runner.read().state.accumulated_shown_ids
    _assert_accumulated_group(
        accumulated_before,
        turn2_finalized,
        accumulated_after,
        group="price_offer_ids",
    )

    turn3 = runner.run_turn(
        TurnSpec(
            patient_message="Расскажите ещё про протокол",
            request_id="a3",
            composer_json=_composer_dict(
                patient_text="Дополнительные детали протокола.",
                service_reference_kind="active_session",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    assert turn3.pipeline.materialized.resolved.price_block is None
    assert runner.read().state.accumulated_shown_ids.price_offer_ids == accumulated_after.price_offer_ids


def test_b_situation_options_comparison_then_prices(tmp_path: Path) -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    ctx = _demo_context(
        evidence=synthetic_full_arch_price_evidence(bundle),
        note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE + "; includes all_on_6 fixed offers",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())

    turn1 = runner.run_turn(
        TurnSpec(
            patient_message="Нет зубов сверху. Какие варианты есть?",
            request_id="b1",
            composer_json=_composer_dict(
                patient_text="Для верхней челюсти есть несколько протоколов.",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
                patient_situation={
                    "extent": "full_arch",
                    "jaw": "upper",
                    "stage": "unknown",
                    "modifiers": [],
                },
            ),
        )
    )
    options = turn1.pipeline.materialized.resolved.service_options_block
    assert options is not None
    shown_ids = tuple(item.service_id for item in options.options)
    assert shown_ids[:2] == ("all_on_4", "all_on_6")
    assert turn1.pipeline.materialized.resolved.price_block is None

    turn2 = runner.run_turn(
        TurnSpec(
            patient_message="Чем они отличаются?",
            request_id="b2",
            composer_json=_composer_dict(
                patient_text="Кратко сравню показанные варианты.",
                service_reference_kind="none",
                option_reference_kind="shown_options",
                topic_id=None,
                requested_aspect_ids=["comparison"],
            ),
        )
    )
    assert turn2.pipeline.materialized.resolved.price_block is None
    assert turn2.pipeline.materialized.resolved.service_options_block is None
    assert turn2.pipeline.selection.comparison_service_ids == shown_ids

    turn3 = runner.run_turn(
        TurnSpec(
            patient_message="Сколько стоит каждый из этих вариантов?",
            request_id="b3",
            composer_json=_composer_dict(
                patient_text="Сейчас покажу цены по обсуждаемым вариантам.",
                service_reference_kind="none",
                option_reference_kind="shown_options",
                topic_id=None,
                requested_aspect_ids=["price"],
            ),
        )
    )
    resolved = turn3.pipeline.materialized.resolved
    assert resolved.price_block is not None
    assert resolved.service_options_block is None
    assert set(turn3.pipeline.selection.price_candidate_service_ids) == set(shown_ids)
    assert len(resolved.price_block.offer_rows) >= 2
    labels = {row.offer_label for row in resolved.price_block.offer_rows}
    assert len(labels) == len(resolved.price_block.offer_rows)


def test_c_clinic_question_does_not_reuse_implant_service(tmp_path: Path) -> None:
    ctx = _demo_context(evidence=synthetic_all_on_4_price_evidence(), note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    runner.run_turn(
        TurnSpec(
            patient_message="Сколько стоит All-on-4?",
            request_id="c1",
            composer_json=_composer_dict(
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["price"],
            ),
        )
    )
    turn2 = runner.run_turn(
        TurnSpec(
            patient_message="Какие у вас часы работы?",
            request_id="c2",
            composer_json=_composer_dict(
                patient_text="Отвечу по режиму работы клиники.",
                service_reference_kind="none",
                explicit_service_id=None,
                topic_id=None,
                requested_aspect_ids=["contact_hours"],
            ),
        )
    )
    assert turn2.pipeline.selection.price_candidate_service_ids == ()
    assert turn2.pipeline.materialized.resolved.price_block is None
    assert turn2.pipeline.selection.response_scope == "clinic"
    assert turn2.pipeline.materialized.resolved.patient_text == "Отвечу по режиму работы клиники."


def test_c_stale_active_service_after_legal_turns(tmp_path: Path) -> None:
    ctx = _demo_context(evidence=synthetic_all_on_4_price_evidence(), note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE)
    stale_policy = _policy(active_service_max_age_turns=1)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=stale_policy)

    runner.run_turn(
        TurnSpec(
            patient_message="Расскажите про All-on-4",
            request_id="c-stale-1",
            composer_json=_composer_dict(
                patient_text="All-on-4 — протокол на 4 имплантах.",
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    after_turn1 = runner.read().state
    assert after_turn1.active_service is not None
    assert after_turn1.active_service.service_id == "all_on_4"
    assert after_turn1.active_service.set_at_turn == 1

    runner.run_turn(
        TurnSpec(
            patient_message="А подробнее про сроки?",
            request_id="c-stale-2",
            composer_json=_composer_dict(
                patient_text="Продолжаю про обсуждаемый протокол.",
                service_reference_kind="active_session",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    after_turn2 = runner.read().state
    assert after_turn2.active_service is not None
    assert after_turn2.active_service.service_id == "all_on_4"
    assert after_turn2.active_service.set_at_turn == 1

    snapshot = runner.read()
    bound3 = begin_bound_session_turn(
        snapshot,
        policy=stale_policy,
        source_client_id=ctx.material.source_client_id,
        bundle=ctx.material.bundle,
        request_id="c-stale-3",
        patient_message="Продолжаем",
    )
    visible = model_visible_session_context(bound3.read_bundle.composer_session_context)  # type: ignore[attr-defined]
    assert visible["active_service_id"] is None
    assert any(item.lane == "active_service" for item in bound3.read_bundle.freshness_diagnostics)

    turn3 = runner.run_turn(
        TurnSpec(
            patient_message="Продолжаем",
            request_id="c-stale-3",
            composer_json=_composer_dict(
                patient_text="Ответ после истечения active service.",
                service_reference_kind="active_session",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    assert turn3.pipeline.selection.reference_service_id is None


def test_d_synthetic_installment_clinic_wide_requested(tmp_path: Path) -> None:
    bundle = _synthetic_installment_policy_bundle(load_response_schema_bundle(TARGET_ROOT))
    ctx = DialogueContext(
        label="demo_installment_policy",
        data_kind="SYNTHETIC_POLICY_FIXTURE",
        session_key=SESSION,
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence={},
        condition_evidence_note="requested_display_policy injected on installment_12",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Есть рассрочка?",
            request_id="d-installment",
            composer_json=_composer_dict(
                patient_text="Про рассрочку.",
                topic_id=None,
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert "installment_12" in resolved.finalized_commercial_ids.requested_fact_ids
    installment_text = bundle.facts["installment_12"].text_fact
    assert installment_text in outcome.prepared.rendered_text


def test_d_real_installment_clinic_with_display_policy_is_shown(tmp_path: Path) -> None:
    ctx = _demo_context()
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Есть рассрочка?",
            request_id="d-real-installment",
            composer_json=_composer_dict(
                patient_text="Про рассрочку.",
                topic_id=None,
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert "installment_12" in resolved.finalized_commercial_ids.requested_fact_ids
    installment_text = ctx.material.bundle.facts["installment_12"].text_fact
    assert installment_text in outcome.prepared.rendered_text


def test_d_synthetic_installment_without_display_policy_is_not_shown(tmp_path: Path) -> None:
    base = load_response_schema_bundle(TARGET_ROOT)
    facts = dict(base.facts)
    facts["installment_12"] = facts["installment_12"].model_copy(update={"requested_display_policy": None})
    bundle = base.model_copy(update={"facts": facts})
    ctx = DialogueContext(
        label="demo_installment_no_policy",
        data_kind="SYNTHETIC_FIXTURE",
        session_key=SESSION,
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence={},
        condition_evidence_note="requested_display_policy removed on installment_12",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Есть рассрочка?",
            request_id="d-synthetic-gap",
            composer_json=_composer_dict(
                patient_text="Про рассрочку.",
                topic_id=None,
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert resolved.finalized_commercial_ids.requested_fact_ids == ()
    selection_codes = {d.code for d in outcome.pipeline.selection.diagnostics}
    assert "requested_fact_inapplicable" in selection_codes


def test_d_warranty_not_automatic_without_request(tmp_path: Path) -> None:
    ctx = _demo_context(evidence=synthetic_all_on_4_price_evidence(), note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Расскажите про All-on-4",
            request_id="d-no-warranty",
            composer_json=_composer_dict(
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    finalized = outcome.pipeline.materialized.resolved.finalized_commercial_ids
    assert "implant_warranty" not in finalized.requested_fact_ids
    assert "implant_warranty" not in finalized.promo_fact_ids
    assert "implant_warranty" not in finalized.amplifier_fact_ids


def test_d_promo_not_repeated_from_accumulated_memory(tmp_path: Path) -> None:
    ctx = _demo_context(evidence=synthetic_all_on_4_price_evidence(), note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    turn1 = runner.run_turn(
        TurnSpec(
            patient_message="Расскажите про All-on-4",
            request_id="d-promo-1",
            composer_json=_composer_dict(
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    turn1_finalized = turn1.pipeline.materialized.resolved.finalized_commercial_ids
    turn1_promos = set(turn1_finalized.promo_fact_ids)
    assert turn1_promos, "turn 1 must show at least one promo fact"
    accumulated_after_turn1 = runner.read().state.accumulated_shown_ids
    _assert_accumulated_group(
        PersistedShownCommercialIds(),
        turn1_finalized,
        accumulated_after_turn1,
        group="promo_fact_ids",
    )

    turn2 = runner.run_turn(
        TurnSpec(
            patient_message="Продолжаем",
            request_id="d-promo-2",
            composer_json=_composer_dict(
                service_reference_kind="active_session",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    turn2_promos = set(turn2.pipeline.materialized.resolved.finalized_commercial_ids.promo_fact_ids)
    assert not (turn2_promos & turn1_promos)
    accumulated_after_turn2 = runner.read().state.accumulated_shown_ids
    assert set(accumulated_after_turn2.promo_fact_ids) >= turn1_promos


def test_c1_requested_warranty_in_topic_scope(tmp_path: Path) -> None:
    bundle = _synthetic_warranty_topic_policy_bundle(load_response_schema_bundle(TARGET_ROOT))
    ctx = DialogueContext(
        label="demo_warranty_topic_policy",
        data_kind="SYNTHETIC_POLICY_FIXTURE",
        session_key=SESSION,
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence={},
        condition_evidence_note="requested_display_policy injected on implant_warranty for implantation topic",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    runner.run_turn(
        TurnSpec(
            patient_message="Интересует имплантация",
            request_id="c1-topic",
            composer_json=_composer_dict(
                patient_text="Расскажу про имплантацию в целом.",
                service_reference_kind="none",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    turn2 = runner.run_turn(
        TurnSpec(
            patient_message="Какая гарантия?",
            request_id="c1-warranty",
            composer_json=_composer_dict(
                patient_text="Про гарантию на имплантацию.",
                service_reference_kind="none",
                explicit_service_id=None,
                topic_id="implantation",
                requested_aspect_ids=[],
                requested_fact_ids=["implant_warranty"],
            ),
        )
    )
    selection = turn2.pipeline.selection
    assert selection.response_scope == "topic"
    assert selection.reference_service_id is None
    resolved = turn2.pipeline.materialized.resolved
    finalized = resolved.finalized_commercial_ids
    assert finalized.requested_fact_ids == ("implant_warranty",)
    assert "implant_warranty" not in finalized.promo_fact_ids
    assert "implant_warranty" not in finalized.amplifier_fact_ids
    warranty_text = bundle.facts["implant_warranty"].text_fact
    assert warranty_text in turn2.prepared.rendered_text
    assert runner.read().state.accumulated_shown_ids.requested_fact_ids == ("implant_warranty",)


def test_c2_requested_fact_and_promo_same_id_single_visible_block(tmp_path: Path) -> None:
    fact_id = "implant_same_day_discount"
    ctx = _demo_context(evidence=synthetic_all_on_4_price_evidence(), note=SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="All-on-4 и скидка",
            request_id="c2-overlap",
            composer_json=_composer_dict(
                patient_text="All-on-4 и условия акции.",
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
                requested_fact_ids=[fact_id],
            ),
        )
    )
    payload = materialize_pre_composer_payload(
        outcome.pipeline.selection,
        outcome.pipeline.adapted,
        _materialization_sources(ctx),
        as_of=AS_OF,
    )
    matches = [fact for fact in payload.plan.commercial_facts if fact.fact_id == fact_id]
    assert len(matches) == 1
    assert "requested_fact" in matches[0].allowed_roles
    assert "promo" in matches[0].allowed_roles

    resolved = outcome.pipeline.materialized.resolved
    finalized = resolved.finalized_commercial_ids
    assert finalized.requested_fact_ids == (fact_id,)
    assert fact_id not in finalized.promo_fact_ids
    assert fact_id not in finalized.amplifier_fact_ids
    promo_block_ids = {block.fact_id for block in resolved.promo_blocks}
    amplifier_block_ids = {block.fact_id for block in resolved.automatic_amplifier_blocks}
    requested_roles = {block.fact_id: block.role for block in resolved.requested_fact_blocks}
    assert fact_id in requested_roles
    assert requested_roles[fact_id] == "requested_fact"
    assert fact_id not in promo_block_ids
    assert fact_id not in amplifier_block_ids
    fact_text = ctx.material.bundle.facts[fact_id].text_fact
    assert outcome.prepared.rendered_text.count(fact_text) == 1
    assert outcome.prepared.proposed_state.accumulated_shown_ids.requested_fact_ids == (fact_id,)


def test_c3_end_to_end_price_with_nonempty_required_conditions(tmp_path: Path) -> None:
    from core.response_text_renderer import _condition_display_texts

    implantium_id = "all_on_4.jaw.implantium"
    impro_id = "all_on_4.jaw.impro"
    implantium_condition = "ACCEPTANCE-COND-IMPLANTIUM"
    impro_condition = "ACCEPTANCE-COND-IMPRO"
    ctx = _demo_context(
        evidence={
            implantium_id: _complete_with_conditions(
                implantium_id,
                text=implantium_condition,
            ),
            impro_id: _complete_with_conditions(
                impro_id,
                text=impro_condition,
            ),
        },
        note="synthetic complete conditions on two all_on_4 fixed offers",
    )
    patient_text = "Стоимость протокола All-on-4."
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    accumulated_before = runner.read().state.accumulated_shown_ids
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Цена All-on-4",
            request_id="c3-conditions",
            composer_json=_composer_dict(
                patient_text=patient_text,
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["price"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert resolved.price_block is not None
    assert resolved.service_options_block is None

    rows_by_id = {row.offer_id: row for row in resolved.price_block.offer_rows}
    assert rows_by_id.keys() >= {implantium_id, impro_id}
    for offer_id in (implantium_id, impro_id):
        row = rows_by_id[offer_id]
        offer = _offer_by_id(ctx.material.bundle, offer_id)
        assert isinstance(offer.price, TargetFixedPrice)
        assert row.amount == offer.price.amount
        assert row.currency == offer.price.currency
        assert row.billing_unit == offer.price.billing_unit

    assert resolved.required_offer_conditions
    entries = {
        entry.offer_id: entry.display_text
        for block in resolved.required_offer_conditions
        for entry in block.entries
    }
    assert entries[implantium_id] == implantium_condition
    assert entries[impro_id] == impro_condition

    rendered = outcome.prepared.rendered_text
    price_text = resolved.price_block.display_text.strip()
    condition_texts = _condition_display_texts(resolved.required_offer_conditions)
    assert len(condition_texts) >= 2
    assert any(implantium_condition in text for text in condition_texts)
    assert any(impro_condition in text for text in condition_texts)
    patient_clean = patient_text.strip()
    price_end = rendered.index(price_text) + len(price_text)
    patient_start = rendered.index(patient_clean)
    for condition_text in condition_texts:
        condition_start = rendered.index(condition_text)
        condition_end = condition_start + len(condition_text)
        assert price_end <= condition_start
        assert condition_end <= patient_start

    finalized = resolved.finalized_commercial_ids
    assert finalized.price_offer_ids
    assert finalized.required_offer_condition_ids
    accumulated_after = runner.read().state.accumulated_shown_ids
    _assert_accumulated_group(
        accumulated_before,
        finalized,
        accumulated_after,
        group="price_offer_ids",
    )
    _assert_accumulated_group(
        accumulated_before,
        finalized,
        accumulated_after,
        group="required_offer_condition_ids",
    )


@pytest.mark.parametrize(
    "case_id,composer_overrides,expect_price,expect_diag",
    [
        (
            "unknown_requested_fact",
            {"requested_fact_ids": ["unknown_fact_xyz"]},
            False,
            None,
        ),
        (
            "unknown_condition_completeness",
            {
                "service_reference_kind": "explicit_current",
                "explicit_service_id": "all_on_4",
                "requested_aspect_ids": ["price"],
            },
            False,
            "materialization_price_conditions_unknown",
        ),
    ],
)
def test_e_missing_material_preserves_patient_text(
    tmp_path: Path,
    case_id: str,
    composer_overrides: dict[str, object],
    expect_price: bool,
    expect_diag: str | None,
) -> None:
    if case_id == "unknown_condition_completeness":
        evidence = {
            "all_on_4.jaw.implantium": OfferConditionEvidence(
                source_client_id="demo",
                offer_id="all_on_4.jaw.implantium",
                completeness="unknown",
                conditions=(),
            )
        }
        note = "synthetic unknown completeness on one offer"
    else:
        evidence = synthetic_all_on_4_price_evidence()
        note = SYNTHETIC_ALL_ON_4_EVIDENCE_NOTE
    ctx = _demo_context(evidence=evidence, note=note)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    patient_text = f"Сохранить текст для {case_id}."
    outcome = runner.run_turn(
        TurnSpec(
            patient_message=f"вопрос {case_id}",
            request_id=f"e-{case_id}",
            composer_json=_composer_dict(patient_text=patient_text, **composer_overrides),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert resolved.patient_text == patient_text
    if expect_price:
        assert resolved.price_block is not None
    else:
        assert resolved.price_block is None
    if expect_diag is not None:
        codes = {d.code for d in outcome.pipeline.materialized.materialization_diagnostics}
        assert expect_diag in codes


def test_e_complete_empty_conditions_allows_price(tmp_path: Path) -> None:
    ctx = _demo_context(
        evidence=_complete_empty_evidence("all_on_4.jaw.implantium"),
        note="single-offer complete+empty synthetic evidence",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Цена All-on-4 Implantium",
            request_id="e-complete-empty",
            composer_json=_composer_dict(
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                requested_aspect_ids=["price"],
            ),
        )
    )
    assert outcome.pipeline.materialized.resolved.price_block is not None


def test_e_unsupported_price_mode_emits_diagnostic_and_keeps_materializable_offer(tmp_path: Path) -> None:
    bundle = _synthetic_filter_bundle()
    ctx = DialogueContext(
        label="cap_offers",
        data_kind="SYNTHETIC_POLICY_FIXTURE",
        session_key=SESSION,
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence=_complete_empty_evidence("cap_fixed"),
        condition_evidence_note="synthetic cap_from/range/no_public_price offers",
    )
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Цена",
            request_id="e-unsupported",
            composer_json=_composer_dict(
                service_reference_kind="explicit_current",
                explicit_service_id="service_one",
                requested_aspect_ids=["price"],
            ),
        )
    )
    diags = {d.code for d in outcome.pipeline.materialized.materialization_diagnostics}
    assert "materialization_unsupported_price_mode" in diags
    resolved = outcome.pipeline.materialized.resolved
    assert resolved.price_block is not None
    assert resolved.price_block.offer_ids == ("cap_fixed",)
    excluded = {row.offer_id for row in resolved.price_block.offer_rows}
    assert "cap_from" not in excluded
    assert "cap_range" not in excluded
    assert "cap_no_public" not in excluded


@pytest.mark.parametrize(
    "route,mode,patient_text,expect_commerce",
    [
        ("ANSWER", "standard", "Обычный ответ.", True),
        ("ANSWER", "contacts", None, False),
        ("ADMIN", "standard", None, False),
        ("ADMIN", "medical_terminal", None, False),
        ("CLARIFY", "standard", "Уточните, пожалуйста.", False),
    ],
)
def test_f_route_mode_matrix_via_session_pipeline(
    tmp_path: Path,
    route: str,
    mode: str,
    patient_text: str | None,
    expect_commerce: bool,
) -> None:
    ctx = _demo_context()
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="маршрут",
            request_id=f"f-{route}-{mode}",
            composer_json=_composer_dict(route=route, mode=mode, patient_text=patient_text),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    if route == "ANSWER" and mode == "standard":
        assert resolved.patient_text == patient_text
    if route == "ANSWER" and mode == "contacts":
        assert resolved.terminal_text == "Контакты demo"
        contact = outcome.prepared.ui_projection.contact
        assert contact is not None
        assert contact.phone == "+7 (495) 000-00-00"
        assert contact.source_client_id == "demo"
    if route == "ADMIN":
        assert resolved.patient_text is None
        assert resolved.terminal_text is not None
    if not expect_commerce:
        assert resolved.finalized_commercial_ids.price_offer_ids == ()
        assert resolved.finalized_commercial_ids.promo_fact_ids == ()


def test_g_client_sessions_with_same_sid_do_not_mix(tmp_path: Path) -> None:
    store = _store(tmp_path)
    demo_ctx = replace(_demo_context(), session_key=SessionKey(client_id="demo", sid=SHARED_SID))
    demo = DialogueRunner(
        store=store,
        ctx=demo_ctx,
        policy=_policy(),
    )
    nikadent = DialogueRunner(store=store, ctx=_nikadent_context(), policy=_policy())

    demo.run_turn(
        TurnSpec(
            patient_message="DEMO-ISOLATION-MARKER",
            request_id="g-demo",
            composer_json=_composer_dict(patient_text="DEMO-ASSISTANT-MARKER"),
        )
    )
    nikadent.run_turn(
        TurnSpec(
            patient_message="NIKADENT-ISOLATION-MARKER",
            request_id="g-nika",
            composer_json=_composer_dict(patient_text="NIKADENT-ASSISTANT-MARKER"),
        )
    )

    demo_state = demo.read().state
    nika_state = nikadent.read().state
    assert demo_state.session_key.client_id == "demo"
    assert nika_state.session_key.client_id == "nikadent"
    assert demo_state.session_key.sid == SHARED_SID
    assert nika_state.session_key.sid == SHARED_SID
    assert demo_state.dialogue_pairs[-1].assistant_text == "DEMO-ASSISTANT-MARKER"
    assert nika_state.dialogue_pairs[-1].assistant_text == "NIKADENT-ASSISTANT-MARKER"
    assert all("NIKADENT" not in pair.patient_text for pair in demo_state.dialogue_pairs)
    assert all("DEMO-ISOLATION" not in pair.patient_text for pair in nika_state.dialogue_pairs)


def test_h_backend_exception_leaves_store_empty(tmp_path: Path) -> None:
    ctx = _demo_context()
    store = _store(tmp_path)
    snapshot = store.read(ctx.session_key)
    bound = begin_bound_session_turn(
        snapshot,
        policy=_policy(),
        source_client_id=ctx.material.source_client_id,
        bundle=ctx.material.bundle,
        request_id="h-backend",
        patient_message="fail",
    )
    backend = RecordingBackend(_answer_json(), should_raise=RuntimeError("backend failed"))
    with pytest.raises(ComposerExecutorError):
        execute_bound_session_turn(
            bound,
            material=ctx.material,
            corpus=ctx.corpus,
            allowed_source_refs=tuple(ctx.corpus.cached_full_context.document_paths),
            sources=_materialization_sources(ctx),
            backend=backend,
            as_of=AS_OF,
        )
    assert len(backend.calls) == 1
    assert store.read(ctx.session_key).exists_in_store is False


def test_h_malformed_json_prevents_prepare_and_commit(tmp_path: Path) -> None:
    ctx = _demo_context()
    store = _store(tmp_path)
    snapshot = store.read(ctx.session_key)
    bound = begin_bound_session_turn(
        snapshot,
        policy=_policy(),
        source_client_id=ctx.material.source_client_id,
        bundle=ctx.material.bundle,
        request_id="h-malformed",
        patient_message="bad json",
    )
    backend = RecordingBackend("{not json")
    with pytest.raises(ComposerOutputError):
        execute_bound_session_turn(
            bound,
            material=ctx.material,
            corpus=ctx.corpus,
            allowed_source_refs=tuple(ctx.corpus.cached_full_context.document_paths),
            sources=_materialization_sources(ctx),
            backend=backend,
            as_of=AS_OF,
        )
    assert store.read(ctx.session_key).exists_in_store is False


def test_h_no_commit_leaves_state_unchanged(tmp_path: Path) -> None:
    ctx = _demo_context()
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    runner.run_turn(
        TurnSpec(
            patient_message="no commit",
            request_id="h-nocommit",
            composer_json=_composer_dict(),
        ),
        commit=False,
    )
    assert runner.read().exists_in_store is False


def test_h_idempotency_replay_is_noop(tmp_path: Path) -> None:
    ctx = _demo_context()
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    prepared_a = runner.run_turn(
        TurnSpec(
            patient_message="one",
            request_id="h-a",
            composer_json=_composer_dict(patient_text="answer one"),
        )
    ).prepared
    for request_id, message in (("h-b", "two"), ("h-c", "three")):
        runner.run_turn(
            TurnSpec(
                patient_message=message,
                request_id=request_id,
                composer_json=_composer_dict(patient_text=f"answer {message}"),
            )
        )
    replay = runner.store.commit(
        prepared_a,
        SessionCompletionReceipt(
            session_key=ctx.session_key,
            request_id="h-a",
            update_fingerprint=prepared_a.update_fingerprint,
            transport_kind="blocking",
        ),
        policy=_policy(),
        source_state=runner.read().state,
    )
    assert replay.idempotent_replay is True
    assert runner.read().state.last_committed_turn_index == 3
