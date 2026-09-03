from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_materialization import OfferConditionEvidence, ResponsePlanMaterializationSources
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_plan_session import (
    PreparedSessionUpdate,
    PersistedActiveService,
    PersistedShownOptionsSnapshot,
    ResponsePlanSessionContractError,
    SESSION_SCHEMA_VERSION,
    SessionCompletionReceipt,
    SessionContinuityPolicy,
    SessionDialoguePair,
)
from core.response_plan_session import commit_session_update
from core.response_plan_session_store import ResponsePlanSessionStore
from core.response_plan_session_turn import (
    begin_bound_session_turn,
    execute_bound_session_turn,
    materialization_sources_for_bound_turn,
    prepare_bound_session_turn,
)
from core.response_schema_loader import load_response_schema_bundle
from tests.test_response_plan_composer_executor import RecordingBackend, _answer_json
from tests.test_response_plan_composer_input import _demo_corpus
from tests.test_response_plan_materialization import (
    AS_OF,
    SESSION,
    _complete_empty_evidence,
    _sources,
)

TARGET_ROOT = Path("clients/demo/target_response")


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle):
    return PostComposerMaterialAuthority(source_client_id="demo", bundle=demo_bundle)


def _policy() -> SessionContinuityPolicy:
    return SessionContinuityPolicy(
        active_service_max_age_turns=5,
        active_topic_max_age_turns=5,
        situation_max_age_turns=5,
        shown_options_max_age_turns=5,
        history_pair_limit=20,
    )


def _store(tmp_path: Path) -> ResponsePlanSessionStore:
    db_path = tmp_path / "integration.db"

    def factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    store = ResponsePlanSessionStore(factory)
    store.ensure_schema()
    return store


def _all_on_4_evidence() -> dict[str, OfferConditionEvidence]:
    return _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )


@dataclass
class TurnSpec:
    patient_message: str
    composer_json: dict[str, object]
    request_id: str


def _run_turn(
    *,
    store: ResponsePlanSessionStore,
    material: PostComposerMaterialAuthority,
    session_key: SessionKey,
    spec: TurnSpec,
    policy: SessionContinuityPolicy,
    commit: bool = True,
) -> tuple[PreparedSessionUpdate, object]:
    snapshot = store.read(session_key)
    bound = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id=material.source_client_id,
        bundle=material.bundle,
        request_id=spec.request_id,
        patient_message=spec.patient_message,
    )
    corpus = _demo_corpus(session_key.client_id)
    backend = RecordingBackend(json.dumps(spec.composer_json, ensure_ascii=False))
    pipeline = execute_bound_session_turn(
        bound,
        material=material,
        corpus=corpus,
        allowed_source_refs=tuple(corpus.cached_full_context.document_paths),
        sources=_sources(material, condition_evidence_by_offer=_all_on_4_evidence()),
        backend=backend,
        as_of=AS_OF,
    )
    prepared = prepare_bound_session_turn(bound, pipeline)
    if not commit:
        return prepared, pipeline
    receipt = SessionCompletionReceipt(
        session_key=session_key,
        request_id=spec.request_id,
        update_fingerprint=prepared.update_fingerprint,
        transport_kind="blocking",
    )
    commit_session_update(
        store,
        prepared,
        receipt,
        policy=policy,
        source_state=snapshot.state,
    )
    return prepared, pipeline


def test_empty_session_read_no_insert(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    snapshot = store.read(SESSION)
    assert snapshot.exists_in_store is False
    bound = begin_bound_session_turn(
        snapshot,
        policy=_policy(),
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="r0",
        patient_message="Привет",
    )
    assert bound.read_bundle.active_session_service_id is None


def test_explicit_service_then_price_follow_up(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        spec=TurnSpec(
            patient_message="Сколько стоит All-on-4?",
            request_id="t1",
            composer_json=json.loads(
                _answer_json(
                    service_reference_kind="explicit_current",
                    explicit_service_id="all_on_4",
                    topic_id="implantation",
                    requested_aspect_ids=["price"],
                )
            ),
        ),
    )
    snapshot = store.read(SESSION)
    bound = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="t2",
        patient_message="А сколько стоит?",
    )
    assert bound.read_bundle.active_session_service_id == "all_on_4"
    _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        spec=TurnSpec(
            patient_message="А сколько стоит?",
            request_id="t2",
            composer_json=json.loads(
                _answer_json(
                    service_reference_kind="active_session",
                    explicit_service_id=None,
                    topic_id="implantation",
                    requested_aspect_ids=["price"],
                )
            ),
        ),
    )
    after = store.read(SESSION)
    assert after.state.active_service is not None
    assert after.state.active_service.service_id == "all_on_4"
    assert after.state.active_service.provenance == "active_session"


def test_situation_persists_after_round_trip(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        spec=TurnSpec(
            patient_message="Нет зубов на верхней челюсти",
            request_id="s1",
            composer_json=json.loads(
                _answer_json(
                    topic_id="implantation",
                    requested_aspect_ids=["overview"],
                    patient_situation={
                        "extent": "full_arch",
                        "jaw": "upper",
                        "stage": "unknown",
                        "modifiers": [],
                    },
                )
            ),
        ),
    )
    snapshot = store.read(SESSION)
    bound = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="s2",
        patient_message="Продолжаем",
    )
    assert bound.read_bundle.prior_situation_state is not None
    assert bound.read_bundle.prior_situation_state.extent == "full_arch"


def test_no_commit_leaves_state_unchanged(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    prepared, _ = _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        commit=False,
        spec=TurnSpec(
            patient_message="Привет",
            request_id="nc1",
            composer_json=json.loads(_answer_json()),
        ),
    )
    assert prepared is not None
    assert store.read(SESSION).exists_in_store is False


def test_idempotency_abc_then_replay_a(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    prepared_a, _ = _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        spec=TurnSpec(
            patient_message="one",
            request_id="a",
            composer_json=json.loads(_answer_json(patient_text="answer one")),
        ),
    )
    for request_id, message in (("b", "two"), ("c", "three")):
        _run_turn(
            store=store,
            material=demo_material,
            session_key=SESSION,
            policy=policy,
            spec=TurnSpec(
                patient_message=message,
                request_id=request_id,
                composer_json=json.loads(_answer_json(patient_text=f"answer {message}")),
            ),
        )
    replay = store.commit(
        prepared_a,
        SessionCompletionReceipt(
            session_key=SESSION,
            request_id="a",
            update_fingerprint=prepared_a.update_fingerprint,
            transport_kind="blocking",
        ),
        policy=policy,
        source_state=store.read(SESSION).state,
    )
    assert replay.idempotent_replay is True
    assert store.read(SESSION).state.last_committed_turn_index == 3


def test_shown_promo_memory_reaches_next_materialization(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    turn1_spec = TurnSpec(
        patient_message="Расскажите про All-on-4",
        request_id="promo1",
        composer_json=json.loads(
            _answer_json(
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            )
        ),
    )
    prepared1, _ = _run_turn(
        store=store,
        material=demo_material,
        session_key=SESSION,
        policy=policy,
        spec=turn1_spec,
    )
    promo_ids = prepared1.proposed_state.accumulated_shown_ids.promo_fact_ids
    assert promo_ids, "turn 1 should finalize at least one promo fact"

    snapshot = store.read(SESSION)
    bound2 = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="promo2",
        patient_message="Продолжаем про All-on-4",
    )
    accumulated = bound2.read_bundle.accumulated_shown_ids  # type: ignore[attr-defined]
    assert accumulated.promo_fact_ids == promo_ids
    assert accumulated.requested_fact_ids == prepared1.proposed_state.accumulated_shown_ids.requested_fact_ids

    base_sources = _sources(demo_material, condition_evidence_by_offer=_all_on_4_evidence())
    bound_sources = materialization_sources_for_bound_turn(bound2, base_sources=base_sources)
    assert bound_sources.shown_promo_fact_ids == promo_ids
    assert bound_sources.shown_requested_fact_ids == accumulated.requested_fact_ids
    assert bound_sources.shown_amplifier_fact_ids == accumulated.amplifier_fact_ids
    assert bound_sources.shown_service_value_ids == accumulated.service_value_ids

    corpus = _demo_corpus(SESSION.client_id)
    backend = RecordingBackend(
        _answer_json(
            service_reference_kind="active_session",
            explicit_service_id=None,
            topic_id="implantation",
            requested_aspect_ids=["overview"],
        )
    )
    pipeline2 = execute_bound_session_turn(
        bound2,
        material=demo_material,
        corpus=corpus,
        allowed_source_refs=tuple(corpus.cached_full_context.document_paths),
        sources=base_sources,
        backend=backend,
        as_of=AS_OF,
    )
    turn1_promos = set(promo_ids)
    turn2_promos = set(pipeline2.materialized.resolved.finalized_commercial_ids.promo_fact_ids)
    assert not (turn2_promos & turn1_promos), "automatic promo must not repeat from session memory"


def test_prepare_rejects_pipeline_from_different_request(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    snapshot = store.read(SESSION)
    bound_a = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="req-a",
        patient_message="Первый запрос",
    )
    bound_b = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id="demo",
        bundle=demo_material.bundle,
        request_id="req-b",
        patient_message="Второй запрос",
    )
    corpus = _demo_corpus(SESSION.client_id)
    pipeline_b = execute_bound_session_turn(
        bound_b,
        material=demo_material,
        corpus=corpus,
        allowed_source_refs=tuple(corpus.cached_full_context.document_paths),
        sources=_sources(demo_material, condition_evidence_by_offer=_all_on_4_evidence()),
        backend=RecordingBackend(_answer_json()),
        as_of=AS_OF,
    )
    with pytest.raises(ResponsePlanSessionContractError, match="bound_pipeline_binding_mismatch"):
        prepare_bound_session_turn(bound_a, pipeline_b)


def _insert_session_state(
    store: ResponsePlanSessionStore,
    state: object,
) -> None:
    import json

    from contracts.response_plan_session import ResponsePlanSessionState

    assert isinstance(state, ResponsePlanSessionState)
    connection = store._connection_factory()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO response_plan_session_state (
                client_id, sid, schema_version, revision, last_committed_turn_index, state_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                state.session_key.client_id,
                state.session_key.sid,
                state.schema_version,
                state.revision,
                state.last_committed_turn_index,
                json.dumps(state.model_dump(mode="json")),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _count_idempotency_rows(store: ResponsePlanSessionStore, session_key: SessionKey) -> int:
    connection = store._connection_factory()
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) FROM response_plan_session_idempotency
            WHERE client_id = ? AND sid = ?
            """,
            (session_key.client_id, session_key.sid),
        ).fetchone()
        return int(row[0])
    finally:
        connection.close()


def _seed_active_service_with_shown_snapshot(
    *,
    active_service_id: str = "all_on_4",
    shown_service_ids: tuple[str, ...] = ("all_on_4", "all_on_6"),
) -> object:
    from contracts.response_plan_session import ResponsePlanSessionState

    shown = PersistedShownOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=shown_service_ids,
        shown_at_turn=1,
    )
    return ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=SESSION,
        revision=1,
        last_committed_turn_index=1,
        dialogue_pairs=(
            SessionDialoguePair(
                patient_text="seed",
                assistant_text="seed reply",
                committed_at_turn=1,
            ),
        ),
        active_service=PersistedActiveService(
            service_id=active_service_id,
            provenance="explicit_current",
            set_at_turn=1,
        ),
        shown_options_snapshot=shown,
    )


def _run_shown_options_bridge_turn(
    *,
    store: ResponsePlanSessionStore,
    material: PostComposerMaterialAuthority,
    policy: SessionContinuityPolicy,
    patient_message: str,
    request_id: str,
    composer_json: dict[str, object],
    commit: bool,
) -> tuple[PreparedSessionUpdate, object, RecordingBackend]:
    snapshot = store.read(SESSION)
    bound = begin_bound_session_turn(
        snapshot,
        policy=policy,
        source_client_id=material.source_client_id,
        bundle=material.bundle,
        request_id=request_id,
        patient_message=patient_message,
    )
    corpus = _demo_corpus(SESSION.client_id)
    backend = RecordingBackend(json.dumps(composer_json, ensure_ascii=False))
    pipeline = execute_bound_session_turn(
        bound,
        material=material,
        corpus=corpus,
        allowed_source_refs=tuple(corpus.cached_full_context.document_paths),
        sources=_sources(material, condition_evidence_by_offer=_all_on_4_evidence()),
        backend=backend,
        as_of=AS_OF,
    )
    prepared = prepare_bound_session_turn(bound, pipeline)
    if commit:
        commit_session_update(
            store,
            prepared,
            SessionCompletionReceipt(
                session_key=SESSION,
                request_id=request_id,
                update_fingerprint=prepared.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=policy,
            source_state=snapshot.state,
        )
    return prepared, pipeline, backend


def test_inactive_shown_snapshot_not_used_for_topic_restoration(tmp_path: Path, demo_bundle) -> None:
    store = _store(tmp_path)
    policy = _policy()
    _insert_session_state(store, _seed_active_service_with_shown_snapshot())
    inactive_bundle = demo_bundle.model_copy(deep=True)
    inactive_bundle.services["all_on_4"] = inactive_bundle.services["all_on_4"].model_copy(
        update={"active": False}
    )
    inactive_bundle.services["all_on_6"] = inactive_bundle.services["all_on_6"].model_copy(
        update={"active": False}
    )
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=inactive_bundle)
    composer_json = json.loads(
        _answer_json(
            patient_text="Продолжаем обсуждение.",
            service_reference_kind="active_session",
            explicit_service_id=None,
            option_reference_kind="shown_options",
            topic_id=None,
            requested_aspect_ids=["overview"],
        )
    )
    prepared, pipeline, backend = _run_shown_options_bridge_turn(
        store=store,
        material=material,
        policy=policy,
        patient_message="Продолжаем обсуждение.",
        request_id="inactive-shown",
        composer_json=composer_json,
        commit=True,
    )
    assert len(backend.calls) == 1
    dynamic_payload = json.loads(backend.calls[0].user_prompt)  # type: ignore[union-attr]
    assert "shown_service_options" not in dynamic_payload
    assert any(
        diagnostic.code == "shown_options_snapshot_unavailable"
        for diagnostic in pipeline.selection.diagnostics
    )
    assert prepared.topic_restoration_shown_snapshot is None
    topic = prepared.proposed_state.active_topic
    assert topic is None or topic.provenance != "shown_options"
    assert prepared.rendered_text
    assert "Продолжаем обсуждение." in prepared.resolved_plan.patient_text
    after = store.read(SESSION)
    assert after.state.active_topic is None or after.state.active_topic.provenance != "shown_options"


def test_partially_eligible_shown_snapshot_keeps_eligible_projection(tmp_path: Path, demo_bundle) -> None:
    store = _store(tmp_path)
    policy = _policy()
    _insert_session_state(store, _seed_active_service_with_shown_snapshot())
    partial_bundle = demo_bundle.model_copy(deep=True)
    partial_bundle.services["all_on_6"] = partial_bundle.services["all_on_6"].model_copy(
        update={"active": False}
    )
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=partial_bundle)
    composer_json = json.loads(
        _answer_json(
            service_reference_kind="active_session",
            explicit_service_id=None,
            option_reference_kind="shown_options",
            topic_id=None,
            requested_aspect_ids=["price", "comparison"],
            patient_situation={
                "extent": "full_arch",
                "jaw": "upper",
                "stage": "unknown",
                "modifiers": [],
            },
        )
    )
    prepared, pipeline, backend = _run_shown_options_bridge_turn(
        store=store,
        material=material,
        policy=policy,
        patient_message="Сколько стоит?",
        request_id="partial-shown",
        composer_json=composer_json,
        commit=False,
    )
    assert len(backend.calls) == 1
    assert pipeline.selection.price_candidate_service_ids == ("all_on_4",)
    assert any(
        diagnostic.code == "shown_options_snapshot_unavailable" and diagnostic.detail == "all_on_6"
        for diagnostic in pipeline.selection.diagnostics
    )
    assert prepared.topic_restoration_shown_snapshot is not None
    assert prepared.topic_restoration_shown_snapshot.service_ids == ("all_on_4", "all_on_6")
    topic = prepared.proposed_state.active_topic
    if topic is not None and topic.provenance == "shown_options":
        assert topic.set_at_turn == 1


def test_positive_shown_snapshot_only_topic_restoration(tmp_path: Path, demo_material) -> None:
    store = _store(tmp_path)
    policy = _policy()
    shown = PersistedShownOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    from contracts.response_plan_session import ResponsePlanSessionState

    _insert_session_state(
        store,
        ResponsePlanSessionState(
            schema_version=SESSION_SCHEMA_VERSION,
            session_key=SESSION,
            revision=1,
            last_committed_turn_index=1,
            dialogue_pairs=(
                SessionDialoguePair(
                    patient_text="seed",
                    assistant_text="seed reply",
                    committed_at_turn=1,
                ),
            ),
            shown_options_snapshot=shown,
        ),
    )
    composer_json = json.loads(
        _answer_json(
            service_reference_kind="none",
            explicit_service_id=None,
            option_reference_kind="shown_options",
            topic_id=None,
            requested_aspect_ids=["overview"],
        )
    )
    prepared, pipeline, backend = _run_shown_options_bridge_turn(
        store=store,
        material=demo_material,
        policy=policy,
        patient_message="Про имплантацию",
        request_id="positive-shown",
        composer_json=composer_json,
        commit=True,
    )
    assert len(backend.calls) == 1
    dynamic_payload = json.loads(backend.calls[0].user_prompt)  # type: ignore[union-attr]
    assert "shown_service_options" in dynamic_payload
    topic = prepared.proposed_state.active_topic
    assert topic is not None
    assert topic.provenance == "shown_options"
    assert topic.set_at_turn == 1
    assert prepared.topic_restoration_shown_snapshot is not None
    after = store.read(SESSION)
    assert after.state.active_topic is not None
    assert after.state.active_topic.provenance == "shown_options"
    assert after.state.active_topic.set_at_turn == 1
