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
TurnLedgerEvent = Literal["START", "FINISH", "ERROR"]
ProviderLedgerEvent = Literal["START", "FINISH", "ERROR"]


def artifact_paths_for_attempt(
    attempt_id: str,
    *,
    artifacts_root: Path | None = None,
) -> dict[str, Path]:
    root = (artifacts_root or ARTIFACTS_ROOT) / attempt_id
    return {
        "attempt_dir": root,
        "attempt_json": root / "attempt.json",
        "turns_jsonl": root / "turns.jsonl",
        "calls_jsonl": root / "calls.jsonl",
        "raw_json": root / "raw.json",
        "result_json": root / "result.json",
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


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
    event: LedgerEvent | TurnLedgerEvent | ProviderLedgerEvent,
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


def ledger_events_balanced(path: Path) -> bool:
    if not path.exists():
        return True
    open_starts: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        event = str(row.get("event") or "")
        key = _ledger_balance_key(row)
        if event == "START":
            open_starts.add(key)
        elif event in {"FINISH", "ERROR"}:
            if key not in open_starts:
                return False
            open_starts.discard(key)
    return not open_starts


def _ledger_balance_key(row: dict[str, Any]) -> str:
    case_id = str(row.get("case_id") or "")
    arm = str(row.get("arm") or "")
    call_index = row.get("call_index")
    if call_index is not None:
        return f"{case_id}:{arm}:call:{call_index}"
    return f"{case_id}:{arm}"
