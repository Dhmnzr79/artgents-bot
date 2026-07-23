"""Provider transport audit for S63 target runtime delta live eval."""

from __future__ import annotations

import contextvars
import inspect
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from evals.v5.s63_target_runtime_live_contract import (
    ALLOWED_PROVIDER_ROLES,
    MAX_BOUNDARY_CALLS,
    MAX_COMPOSER_CALLS,
    MAX_INGRESS_CALLS,
    MAX_PLANNER_CALLS,
    MAX_PROVIDER_CALLS,
    MAX_VERIFIER_CALLS,
    ProviderRoleViolationError,
    append_call_ledger_entry,
    load_attempt_marker,
    persist_attempt_marker,
)


@dataclass
class ProviderAuditState:
    current_turn: int = 0
    sequence: int = 0
    total_started: int = 0
    role_totals: dict[str, int] = field(
        default_factory=lambda: {role: 0 for role in sorted(ALLOWED_PROVIDER_ROLES)}
    )
    turn_roles: dict[int, set[str]] = field(default_factory=dict)
    turn_role_counts: dict[int, dict[str, int]] = field(default_factory=dict)
    legacy_hits: list[str] = field(default_factory=list)
    fullcontext_build_count: int = 0


_STATE = ProviderAuditState()
_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINAL_CHAT = None
_ORIGINAL_MODULE_BINDINGS: dict[str, object] = {}
_PENDING_ROLE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "s63_pending_provider_role",
    default=None,
)


def get_audit_state() -> ProviderAuditState:
    return _STATE


def reset_audit_state() -> None:
    global _STATE
    with _LOCK:
        _STATE = ProviderAuditState()


def set_current_turn(turn_number: int) -> None:
    with _LOCK:
        _STATE.current_turn = turn_number
        _STATE.turn_roles.setdefault(turn_number, set())
        _STATE.turn_role_counts.setdefault(
            turn_number,
            {role: 0 for role in sorted(ALLOWED_PROVIDER_ROLES)},
        )


def record_legacy_hit(name: str) -> None:
    with _LOCK:
        _STATE.legacy_hits.append(name)


def record_fullcontext_build() -> None:
    with _LOCK:
        _STATE.fullcontext_build_count += 1


def _infer_provider_role() -> str:
    pending = _PENDING_ROLE.get()
    if pending:
        return pending
    for frame in inspect.stack()[2:40]:
        filename = frame.filename.replace("\\", "/")
        function = frame.function
        if filename.endswith("/ingress_gate.py") or function in {
            "_call_ingress_llm",
            "classify_ingress_route",
        }:
            return "ingress"
        if "/turn_planner_llm.py" in filename or function in {
            "_planner_chat_completions_create",
            "plan_turn_attempt",
        }:
            return "planner"
        if "/target_runtime_llm_backends.py" in filename:
            if function == "generate":
                return "composer"
            if function == "assess":
                return "semantic_verifier"
            if function == "classify":
                return "medical_boundary"
    raise ProviderRoleViolationError("unknown provider call role")


def _role_wrapped(role: str, audited_chat):
    def wrapped(**kwargs: Any):
        token = _PENDING_ROLE.set(role)
        try:
            return audited_chat(**kwargs)
        finally:
            _PENDING_ROLE.reset(token)

    return wrapped


def _rebind_audited_chat(audited_chat) -> None:
    import importlib

    import llm

    llm.chat_completions_create = audited_chat
    for module_name, role in (
        ("ingress_gate", "ingress"),
        ("core.turn_planner_llm", "planner"),
    ):
        module = importlib.import_module(module_name)
        if hasattr(module, "chat_completions_create"):
            binding_key = f"{module_name}.chat_completions_create"
            if binding_key not in _ORIGINAL_MODULE_BINDINGS:
                _ORIGINAL_MODULE_BINDINGS[binding_key] = getattr(
                    module,
                    "chat_completions_create",
                )
            setattr(
                module,
                "chat_completions_create",
                _role_wrapped(role, audited_chat),
            )
        if module_name == "core.turn_planner_llm" and hasattr(
            module,
            "_planner_chat_completions_create",
        ):
            planner_key = f"{module_name}._planner_chat_completions_create"
            if planner_key not in _ORIGINAL_MODULE_BINDINGS:
                _ORIGINAL_MODULE_BINDINGS[planner_key] = getattr(
                    module,
                    "_planner_chat_completions_create",
                )
            setattr(
                module,
                "_planner_chat_completions_create",
                _role_wrapped("planner", audited_chat),
            )


def _restore_module_bindings() -> None:
    import importlib

    for binding_key, original in list(_ORIGINAL_MODULE_BINDINGS.items()):
        module_name, attr = binding_key.rsplit(".", 1)
        module = importlib.import_module(module_name)
        setattr(module, attr, original)
    _ORIGINAL_MODULE_BINDINGS.clear()


def _role_budget(role: str, count: int) -> int:
    return {
        "ingress": MAX_INGRESS_CALLS,
        "planner": MAX_PLANNER_CALLS,
        "medical_boundary": MAX_BOUNDARY_CALLS,
        "composer": MAX_COMPOSER_CALLS,
        "semantic_verifier": MAX_VERIFIER_CALLS,
    }[role]


def _record_call_started(
    *,
    attempt_marker_path: Path,
    call_ledger_path: Path,
    role: str,
    model: str,
    turn_number: int,
) -> int:
    with _LOCK:
        if role not in ALLOWED_PROVIDER_ROLES:
            raise ProviderRoleViolationError(f"disallowed provider role: {role}")
        if _STATE.total_started >= MAX_PROVIDER_CALLS:
            raise ProviderRoleViolationError(
                f"provider call budget exceeded before start total={_STATE.total_started}"
            )
        turn_counts = _STATE.turn_role_counts.setdefault(
            turn_number,
            {name: 0 for name in sorted(ALLOWED_PROVIDER_ROLES)},
        )
        if turn_counts[role] >= 1:
            raise ProviderRoleViolationError(
                f"duplicate provider role in turn turn={turn_number} role={role}"
            )
        total_for_role = _STATE.role_totals[role] + 1
        if total_for_role > _role_budget(role, total_for_role):
            raise ProviderRoleViolationError(
                f"role budget exceeded role={role} count={total_for_role}"
            )
        _STATE.sequence += 1
        _STATE.total_started += 1
        _STATE.role_totals[role] = total_for_role
        turn_counts[role] += 1
        _STATE.turn_roles.setdefault(turn_number, set()).add(role)
        sequence = _STATE.sequence

    marker = load_attempt_marker(attempt_marker_path)
    marker["started_provider_calls"] = _STATE.total_started
    role_counts = marker.setdefault("role_counts", {})
    role_counts[role] = int(role_counts.get(role, 0)) + 1
    persist_attempt_marker(attempt_marker_path, marker)

    append_call_ledger_entry(
        call_ledger_path,
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sequence": sequence,
            "turn_number": turn_number,
            "role": role,
            "model": model,
            "phase": "call_start",
        },
    )
    return sequence


def _record_call_finished(
    *,
    call_ledger_path: Path,
    sequence: int,
    turn_number: int,
    role: str,
    phase: str,
    error: str | None = None,
    usage: dict[str, Any] | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "turn_number": turn_number,
        "role": role,
        "phase": phase,
    }
    if error is not None:
        entry["error"] = error
    if usage is not None:
        entry["usage"] = usage
    append_call_ledger_entry(call_ledger_path, entry)


def install_provider_audit(
    *,
    attempt_marker_path: Path,
    call_ledger_path: Path,
) -> None:
    global _INSTALLED, _ORIGINAL_CHAT
    if _INSTALLED:
        return
    import llm

    _ORIGINAL_CHAT = llm.chat_completions_create

    def audited_chat_completions_create(*, model: str, **kwargs: Any):
        turn_number = _STATE.current_turn or 0
        role = _infer_provider_role()
        sequence = _record_call_started(
            attempt_marker_path=attempt_marker_path,
            call_ledger_path=call_ledger_path,
            role=role,
            model=model,
            turn_number=turn_number,
        )
        try:
            response = _ORIGINAL_CHAT(model=model, **kwargs)
        except Exception as exc:
            _record_call_finished(
                call_ledger_path=call_ledger_path,
                sequence=sequence,
                turn_number=turn_number,
                role=role,
                phase="call_error",
                error=type(exc).__name__,
            )
            raise
        usage = None
        try:
            usage_obj = getattr(response, "usage", None)
            if usage_obj is not None:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }
        except Exception:
            usage = None
        _record_call_finished(
            call_ledger_path=call_ledger_path,
            sequence=sequence,
            turn_number=turn_number,
            role=role,
            phase="call_complete",
            usage=usage,
        )
        return response

    llm.chat_completions_create = audited_chat_completions_create
    _rebind_audited_chat(audited_chat_completions_create)
    _INSTALLED = True


def uninstall_provider_audit() -> None:
    global _INSTALLED, _ORIGINAL_CHAT
    if not _INSTALLED or _ORIGINAL_CHAT is None:
        return
    import llm

    llm.chat_completions_create = _ORIGINAL_CHAT
    _restore_module_bindings()
    _INSTALLED = False
    _ORIGINAL_CHAT = None
    reset_audit_state()


@contextmanager
def provider_audit_context(
    *,
    attempt_marker_path: Path,
    call_ledger_path: Path,
) -> Iterator[ProviderAuditState]:
    reset_audit_state()
    install_provider_audit(
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
    )
    try:
        yield _STATE
    finally:
        uninstall_provider_audit()
