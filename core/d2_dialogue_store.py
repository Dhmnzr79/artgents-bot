"""Single ordinary-state/result owner for the isolated D2 entry.

The SQLite transaction is the only D2 state writer. A request is first
reserved, then its state transition and complete replayable result are written
together. Lead delivery is outside that transaction: only its PII-free effect
receipt is persisted here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from contracts.d2_dialogue import D2CompletedTurn, D2DialogueRecord, D2LeadEffect
from contracts.response_plan import SessionKey
from contracts.response_plan_session import ResponsePlanSessionRevisionConflict


class D2RequestIdConflict(ValueError):
    pass


class D2RequestInProgress(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class D2RequestReservation:
    request_id: str
    request_fingerprint: str
    completed: D2CompletedTurn | None = None

    @property
    def is_replay(self) -> bool:
        return self.completed is not None


class D2DialogueStore:
    def __init__(self, path: Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS d2_dialogue "
            "(client_id TEXT NOT NULL, sid TEXT NOT NULL, payload TEXT NOT NULL, "
            "PRIMARY KEY (client_id, sid))"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS d2_turn_request "
            "(client_id TEXT NOT NULL, sid TEXT NOT NULL, request_id TEXT NOT NULL, "
            "request_fingerprint TEXT NOT NULL, status TEXT NOT NULL, payload TEXT, "
            "PRIMARY KEY (client_id, sid, request_id))"
        )
        self._connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self) -> None:
        self._connection.close()

    def read(self, key: SessionKey) -> D2DialogueRecord | None:
        row = self._connection.execute(
            "SELECT payload FROM d2_dialogue WHERE client_id=? AND sid=?", (key.client_id, key.sid)
        ).fetchone()
        if row is None:
            return None
        record = D2DialogueRecord.model_validate_json(row[0])
        if record.state.session_key != key:
            raise ValueError("d2_stored_owner_mismatch")
        return record

    def reserve_request(
        self, key: SessionKey, *, request_id: str, request_fingerprint: str,
    ) -> D2RequestReservation:
        """Reserve one serial request, or return its exact completed result."""
        if not request_id.strip() or not request_fingerprint.strip():
            raise ValueError("d2_request_identity_required")
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT request_fingerprint,status,payload FROM d2_turn_request "
                "WHERE client_id=? AND sid=? AND request_id=?",
                (key.client_id, key.sid, request_id),
            ).fetchone()
            if row is not None:
                fingerprint, status, payload = row
                if fingerprint != request_fingerprint:
                    raise D2RequestIdConflict("d2_request_id_payload_conflict")
                if status == "complete" and payload is not None:
                    return D2RequestReservation(
                        request_id=request_id,
                        request_fingerprint=request_fingerprint,
                        completed=D2CompletedTurn.model_validate_json(payload),
                    )
                raise D2RequestInProgress("d2_request_in_progress")
            inflight = self._connection.execute(
                "SELECT request_id FROM d2_turn_request "
                "WHERE client_id=? AND sid=? AND status='inflight' LIMIT 1",
                (key.client_id, key.sid),
            ).fetchone()
            if inflight is not None:
                raise D2RequestInProgress("d2_session_request_in_progress")
            self._connection.execute(
                "INSERT INTO d2_turn_request(client_id,sid,request_id,request_fingerprint,status,payload) "
                "VALUES(?,?,?,?,?,NULL)",
                (key.client_id, key.sid, request_id, request_fingerprint, "inflight"),
            )
        return D2RequestReservation(request_id=request_id, request_fingerprint=request_fingerprint)

    def abandon_request(self, key: SessionKey, *, request_id: str, request_fingerprint: str) -> None:
        """A failed, non-final request is retryable and must not look completed."""
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "DELETE FROM d2_turn_request WHERE client_id=? AND sid=? AND request_id=? "
                "AND request_fingerprint=? AND status='inflight'",
                (key.client_id, key.sid, request_id, request_fingerprint),
            )

    def complete(
        self, record: D2DialogueRecord, *, expected_revision: int, completion: D2CompletedTurn,
    ) -> None:
        """Atomically publish ordinary state and the exact replayable final result."""
        key = record.state.session_key
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            request = self._connection.execute(
                "SELECT request_fingerprint,status FROM d2_turn_request "
                "WHERE client_id=? AND sid=? AND request_id=?",
                (key.client_id, key.sid, completion.request_id),
            ).fetchone()
            if request is None or request[0] != completion.request_fingerprint or request[1] != "inflight":
                raise D2RequestInProgress("d2_request_not_reserved")
            previous = self.read(key)
            revision = previous.state.revision if previous else 0
            turn = previous.state.last_committed_turn_index if previous else 0
            if revision != expected_revision or record.state.revision != revision + 1:
                raise ResponsePlanSessionRevisionConflict("d2_revision_conflict")
            if record.state.last_committed_turn_index != turn + 1:
                raise ValueError("d2_turn_sequence_invalid")
            if previous and record.activity.last_user_turn_at < previous.activity.last_user_turn_at:
                raise ValueError("d2_activity_moved_backwards")
            if completion.committed_revision != record.state.revision:
                raise ValueError("d2_completion_revision_mismatch")
            self._connection.execute(
                "INSERT INTO d2_dialogue(client_id,sid,payload) VALUES(?,?,?) "
                "ON CONFLICT(client_id,sid) DO UPDATE SET payload=excluded.payload",
                (key.client_id, key.sid, record.model_dump_json()),
            )
            self._connection.execute(
                "UPDATE d2_turn_request SET status='complete',payload=? "
                "WHERE client_id=? AND sid=? AND request_id=? AND status='inflight'",
                (completion.model_dump_json(), key.client_id, key.sid, completion.request_id),
            )

    def update_lead_effect(
        self, key: SessionKey, *, request_id: str, effect: D2LeadEffect,
    ) -> D2CompletedTurn:
        """Persist one terminal receipt; ``unknown`` is never retried here."""
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT status,payload FROM d2_turn_request WHERE client_id=? AND sid=? AND request_id=?",
                (key.client_id, key.sid, request_id),
            ).fetchone()
            if row is None or row[0] != "complete" or row[1] is None:
                raise D2RequestInProgress("d2_effect_result_not_complete")
            completion = D2CompletedTurn.model_validate_json(row[1])
            if completion.lead_effect.status != "pending":
                return completion
            if completion.lead_effect.effect_id != effect.effect_id or effect.status in {"pending", "not_requested"}:
                raise ValueError("d2_effect_transition_invalid")
            updated = completion.model_copy(update={"lead_effect": effect})
            self._connection.execute(
                "UPDATE d2_turn_request SET payload=? WHERE client_id=? AND sid=? AND request_id=?",
                (updated.model_dump_json(), key.client_id, key.sid, request_id),
            )
            return updated
