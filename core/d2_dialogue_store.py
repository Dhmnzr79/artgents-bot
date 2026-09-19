"""Single ordinary-state owner for the isolated D2 entry.

Explicit database path only. State and activity share one atomic record; no
legacy session table, global cache, model-side memory or second writer.
"""

import sqlite3
from pathlib import Path

from contracts.d2_dialogue import D2DialogueRecord
from contracts.response_plan import SessionKey
from contracts.response_plan_session import ResponsePlanSessionRevisionConflict


class D2DialogueStore:
    def __init__(self, path: Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS d2_dialogue "
            "(client_id TEXT NOT NULL, sid TEXT NOT NULL, payload TEXT NOT NULL, "
            "PRIMARY KEY (client_id, sid))"
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

    def commit(self, record: D2DialogueRecord, *, expected_revision: int) -> None:
        key = record.state.session_key
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            previous = self.read(key)
            revision = previous.state.revision if previous else 0
            turn = previous.state.last_committed_turn_index if previous else 0
            if revision != expected_revision or record.state.revision != revision + 1:
                raise ResponsePlanSessionRevisionConflict("d2_revision_conflict")
            if record.state.last_committed_turn_index != turn + 1:
                raise ValueError("d2_turn_sequence_invalid")
            if previous and record.activity.last_user_turn_at < previous.activity.last_user_turn_at:
                raise ValueError("d2_activity_moved_backwards")
            self._connection.execute(
                "INSERT INTO d2_dialogue(client_id,sid,payload) VALUES(?,?,?) "
                "ON CONFLICT(client_id,sid) DO UPDATE SET payload=excluded.payload",
                (key.client_id, key.sid, record.model_dump_json()),
            )
