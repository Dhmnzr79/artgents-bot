"""Durable artifacts for Stage 3C Speed Gate LIVE (prepared, gate closed)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    prepare_json_artifact_payload,
)
from evals.v5.one_call_stage3c_speed_gate_contract import ATTEMPT_MARKER_EXISTS_CODE

_REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = _REPO_ROOT / "evals" / "v5" / "artifacts"

LedgerEvent = Literal["START", "FINISH", "ERROR"]


def artifact_paths_for_attempt(attempt_id: str) -> dict[str, Path]:
    root = ARTIFACTS_ROOT / attempt_id
    return {
        "attempt_dir": root,
        "attempt_json": root / "attempt.json",
        "calls_jsonl": root / "calls.jsonl",
        "raw_json": root / "raw.json",
        "result_json": root / "result.json",
    }


def create_attempt_marker_exclusive(path: Path, payload: dict[str, Any]) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise AttemptMarkerExistsError(ATTEMPT_MARKER_EXISTS_CODE) from exc


def append_ledger_event(
    path: Path,
    *,
    event: LedgerEvent,
    case_id: str,
    attempt_id: str,
    extra: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {
        "event": event,
        "case_id": case_id,
        "attempt_id": attempt_id,
    }
    if extra:
        row.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
