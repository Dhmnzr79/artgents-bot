"""CLI and runner for BOT-CLEANUP-LIVE-1 (sales-fast /ask path, eval-only transport injection)."""

from __future__ import annotations

import argparse
import hashlib
import json
import msvcrt
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import config
from evals.v5.bot_cleanup_live_backend import (
    BotCleanupBudgetExceeded,
    BotCleanupCallBudget,
    BotCleanupLiveBackend,
    BotCleanupModelMismatch,
    BotCleanupRawPersistError,
    BotCleanupRequestHashConflict,
    BotCleanupTransportAlreadyCompleted,
    BotCleanupUncertainAttempt,
    INFERENCE_SETTINGS,
    REQUESTED_PROVIDER_MODEL_ID,
    assert_not_flash_model,
    provider_raw_content,
    resolve_transport_observability,
)
from evals.v5.bot_cleanup_scenarios_format import (
    CLIENT_ID,
    DEFAULT_MAX_PROVIDER_CALLS,
    DEFAULT_MONETARY_CAP_USD,
    DEFAULT_SCENARIOS_PATH,
    EXPECTED_HEAD,
    FUTURE_LIVE_MODEL,
    MEASUREMENT_ID,
    load_bot_cleanup_scenarios,
    render_transcript_markdown,
    summarize_bot_cleanup_scenarios,
    validate_bot_cleanup_scenarios,
)
from evals.v5.speaker_experiment_cost import (
    DEFAULT_SPEAKER_PRICING,
    SpeakerCostLedger,
)

_FULL_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PLACEHOLDER_KEY_MARKERS = (
    "placeholder",
    "your-api-key",
    "sk-test",
    "sk-fake",
    "changeme",
    "offline-test",
)
_GOVERNANCE_MODULE_PATHS = (
    "core/one_call_presentation_pass.py",
    "core/one_call_prompt_contract.py",
    "core/sales_one_plus_protocol.py",
    "core/sales_fast_authoritative_commerce.py",
    "core/one_call_price_microfacts.py",
    "core/sales_fast_widget_runtime.py",
    "orchestration/sales_one_plus_ask_turn.py",
    "orchestration/sales_fast_widget_turn.py",
)
_EXECUTABLE_MODULE_PATHS = (
    "evals/v5/run_bot_cleanup_live.py",
    "evals/v5/bot_cleanup_live_backend.py",
)
_RUN_CONFIG_FILENAME = "run_config.json"
_RUN_PROGRESS_FILENAME = "run_progress.json"
_EXPERIMENT_LOCK_FILENAME = "experiment.lock"
_RUN_CONFIG_IDENTITY_KEYS = (
    "measurement_id",
    "attempt_id",
    "scenarios_sha256",
    "client_pack_hash",
    "prompt_contract_version",
    "requested_provider_model_id",
    "inference_settings",
    "endpoint_host",
    "provider_region",
    "governance_module_hashes",
    "executable_module_hashes",
    "max_calls",
    "monetary_cap_usd",
    "pricing_snapshot",
    "config_digest",
)


class BotCleanupLiveGovernanceError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise BotCleanupLiveGovernanceError("git_head_unavailable", proc.stderr.strip())
    return proc.stdout.strip()


def _git_branch() -> str:
    proc = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def working_tree_fingerprint() -> dict[str, Any]:
    status_proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    porcelain = status_proc.stdout if status_proc.returncode == 0 else ""
    diff_proc = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    diff_text = diff_proc.stdout if diff_proc.returncode == 0 else ""
    combined = f"{porcelain}\n---\n{diff_text}".encode("utf-8")
    return {
        "porcelain": porcelain.strip(),
        "working_tree_sha256": hashlib.sha256(combined).hexdigest(),
    }


def governance_module_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for relative in _GOVERNANCE_MODULE_PATHS:
        path = _REPO_ROOT / relative
        if path.is_file():
            out[relative] = sha256_file(path)
    return out


def executable_module_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for relative in _EXECUTABLE_MODULE_PATHS:
        path = _REPO_ROOT / relative
        if path.is_file():
            out[relative] = sha256_file(path)
    return out


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd: int | None = None
    try:
        fd = os.open(str(tmp_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        encoded = text.encode("utf-8")
        os.write(fd, encoded)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(tmp_path, path)
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        tmp_path.unlink(missing_ok=True)
        raise BotCleanupLiveGovernanceError("atomic_write_failed", f"{path}:{exc}") from exc


def atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _acquire_file_lock(file_obj) -> None:
    file_obj.seek(0)
    if sys.platform == "win32":
        try:
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BotCleanupLiveGovernanceError(
                "experiment_already_running",
                "lock_not_available",
            ) from exc
        return
    import fcntl

    try:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise BotCleanupLiveGovernanceError(
            "experiment_already_running",
            "lock_not_available",
        ) from exc


def _release_file_lock(file_obj) -> None:
    file_obj.seek(0)
    if sys.platform == "win32":
        try:
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            return
        return
    import fcntl

    try:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
    except OSError:
        return


class ExperimentLock:
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fp = None

    def __enter__(self) -> ExperimentLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._lock_path, "a+b")
        try:
            _acquire_file_lock(self._fp)
            self._fp.seek(0)
            self._fp.truncate()
            self._fp.write(f"{os.getpid()}\n".encode("utf-8"))
            self._fp.flush()
        except BotCleanupLiveGovernanceError:
            self._fp.close()
            self._fp = None
            raise
        except OSError as exc:
            self._fp.close()
            self._fp = None
            raise BotCleanupLiveGovernanceError(
                "experiment_already_running",
                "lock_not_available",
            ) from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._fp is not None:
                _release_file_lock(self._fp)
                self._fp.close()
        finally:
            self._fp = None
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def _artifact_has_progress(artifact_dir: Path) -> bool:
    if (artifact_dir / "turn_results.json").exists():
        return True
    budget_path = artifact_dir / "call_budget.json"
    if budget_path.exists():
        payload = _read_json(budget_path)
        if int(payload.get("consumed") or 0) > 0:
            return True
    provider_raw_dir = artifact_dir / "provider_raw"
    if provider_raw_dir.exists() and any(provider_raw_dir.iterdir()):
        return True
    snapshots_dir = artifact_dir / "session_snapshots"
    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
        return True
    return False


def build_run_config(
    *,
    preflight: dict[str, Any],
    attempt_id: str,
    max_calls: int,
    monetary_cap_usd: str,
) -> dict[str, Any]:
    payload = {
        key: preflight.get(key)
        for key in (
            "measurement_id",
            "expected_head",
            "actual_head",
            "git_branch",
            "working_tree",
            "scenarios_path",
            "scenarios_sha256",
            "client_id",
            "client_pack_hash",
            "prompt_contract_version",
            "governance_module_hashes",
            "requested_provider_model_id",
            "config_qwen_plus_model",
            "config_sales_one_plus_flash_model",
            "target_path",
            "endpoint_host",
            "provider_region",
            "inference_settings",
            "pricing_snapshot",
        )
    }
    payload.update(
        {
            "attempt_id": attempt_id,
            "executable_module_hashes": executable_module_hashes(),
            "max_calls": max_calls,
            "monetary_cap_usd": monetary_cap_usd,
        }
    )
    digest_source = {
        key: payload.get(key)
        for key in _RUN_CONFIG_IDENTITY_KEYS
        if key != "config_digest"
    }
    payload["config_digest"] = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return payload


def _assert_run_config_identity(current: dict[str, Any], saved: dict[str, Any]) -> None:
    for key in _RUN_CONFIG_IDENTITY_KEYS:
        if saved.get(key) != current.get(key):
            raise BotCleanupLiveGovernanceError(
                "resume_identity_mismatch",
                f"{key}:{saved.get(key)}!={current.get(key)}",
            )


def bootstrap_run_config(
    *,
    artifact_dir: Path,
    current_config: dict[str, Any],
) -> dict[str, Any]:
    config_path = artifact_dir / _RUN_CONFIG_FILENAME
    if config_path.exists():
        saved = _read_json(config_path)
        _assert_run_config_identity(current_config, saved)
        return saved
    if _artifact_has_progress(artifact_dir):
        raise BotCleanupLiveGovernanceError(
            "resume_config_missing",
            "progress_exists_without_run_config",
        )
    atomic_write_json(config_path, current_config)
    return current_config


def load_run_progress(artifact_dir: Path) -> dict[str, Any]:
    path = artifact_dir / _RUN_PROGRESS_FILENAME
    if not path.exists():
        return {"stop_live": False, "stop_reason": None}
    payload = _read_json(path)
    return {
        "stop_live": bool(payload.get("stop_live")),
        "stop_reason": payload.get("stop_reason"),
    }


def persist_run_progress(artifact_dir: Path, progress: dict[str, Any]) -> None:
    atomic_write_json(artifact_dir / _RUN_PROGRESS_FILENAME, progress)


def build_identity_snapshot(
    *,
    scenarios_path: Path,
    expected_head: str,
) -> dict[str, Any]:
    from core.one_call_client_pack_identity import build_client_pack_identity

    scenarios_bytes = scenarios_path.read_bytes()
    scenarios_sha256 = hashlib.sha256(scenarios_bytes).hexdigest()
    pack_identity = build_client_pack_identity(CLIENT_ID)
    transport = resolve_transport_observability()
    return {
        "measurement_id": MEASUREMENT_ID,
        "expected_head": expected_head,
        "actual_head": _git_head(),
        "git_branch": _git_branch(),
        "working_tree": working_tree_fingerprint(),
        "scenarios_path": str(scenarios_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "scenarios_sha256": scenarios_sha256,
        "client_id": CLIENT_ID,
        "client_pack_hash": pack_identity.client_pack_hash,
        "prompt_contract_version": pack_identity.prompt_contract_version,
        "governance_module_hashes": governance_module_hashes(),
        "requested_provider_model_id": REQUESTED_PROVIDER_MODEL_ID,
        "config_qwen_plus_model": config.QWEN_PLUS_MODEL,
        "config_sales_one_plus_flash_model": config.SALES_ONE_PLUS_FLASH_MODEL,
        "target_path": "SALES_ONE_PLUS_ON=1 -> /ask,/ask/stream -> run_sales_fast_widget_turn",
        "endpoint_host": transport.endpoint_host,
        "provider_region": transport.provider_region,
        "inference_settings": transport.inference_settings,
        "pricing_snapshot": DEFAULT_SPEAKER_PRICING.to_dict(),
    }


def _credentials_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_KEY_MARKERS)


def assert_preflight(
    *,
    expected_head: str,
    live: bool,
    scenarios_path: Path = DEFAULT_SCENARIOS_PATH,
) -> dict[str, Any]:
    if not _FULL_COMMIT_SHA_RE.fullmatch(expected_head):
        raise BotCleanupLiveGovernanceError("expected_head_invalid", expected_head)
    head = _git_head()
    if head != expected_head:
        raise BotCleanupLiveGovernanceError(
            "head_mismatch",
            f"expected={expected_head} actual={head}",
        )
    data = load_bot_cleanup_scenarios(scenarios_path)
    errors = validate_bot_cleanup_scenarios(data)
    if errors:
        raise BotCleanupLiveGovernanceError(
            "scenarios_invalid",
            ";".join(errors[:5]),
        )
    assert_not_flash_model(REQUESTED_PROVIDER_MODEL_ID)
    assert_not_flash_model(FUTURE_LIVE_MODEL)

    api_key = (os.getenv("CHAT_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    base_url = (os.getenv("CHAT_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or "").strip()
    if live:
        if _credentials_placeholder(api_key):
            raise BotCleanupLiveGovernanceError("chat_api_key_missing", "chat_api_key")
        if not base_url:
            raise BotCleanupLiveGovernanceError("chat_base_url_missing", "chat_base_url")

    summary = summarize_bot_cleanup_scenarios(data)
    identity = build_identity_snapshot(scenarios_path=scenarios_path, expected_head=expected_head)
    return {
        **identity,
        **summary,
        "live_requested": live,
        "max_provider_calls": DEFAULT_MAX_PROVIDER_CALLS,
        "monetary_cap_usd": DEFAULT_MONETARY_CAP_USD,
    }


def artifact_dir_for_attempt(attempt_id: str) -> Path:
    return _REPO_ROOT / "evals" / "v5" / "artifacts" / MEASUREMENT_ID / attempt_id


def _artifact_ref(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _parse_sse_events(resp) -> list[tuple[str, dict[str, Any]]]:
    buffer = ""
    events: list[tuple[str, dict[str, Any]]] = []
    current_event: str | None = None
    for chunk in resp.response:
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.startswith("event: "):
                current_event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                raw = line[len("data: ") :]
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    data = {}
                if current_event:
                    events.append((current_event, data))
                current_event = None
    return events


def extract_ui_payload_from_ask_json(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": body.get("answer"),
        "followups": body.get("followups"),
        "video": body.get("video"),
        "cta": body.get("cta"),
        "meta": body.get("meta"),
    }


def extract_ui_payload_from_stream(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    ui_events = [data for name, data in events if name == "ui"]
    if not ui_events:
        return {}
    return dict(ui_events[-1])


def compare_ask_stream_payloads(
    ask_payload: dict[str, Any],
    stream_payload: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    ask_answer = str(ask_payload.get("answer") or "").strip()
    stream_answer = str(stream_payload.get("answer") or "").strip()
    if ask_answer != stream_answer:
        mismatches.append("answer")
    for key in ("followups", "video", "cta"):
        if ask_payload.get(key) != stream_payload.get(key):
            mismatches.append(key)
    return mismatches


def _clear_session_connection_cache() -> None:
    import session as session_module

    with session_module._lock:
        for conn in list(session_module._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_module._conns.clear()


def _isolated_sqlite_path(artifact_dir: Path, client_id: str | None) -> str:
    pack = client_id or CLIENT_ID
    return str((artifact_dir / "sessions" / f"{pack}.db").resolve())


@contextmanager
def bot_cleanup_eval_guards(
    *,
    artifact_dir: Path,
    backend_factory: Callable[[], BotCleanupLiveBackend],
    block_external_notifications: bool = True,
):
    import app as app_module
    from session import bind_session_client

    sessions_dir = artifact_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    _clear_session_connection_cache()

    def _sqlite_path(client_id: str | None) -> str:
        return _isolated_sqlite_path(artifact_dir, client_id)

    patches = [
        patch.object(config, "SALES_ONE_PLUS_ON", True),
        patch.object(app_module, "SALES_ONE_PLUS_ON", True),
        patch(
            "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
            backend_factory,
        ),
        patch("core.client_runtime.sqlite_path_for_client", _sqlite_path),
        patch("session.sqlite_path_for_client", _sqlite_path),
    ]
    if block_external_notifications:
        patches.append(
            patch("core.lead_email.send_lead_email", return_value=(True, "blocked_eval"))
        )

    bind_session_client(CLIENT_ID)
    started: list[Any] = []
    for patch_obj in patches:
        patch_obj.start()
        started.append(patch_obj)
    try:
        yield
    finally:
        for patch_obj in reversed(started):
            patch_obj.stop()
        _clear_session_connection_cache()


def _provider_attempt_dict(backend: BotCleanupLiveBackend | None) -> dict[str, Any] | None:
    if backend is None or backend.last_record is None:
        return None
    row = backend.last_record.to_dict()
    obs = backend.last_observability
    if obs is not None:
        row["observability"] = asdict(obs)
    return row


def execute_http_turn(
    *,
    client,
    endpoint: str,
    patient_message: str,
    session_sid: str,
    client_id: str = CLIENT_ID,
    backend: BotCleanupLiveBackend | None = None,
) -> dict[str, Any]:
    payload = {"q": patient_message, "sid": session_sid, "client_id": client_id}
    resp = client.post(endpoint, json=payload)
    http_status = resp.status_code
    if endpoint.endswith("/stream"):
        events = _parse_sse_events(resp)
        ui = extract_ui_payload_from_stream(events)
        body = ui
    else:
        body = resp.get_json(silent=True) or {}
        ui = extract_ui_payload_from_ask_json(body)
    final_answer = ui.get("answer")
    if final_answer is None and isinstance(body, dict):
        final_answer = body.get("answer")
    return {
        "endpoint": endpoint,
        "http_status": http_status,
        "http_body": body,
        "final_answer": final_answer,
        "ui": {
            "followups": ui.get("followups"),
            "video": ui.get("video"),
            "cta": ui.get("cta"),
        },
        "model_raw_output": getattr(backend, "last_raw_output", None),
        "provider_attempt": _provider_attempt_dict(backend),
        "request_payload": getattr(backend, "last_request_payload", None),
        "request_sha256": getattr(backend, "last_request_sha256", None),
    }


def _cost_request_from_provider(payload: dict[str, Any] | None, turn_id: str) -> dict[str, Any]:
    messages = (payload or {}).get("messages") or []
    return {"case_id": turn_id, "messages": messages}


def _load_turn_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _load_saved_turn_record(
    *,
    artifact_dir: Path,
    turn_id: str,
    existing_turns: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    saved = existing_turns.get(turn_id)
    if saved is not None:
        return saved
    raw_path = artifact_dir / "raw_turns" / f"{turn_id}.json"
    if not raw_path.exists():
        return None
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    turn = payload.get("turn")
    return turn if isinstance(turn, dict) else None


def runtime_session_to_dict(state: Any) -> dict[str, Any]:
    from core.target_effective_scope import patient_facts_payload

    patient_facts = None
    if state.patient_facts is not None:
        patient_facts = patient_facts_payload(state.patient_facts)
    return {
        "last_service_id": state.last_service_id,
        "last_topic": state.last_topic,
        "last_primary_aspect": state.last_primary_aspect,
        "service_focus_set_at_turn": state.service_focus_set_at_turn,
        "session_turn_count": state.session_turn_count,
        "shown_fact_ids": list(state.shown_fact_ids),
        "shown_amplifier_refs": list(state.shown_amplifier_refs),
        "shown_consultation_value_refs": list(state.shown_consultation_value_refs),
        "shown_video_ids": list(state.shown_video_ids),
        "shown_content_followup_refs": list(state.shown_content_followup_refs),
        "shown_price_followup_refs": list(state.shown_price_followup_refs),
        "situation_offered": state.situation_offered,
        "shown_service_value_ids": list(state.shown_service_value_ids),
        "last_rendered_promo_fact_id": state.last_rendered_promo_fact_id,
        "rendered_promo_fact_ids": list(state.rendered_promo_fact_ids),
        "last_turn_rendered_promo_fact_ids": list(state.last_turn_rendered_promo_fact_ids),
        "followups": [
            {"ref": item.ref, "label": item.label, "client_id": item.client_id}
            for item in state.followups
        ],
        "patient_facts": patient_facts,
    }


def capture_session_snapshot(session_sid: str, *, turn_id: str, config_digest: str) -> dict[str, Any]:
    from collections import deque

    from config import MAX_TURNS
    from core.target_runtime_session import read_target_runtime_session
    from session import mem_get

    st = mem_get(session_sid)
    mem_state: dict[str, Any] = {}
    for key, value in st.items():
        if key == "hist" and isinstance(value, deque):
            mem_state[key] = list(value)
        else:
            mem_state[key] = value
    runtime = read_target_runtime_session(session_sid)
    return {
        "session_sid": session_sid,
        "turn_id": turn_id,
        "config_digest": config_digest,
        "mem_state": mem_state,
        "runtime_session": runtime_session_to_dict(runtime),
    }


def restore_session_snapshot(snapshot: dict[str, Any]) -> None:
    from collections import deque

    from config import MAX_TURNS
    import session as session_module

    session_sid = str(snapshot.get("session_sid") or "")
    mem_state = snapshot.get("mem_state")
    if not session_sid or not isinstance(mem_state, dict):
        raise BotCleanupLiveGovernanceError("session_snapshot_invalid", session_sid)
    restored = session_module._fresh_defaults()
    for key, value in mem_state.items():
        if key == "pending_clarify":
            continue
        if key == "hist" and isinstance(value, list):
            restored["hist"] = deque(value, maxlen=MAX_TURNS * 2)
        else:
            restored[key] = value
    with session_module._lock:
        session_module._persist_unlocked(session_sid, restored)


def provider_raw_path(artifact_dir: Path, turn_id: str, attempt_index: int) -> Path:
    return artifact_dir / "provider_raw" / f"{turn_id}_attempt_{attempt_index}.json"


def session_snapshot_path(artifact_dir: Path, turn_id: str) -> Path:
    return artifact_dir / "session_snapshots" / f"{turn_id}.json"


def _validate_provider_raw_identity(
    *,
    payload: dict[str, Any],
    run_config: dict[str, Any],
    turn_id: str,
) -> None:
    if str(payload.get("turn_id") or "") != turn_id:
        raise BotCleanupLiveGovernanceError(
            "provider_raw_identity_mismatch",
            f"turn_id:{payload.get('turn_id')}",
        )
    if payload.get("config_digest") != run_config.get("config_digest"):
        raise BotCleanupLiveGovernanceError(
            "provider_raw_identity_mismatch",
            "config_digest",
        )
    if payload.get("measurement_id") != run_config.get("measurement_id"):
        raise BotCleanupLiveGovernanceError(
            "provider_raw_identity_mismatch",
            "measurement_id",
        )


def load_provider_raw(
    *,
    artifact_dir: Path,
    turn_id: str,
    attempt_index: int,
    run_config: dict[str, Any],
    request_sha256: str | None = None,
) -> dict[str, Any]:
    path = provider_raw_path(artifact_dir, turn_id, attempt_index)
    if not path.exists():
        raise BotCleanupLiveGovernanceError("provider_raw_missing", str(path))
    payload = _read_json(path)
    _validate_provider_raw_identity(payload=payload, run_config=run_config, turn_id=turn_id)
    if request_sha256 and payload.get("request_sha256") != request_sha256:
        raise BotCleanupLiveGovernanceError(
            "provider_raw_identity_mismatch",
            "request_sha256",
        )
    return payload


def _persist_turn_results(artifact_dir: Path, turn_results: list[dict[str, Any]]) -> None:
    atomic_write_json(artifact_dir / "turn_results.json", turn_results)


def _assert_resume_identity(current: dict[str, Any], saved: dict[str, Any]) -> None:
    _assert_run_config_identity(current, saved)


def _turn_is_resumable(saved: dict[str, Any]) -> bool:
    status = str(saved.get("status") or "")
    if status in {"fixture_skipped", "skipped", "not_run"}:
        return True
    attempt = saved.get("provider_attempt") or {}
    outcome = str(attempt.get("outcome") or "")
    if status == "uncertain" or outcome in {"reserved", "uncertain"}:
        raise BotCleanupLiveGovernanceError(
            "resume_uncertain_attempt",
            str(saved.get("turn_id") or ""),
        )
    return bool(saved.get("checkpoint_complete")) and status in {"ok", "error", "blocked"}


def _is_checkpoint_complete(saved: dict[str, Any]) -> bool:
    return bool(saved.get("checkpoint_complete")) and bool(saved.get("session_snapshot_path"))


def _seed_session_from_saved_turn(
    session_sid: str,
    *,
    patient_message: str,
    saved: dict[str, Any],
) -> None:
    raise BotCleanupLiveGovernanceError(
        "session_snapshot_required",
        "text_replay_disabled_use_session_snapshot",
    )


def _is_replayable_turn(saved: dict[str, Any]) -> bool:
    return _is_checkpoint_complete(saved)


def _prepare_scenario_session(
    *,
    session_sid: str,
    scenario: dict[str, Any],
    artifact_dir: Path,
    existing_turns: dict[str, dict[str, Any]],
    run_config: dict[str, Any],
) -> None:
    last_snapshot_turn_id: str | None = None
    for turn in scenario.get("turns") or []:
        turn_id = str(turn.get("id") or "")
        saved = _load_saved_turn_record(
            artifact_dir=artifact_dir,
            turn_id=turn_id,
            existing_turns=existing_turns,
        )
        if saved and _is_checkpoint_complete(saved):
            last_snapshot_turn_id = turn_id
            continue
        break

    if last_snapshot_turn_id:
        snapshot_path = session_snapshot_path(artifact_dir, last_snapshot_turn_id)
        if not snapshot_path.exists():
            raise BotCleanupLiveGovernanceError(
                "session_snapshot_missing",
                last_snapshot_turn_id,
            )
        snapshot = _read_json(snapshot_path)
        if snapshot.get("config_digest") != run_config.get("config_digest"):
            raise BotCleanupLiveGovernanceError(
                "session_snapshot_identity_mismatch",
                last_snapshot_turn_id,
            )
        if str(snapshot.get("session_sid") or "") != session_sid:
            raise BotCleanupLiveGovernanceError(
                "session_snapshot_sid_mismatch",
                last_snapshot_turn_id,
            )
        restore_session_snapshot(snapshot)
        return

    from session import mem_reset

    mem_reset(session_sid)


def _assert_ledger_present(artifact_dir: Path) -> None:
    if _artifact_has_progress(artifact_dir) and not (artifact_dir / "call_budget.json").exists():
        raise BotCleanupLiveGovernanceError(
            "resume_ledger_missing",
            "call_budget.json",
        )


def _assert_global_governance_state(
    *,
    artifact_dir: Path,
    budget: BotCleanupCallBudget,
    run_progress: dict[str, Any],
    run_config: dict[str, Any],
) -> None:
    if run_progress.get("stop_live"):
        return
    for record in budget.ledger:
        if record.outcome not in {"reserved", "uncertain"}:
            continue
        raw_path = provider_raw_path(artifact_dir, str(record.turn_id or ""), record.attempt_index)
        if not raw_path.exists():
            raise BotCleanupLiveGovernanceError(
                "resume_uncertain_attempt",
                f"{record.turn_id}:{record.outcome}",
            )


def _find_recovery_context(
    *,
    artifact_dir: Path,
    budget: BotCleanupCallBudget,
    turn_id: str,
    run_config: dict[str, Any],
) -> dict[str, Any] | None:
    records = budget.find_turn_records(turn_id)
    if not records:
        return None
    record = records[-1]
    if record.outcome in _FINALIZED_BUDGET_OUTCOMES:
        return None
    if record.outcome not in {"reserved", "uncertain"}:
        return None
    raw_path = provider_raw_path(artifact_dir, turn_id, record.attempt_index)
    if not raw_path.exists():
        raise BotCleanupLiveGovernanceError(
            "resume_uncertain_attempt",
            f"{turn_id}:{record.outcome}",
        )
    raw_payload = load_provider_raw(
        artifact_dir=artifact_dir,
        turn_id=turn_id,
        attempt_index=record.attempt_index,
        run_config=run_config,
        request_sha256=record.request_sha256,
    )
    return {"record": record, "provider_raw": raw_payload}


def _should_stop_after_turn(
    *,
    http_result: dict[str, Any],
    backend: BotCleanupLiveBackend | None,
    status: str,
    error_code: str | None,
) -> tuple[bool, str | None]:
    if status == "error":
        return True, error_code or "turn_error"
    if backend is not None and backend.last_record is not None:
        outcome = str(backend.last_record.outcome or "")
        if outcome in {"error", "model_mismatch", "uncertain", "reserved"}:
            return True, outcome
    meta = _payload_meta(http_result.get("http_body"))
    if str(meta.get("service_route") or "").endswith("_error"):
        return True, "service_route_error"
    return False, None


_FINALIZED_BUDGET_OUTCOMES = frozenset({"ok", "error", "model_mismatch"})


def _payload_meta(http_body: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(http_body, dict):
        return {}
    meta = http_body.get("meta")
    return meta if isinstance(meta, dict) else {}


def _classify_turn_execution(
    *,
    http_result: dict[str, Any],
    backend: BotCleanupLiveBackend | None,
) -> tuple[str, str | None, str | None]:
    if http_result.get("http_status") != 200:
        return (
            "error",
            "http_error",
            f"status={http_result.get('http_status')}",
        )
    meta = _payload_meta(http_result.get("http_body"))
    service_route = str(meta.get("service_route") or "").strip().lower()
    if service_route.endswith("_error") or service_route in {"error", "sales_fast_error"}:
        return (
            "error",
            "service_route_error",
            service_route or "sales_fast_error",
        )
    meta_error = meta.get("error") or meta.get("meta_error")
    if meta_error:
        return ("error", "payload_meta_error", str(meta_error))
    if backend is not None and backend.last_record is not None:
        outcome = str(backend.last_record.outcome or "")
        if outcome in {"error", "model_mismatch", "uncertain", "reserved"}:
            return (
                "error",
                outcome,
                str(backend.last_record.error_code or outcome),
            )
    return ("ok", None, None)


def run_measurement(
    *,
    attempt_id: str,
    expected_head: str = EXPECTED_HEAD,
    live: bool = False,
    max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
    monetary_cap_usd: str = DEFAULT_MONETARY_CAP_USD,
    scenarios_path: Path = DEFAULT_SCENARIOS_PATH,
    chat_completions_create: Callable[..., Any] | None = None,
    scenario_filter: tuple[str, ...] | None = None,
    turn_filter: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if not live and chat_completions_create is None:
        raise BotCleanupLiveGovernanceError(
            "offline_transport_stub_required",
            "run_measurement(live=False) requires chat_completions_create stub",
        )

    preflight = assert_preflight(expected_head=expected_head, live=live, scenarios_path=scenarios_path)
    artifact_dir = artifact_dir_for_attempt(attempt_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "raw_turns").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "provider_raw").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "session_snapshots").mkdir(parents=True, exist_ok=True)

    current_run_config = build_run_config(
        preflight=preflight,
        attempt_id=attempt_id,
        max_calls=max_calls,
        monetary_cap_usd=monetary_cap_usd,
    )

    scenarios_data = load_bot_cleanup_scenarios(scenarios_path)
    scenarios = scenarios_data.get("scenarios") or []

    with ExperimentLock(artifact_dir / _EXPERIMENT_LOCK_FILENAME):
        run_config = bootstrap_run_config(
            artifact_dir=artifact_dir,
            current_config=current_run_config,
        )
        _assert_ledger_present(artifact_dir)
        run_progress = load_run_progress(artifact_dir)
        stop_live = bool(run_progress.get("stop_live"))
        stop_reason = run_progress.get("stop_reason")

        shutil.copy2(scenarios_path, artifact_dir / "frozen_scenarios.json")

        budget = BotCleanupCallBudget(
            max_calls=max_calls,
            ledger_path=artifact_dir / "call_budget.json",
        )
        budget.load()
        cost_ledger = SpeakerCostLedger(
            experiment_id=MEASUREMENT_ID,
            monetary_cap_usd=monetary_cap_usd,
            ledger_path=artifact_dir / "cost_ledger.json",
            pricing=DEFAULT_SPEAKER_PRICING,
        )
        cost_ledger.load()
        _assert_global_governance_state(
            artifact_dir=artifact_dir,
            budget=budget,
            run_progress=run_progress,
            run_config=run_config,
        )

        turn_results = _load_turn_results(artifact_dir / "turn_results.json")
        existing_turns = {
            str(row.get("turn_id") or ""): row
            for row in turn_results
            if str(row.get("turn_id") or "").strip()
        }

        import app as app_module

        client = app_module.app.test_client()
        backend_holder: dict[str, BotCleanupLiveBackend | None] = {"backend": None}
        active_turn_id: dict[str, str | None] = {"value": None}
        recovery_holder: dict[str, dict[str, Any] | None] = {"context": None}
        transport_calls = {"count": 0}

        def _persist_provider_raw(payload: dict[str, Any]) -> None:
            turn = str(payload.get("turn_id") or active_turn_id["value"] or "")
            attempt_index = int(payload.get("attempt_index") or 0)
            enriched = {
                **payload,
                "measurement_id": run_config.get("measurement_id"),
                "attempt_id": run_config.get("attempt_id"),
                "config_digest": run_config.get("config_digest"),
            }
            path = provider_raw_path(artifact_dir, turn, attempt_index)
            atomic_write_json(path, enriched)
            backend = backend_holder.get("backend")
            if backend is not None:
                backend.last_provider_raw_path = _artifact_ref(path)

        def _wrapped_transport(**kwargs: Any) -> Any:
            transport_calls["count"] += 1
            assert chat_completions_create is not None
            return chat_completions_create(**kwargs)

        def _factory() -> BotCleanupLiveBackend:
            recovery = recovery_holder["context"]
            backend = BotCleanupLiveBackend(
                budget=budget,
                turn_id=active_turn_id["value"],
                model=REQUESTED_PROVIDER_MODEL_ID,
                chat_completions_create=(
                    None
                    if recovery
                    else (_wrapped_transport if chat_completions_create else None)
                ),
                cost_ledger=cost_ledger if live else None,
                provider_raw_persist=_persist_provider_raw,
                replay_provider_raw=(recovery or {}).get("provider_raw") if recovery else None,
                replay_record=(recovery or {}).get("record") if recovery else None,
            )
            backend_holder["backend"] = backend
            return backend

        def _restore_session_before_turn(
            *,
            scenario: dict[str, Any],
            turn_id: str,
            session_sid: str,
        ) -> None:
            turn_ids = [str(item.get("id") or "") for item in scenario.get("turns") or []]
            if turn_id not in turn_ids:
                from session import mem_reset

                mem_reset(session_sid)
                return
            index = turn_ids.index(turn_id)
            if index == 0:
                from session import mem_reset

                mem_reset(session_sid)
                return
            prev_turn_id = turn_ids[index - 1]
            prev_saved = existing_turns.get(prev_turn_id)
            if prev_saved and _is_checkpoint_complete(prev_saved):
                snapshot = _read_json(session_snapshot_path(artifact_dir, prev_turn_id))
                restore_session_snapshot(snapshot)
                return
            from session import mem_reset

            mem_reset(session_sid)

        with bot_cleanup_eval_guards(artifact_dir=artifact_dir, backend_factory=_factory):
            for scenario in scenarios:
                scenario_id = str(scenario.get("id") or "")
                if scenario_filter and scenario_id not in scenario_filter:
                    continue
                session_sid = str(scenario.get("session_sid") or "")
                fixture_only = bool(scenario.get("fixture_only"))
                scenario_blocked = False

                if not fixture_only:
                    _prepare_scenario_session(
                        session_sid=session_sid,
                        scenario=scenario,
                        artifact_dir=artifact_dir,
                        existing_turns=existing_turns,
                        run_config=run_config,
                    )

                for turn in scenario.get("turns") or []:
                    turn_id = str(turn.get("id") or "")
                    if turn_filter and turn_id not in turn_filter:
                        continue
                    patient_message = str(turn.get("patient_message") or "")

                    if fixture_only:
                        row = {
                            "scenario_id": scenario_id,
                            "turn_id": turn_id,
                            "patient_message": patient_message,
                            "status": "fixture_skipped",
                            "final_answer": None,
                            "review_verdict": "not_reviewed",
                            "transport_completed": False,
                            "checkpoint_complete": False,
                        }
                        if turn_id not in existing_turns:
                            turn_results.append(row)
                            existing_turns[turn_id] = row
                            _persist_turn_results(artifact_dir, turn_results)
                        continue

                    saved = _load_saved_turn_record(
                        artifact_dir=artifact_dir,
                        turn_id=turn_id,
                        existing_turns=existing_turns,
                    )
                    if saved and _turn_is_resumable(saved):
                        if turn_id not in existing_turns:
                            turn_results.append(saved)
                            existing_turns[turn_id] = saved
                            _persist_turn_results(artifact_dir, turn_results)
                        continue

                    if stop_live or scenario_blocked:
                        row = {
                            "scenario_id": scenario_id,
                            "turn_id": turn_id,
                            "patient_message": patient_message,
                            "status": "skipped",
                            "error_code": stop_reason or "dependency_blocked",
                            "error_message": "Prior turn blocked the dialog chain.",
                            "final_answer": None,
                            "review_verdict": "not_reviewed",
                            "transport_completed": False,
                            "checkpoint_complete": False,
                        }
                        if turn_id not in existing_turns:
                            turn_results.append(row)
                            existing_turns[turn_id] = row
                            _persist_turn_results(artifact_dir, turn_results)
                        continue

                    recovery_holder["context"] = _find_recovery_context(
                        artifact_dir=artifact_dir,
                        budget=budget,
                        turn_id=turn_id,
                        run_config=run_config,
                    )
                    if recovery_holder["context"] is not None:
                        _restore_session_before_turn(
                            scenario=scenario,
                            turn_id=turn_id,
                            session_sid=session_sid,
                        )

                    active_turn_id["value"] = turn_id
                    backend_holder["backend"] = None
                    http_result: dict[str, Any] | None = None

                    try:
                        http_result = execute_http_turn(
                            client=client,
                            endpoint="/ask",
                            patient_message=patient_message,
                            session_sid=session_sid,
                        )
                        backend = backend_holder.get("backend")
                        if backend is not None:
                            http_result["model_raw_output"] = backend.last_raw_output
                            http_result["provider_attempt"] = _provider_attempt_dict(backend)
                            http_result["request_payload"] = backend.last_request_payload
                            http_result["request_sha256"] = backend.last_request_sha256
                    except BotCleanupBudgetExceeded as exc:
                        stop_live = True
                        stop_reason = "budget_exhausted"
                        row = {
                            "scenario_id": scenario_id,
                            "turn_id": turn_id,
                            "patient_message": patient_message,
                            "status": "blocked",
                            "error_code": "budget_exhausted",
                            "error_message": str(exc),
                            "final_answer": None,
                            "review_verdict": "not_reviewed",
                            "transport_completed": False,
                            "checkpoint_complete": False,
                        }
                        turn_results = [row if r.get("turn_id") == turn_id else r for r in turn_results]
                        if turn_id not in existing_turns:
                            turn_results.append(row)
                        existing_turns[turn_id] = row
                        _persist_turn_results(artifact_dir, turn_results)
                        persist_run_progress(
                            artifact_dir,
                            {"stop_live": True, "stop_reason": stop_reason},
                        )
                        continue
                    except (
                        BotCleanupModelMismatch,
                        BotCleanupTransportAlreadyCompleted,
                        BotCleanupUncertainAttempt,
                        BotCleanupRequestHashConflict,
                    ) as exc:
                        stop_live = True
                        stop_reason = type(exc).__name__
                        backend = backend_holder.get("backend")
                        row = {
                            "scenario_id": scenario_id,
                            "turn_id": turn_id,
                            "patient_message": patient_message,
                            "status": "error",
                            "error_code": type(exc).__name__,
                            "error_message": str(exc),
                            "final_answer": (http_result or {}).get("final_answer"),
                            "model_raw_output": getattr(backend, "last_raw_output", None),
                            "review_verdict": "not_reviewed",
                            "transport_completed": True,
                            "checkpoint_complete": False,
                        }
                        if turn_id not in existing_turns:
                            turn_results.append(row)
                        existing_turns[turn_id] = row
                        _persist_turn_results(artifact_dir, turn_results)
                        persist_run_progress(
                            artifact_dir,
                            {"stop_live": True, "stop_reason": stop_reason},
                        )
                        break
                    finally:
                        recovery_holder["context"] = None

                    if http_result is None:
                        continue

                    backend = backend_holder.get("backend")
                    status, error_code, error_message = _classify_turn_execution(
                        http_result=http_result,
                        backend=backend,
                    )
                    should_stop, stop_code = _should_stop_after_turn(
                        http_result=http_result,
                        backend=backend,
                        status=status,
                        error_code=error_code,
                    )
                    if status == "error":
                        scenario_blocked = True
                    if should_stop:
                        stop_live = True
                        stop_reason = stop_code

                    snapshot = capture_session_snapshot(
                        session_sid,
                        turn_id=turn_id,
                        config_digest=str(run_config.get("config_digest") or ""),
                    )
                    snapshot_path = session_snapshot_path(artifact_dir, turn_id)
                    atomic_write_json(snapshot_path, snapshot)

                    row = {
                        "scenario_id": scenario_id,
                        "turn_id": turn_id,
                        "request_id": str(uuid.uuid4()),
                        "patient_message": patient_message,
                        "status": status,
                        "final_answer": http_result.get("final_answer"),
                        "model_raw_output": http_result.get("model_raw_output"),
                        "error_code": error_code,
                        "error_message": error_message,
                        "ui": http_result.get("ui") or {},
                        "provider_attempt": http_result.get("provider_attempt"),
                        "http": {
                            "endpoint": http_result.get("endpoint"),
                            "status_code": http_result.get("http_status"),
                            "service_route": _payload_meta(http_result.get("http_body")).get(
                                "service_route"
                            ),
                        },
                        "review_verdict": "not_reviewed",
                        "transport_completed": True,
                        "checkpoint_complete": True,
                        "session_snapshot_path": _artifact_ref(snapshot_path),
                        "provider_raw_path": (
                            backend.last_provider_raw_path
                            if backend and backend.last_provider_raw_path
                            else None
                        ),
                    }
                    raw_path = artifact_dir / "raw_turns" / f"{turn_id}.json"
                    atomic_write_json(
                        raw_path,
                        {
                            "turn": row,
                            "http_body": http_result.get("http_body"),
                            "request_payload": http_result.get("request_payload"),
                            "request_sha256": http_result.get("request_sha256"),
                        },
                    )
                    row["raw_turn_path"] = _artifact_ref(raw_path)
                    turn_results = [item for item in turn_results if item.get("turn_id") != turn_id]
                    turn_results.append(row)
                    existing_turns[turn_id] = row
                    _persist_turn_results(artifact_dir, turn_results)
                    if should_stop:
                        persist_run_progress(
                            artifact_dir,
                            {"stop_live": True, "stop_reason": stop_reason},
                        )

        transcript = render_transcript_markdown(
            attempt_id=attempt_id,
            scenarios=scenarios,
            turn_results=turn_results,
            artifact_dir=_artifact_ref(artifact_dir),
        )
        _atomic_write_text(artifact_dir / "transcript.md", transcript)

        manifest = {
            **run_config,
            "provider_calls_consumed": budget.consumed,
            "stop_live": stop_live,
            "stop_reason": stop_reason,
            "transport_calls_this_run": transport_calls["count"],
        }
        atomic_write_json(artifact_dir / "manifest.json", manifest)
        persist_run_progress(
            artifact_dir,
            {"stop_live": stop_live, "stop_reason": stop_reason},
        )
        _persist_turn_results(artifact_dir, turn_results)
        return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bot cleanup LIVE runner (sales-fast /ask)")
    parser.add_argument("--live", action="store_true", help="Execute provider calls")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--expected-head", default=EXPECTED_HEAD)
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_PROVIDER_CALLS)
    parser.add_argument("--monetary-cap-usd", default=DEFAULT_MONETARY_CAP_USD)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        for key in ("CHAT_API_KEY", "DASHSCOPE_API_KEY"):
            value = (os.getenv(key) or "").strip()
            if value:
                os.environ["OPENAI_API_KEY"] = value
                break
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        os.environ["OPENAI_API_KEY"] = "sk-offline-preflight-placeholder"

    args = build_parser().parse_args(argv)
    attempt_id = args.attempt_id.strip()
    if not attempt_id:
        print("attempt_id_required", file=sys.stderr)
        return 2

    try:
        if args.preflight_only or not args.live:
            summary = assert_preflight(
                expected_head=args.expected_head,
                live=args.live,
                scenarios_path=DEFAULT_SCENARIOS_PATH,
            )
            summary["attempt_id"] = attempt_id
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if args.preflight_only else 3

        manifest = run_measurement(
            attempt_id=attempt_id,
            expected_head=args.expected_head,
            live=True,
            max_calls=args.max_calls,
            monetary_cap_usd=args.monetary_cap_usd,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0 if not manifest.get("stop_live") else 1
    except BotCleanupLiveGovernanceError as exc:
        print(f"governance_error:{exc.code}:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
