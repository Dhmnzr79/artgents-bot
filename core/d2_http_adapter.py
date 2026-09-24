"""JSON transport for the single durable D2 dialogue turn."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contracts.response_plan import SessionKey
from core.client_runtime import per_client_data_dir
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore, D2RequestIdConflict, D2RequestInProgress
from core.d2_live_provider import D2HttpProvider
from core.d2_outcome import D2OutcomeError, classify_d2_error, safe_diagnostic_code, safe_failure_site
from session import (
    bind_session_client, capture_lead_session_row, restore_lead_session_row, sid_from_body,
)


def _store_path(client_id: str) -> Path:
    configured = os.getenv("D2_DIALOGUE_DB_PATH")
    if configured:
        return Path(configured)
    return Path(per_client_data_dir(client_id)) / "d2_dialogue.sqlite"


def _clients_root() -> Path:
    return Path(os.getenv("D2_CLIENTS_ROOT") or Path(__file__).resolve().parents[1] / "clients")


def _response_payload(turn, *, session_key: SessionKey) -> dict:
    # The D2 completion already contains the final text and projected UI.
    # Do not reselect, re-render, or run legacy finalization here.
    ui = turn.response.ui_projection.model_dump(mode="json")
    return {
        "answer": turn.response.rendered_text,
        "sid": session_key.sid,
        "client_id": session_key.client_id,
        "request_id": turn.request_id,
        "ui": ui,
        "actions": {
            "quick_replies": ui["quick_replies"],
            "buttons": ui["buttons"],
            "widget": ui["widget"],
            "video": ui["video"],
        },
        "revision": turn.committed_revision,
        "lead_effect": turn.lead_effect.model_dump(mode="json"),
    }


def run_d2_ask_json(data: dict, *, client_id: str) -> dict:
    supported = {"client_id", "sid", "request_id", "q", "ref", "ui_revision", "situation_action"}
    if set(data) - supported:
        raise ValueError("d2_unsupported_request_fields")
    for name in ("sid", "ref", "situation_action"):
        if name in data and data[name] is not None and not isinstance(data[name], str):
            raise ValueError("d2_request_field_invalid")
    if data.get("ref") is not None and not data["ref"].strip():
        raise ValueError("d2_stale_or_unsupported_ref")
    if data.get("ref"):
        if type(data.get("ui_revision")) is not int or data["ui_revision"] < 1:
            raise ValueError("d2_ui_revision_required")
        if data.get("q"):
            raise ValueError("d2_ui_action_requires_empty_question")
    elif "ui_revision" in data:
        raise ValueError("d2_ui_revision_without_action")
    if data.get("situation_action") and data["situation_action"] not in {"start", "back"}:
        raise ValueError("d2_situation_action_invalid")
    sid = sid_from_body(data)
    request_id = data.get("request_id")
    if request_id is None:
        request_id = uuid.uuid4().hex
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("d2_request_id_required")
    user_message = data.get("q") or ""
    if not isinstance(user_message, str):
        raise ValueError("d2_question_invalid")
    key = SessionKey(client_id=client_id, sid=sid)
    bind_session_client(client_id)
    path = _store_path(client_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with D2DialogueStore(path) as store:
        lead_before = capture_lead_session_row(sid)
        try:
            turn = run_d2_dialogue_turn(
                session_key=key,
                user_message=user_message,
                provider=D2HttpProvider(),
                clients_root=_clients_root(),
                store=store,
                now=datetime.now(timezone.utc),
                request_id=request_id,
                lead_ui_ref=data.get("ref"),
                ui_revision=data.get("ui_revision"),
                situation_action=data.get("situation_action"),
                lead_bridge=True,
            )
        except Exception as exc:
            try:
                completed = store._connection.execute(
                    "SELECT 1 FROM d2_turn_request WHERE client_id=? AND sid=? "
                    "AND request_id=? AND status='complete'",
                    (client_id, sid, request_id),
                ).fetchone()
            except Exception as store_error:
                raise D2OutcomeError("store", "store_failed", "storage",
                                     diagnostic_code=safe_diagnostic_code(store_error),
                                     diagnostic_site=safe_failure_site(store_error)) from None
            if completed is None:
                restore_lead_session_row(sid, lead_before)
            raise classify_d2_error(
                exc, committed=completed is not None and not isinstance(exc, (D2RequestIdConflict, D2RequestInProgress)),
            ) from exc
    try:
        return _response_payload(turn, session_key=key)
    except Exception as exc:
        raise D2OutcomeError("transport", "transport_failed", "unexpected", True,
                             safe_diagnostic_code(exc), safe_failure_site(exc)) from exc
