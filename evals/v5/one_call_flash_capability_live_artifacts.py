"""Durable artifacts and ledger for ONE_CALL Flash capability LIVE eval (Stage 3B)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    prepare_json_artifact_payload,
)
from evals.v5.one_call_flash_capability_contract import ATTEMPT_MARKER_EXISTS_CODE

_REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = _REPO_ROOT / "evals" / "v5" / "artifacts"

LedgerEvent = Literal["START", "FINISH", "ERROR"]


@dataclass(frozen=True, slots=True)
class CapabilityArtifactPaths:
    attempt_dir: Path
    attempt_json: Path
    calls_jsonl: Path
    raw_json: Path
    result_json: Path


def artifact_paths_for_attempt(
    attempt_id: str,
    *,
    artifacts_root: Path | None = None,
) -> CapabilityArtifactPaths:
    root = artifacts_root or ARTIFACTS_ROOT
    attempt_dir = root / attempt_id
    return CapabilityArtifactPaths(
        attempt_dir=attempt_dir,
        attempt_json=attempt_dir / "attempt.json",
        calls_jsonl=attempt_dir / "calls.jsonl",
        raw_json=attempt_dir / "raw.json",
        result_json=attempt_dir / "result.json",
    )


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


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


@dataclass(slots=True)
class CapabilityLiveCaseRecord:
    case_id: str
    outcome: str
    requested_model: str
    observed_model: str | None
    provider_model_verified: bool
    stream: bool
    response_format_strategy: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    transport_attempts: int
    ttft_ms: int | None
    total_ms: int
    first_delta_excerpt: str | None
    response_excerpt: str | None
    error_code: str | None
    provider_kind: str | None = None
    provider_region: str | None = None
    stable_prefix_sha256: str | None = None
    ledger_event: str | None = None

    def to_artifact_dict(self) -> dict[str, Any]:
        return asdict(self)
