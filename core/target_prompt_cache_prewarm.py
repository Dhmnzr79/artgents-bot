"""Owner-controlled provider prompt-cache prewarm core (PERF-3, Option B).

Standalone helper for a manual CLI (``scripts/prewarm_prompt_cache.py``). It is NEVER imported
by ``app.py``, a request handler, a startup hook, or the pytest import graph of the running
application -- importing this module makes zero provider calls and creates zero files.

What it does (see docs/evidence/performance/FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md):

* ``compute_fingerprint`` / ``build_dry_run_report`` -- pure, offline. Reuse the production
  message builders (``build_composer_sdk_messages`` / ``build_verifier_sdk_messages``) verbatim,
  slice the assembled messages up to the end of the corpus (the static/dynamic boundary), and
  hash that actual assembled prefix. Composer and Verifier are separate cache identities.
* ``execute_prewarm_attempt`` -- the attempt/ledger machinery: one run-level marker keyed by
  ``attempt_id`` alone via ``O_EXCL`` (reuse of the same id is a hard error before any provider
  call), one shared ledger for both roles, hard budget of 2 with ``retry=0``, abort after the
  first provider error or observed-model mismatch, provider response content discarded (only
  anonymized usage/metadata recorded), usage logged via the existing ``log_llm_usage``. The
  provider transport is injected, so tests drive it with a fake and never touch the network.
* ``run_live`` -- the CLI-facing live path. It runs the model-pin and fingerprint preflight
  (both abort BEFORE any marker write or provider call) and then hits a hard activation gate:
  ``LIVE_ACTIVATION_AUTHORIZED`` is ``False`` and flipping it requires a SEPARATE owner LIVE/LLM
  GO (the second rollout gate). While blocked, ``run_live`` returns before constructing a real
  provider call or creating any marker -- so the shipping CLI performs zero live provider calls.

An attempt marker proves only the fact and final state of one owner-authorized run. It never
means the provider's cache is still warm -- only a live ``cached_tokens`` measurement does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from contracts.target_prompt_cache_attempt import (
    TargetPromptCacheAttempt,
    TargetPromptCacheAttemptStatus,
)
from contracts.target_prompt_cache_fingerprint import (
    TargetPromptCacheFingerprint,
    TargetPromptCacheRole,
)
from core.target_composer_executor import (
    TARGET_COMPOSER_SYSTEM_POLICY,
    TargetComposerInvocation,
)
from core.target_response_verifier import (
    TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
    TargetSemanticVerifierInvocation,
)
from core.target_runtime_client_context import (
    TargetRuntimeClientContext,
    load_target_runtime_client_context,
)
from core.target_runtime_llm_backends import (
    target_fullcontext_composer_model,
    target_fullcontext_verifier_model,
)
from core.target_runtime_llm_messages import (
    build_composer_sdk_messages,
    build_verifier_sdk_messages,
)
from logging_setup import get_logger, log_llm_usage, usage_dict_from_completion

logger = get_logger("target_prewarm")

_REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Version markers (sec 5). Bump manually on the change each marker's comment names. ---
PROMPT_TEMPLATE_VERSION = 1
"""Human-readable prompt/template version. Bump when policy/preamble wording changes."""
MESSAGE_SERIALIZATION_VERSION = 1
"""Message-list structure version (field order, message count, role list). Bump when the
assembly *code* changes without changing the resulting *text* -- the one class of change a
content hash alone cannot catch. Mirrors the BOT_EVENTS_SCHEMA_VERSION discipline."""

_ROLES: tuple[TargetPromptCacheRole, ...] = ("composer", "verifier")
_BUDGET = 2
_RETRY = 0

# Fixed, non-PII placeholders for the dynamic tail (rule 5): the warmed prefix ends at the
# corpus, so the tail's content is irrelevant and must never come from a real request.
_PLACEHOLDER_JSON = "{}"
_PLACEHOLDER_TEXT = ""

# Discarded-response prewarm output cap -- the answer text is thrown away, so keep it tiny.
_PREWARM_MAX_COMPLETION_TOKENS = 16

DEFAULT_LEDGER_ROOT = _REPO_ROOT / ".prewarm_ledger"

# HARD GATE. Live activation against the real provider requires a SEPARATE, explicit owner
# LIVE/LLM GO on top of the implementation GO (two-gate rollout, sec 8/sec 12). Flipping this
# is out of scope for the implementation phase and must not happen without that separate GO.
LIVE_ACTIVATION_AUTHORIZED = False

_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Live-outcome kinds (mapped to CLI exit codes by the script).
LIVE_OUTCOME_MODEL_MISMATCH = "preflight_model_mismatch"
LIVE_OUTCOME_FINGERPRINT_MISMATCH = "preflight_fingerprint_mismatch"
LIVE_OUTCOME_BLOCKED = "live_blocked"
LIVE_OUTCOME_EXECUTED = "executed"


class PrewarmError(RuntimeError):
    """Base class for prewarm CLI/core failures."""


class PrewarmAttemptIdError(PrewarmError):
    """attempt_id is missing, empty, or not a safe single-path-segment token."""


class PrewarmAttemptReuseError(PrewarmError):
    """The attempt_id has already been used -- its marker already exists (replay guard)."""


# --------------------------------------------------------------------------------------------
# Pure fingerprint / prefix computation (offline, zero provider calls)
# --------------------------------------------------------------------------------------------


def _role_messages(role: TargetPromptCacheRole, ctx: TargetRuntimeClientContext) -> list[dict[str, str]]:
    """Full SDK messages for a role, built by the production builder verbatim with fixed
    non-PII placeholders for the dynamic tail. Never a parallel assembly path."""

    corpus = ctx.cached_full_context.corpus_text
    if role == "composer":
        invocation = TargetComposerInvocation(
            system_policy=TARGET_COMPOSER_SYSTEM_POLICY,
            cached_full_context=corpus,
            response_directives_json=_PLACEHOLDER_JSON,
            primary_evidence_json=_PLACEHOLDER_JSON,
            user_message=_PLACEHOLDER_TEXT,
            governed_action_context_json=None,
        )
        return build_composer_sdk_messages(invocation)
    invocation = TargetSemanticVerifierInvocation(
        system_policy=TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
        cached_full_context=corpus,
        response_spec_json=_PLACEHOLDER_JSON,
        primary_evidence_json=_PLACEHOLDER_JSON,
        candidate_text=_PLACEHOLDER_TEXT,
    )
    return build_verifier_sdk_messages(invocation)


def _static_prefix_serialization(role: TargetPromptCacheRole, ctx: TargetRuntimeClientContext) -> str:
    """The actual assembled static prefix (system message + user content through the end of the
    corpus), serialized deterministically. Sliced from the real builder output at the corpus
    boundary -- never hand-assembled separately, so it is guaranteed identical to what a real
    call would send up to the dynamic tail."""

    messages = _role_messages(role, ctx)
    corpus = ctx.cached_full_context.corpus_text
    system_content = messages[0]["content"]
    user_content = messages[1]["content"]
    boundary = user_content.index(corpus) + len(corpus)
    static_user = user_content[:boundary]
    return json.dumps(
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": static_user},
        ],
        ensure_ascii=False,
    )


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_fingerprint(
    role: TargetPromptCacheRole,
    ctx: TargetRuntimeClientContext,
    model: str,
) -> TargetPromptCacheFingerprint:
    """Cache identity for one role's static prefix (sec 5). Descriptive/audit only -- never a
    lookup or lifecycle key."""

    static_prefix_hash = _sha256_hex(_static_prefix_serialization(role, ctx))
    corpus_sha256 = ctx.cached_full_context.sha256
    composite = _sha256_hex(
        "|".join(
            (
                ctx.client_id,
                role,
                model,
                static_prefix_hash,
                corpus_sha256,
                str(PROMPT_TEMPLATE_VERSION),
                str(MESSAGE_SERIALIZATION_VERSION),
            )
        )
    )
    return TargetPromptCacheFingerprint(
        client_id=ctx.client_id,
        role=role,
        model=model,
        static_prefix_hash=static_prefix_hash,
        corpus_sha256=corpus_sha256,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        message_serialization_version=MESSAGE_SERIALIZATION_VERSION,
        fingerprint=composite,
    )


def _configured_model(role: TargetPromptCacheRole) -> str:
    """Model resolved from env/config at attempt time, via the production accessors verbatim
    (no parallel model resolution)."""

    if role == "composer":
        return target_fullcontext_composer_model()
    return target_fullcontext_verifier_model()


def _estimate_tokens(text: str) -> int:
    """Rough character-based token estimate (~4 chars/token). Advisory only, never a budget."""

    return len(text) // 4


# --------------------------------------------------------------------------------------------
# Dry-run report (default action: zero provider calls, zero artifacts, safe metadata only)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DryRunRoleReport:
    role: TargetPromptCacheRole
    model: str
    static_prefix_hash: str
    corpus_sha256: str
    static_prefix_chars: int
    estimated_tokens: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DryRunReport:
    client_id: str
    roles: tuple[DryRunRoleReport, ...]
    budget: int
    retry: int


def build_dry_run_report(client_id: str) -> DryRunReport:
    """Load the real client pack, build the real Composer/Verifier messages, and compute the
    per-role fingerprint. Returns only anonymized scalar metadata -- never corpus text, a
    synthetic answer, contacts, SID/session, or any client-pack content."""

    ctx = load_target_runtime_client_context(client_id)
    roles: list[DryRunRoleReport] = []
    for role in _ROLES:
        model = _configured_model(role)
        fingerprint = compute_fingerprint(role, ctx, model)
        prefix = _static_prefix_serialization(role, ctx)
        roles.append(
            DryRunRoleReport(
                role=role,
                model=model,
                static_prefix_hash=fingerprint.static_prefix_hash,
                corpus_sha256=fingerprint.corpus_sha256,
                static_prefix_chars=len(prefix),
                estimated_tokens=_estimate_tokens(prefix),
                fingerprint=fingerprint.fingerprint,
            )
        )
    return DryRunReport(client_id=client_id, roles=tuple(roles), budget=_BUDGET, retry=_RETRY)


# --------------------------------------------------------------------------------------------
# Attempt / ledger machinery (transport injected; tests drive it with a fake provider)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrewarmRolePlan:
    role: TargetPromptCacheRole
    requested_model: str
    configured_model: str
    fingerprint: TargetPromptCacheFingerprint


@dataclass(frozen=True, slots=True)
class PrewarmAttemptRequest:
    attempt_id: str
    client_id: str
    roles: tuple[PrewarmRolePlan, ...]


def _validate_attempt_id(attempt_id: str) -> None:
    if not attempt_id or attempt_id in (".", "..") or not _ATTEMPT_ID_RE.match(attempt_id):
        raise PrewarmAttemptIdError(f"invalid attempt_id: {attempt_id!r}")


def _marker_path(ledger_root: Path, attempt_id: str) -> Path:
    return Path(ledger_root) / "attempts" / f"{attempt_id}.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role_fingerprint(request: PrewarmAttemptRequest, role: TargetPromptCacheRole) -> str:
    for plan in request.roles:
        if plan.role == role:
            return plan.fingerprint.fingerprint
    raise PrewarmError(f"role not planned: {role}")


def _ledger_payload(attempt: TargetPromptCacheAttempt, calls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "attempt": {
            "attempt_id": attempt.attempt_id,
            "client_id": attempt.client_id,
            "requested_model": attempt.requested_model,
            "configured_model": attempt.configured_model,
            "composer_fingerprint": attempt.composer_fingerprint,
            "verifier_fingerprint": attempt.verifier_fingerprint,
            "planned_roles": list(attempt.planned_roles),
            "budget": attempt.budget,
            "retry": attempt.retry,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "completed_at": attempt.completed_at,
            "calls_started": attempt.calls_started,
            "calls_completed": attempt.calls_completed,
        },
        "calls": calls,
    }


def _create_marker_exclusive(
    marker_path: Path,
    attempt: TargetPromptCacheAttempt,
    calls: list[dict[str, object]],
) -> None:
    """Create the one run-level marker via O_EXCL, keyed by attempt_id alone. If it already
    exists, that attempt_id is already consumed -- a hard reuse error BEFORE any provider call.
    There is deliberately no force/reclaim/delete path anywhere in this module."""

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_ledger_payload(attempt, calls), ensure_ascii=False, indent=2)
    try:
        fd = os.open(str(marker_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise PrewarmAttemptReuseError(f"attempt_id already used: {attempt.attempt_id!r}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _write_marker(
    marker_path: Path,
    attempt: TargetPromptCacheAttempt,
    calls: list[dict[str, object]],
) -> None:
    payload = json.dumps(_ledger_payload(attempt, calls), ensure_ascii=False, indent=2)
    marker_path.write_text(payload, encoding="utf-8")


def execute_prewarm_attempt(
    *,
    request: PrewarmAttemptRequest,
    provider_call,
    ledger_root: Path = DEFAULT_LEDGER_ROOT,
) -> TargetPromptCacheAttempt:
    """Run one owner-authorized attempt against ``provider_call`` (injected transport).

    ``provider_call(role, model, messages) -> response`` -- the response is inspected ONLY for
    ``.model`` (observed provenance) and ``.usage`` (anonymized metadata). Its answer content is
    never read, stored, shown, or cached.

    Hard invariants: one shared ledger per attempt; budget 2 (<=1 Composer + <=1 Verifier);
    retry 0 (no call is ever repeated); abort on the first provider error or observed-model
    mismatch (remaining roles never called); the marker is consumed for good in whatever state
    it was last written (a crash leaves a non-completed marker, never auto-resumed).
    """

    _validate_attempt_id(request.attempt_id)
    ctx = load_target_runtime_client_context(request.client_id)
    marker_path = _marker_path(ledger_root, request.attempt_id)

    attempt = TargetPromptCacheAttempt(
        attempt_id=request.attempt_id,
        client_id=request.client_id,
        requested_model=request.roles[0].requested_model,
        configured_model=request.roles[0].configured_model,
        composer_fingerprint=_role_fingerprint(request, "composer"),
        verifier_fingerprint=_role_fingerprint(request, "verifier"),
        planned_roles=tuple(plan.role for plan in request.roles),
        status="started",
        started_at=_utc_now_iso(),
        completed_at=None,
        calls_started=0,
        calls_completed=0,
    )
    calls: list[dict[str, object]] = []
    # Create-before-first-call. Reuse of attempt_id fails here, before any provider call.
    _create_marker_exclusive(marker_path, attempt, calls)

    def _finalize(status: TargetPromptCacheAttemptStatus) -> TargetPromptCacheAttempt:
        nonlocal attempt
        attempt = replace(attempt, status=status, completed_at=_utc_now_iso())
        _write_marker(marker_path, attempt, calls)
        return attempt

    for plan in request.roles:
        if attempt.calls_started >= attempt.budget:
            break
        messages = _role_messages(plan.role, ctx)
        record: dict[str, object] = {
            "role": plan.role,
            "requested_model": plan.requested_model,
            "configured_model": plan.configured_model,
            "observed_model": None,
            "status": "started",
        }
        # Increment + persist BEFORE the call, so a crash mid-call is visibly consumed.
        attempt = replace(attempt, calls_started=attempt.calls_started + 1)
        _write_marker(marker_path, attempt, calls + [record])

        started = time.perf_counter()
        try:
            response = provider_call(plan.role, plan.configured_model, messages)
        except Exception as exc:  # noqa: BLE001 -- record class/code only, never prompt/response
            record["status"] = "failed"
            record["error_class"] = type(exc).__name__
            code = getattr(exc, "code", None)
            record["error_code"] = code if isinstance(code, (str, int)) else None
            record["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            calls.append(record)
            return _finalize("failed")

        # Response content is discarded: only model provenance + anonymized usage are read.
        record["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        observed_model = getattr(response, "model", None)
        record["observed_model"] = observed_model
        usage = usage_dict_from_completion(response) or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"):
            if key in usage and usage[key] is not None:
                record[key] = usage[key]
        # Reuse the existing usage logger -- no second usage-parsing implementation.
        log_llm_usage(
            logger,
            response,
            call_type=f"target_fullcontext_prewarm_{plan.role}",
            model=plan.configured_model,
        )

        if observed_model != plan.configured_model:
            record["status"] = "model_mismatch"
            calls.append(record)
            return _finalize("aborted")

        record["status"] = "completed"
        calls.append(record)
        attempt = replace(attempt, calls_completed=attempt.calls_completed + 1)
        _write_marker(marker_path, attempt, calls)

    return _finalize("completed")


def live_provider_call(role: TargetPromptCacheRole, model: str, messages: list[dict[str, str]]):
    """Real provider transport for the future authorized live path (unreached in Phase 2).

    Discards nothing here beyond what the caller ignores: it returns the raw response; the
    caller reads only ``.model``/``.usage`` and never the answer content. Only invoked once
    ``LIVE_ACTIVATION_AUTHORIZED`` is flipped under a separate owner LIVE/LLM GO."""

    from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create

    return chat_completions_create(
        model=model,
        temperature=0,
        max_completion_tokens=_PREWARM_MAX_COMPLETION_TOKENS,
        response_format={"type": "json_object"},
        timeout=LLM_REQUEST_TIMEOUT_SEC,
        messages=messages,
    )


# --------------------------------------------------------------------------------------------
# Live CLI path -- preflight (aborts before marker/call) then the hard activation gate
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveRoleExpectation:
    role: TargetPromptCacheRole
    expected_model: str
    expected_fingerprint: str


@dataclass(frozen=True, slots=True)
class LiveRequest:
    attempt_id: str
    client_id: str
    expectations: tuple[LiveRoleExpectation, ...]


@dataclass(frozen=True, slots=True)
class LiveOutcome:
    kind: str
    role: TargetPromptCacheRole | None = None
    expected: str | None = None
    actual: str | None = None
    attempt: TargetPromptCacheAttempt | None = None


def run_live(request: LiveRequest, *, ledger_root: Path = DEFAULT_LEDGER_ROOT) -> LiveOutcome:
    """CLI live entry. Order is safety-critical: validate id, then the model-pin and fingerprint
    preflight (both abort BEFORE any marker write or provider call), then the hard activation
    gate. While ``LIVE_ACTIVATION_AUTHORIZED`` is False this returns ``LIVE_OUTCOME_BLOCKED``
    before constructing a real provider call or creating a marker."""

    _validate_attempt_id(request.attempt_id)
    ctx = load_target_runtime_client_context(request.client_id)

    plans: list[PrewarmRolePlan] = []
    for expectation in request.expectations:
        configured = _configured_model(expectation.role)
        # A9R2c model-pin defense: the operator states the model they expect to be configured;
        # a stale/mismatched configured model aborts here, before marker/provider call.
        if expectation.expected_model != configured:
            return LiveOutcome(
                kind=LIVE_OUTCOME_MODEL_MISMATCH,
                role=expectation.role,
                expected=expectation.expected_model,
                actual=configured,
            )
        fingerprint = compute_fingerprint(expectation.role, ctx, configured)
        if expectation.expected_fingerprint != fingerprint.fingerprint:
            return LiveOutcome(
                kind=LIVE_OUTCOME_FINGERPRINT_MISMATCH,
                role=expectation.role,
                expected=expectation.expected_fingerprint,
                actual=fingerprint.fingerprint,
            )
        plans.append(
            PrewarmRolePlan(
                role=expectation.role,
                requested_model=expectation.expected_model,
                configured_model=configured,
                fingerprint=fingerprint,
            )
        )

    if not LIVE_ACTIVATION_AUTHORIZED:
        # Blocked BEFORE any marker write or provider call. Unblocking is a separate owner
        # LIVE/LLM GO (two-gate rollout) -- not part of the implementation phase.
        return LiveOutcome(kind=LIVE_OUTCOME_BLOCKED)

    # ---- Beyond here requires a separate owner LIVE/LLM GO; unreached in Phase 2. ----
    attempt = execute_prewarm_attempt(
        request=PrewarmAttemptRequest(
            attempt_id=request.attempt_id,
            client_id=request.client_id,
            roles=tuple(plans),
        ),
        provider_call=live_provider_call,
        ledger_root=ledger_root,
    )
    return LiveOutcome(kind=LIVE_OUTCOME_EXECUTED, attempt=attempt)
