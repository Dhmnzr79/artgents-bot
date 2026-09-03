"""SQLite persistence for typed response-plan session state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable

from contracts.response_plan import SessionKey
from contracts.response_plan_session import (
    PreparedSessionUpdate,
    ResponsePlanSessionIdempotencyConflict,
    ResponsePlanSessionPayloadError,
    ResponsePlanSessionRevisionConflict,
    ResponsePlanSessionSnapshot,
    ResponsePlanSessionState,
    SessionCommitResult,
    SessionCompletionReceipt,
    SessionContinuityPolicy,
    empty_session_snapshot,
)
from core.response_plan_session import (
    validate_prepared_session_update,
    validate_prepared_update_intrinsic,
)

ConnectionFactory = Callable[[], sqlite3.Connection]

_STATE_DDL = """
CREATE TABLE IF NOT EXISTS response_plan_session_state (
    client_id TEXT NOT NULL,
    sid TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    last_committed_turn_index INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY (client_id, sid)
);
"""

_IDEMPOTENCY_DDL = """
CREATE TABLE IF NOT EXISTS response_plan_session_idempotency (
    client_id TEXT NOT NULL,
    sid TEXT NOT NULL,
    request_id TEXT NOT NULL,
    update_fingerprint TEXT NOT NULL,
    committed_revision INTEGER NOT NULL,
    PRIMARY KEY (client_id, sid, request_id)
);
"""


class ResponsePlanSessionStore:
    """Opt-in SQLite store with explicit connection injection."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        try:
            connection.execute(_STATE_DDL)
            connection.execute(_IDEMPOTENCY_DDL)
            connection.commit()
        finally:
            connection.close()

    def read(self, session_key: SessionKey) -> ResponsePlanSessionSnapshot:
        connection = self._connection_factory()
        try:
            row = connection.execute(
                """
                SELECT schema_version, revision, last_committed_turn_index, state_json
                FROM response_plan_session_state
                WHERE client_id = ? AND sid = ?
                """,
                (session_key.client_id, session_key.sid),
            ).fetchone()
            if row is None:
                return empty_session_snapshot(session_key)
            try:
                payload = json.loads(row[3])
                state = ResponsePlanSessionState.model_validate(payload)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise ResponsePlanSessionPayloadError("session_payload_corrupt") from exc
            if state.session_key != session_key:
                raise ResponsePlanSessionPayloadError("session_key_payload_mismatch")
            if state.revision != row[1]:
                raise ResponsePlanSessionPayloadError("session_revision_column_mismatch")
            if state.last_committed_turn_index != row[2]:
                raise ResponsePlanSessionPayloadError("session_turn_column_mismatch")
            if state.schema_version != row[0]:
                raise ResponsePlanSessionPayloadError("session_schema_column_mismatch")
            return ResponsePlanSessionSnapshot(state=state, exists_in_store=True)
        finally:
            connection.close()

    def commit(
        self,
        prepared: PreparedSessionUpdate,
        receipt: SessionCompletionReceipt,
        *,
        policy: SessionContinuityPolicy,
        source_state: ResponsePlanSessionState,
    ) -> SessionCommitResult:
        recalculated_fingerprint = validate_prepared_update_intrinsic(prepared, receipt)

        session_key = prepared.request_binding.session_key
        connection = self._connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT update_fingerprint, committed_revision
                FROM response_plan_session_idempotency
                WHERE client_id = ? AND sid = ? AND request_id = ?
                """,
                (session_key.client_id, session_key.sid, receipt.request_id),
            ).fetchone()
            if existing is not None:
                if existing[0] == recalculated_fingerprint:
                    connection.commit()
                    return SessionCommitResult(
                        session_key=session_key,
                        revision=existing[1],
                        last_committed_turn_index=prepared.proposed_state.last_committed_turn_index,
                        idempotent_replay=True,
                    )
                connection.rollback()
                raise ResponsePlanSessionIdempotencyConflict("request_id_fingerprint_conflict")

            current = connection.execute(
                """
                SELECT revision, last_committed_turn_index, state_json
                FROM response_plan_session_state
                WHERE client_id = ? AND sid = ?
                """,
                (session_key.client_id, session_key.sid),
            ).fetchone()
            current_revision = 0 if current is None else int(current[0])
            if prepared.request_binding.expected_revision != current_revision:
                connection.rollback()
                raise ResponsePlanSessionRevisionConflict("expected_revision_stale")

            if current is None:
                db_source_state = source_state
            else:
                db_source_state = ResponsePlanSessionState.model_validate(json.loads(current[2]))
            if db_source_state.revision != source_state.revision:
                connection.rollback()
                raise ResponsePlanSessionRevisionConflict("source_state_revision_stale")

            validate_prepared_session_update(
                prepared,
                source_state=db_source_state,
                policy=policy,
            )

            state_json = prepared.proposed_state.model_dump_json()
            connection.execute(
                """
                INSERT INTO response_plan_session_state (
                    client_id, sid, schema_version, revision,
                    last_committed_turn_index, state_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id, sid) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    revision = excluded.revision,
                    last_committed_turn_index = excluded.last_committed_turn_index,
                    state_json = excluded.state_json
                """,
                (
                    session_key.client_id,
                    session_key.sid,
                    prepared.proposed_state.schema_version,
                    prepared.proposed_state.revision,
                    prepared.proposed_state.last_committed_turn_index,
                    state_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO response_plan_session_idempotency (
                    client_id, sid, request_id, update_fingerprint, committed_revision
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_key.client_id,
                    session_key.sid,
                    receipt.request_id,
                    recalculated_fingerprint,
                    prepared.proposed_state.revision,
                ),
            )
            connection.commit()
            return SessionCommitResult(
                session_key=session_key,
                revision=prepared.proposed_state.revision,
                last_committed_turn_index=prepared.proposed_state.last_committed_turn_index,
                idempotent_replay=False,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class FailingAfterStateWriteConnection:
    """Test helper that fails after state write but before idempotency insert."""

    def __init__(self, inner: sqlite3.Connection) -> None:
        self._inner = inner
        self._state_writes = 0

    def execute(self, sql: str, params: object = ()) -> sqlite3.Cursor:
        if "INSERT INTO response_plan_session_state" in sql or (
            "ON CONFLICT(client_id, sid) DO UPDATE" in sql
        ):
            self._state_writes += 1
        cursor = self._inner.execute(sql, params)
        if (
            "INSERT INTO response_plan_session_idempotency" in sql
            and self._state_writes > 0
        ):
            raise sqlite3.OperationalError("simulated_commit_failure")
        return cursor

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def close(self) -> None:
        self._inner.close()


class FailingConnectionFactory:
    """Wraps a store factory to inject commit failure after state write."""

    def __init__(self, base_factory: ConnectionFactory) -> None:
        self._base_factory = base_factory

    def __call__(self) -> FailingAfterStateWriteConnection:
        return FailingAfterStateWriteConnection(self._base_factory())
