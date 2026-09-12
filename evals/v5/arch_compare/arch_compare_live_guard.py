"""Default-deny LIVE guard for architecture comparison (eval-only)."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.v5.arch_compare.arch_compare_configs import all_arch_compare_configs
from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID, FROZEN_MATRIX_DIGEST
from evals.v5.arch_compare.arch_compare_live_contract import (
    CAPABILITY_PREFLIGHT_BUDGET,
    MEASUREMENT_PROVIDER_BUDGET,
    OPTIONAL_CACHE_PROBE_BUDGET,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
    ArchCompareLiveAuthorizationManifest,
    assert_authorization_manifest_budget,
    frozen_config_digest,
)
from evals.v5.arch_compare.arch_compare_matrix import assert_frozen_matrix_unchanged, frozen_matrix_digest

_FULL_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PLACEHOLDER_KEY_MARKERS = (
    "placeholder",
    "your-api-key",
    "sk-test",
    "sk-fake",
    "changeme",
    "offline-test",
)


class ArchCompareLiveGuardError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ArchCompareLiveGuardContext:
    repo_root: Path
    attempt_id: str
    live_requested: bool
    authorization: ArchCompareLiveAuthorizationManifest | None
    artifact_dir: Path | None
    transport_kind: str
    working_tree_clean: bool
    head_sha: str
    chat_api_key: str | None
    chat_base_url: str | None


def _git_head(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ArchCompareLiveGuardError("git_head_unavailable", proc.stderr.strip() or "git_head_failed")
    return proc.stdout.strip()


def _working_tree_clean(repo_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ArchCompareLiveGuardError("git_status_unavailable", proc.stderr.strip() or "git_status_failed")
    return proc.stdout.strip() == ""


def _resolve_chat_api_key() -> str:
    return (os.getenv("CHAT_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip()


def _resolve_chat_base_url() -> str:
    return (os.getenv("CHAT_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or "").strip()


def _credentials_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_KEY_MARKERS)


def _assert_live_credential_field(*, field_name: str, value: str) -> None:
    if not value.strip():
        raise ArchCompareLiveGuardError(f"{field_name}_missing", field_name)
    if _credentials_placeholder(value):
        raise ArchCompareLiveGuardError(f"{field_name}_placeholder", field_name)


def assert_fake_mode_allowed(*, live_requested: bool) -> None:
    if live_requested:
        raise ArchCompareLiveGuardError(
            "live_requires_authorization",
            "LIVE mode requires external authorization manifest",
        )


def assert_live_authorized(ctx: ArchCompareLiveGuardContext) -> None:
    if not ctx.live_requested:
        raise ArchCompareLiveGuardError("live_flag_missing", "--live required")
    if ctx.authorization is None:
        raise ArchCompareLiveGuardError("authorization_missing", "authorization manifest missing")
    manifest = ctx.authorization
    if not manifest.explicit_live:
        raise ArchCompareLiveGuardError("explicit_live_false", "explicit_live must be true")
    if manifest.attempt_id != ctx.attempt_id:
        raise ArchCompareLiveGuardError(
            "attempt_id_mismatch",
            f"requested={ctx.attempt_id} authorized={manifest.attempt_id}",
        )
    if manifest.client_id != CLIENT_ID:
        raise ArchCompareLiveGuardError("client_id_mismatch", manifest.client_id)
    if manifest.issued_for_measurement != "one_call_arch_compare_live_v1":
        raise ArchCompareLiveGuardError("measurement_mismatch", manifest.issued_for_measurement)
    if not _FULL_COMMIT_SHA_RE.match(manifest.expected_head):
        raise ArchCompareLiveGuardError("expected_head_invalid", manifest.expected_head)
    if ctx.head_sha != manifest.expected_head:
        raise ArchCompareLiveGuardError(
            "head_mismatch",
            f"head={ctx.head_sha} expected={manifest.expected_head}",
        )
    if not ctx.working_tree_clean:
        raise ArchCompareLiveGuardError("working_tree_dirty", "working tree must be clean for LIVE")
    if manifest.matrix_digest != FROZEN_MATRIX_DIGEST:
        raise ArchCompareLiveGuardError("matrix_digest_mismatch", manifest.matrix_digest)
    try:
        assert_frozen_matrix_unchanged()
    except RuntimeError as exc:
        raise ArchCompareLiveGuardError("matrix_guard_failed", str(exc)) from exc
    if frozen_matrix_digest() != manifest.matrix_digest:
        raise ArchCompareLiveGuardError("matrix_digest_runtime_mismatch", manifest.matrix_digest)
    if manifest.config_digest != frozen_config_digest():
        raise ArchCompareLiveGuardError("config_digest_mismatch", manifest.config_digest)
    try:
        assert_authorization_manifest_budget(
            max_provider_calls=manifest.max_provider_calls,
            includes_preflight=manifest.includes_capability_preflight,
        )
    except RuntimeError as exc:
        raise ArchCompareLiveGuardError("authorization_budget_invalid", str(exc)) from exc
    if manifest.includes_capability_preflight and manifest.max_provider_calls != TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        raise ArchCompareLiveGuardError(
            "authorization_budget_invalid",
            f"max={manifest.max_provider_calls} expected={TOTAL_AUTHORIZED_PROVIDER_BUDGET}",
        )
    if (
        not manifest.includes_capability_preflight
        and manifest.max_provider_calls == MEASUREMENT_PROVIDER_BUDGET
    ):
        raise ArchCompareLiveGuardError(
            "measurement_without_preflight_forbidden",
            "full attempt requires capability preflight authorization",
        )
    if manifest.max_provider_calls > TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        raise ArchCompareLiveGuardError(
            "authorization_budget_exceeded",
            f"max={manifest.max_provider_calls}",
        )
    allowed = set(manifest.allowed_model_ids)
    for config in all_arch_compare_configs():
        if config.provider_model_id_status == "unresolved":
            raise ArchCompareLiveGuardError(
                "plus_model_unresolved",
                f"config={config.config_id}",
            )
        if config.provider_model_id not in allowed:
            raise ArchCompareLiveGuardError(
                "model_not_allowed",
                f"config={config.config_id} model={config.provider_model_id}",
            )
    _assert_live_credential_field(
        field_name="chat_api_key",
        value=(ctx.chat_api_key or "").strip(),
    )
    _assert_live_credential_field(
        field_name="chat_base_url",
        value=(ctx.chat_base_url or "").strip(),
    )
    if ctx.transport_kind == "fake":
        raise ArchCompareLiveGuardError("fake_transport_in_live", "fake transport forbidden for LIVE artifacts")
    if ctx.artifact_dir is not None and ctx.artifact_dir.exists():
        raise ArchCompareLiveGuardError("artifact_dir_exists", str(ctx.artifact_dir))


def build_guard_context(
    *,
    repo_root: Path,
    attempt_id: str,
    live_requested: bool,
    authorization: ArchCompareLiveAuthorizationManifest | None,
    artifact_dir: Path | None,
    transport_kind: str = "fake",
    head_sha: str | None = None,
    working_tree_clean: bool | None = None,
    chat_api_key: str | None = None,
    chat_base_url: str | None = None,
) -> ArchCompareLiveGuardContext:
    return ArchCompareLiveGuardContext(
        repo_root=repo_root,
        attempt_id=attempt_id,
        live_requested=live_requested,
        authorization=authorization,
        artifact_dir=artifact_dir,
        transport_kind=transport_kind,
        working_tree_clean=(
            working_tree_clean if working_tree_clean is not None else _working_tree_clean(repo_root)
        ),
        head_sha=head_sha or _git_head(repo_root),
        chat_api_key=chat_api_key if chat_api_key is not None else _resolve_chat_api_key(),
        chat_base_url=chat_base_url if chat_base_url is not None else _resolve_chat_base_url(),
    )


def validate_run_mode(ctx: ArchCompareLiveGuardContext) -> str:
    if ctx.live_requested:
        assert_live_authorized(ctx)
        return "live"
    assert_fake_mode_allowed(live_requested=False)
    return "fake"


def assert_provider_budget(*, consumed: int, max_calls: int) -> None:
    if consumed > max_calls:
        raise ArchCompareLiveGuardError(
            "provider_budget_exceeded",
            f"consumed={consumed} max={max_calls}",
        )


def assert_seventy_first_call_blocked(*, call_index: int) -> None:
    if call_index > TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        raise ArchCompareLiveGuardError(
            "total_provider_budget_exceeded",
            f"call_index={call_index} max={TOTAL_AUTHORIZED_PROVIDER_BUDGET}",
        )


def budget_plan_summary() -> dict[str, int]:
    return {
        "capability_preflight_budget": CAPABILITY_PREFLIGHT_BUDGET,
        "measurement_budget": MEASUREMENT_PROVIDER_BUDGET,
        "total_authorized_budget": TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        "optional_cache_probe_budget": OPTIONAL_CACHE_PROBE_BUDGET,
    }


def assert_single_provider_call_per_turn(*, turn_calls: int) -> None:
    if turn_calls > 1:
        raise ArchCompareLiveGuardError(
            "provider_call_budget_per_turn",
            f"turn_calls={turn_calls}",
        )


def authorization_manifest_from_dict(payload: dict[str, Any]) -> ArchCompareLiveAuthorizationManifest:
    return ArchCompareLiveAuthorizationManifest.from_dict(payload)
