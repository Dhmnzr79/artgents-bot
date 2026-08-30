"""Incremental artifact persistence and call ledger for architecture comparison LIVE (eval-only)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID
from evals.v5.arch_compare.arch_compare_live_contract import (
    CAPABILITY_PREFLIGHT_BUDGET,
    EVAL_REQUEST_TIMEOUT_SEC,
    MAX_RETRIES,
    MEASUREMENT_PROVIDER_BUDGET,
    PRODUCTION_SLA_REFERENCE_SEC,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
)

CallPhase = Literal["preflight", "measurement"]
CallStatus = Literal["started", "completed", "failed"]
AttemptStatus = Literal[
    "PREFLIGHT_PENDING",
    "PREFLIGHT_FAILED",
    "MEASUREMENT_IN_PROGRESS",
    "MEASUREMENT_COMPLETE",
    "MEASUREMENT_COMPLETE_WITH_ERRORS",
    "INCOMPLETE_FATAL",
]

PROVIDER_ERROR_REVIEW_TEXT = "Ответ не получен: timeout/provider error"

_REPLACE_RETRY_DELAYS_SEC = (0.05, 0.1, 0.2, 0.4, 0.8)
_REPLACE_MAX_ATTEMPTS = len(_REPLACE_RETRY_DELAYS_SEC) + 1
_TRANSIENT_WINDOWS_REPLACE_ERRORS = frozenset({5, 32})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_transient_windows_replace_error(exc: OSError) -> bool:
    winerror = getattr(exc, "winerror", None)
    return winerror in _TRANSIENT_WINDOWS_REPLACE_ERRORS


def _atomic_replace_with_retry(tmp_path: Path, path: Path) -> None:
    for attempt in range(_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(tmp_path, path)
            return
        except OSError as exc:
            if not _is_transient_windows_replace_error(exc) or attempt >= _REPLACE_MAX_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_RETRY_DELAYS_SEC[attempt])


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_replace_with_retry(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


@dataclass
class ArchCompareCallLedgerEntry:
    call_index: int
    phase: CallPhase
    scenario_id: str
    turn_id: str
    config_id: str
    model_id: str
    status: CallStatus
    started_at: str
    finished_at: str | None = None
    latency_ms: int | None = None
    usage: dict[str, Any] | None = None
    error_type: str | None = None
    error_code: str | None = None
    request_timeout_sec: int = EVAL_REQUEST_TIMEOUT_SEC
    production_sla_sec: int = PRODUCTION_SLA_REFERENCE_SEC
    production_sla_breached: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArchCompareCallLedger:
    attempt_id: str
    max_provider_calls: int = TOTAL_AUTHORIZED_PROVIDER_BUDGET
    retries: int = MAX_RETRIES
    entries: list[ArchCompareCallLedgerEntry] = field(default_factory=list)

    @property
    def consumed_calls(self) -> int:
        return len(self.entries)

    @property
    def started_calls(self) -> int:
        return sum(1 for row in self.entries if row.status == "started")

    def next_call_index(self) -> int:
        return len(self.entries) + 1

    def assert_can_start(self) -> int:
        call_index = self.next_call_index()
        if call_index > self.max_provider_calls:
            raise RuntimeError(
                f"provider_budget_exceeded:call_index={call_index} max={self.max_provider_calls}"
            )
        return call_index

    def start_call(
        self,
        *,
        phase: CallPhase,
        scenario_id: str,
        turn_id: str,
        config_id: str,
        model_id: str,
    ) -> ArchCompareCallLedgerEntry:
        call_index = self.assert_can_start()
        entry = ArchCompareCallLedgerEntry(
            call_index=call_index,
            phase=phase,
            scenario_id=scenario_id,
            turn_id=turn_id,
            config_id=config_id,
            model_id=model_id,
            status="started",
            started_at=utc_now_iso(),
        )
        self.entries.append(entry)
        return entry

    def complete_call(
        self,
        entry: ArchCompareCallLedgerEntry,
        *,
        latency_ms: int | None,
        usage: dict[str, Any] | None,
    ) -> None:
        entry.status = "completed"
        entry.finished_at = utc_now_iso()
        entry.latency_ms = latency_ms
        entry.usage = usage
        if latency_ms is not None:
            entry.production_sla_breached = latency_ms > (entry.production_sla_sec * 1000)

    def fail_call(
        self,
        entry: ArchCompareCallLedgerEntry,
        *,
        error_type: str,
        error_code: str,
        latency_ms: int | None = None,
    ) -> None:
        entry.status = "failed"
        entry.finished_at = utc_now_iso()
        entry.error_type = error_type
        entry.error_code = error_code
        entry.latency_ms = latency_ms
        entry.production_sla_breached = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "max_provider_calls": self.max_provider_calls,
            "retries": self.retries,
            "consumed_calls": self.consumed_calls,
            "calls": [row.to_dict() for row in self.entries],
        }

    def validate_integrity(self) -> None:
        for idx, row in enumerate(self.entries, start=1):
            if row.call_index != idx:
                raise RuntimeError("call_ledger_corruption:call_index_mismatch")


class ArchCompareArtifactWriteError(RuntimeError):
    code = "artifact_write_failed"


@dataclass
class ArchCompareLiveArtifactStore:
    artifact_dir: Path
    attempt_id: str
    manifest: dict[str, Any]
    schedule: dict[str, Any]
    ledger: ArchCompareCallLedger
    raw_turns: list[dict[str, Any]] = field(default_factory=list)
    structured_turns: list[dict[str, Any]] = field(default_factory=list)
    blind_variant_mapping: dict[str, Any] = field(default_factory=dict)
    preflight: dict[str, Any] = field(default_factory=dict)
    measurement_errors: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def initialize(
        cls,
        *,
        artifact_dir: Path,
        attempt_id: str,
        schedule: dict[str, Any],
        budget_plan: dict[str, Any],
        head_sha: str,
        matrix_digest: str,
        config_digest: str,
        measurement_id: str,
        authorization: dict[str, Any] | None = None,
    ) -> ArchCompareLiveArtifactStore:
        manifest: dict[str, Any] = {
            "attempt_id": attempt_id,
            "measurement_id": measurement_id,
            "client_id": CLIENT_ID,
            "head_sha": head_sha,
            "matrix_digest": matrix_digest,
            "config_digest": config_digest,
            "call_budget": budget_plan,
            "status": "PREFLIGHT_PENDING",
            "provider_call_total": 0,
            "preflight_call_total": 0,
            "measurement_call_total": 0,
            "measurement_error_total": 0,
            "retries": MAX_RETRIES,
            "request_timeout_sec": EVAL_REQUEST_TIMEOUT_SEC,
            "production_sla_sec": PRODUCTION_SLA_REFERENCE_SEC,
            "cache_probe_enabled": False,
            "authorization": authorization,
        }
        store = cls(
            artifact_dir=artifact_dir,
            attempt_id=attempt_id,
            manifest=manifest,
            schedule=schedule,
            ledger=ArchCompareCallLedger(attempt_id=attempt_id),
        )
        store.artifact_dir.mkdir(parents=True, exist_ok=True)
        store.persist_core()
        return store

    def set_status(self, status: AttemptStatus) -> None:
        self.manifest["status"] = status

    def update_counts(self) -> None:
        completed = [row for row in self.ledger.entries if row.status in {"completed", "failed"}]
        preflight = [row for row in completed if row.phase == "preflight"]
        measurement = [row for row in completed if row.phase == "measurement"]
        self.manifest["provider_call_total"] = len(completed)
        self.manifest["preflight_call_total"] = len(preflight)
        self.manifest["measurement_call_total"] = len(measurement)
        self.manifest["measurement_error_total"] = sum(
            1 for row in measurement if row.status == "failed"
        )

    def persist_core(self) -> None:
        self.ledger.validate_integrity()
        self.update_counts()
        try:
            atomic_write_json(self.artifact_dir / "manifest.json", self.manifest)
            atomic_write_json(self.artifact_dir / "schedule.json", self.schedule)
            atomic_write_json(self.artifact_dir / "call_ledger.json", self.ledger.to_dict())
            atomic_write_json(self.artifact_dir / "raw_turns.json", self.raw_turns)
            atomic_write_json(self.artifact_dir / "structured_turns.json", self.structured_turns)
        except OSError as exc:
            raise ArchCompareArtifactWriteError(f"artifact_write_failed:{exc}") from exc

    def persist_after_call_started(self, entry: ArchCompareCallLedgerEntry) -> None:
        self.ledger.validate_integrity()
        self.update_counts()
        atomic_write_json(self.artifact_dir / "call_ledger.json", self.ledger.to_dict())
        atomic_write_json(self.artifact_dir / "manifest.json", self.manifest)

    def append_turn(
        self,
        *,
        raw_turn: dict[str, Any],
        structured_turn: dict[str, Any],
    ) -> None:
        self.raw_turns.append(raw_turn)
        self.structured_turns.append(structured_turn)
        self.persist_core()

    def record_measurement_error(self, error_record: dict[str, Any]) -> None:
        self.measurement_errors.append(error_record)
        self.manifest["measurement_errors"] = list(self.measurement_errors)

    def write_error_report(self, payload: dict[str, Any]) -> None:
        atomic_write_json(self.artifact_dir / "error_report.json", payload)

    def build_run_result(self, *, mode: str, head_sha: str, config_registry: dict[str, Any]) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "mode": mode,
            "status": self.manifest.get("status"),
            "measurement_id": self.manifest.get("measurement_id"),
            "head_sha": head_sha,
            "matrix_digest": self.manifest.get("matrix_digest"),
            "config_digest": self.manifest.get("config_digest"),
            "config_registry": config_registry,
            "schedule": self.schedule,
            "call_budget": self.manifest.get("call_budget"),
            "preflight": self.preflight,
            "provider_call_total": self.manifest.get("provider_call_total", 0),
            "fake_transport_call_total": 0,
            "raw_turns": self.raw_turns,
            "structured_turns": self.structured_turns,
            "blind_variant_mapping": self.blind_variant_mapping,
            "measurement_errors": list(self.measurement_errors),
            "call_ledger": self.ledger.to_dict(),
            "live_readiness": {
                "status": self.manifest.get("status"),
                "request_timeout_sec": EVAL_REQUEST_TIMEOUT_SEC,
                "production_sla_sec": PRODUCTION_SLA_REFERENCE_SEC,
            },
        }


def classify_provider_error(exc: BaseException) -> tuple[str, str]:
    message = str(exc).lower()
    if "timeout" in message or "timed out" in message:
        return "timeout", "request_timeout"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json", "invalid_json"
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return "envelope", code
    return "provider", type(exc).__name__
