from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from contracts.response_plan import FinalizedCommercialIds, ResponseSessionDelta, ResponseUIProjection, SessionKey
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_plan_session import (
    PreparedSessionUpdate,
    ResponsePlanSessionContractError,
    ResponsePlanSessionIdempotencyConflict,
    ResponsePlanSessionOwnershipError,
    ResponsePlanSessionPayloadError,
    ResponsePlanSessionReceiptMismatch,
    ResponsePlanSessionRevisionConflict,
    ResponsePlanSessionState,
    SESSION_SCHEMA_VERSION,
    PersistedShownOptionsSnapshot,
    SessionCompletionReceipt,
    SessionContinuityPolicy,
    attach_update_fingerprint,
)
from core.response_plan_session import (
    apply_session_state_transition,
    create_turn_request_binding,
    resolve_topic_restoration_shown_snapshot_for_state,
)
from core.response_plan_session_store import FailingConnectionFactory, ResponsePlanSessionStore
from core.response_schema_loader import load_response_schema_bundle
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_response_plan_contract import _minimal_answer_resolved
from tests.test_response_plan_materialization import AS_OF, _adapted, _selection_from_post_composer

TARGET_ROOT = Path("clients/demo/target_response")

POLICY = SessionContinuityPolicy(
    active_service_max_age_turns=5,
    active_topic_max_age_turns=5,
    situation_max_age_turns=5,
    shown_options_max_age_turns=5,
    history_pair_limit=20,
)


def _store(tmp_path: Path) -> ResponsePlanSessionStore:
    db_path = tmp_path / "session.db"

    def factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    store = ResponsePlanSessionStore(factory)
    store.ensure_schema()
    return store


def _source_state(session_key: SessionKey, *, revision: int, turn: int) -> ResponsePlanSessionState:
    return ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=revision,
        last_committed_turn_index=max(0, turn - 1),
    )


def _prepared(
    store: ResponsePlanSessionStore,
    session_key: SessionKey,
    *,
    request_id: str,
    text: str,
) -> PreparedSessionUpdate:
    snapshot = store.read(session_key)
    source = snapshot.state
    binding = create_turn_request_binding(
        snapshot,
        request_id=request_id,
        patient_message="p",
    )
    material = PostComposerMaterialAuthority(
        source_client_id=session_key.client_id,
        bundle=load_response_schema_bundle(TARGET_ROOT),
    )
    adapted = _adapted(patient_text=text)
    from core.response_plan_post_composer import resolve_post_composer_selection
    from core.response_plan_session import situation_continuity_policy, shown_options_freshness_policy

    selection = resolve_post_composer_selection(
        session_key=session_key,
        adapted=adapted,
        material=material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=binding.current_turn_index,
        policy=situation_continuity_policy(POLICY),
        shown_options_policy=shown_options_freshness_policy(POLICY),
        as_of=AS_OF,
    )
    from core.response_plan_materialization import resolve_materialized_response
    from tests.test_response_plan_materialization import _sources

    materialized = resolve_materialized_response(
        selection,
        adapted,
        _sources(material, session_key=session_key),
        as_of=AS_OF,
    )
    resolved = materialized.resolved
    rendered = render_response_text(resolved)
    ui = project_response_ui(resolved)
    topic_restoration = resolve_topic_restoration_shown_snapshot_for_state(
        source,
        policy=POLICY,
        source_client_id=session_key.client_id,
        bundle=material.bundle,
        current_turn_index=binding.current_turn_index,
        selection=selection,
    )
    proposed = apply_session_state_transition(
        source,
        policy=POLICY,
        binding=binding,
        rendered_text=rendered,
        selection=selection,
        resolved=resolved,
        topic_restoration_shown_snapshot=topic_restoration,
    )
    prepared = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="p",
        rendered_text=rendered,
        proposed_state=proposed,
        resolved_plan=resolved,
        ui_projection=ui,
        selection=selection,
        topic_restoration_shown_snapshot=topic_restoration,
        update_fingerprint="",
    )
    return attach_update_fingerprint(prepared)


def _commit(store: ResponsePlanSessionStore, prepared: PreparedSessionUpdate) -> None:
    store.commit(
        prepared,
        SessionCompletionReceipt(
            session_key=prepared.request_binding.session_key,
            request_id=prepared.request_binding.request_id,
            update_fingerprint=prepared.update_fingerprint,
            transport_kind="blocking",
        ),
        policy=POLICY,
        source_state=store.read(prepared.request_binding.session_key).state,
    )


def test_read_missing_does_not_insert(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    snapshot = store.read(key)
    assert snapshot.exists_in_store is False
    assert store.read(key).exists_in_store is False


def test_commit_and_durable_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    reread = store.read(key)
    assert reread.exists_in_store is True
    assert reread.state.last_committed_turn_index == 1
    assert reread.state.dialogue_pairs[0].assistant_text == "one"


def test_idempotent_replay(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared_a = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared_a)
    prepared_b = _prepared(store, key, request_id="b", text="two")
    _commit(store, prepared_b)
    prepared_c = _prepared(store, key, request_id="c", text="three")
    _commit(store, prepared_c)
    replay = store.commit(
        prepared_a,
        SessionCompletionReceipt(
            session_key=key,
            request_id="a",
            update_fingerprint=prepared_a.update_fingerprint,
            transport_kind="blocking",
        ),
        policy=POLICY,
        source_state=store.read(key).state,
    )
    assert replay.idempotent_replay is True
    assert replay.revision == 1
    after = store.read(key)
    assert after.state.last_committed_turn_index == 3


def test_idempotency_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    altered_resolved = prepared.resolved_plan.model_copy(update={"patient_text": "other"})
    altered_rendered = render_response_text(altered_resolved)
    altered_ui = project_response_ui(altered_resolved)
    altered_selection = replace(
        prepared.selection,
        decision=replace(prepared.selection.decision, patient_text="other"),
    )
    altered = prepared.model_copy(
        update={
            "rendered_text": altered_rendered,
            "resolved_plan": altered_resolved,
            "ui_projection": altered_ui,
            "selection": altered_selection,
            "update_fingerprint": "",
        }
    )
    altered = attach_update_fingerprint(altered)
    with pytest.raises(ResponsePlanSessionIdempotencyConflict):
        store.commit(
            altered,
            SessionCompletionReceipt(
                session_key=key,
                request_id="a",
                update_fingerprint=altered.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=store.read(key).state,
        )


def test_revision_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    stale = _prepared(store, key, request_id="b", text="two")
    stale = stale.model_copy(
        update={
            "request_binding": stale.request_binding.model_copy(update={"expected_revision": 0}),
            "update_fingerprint": "",
        }
    )
    stale = attach_update_fingerprint(stale)
    with pytest.raises(ResponsePlanSessionRevisionConflict):
        _commit(store, stale)


def test_client_isolation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key_a = SessionKey(client_id="demo", sid="shared")
    key_b = SessionKey(client_id="nikadent", sid="shared")
    _commit(store, _prepared(store, key_a, request_id="a", text="demo"))
    assert store.read(key_b).exists_in_store is False


def test_altered_fingerprint_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    tampered = prepared.model_copy(update={"update_fingerprint": "deadbeef"})
    with pytest.raises(ResponsePlanSessionContractError, match="prepared_fingerprint_invalid"):
        store.commit(
            tampered,
            SessionCompletionReceipt(
                session_key=key,
                request_id="a",
                update_fingerprint=prepared.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=store.read(key).state,
        )


def test_transaction_rollback_on_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "fail.db"

    def base_factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    store = ResponsePlanSessionStore(FailingConnectionFactory(base_factory))
    store.ensure_schema()
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    with pytest.raises(sqlite3.OperationalError):
        _commit(store, prepared)
    assert store.read(key).exists_in_store is False


def test_retry_after_transaction_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "retry.db"

    def base_factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    failing_store = ResponsePlanSessionStore(FailingConnectionFactory(base_factory))
    failing_store.ensure_schema()
    normal_store = ResponsePlanSessionStore(base_factory)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(failing_store, key, request_id="a", text="one")
    with pytest.raises(sqlite3.OperationalError):
        _commit(failing_store, prepared)
    _commit(normal_store, prepared)
    assert normal_store.read(key).state.last_committed_turn_index == 1


def test_replay_rejects_wrong_receipt_fingerprint(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    with pytest.raises(ResponsePlanSessionReceiptMismatch, match="receipt_fingerprint_mismatch"):
        store.commit(
            prepared,
            SessionCompletionReceipt(
                session_key=key,
                request_id="a",
                update_fingerprint="deadbeef",
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=store.read(key).state,
        )
    assert store.read(key).state.last_committed_turn_index == 1


def test_replay_rejects_wrong_receipt_session_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    other_key = SessionKey(client_id="demo", sid="other")
    with pytest.raises(ResponsePlanSessionOwnershipError, match="receipt_session_key_mismatch"):
        store.commit(
            prepared,
            SessionCompletionReceipt(
                session_key=other_key,
                request_id="a",
                update_fingerprint=prepared.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=store.read(key).state,
        )


def test_corrupt_numeric_revision_rejected_on_read(tmp_path: Path) -> None:
    db_path = tmp_path / "corrupt.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE response_plan_session_state (
            client_id TEXT NOT NULL,
            sid TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            revision INTEGER NOT NULL,
            last_committed_turn_index INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (client_id, sid)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO response_plan_session_state (
            client_id, sid, schema_version, revision, last_committed_turn_index, state_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "demo",
            "s1",
            1,
            1,
            1,
            json.dumps(
                {
                    "schema_version": 1.0,
                    "session_key": {"client_id": "demo", "sid": "s1"},
                    "revision": 1,
                    "last_committed_turn_index": 1,
                }
            ),
        ),
    )
    connection.commit()
    connection.close()

    def factory() -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    store = ResponsePlanSessionStore(factory)
    with pytest.raises(ResponsePlanSessionPayloadError):
        store.read(SessionKey(client_id="demo", sid="s1"))


def test_commit_rejects_incoherent_price_rows_leaving_db_unchanged(tmp_path: Path) -> None:
    from contracts.response_plan import FinalizedCommercialIds, FrozenPriceOfferRow, ResolvedPriceBlock
    from contracts.response_plan_post_composer import ResponseSituationDelta

    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    prepared = _prepared(store, key, request_id="a", text="one")
    _commit(store, prepared)
    source_state = store.read(key).state
    state_row_count = _count_state_rows(store, key)
    idempotency_row_count = _count_idempotency_rows(store, key)
    selection = replace(
        prepared.selection,
        response_scope="service",
        reference_service_id="all_on_4",
        reference_service_status="compatible",
        price_candidate_service_ids=("all_on_4",),
    )
    foreign_row = FrozenPriceOfferRow(
        source_client_id="demo",
        offer_id="offer_foreign",
        service_id="other_service",
        offer_label="Foreign",
        amount=50_000,
        currency="RUB",
        billing_unit="service",
    )
    tampered_resolved = prepared.resolved_plan.model_copy(
        update={
            "response_scope": "service",
            "session_delta": prepared.resolved_plan.session_delta.model_copy(
                update={
                    "active_service_id": "all_on_4",
                    "shown_price_offer_ids": ("offer_foreign",),
                }
            ),
            "price_block": ResolvedPriceBlock(
                source_client_id="demo",
                offer_ids=("offer_foreign",),
                display_text="50 000 ₽",
                owner="canonical_single",
                amount=50_000,
                currency="RUB",
                billing_unit="service",
                offer_rows=(foreign_row,),
            ),
            "finalized_commercial_ids": FinalizedCommercialIds(price_offer_ids=("offer_foreign",)),
        }
    )
    tampered_rendered = render_response_text(tampered_resolved)
    tampered_ui = project_response_ui(tampered_resolved)
    tampered = prepared.model_copy(
        update={
            "selection": selection,
            "resolved_plan": tampered_resolved,
            "rendered_text": tampered_rendered,
            "ui_projection": tampered_ui,
            "request_binding": prepared.request_binding.model_copy(update={"request_id": "incoherent"}),
            "update_fingerprint": "",
        }
    )
    tampered = attach_update_fingerprint(tampered)
    with pytest.raises(ResponsePlanSessionContractError, match="prepared_price_row_service_mismatch"):
        store.commit(
            tampered,
            SessionCompletionReceipt(
                session_key=key,
                request_id="incoherent",
                update_fingerprint=tampered.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=source_state,
        )
    assert store.read(key).state.last_committed_turn_index == 1
    assert _count_state_rows(store, key) == state_row_count
    assert _count_idempotency_rows(store, key) == idempotency_row_count


def _count_state_rows(store: ResponsePlanSessionStore, session_key: SessionKey) -> int:
    connection = store._connection_factory()
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) FROM response_plan_session_state
            WHERE client_id = ? AND sid = ?
            """,
            (session_key.client_id, session_key.sid),
        ).fetchone()
        return int(row[0])
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


def _seed_state_with_shown_snapshot(
    store: ResponsePlanSessionStore,
    session_key: SessionKey,
) -> ResponsePlanSessionState:
    from contracts.response_plan_session import PersistedShownOptionsSnapshot

    shown = PersistedShownOptionsSnapshot(
        session_key=session_key,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    prepared = _prepared(store, session_key, request_id="seed", text="seed")
    seeded = prepared.proposed_state.model_copy(update={"shown_options_snapshot": shown})
    connection = store._connection_factory()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO response_plan_session_state (
                client_id, sid, schema_version, revision,
                last_committed_turn_index, state_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_key.client_id,
                session_key.sid,
                seeded.schema_version,
                seeded.revision,
                seeded.last_committed_turn_index,
                seeded.model_dump_json(),
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO response_plan_session_idempotency (
                client_id, sid, request_id, update_fingerprint, committed_revision
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_key.client_id,
                session_key.sid,
                "seed",
                prepared.update_fingerprint,
                seeded.revision,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return seeded


def _prepared_with_topic_restoration(
    store: ResponsePlanSessionStore,
    session_key: SessionKey,
    *,
    request_id: str,
    topic_restoration,
) -> PreparedSessionUpdate:
    snapshot = store.read(session_key)
    source = snapshot.state
    binding = create_turn_request_binding(
        snapshot,
        request_id=request_id,
        patient_message="p",
    )
    material = PostComposerMaterialAuthority(
        source_client_id=session_key.client_id,
        bundle=load_response_schema_bundle(TARGET_ROOT),
    )
    adapted = _adapted(patient_text="tampered topic restoration")
    from core.response_plan_post_composer import resolve_post_composer_selection
    from core.response_plan_session import situation_continuity_policy, shown_options_freshness_policy

    selection = resolve_post_composer_selection(
        session_key=session_key,
        adapted=adapted,
        material=material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=binding.current_turn_index,
        policy=situation_continuity_policy(POLICY),
        shown_options_policy=shown_options_freshness_policy(POLICY),
        as_of=AS_OF,
    )
    from core.response_plan_materialization import resolve_materialized_response
    from tests.test_response_plan_materialization import _sources

    materialized = resolve_materialized_response(
        selection,
        adapted,
        _sources(material, session_key=session_key),
        as_of=AS_OF,
    )
    resolved = materialized.resolved
    rendered = render_response_text(resolved)
    ui = project_response_ui(resolved)
    proposed = apply_session_state_transition(
        source,
        policy=POLICY,
        binding=binding,
        rendered_text=rendered,
        selection=selection,
        resolved=resolved,
        topic_restoration_shown_snapshot=topic_restoration,
    )
    prepared = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="p",
        rendered_text=rendered,
        proposed_state=proposed,
        resolved_plan=resolved,
        ui_projection=ui,
        selection=selection,
        topic_restoration_shown_snapshot=topic_restoration,
        update_fingerprint="",
    )
    return attach_update_fingerprint(prepared)


@pytest.mark.parametrize(
    ("topic_restoration_factory", "expected_error"),
    [
        (
            lambda key: PersistedShownOptionsSnapshot(
                session_key=SessionKey(client_id="other", sid="s1"),
                topic_id="implantation",
                service_ids=("all_on_4",),
                shown_at_turn=1,
            ),
            "topic_restoration_source_session_mismatch",
        ),
        (
            lambda key: PersistedShownOptionsSnapshot(
                session_key=key,
                topic_id="implantation",
                service_ids=("all_on_4",),
                shown_at_turn=4,
            ),
            "topic_restoration_source_snapshot_mismatch",
        ),
    ],
)
def test_commit_rejects_foreign_topic_restoration_source_leaving_db_unchanged(
    tmp_path: Path,
    topic_restoration_factory,
    expected_error: str,
) -> None:
    store = _store(tmp_path)
    key = SessionKey(client_id="demo", sid="s1")
    _seed_state_with_shown_snapshot(store, key)
    source_state = store.read(key).state
    state_row_count = _count_state_rows(store, key)
    idempotency_row_count = _count_idempotency_rows(store, key)
    tampered = _prepared_with_topic_restoration(
        store,
        key,
        request_id="foreign-topic-restoration",
        topic_restoration=topic_restoration_factory(key),
    )
    with pytest.raises(ResponsePlanSessionContractError, match=expected_error):
        store.commit(
            tampered,
            SessionCompletionReceipt(
                session_key=key,
                request_id="foreign-topic-restoration",
                update_fingerprint=tampered.update_fingerprint,
                transport_kind="blocking",
            ),
            policy=POLICY,
            source_state=source_state,
        )
    assert store.read(key).state == source_state
    assert _count_state_rows(store, key) == state_row_count
    assert _count_idempotency_rows(store, key) == idempotency_row_count
