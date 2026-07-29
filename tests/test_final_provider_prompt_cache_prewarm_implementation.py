"""Implementation acceptance matrix for FINAL_PROVIDER_PROMPT_CACHE_PREWARM / PERF-3.

Covers the 32-scenario matrix (seam audit sec 14) with a FAKE injected provider only -- no
network, no real provider call, no repo artifact. The attempt/ledger machinery is exercised in
pytest ``tmp_path`` (ephemeral), the dry-run/blocked-live CLI via subprocess. The real live path
is never invoked (it is hard-blocked behind ``LIVE_ACTIVATION_AUTHORIZED``).
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from contracts.target_prompt_cache_attempt import TargetPromptCacheAttempt
from contracts.target_prompt_cache_fingerprint import TargetPromptCacheFingerprint
from core.target_runtime_client_context import load_target_runtime_client_context
from core.target_runtime_llm_messages import build_composer_sdk_messages
from core.target_composer_executor import (
    TARGET_COMPOSER_SYSTEM_POLICY,
    TargetComposerInvocation,
)
from core import target_prompt_cache_prewarm as prewarm
from core.target_prompt_cache_prewarm import (
    LIVE_OUTCOME_BLOCKED,
    LIVE_OUTCOME_FINGERPRINT_MISMATCH,
    LIVE_OUTCOME_MODEL_MISMATCH,
    LiveRequest,
    LiveRoleExpectation,
    PrewarmAttemptIdError,
    PrewarmAttemptRequest,
    PrewarmAttemptReuseError,
    PrewarmRolePlan,
    build_dry_run_report,
    compute_fingerprint,
    execute_prewarm_attempt,
    run_live,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = _REPO_ROOT / "scripts" / "prewarm_prompt_cache.py"
_MODEL = "qwen3.7-plus"


# --------------------------------------------------------------------------------------------
# Fakes (no network). The response's answer content is booby-trapped: reading it fails the test.
# --------------------------------------------------------------------------------------------


class _FakeDetails:
    def __init__(self, cached_tokens: int) -> None:
        self.cached_tokens = cached_tokens


class _FakeUsage:
    def __init__(self, cached_tokens: int) -> None:
        self.prompt_tokens = 26500
        self.completion_tokens = 4
        self.total_tokens = 26504
        self.prompt_tokens_details = _FakeDetails(cached_tokens)


class _FakeResponse:
    def __init__(self, model: str, cached_tokens: int = 26490) -> None:
        self.model = model
        self.usage = _FakeUsage(cached_tokens)

    @property
    def choices(self):  # pragma: no cover - accessing this is a test failure
        raise AssertionError("prewarm must discard response content, never read .choices")


def _success_provider(log: list[tuple[str, str]]):
    def call(role, model, messages):
        log.append((role, model))
        return _FakeResponse(model=model)

    return call


def _mismatch_provider(log: list[tuple[str, str]]):
    def call(role, model, messages):
        log.append((role, model))
        return _FakeResponse(model=model + "-DRIFT")

    return call


def _composer_failure_provider(log: list[tuple[str, str]]):
    def call(role, model, messages):
        log.append((role, model))
        if role == "composer":
            raise RuntimeError("boom-composer")
        return _FakeResponse(model=model)

    return call


def _demo_request(attempt_id: str) -> PrewarmAttemptRequest:
    ctx = load_target_runtime_client_context("demo")
    plans = tuple(
        PrewarmRolePlan(
            role=role,
            requested_model=_MODEL,
            configured_model=_MODEL,
            fingerprint=compute_fingerprint(role, ctx, _MODEL),
        )
        for role in ("composer", "verifier")
    )
    return PrewarmAttemptRequest(attempt_id=attempt_id, client_id="demo", roles=plans)


class _FakeCorpus:
    def __init__(self, corpus_text: str) -> None:
        self.corpus_text = corpus_text
        self.sha256 = "sha-" + str(abs(hash(corpus_text)))


class _FakeCtx:
    def __init__(self, client_id: str, corpus_text: str) -> None:
        self.client_id = client_id
        self.cached_full_context = _FakeCorpus(corpus_text)


# --------------------------------------------------------------------------------------------
# Contract invariants
# --------------------------------------------------------------------------------------------


def test_attempt_budget_and_retry_are_hard_literals() -> None:
    hints = typing.get_type_hints(TargetPromptCacheAttempt, include_extras=True)
    assert typing.get_args(hints["budget"]) == (2,)
    assert typing.get_args(hints["retry"]) == (0,)
    fields = TargetPromptCacheAttempt.__dataclass_fields__
    assert fields["budget"].default == 2
    assert fields["retry"].default == 0


def test_planned_roles_use_typed_role_literal() -> None:
    hints = typing.get_type_hints(TargetPromptCacheAttempt)
    # tuple[TargetPromptCacheRole, ...] -> role literal is composer/verifier only
    role_type = typing.get_args(hints["planned_roles"])[0]
    assert set(typing.get_args(role_type)) == {"composer", "verifier"}


def test_fingerprint_contract_is_cache_identity_shape() -> None:
    names = set(TargetPromptCacheFingerprint.__dataclass_fields__)
    assert names == {
        "client_id",
        "role",
        "model",
        "static_prefix_hash",
        "corpus_sha256",
        "prompt_template_version",
        "message_serialization_version",
        "fingerprint",
    }


# --------------------------------------------------------------------------------------------
# Fingerprint / prefix identity (rows 22-25, 31; GO items 3-6)
# --------------------------------------------------------------------------------------------


def test_offline_static_prefix_matches_real_builder_up_to_boundary() -> None:
    """The CLI's static prefix equals what a real Composer call builds, up to the dynamic
    boundary -- independent of the dynamic tail (message-content identity, not wire-byte)."""

    ctx = load_target_runtime_client_context("demo")
    corpus = ctx.cached_full_context.corpus_text

    real_call = build_composer_sdk_messages(
        TargetComposerInvocation(
            system_policy=TARGET_COMPOSER_SYSTEM_POLICY,
            cached_full_context=corpus,
            response_directives_json='{"real":"directives"}',
            primary_evidence_json='{"real":"evidence"}',
            user_message="a real patient question",
            governed_action_context_json='{"real":"action"}',
        )
    )
    real_user = real_call[1]["content"]
    real_prefix_user = real_user[: real_user.index(corpus) + len(corpus)]

    placeholder = prewarm._role_messages("composer", ctx)
    ph_user = placeholder[1]["content"]
    ph_prefix_user = ph_user[: ph_user.index(corpus) + len(corpus)]

    assert real_call[0]["content"] == placeholder[0]["content"]  # system identical
    assert real_prefix_user == ph_prefix_user  # user prefix identical up to corpus end


def test_composer_and_verifier_fingerprints_differ() -> None:
    ctx = load_target_runtime_client_context("demo")
    composer = compute_fingerprint("composer", ctx, _MODEL)
    verifier = compute_fingerprint("verifier", ctx, _MODEL)
    assert composer.fingerprint != verifier.fingerprint
    assert composer.static_prefix_hash != verifier.static_prefix_hash
    assert composer.corpus_sha256 == verifier.corpus_sha256  # shared corpus


def test_fingerprint_stable_for_same_inputs() -> None:
    ctx = load_target_runtime_client_context("demo")
    a = compute_fingerprint("composer", ctx, _MODEL)
    b = compute_fingerprint("composer", ctx, _MODEL)
    assert a == b


def test_fingerprint_changes_on_client_model_corpus_and_version() -> None:
    base = compute_fingerprint("composer", _FakeCtx("demo", "CORPUS-A"), _MODEL)

    assert compute_fingerprint("composer", _FakeCtx("other", "CORPUS-A"), _MODEL).fingerprint != base.fingerprint
    assert compute_fingerprint("composer", _FakeCtx("demo", "CORPUS-A"), "gpt-4o").fingerprint != base.fingerprint
    assert compute_fingerprint("composer", _FakeCtx("demo", "CORPUS-B"), _MODEL).fingerprint != base.fingerprint
    # role change is a namespace change
    assert compute_fingerprint("verifier", _FakeCtx("demo", "CORPUS-A"), _MODEL).fingerprint != base.fingerprint


def test_fingerprint_changes_on_template_or_serialization_version_bump(monkeypatch) -> None:
    ctx = _FakeCtx("demo", "CORPUS-A")
    base = compute_fingerprint("composer", ctx, _MODEL).fingerprint
    monkeypatch.setattr(prewarm, "PROMPT_TEMPLATE_VERSION", prewarm.PROMPT_TEMPLATE_VERSION + 1)
    assert compute_fingerprint("composer", ctx, _MODEL).fingerprint != base
    monkeypatch.setattr(prewarm, "PROMPT_TEMPLATE_VERSION", prewarm.PROMPT_TEMPLATE_VERSION)  # restore-ish
    monkeypatch.setattr(
        prewarm, "MESSAGE_SERIALIZATION_VERSION", prewarm.MESSAGE_SERIALIZATION_VERSION + 1
    )
    assert compute_fingerprint("composer", ctx, _MODEL).fingerprint != base


# --------------------------------------------------------------------------------------------
# Dry-run (rows 2-3; GO items 1, 19)
# --------------------------------------------------------------------------------------------


def test_dry_run_report_is_safe_metadata_only() -> None:
    report = build_dry_run_report("demo")
    assert report.budget == 2 and report.retry == 0
    assert tuple(r.role for r in report.roles) == ("composer", "verifier")
    blob = json.dumps([dataclasses.asdict(r) for r in report.roles])
    # no corpus content leaks into the report
    ctx = load_target_runtime_client_context("demo")
    corpus_sample = ctx.cached_full_context.corpus_text[:200]
    assert corpus_sample not in blob
    assert "BEGIN DOC" not in blob


def test_dry_run_cli_zero_calls_zero_artifacts(tmp_path) -> None:
    result = _run_cli(["--client-id", "demo"])
    assert result.returncode == 0
    assert "provider_calls=0 markers=0" in result.stdout
    assert "BEGIN DOC" not in result.stdout
    assert "CACHED_FULL_CONTEXT" not in result.stdout
    assert not (_REPO_ROOT / ".prewarm_ledger").exists()


# --------------------------------------------------------------------------------------------
# Attempt / ledger machinery via fake provider (rows 8-21; GO items 7-18, 20)
# --------------------------------------------------------------------------------------------


def _attempts_dir(ledger_root: Path) -> Path:
    return ledger_root / "attempts"


def test_marker_created_via_oexcl_keyed_by_attempt_id_alone(tmp_path) -> None:
    log: list = []
    attempt = execute_prewarm_attempt(
        request=_demo_request("2026-07-29-demo-01"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    marker = _attempts_dir(tmp_path) / "2026-07-29-demo-01.json"
    assert marker.is_file()
    assert attempt.status == "completed"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    # key is attempt_id alone; fingerprint is present only as descriptive data inside
    assert marker.name == "2026-07-29-demo-01.json"
    assert attempt.composer_fingerprint not in marker.name
    assert payload["attempt"]["composer_fingerprint"]  # recorded for audit
    assert payload["attempt"]["verifier_fingerprint"]


def test_marker_records_all_required_fields(tmp_path) -> None:
    log: list = []
    execute_prewarm_attempt(
        request=_demo_request("attempt-fields"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    payload = json.loads((_attempts_dir(tmp_path) / "attempt-fields.json").read_text(encoding="utf-8"))
    a = payload["attempt"]
    for field in (
        "attempt_id",
        "client_id",
        "requested_model",
        "configured_model",
        "composer_fingerprint",
        "verifier_fingerprint",
        "planned_roles",
        "budget",
        "retry",
        "status",
        "started_at",
        "completed_at",
        "calls_started",
        "calls_completed",
    ):
        assert field in a, field
    assert a["budget"] == 2 and a["retry"] == 0


def test_one_shared_ledger_holds_both_roles(tmp_path) -> None:
    log: list = []
    execute_prewarm_attempt(
        request=_demo_request("shared-ledger"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    markers = list(_attempts_dir(tmp_path).glob("*.json"))
    assert len(markers) == 1  # one shared file, not two per-role files
    payload = json.loads(markers[0].read_text(encoding="utf-8"))
    roles = [c["role"] for c in payload["calls"]]
    assert roles == ["composer", "verifier"]


def test_budget_two_and_retry_zero(tmp_path) -> None:
    log: list = []
    attempt = execute_prewarm_attempt(
        request=_demo_request("budget"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    assert len(log) == 2  # exactly one Composer + one Verifier, never more
    assert attempt.calls_started == 2 and attempt.calls_completed == 2
    # retry=0: each role called exactly once
    assert [r for r, _ in log] == ["composer", "verifier"]


def test_composer_failure_aborts_before_verifier(tmp_path) -> None:
    log: list = []
    attempt = execute_prewarm_attempt(
        request=_demo_request("composer-fail"),
        provider_call=_composer_failure_provider(log),
        ledger_root=tmp_path,
    )
    assert attempt.status == "failed"
    assert log == [("composer", _MODEL)]  # verifier never called
    payload = json.loads((_attempts_dir(tmp_path) / "composer-fail.json").read_text(encoding="utf-8"))
    assert payload["calls"][0]["status"] == "failed"
    assert payload["calls"][0]["error_class"] == "RuntimeError"
    # no prompt/response text stored
    assert "boom-composer" not in json.dumps(payload)


def test_model_mismatch_aborts_after_first_call(tmp_path) -> None:
    log: list = []
    attempt = execute_prewarm_attempt(
        request=_demo_request("model-drift"),
        provider_call=_mismatch_provider(log),
        ledger_root=tmp_path,
    )
    assert attempt.status == "aborted"
    assert len(log) == 1  # abort after the first call; verifier never reached
    payload = json.loads((_attempts_dir(tmp_path) / "model-drift.json").read_text(encoding="utf-8"))
    assert payload["calls"][0]["status"] == "model_mismatch"
    assert payload["calls"][0]["observed_model"] == _MODEL + "-DRIFT"


def test_duplicate_attempt_id_blocked_before_any_call(tmp_path) -> None:
    first_log: list = []
    execute_prewarm_attempt(
        request=_demo_request("dup"),
        provider_call=_success_provider(first_log),
        ledger_root=tmp_path,
    )
    assert len(first_log) == 2
    second_log: list = []
    with pytest.raises(PrewarmAttemptReuseError):
        execute_prewarm_attempt(
            request=_demo_request("dup"),
            provider_call=_success_provider(second_log),
            ledger_root=tmp_path,
        )
    assert second_log == []  # reuse fails at marker creation, before any provider call


def test_new_attempt_id_for_unchanged_fingerprint_allowed(tmp_path) -> None:
    """The core fix: an unchanged fingerprint never blocks a fresh, differently-attempt_id'd run."""

    log_a: list = []
    a = execute_prewarm_attempt(
        request=_demo_request("rewarm-a"),
        provider_call=_success_provider(log_a),
        ledger_root=tmp_path,
    )
    log_b: list = []
    b = execute_prewarm_attempt(
        request=_demo_request("rewarm-b"),  # same fingerprints, new attempt_id
        provider_call=_success_provider(log_b),
        ledger_root=tmp_path,
    )
    assert a.composer_fingerprint == b.composer_fingerprint  # unchanged fingerprint
    assert a.status == "completed" and b.status == "completed"
    assert len(list(_attempts_dir(tmp_path).glob("*.json"))) == 2


def test_partial_attempt_consumed_no_resume(tmp_path) -> None:
    log: list = []
    execute_prewarm_attempt(
        request=_demo_request("partial"),
        provider_call=_composer_failure_provider(log),
        ledger_root=tmp_path,
    )
    payload = json.loads((_attempts_dir(tmp_path) / "partial.json").read_text(encoding="utf-8"))
    assert payload["attempt"]["status"] != "completed"  # left non-completed forever
    # re-running the same attempt_id is refused (consumed), not resumed
    resume_log: list = []
    with pytest.raises(PrewarmAttemptReuseError):
        execute_prewarm_attempt(
            request=_demo_request("partial"),
            provider_call=_success_provider(resume_log),
            ledger_root=tmp_path,
        )
    assert resume_log == []


def test_response_content_discarded_and_usage_recorded(tmp_path) -> None:
    log: list = []
    execute_prewarm_attempt(
        request=_demo_request("usage"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    # If the machinery had read response.choices, the property would have raised (test fails).
    payload = json.loads((_attempts_dir(tmp_path) / "usage.json").read_text(encoding="utf-8"))
    call = payload["calls"][0]
    assert call["cached_tokens"] == 26490
    assert call["prompt_tokens"] == 26500
    assert "duration_ms" in call


def test_marker_content_has_no_corpus_or_pii(tmp_path) -> None:
    log: list = []
    execute_prewarm_attempt(
        request=_demo_request("no-corpus"),
        provider_call=_success_provider(log),
        ledger_root=tmp_path,
    )
    text = (_attempts_dir(tmp_path) / "no-corpus.json").read_text(encoding="utf-8")
    ctx = load_target_runtime_client_context("demo")
    assert ctx.cached_full_context.corpus_text[:200] not in text
    assert "BEGIN DOC" not in text
    assert "CACHED_FULL_CONTEXT" not in text


def test_bad_attempt_id_rejected(tmp_path) -> None:
    for bad in ("", ".", "..", "a/b", "../escape", "x" * 200):
        with pytest.raises(PrewarmAttemptIdError):
            execute_prewarm_attempt(
                request=_demo_request(bad),
                provider_call=_success_provider([]),
                ledger_root=tmp_path,
            )


# --------------------------------------------------------------------------------------------
# Live gate: blocked / preflight abort before marker or call (rows 4-7; GO items 2, 15)
# --------------------------------------------------------------------------------------------


def _live_request(attempt_id: str, *, composer_model: str, expected_fp_composer: str, expected_fp_verifier: str) -> LiveRequest:
    return LiveRequest(
        attempt_id=attempt_id,
        client_id="demo",
        expectations=(
            LiveRoleExpectation("composer", composer_model, expected_fp_composer),
            LiveRoleExpectation("verifier", _MODEL, expected_fp_verifier),
        ),
    )


def test_live_blocked_makes_zero_calls_zero_markers(tmp_path) -> None:
    ctx = load_target_runtime_client_context("demo")
    fp_c = compute_fingerprint("composer", ctx, _MODEL).fingerprint
    fp_v = compute_fingerprint("verifier", ctx, _MODEL).fingerprint
    outcome = run_live(
        _live_request("live-ok", composer_model=_MODEL, expected_fp_composer=fp_c, expected_fp_verifier=fp_v),
        ledger_root=tmp_path,
    )
    assert outcome.kind == LIVE_OUTCOME_BLOCKED
    assert not _attempts_dir(tmp_path).exists()  # no marker created at all


def test_live_stale_model_aborts_before_marker(tmp_path) -> None:
    outcome = run_live(
        _live_request("live-stale", composer_model="gpt-4o", expected_fp_composer="x", expected_fp_verifier="y"),
        ledger_root=tmp_path,
    )
    assert outcome.kind == LIVE_OUTCOME_MODEL_MISMATCH
    assert outcome.role == "composer"
    assert not _attempts_dir(tmp_path).exists()


def test_live_fingerprint_mismatch_aborts_before_marker(tmp_path) -> None:
    outcome = run_live(
        _live_request("live-fp", composer_model=_MODEL, expected_fp_composer="deadbeef", expected_fp_verifier="cafe"),
        ledger_root=tmp_path,
    )
    assert outcome.kind == LIVE_OUTCOME_FINGERPRINT_MISMATCH
    assert not _attempts_dir(tmp_path).exists()


def test_live_activation_is_hard_disabled() -> None:
    assert prewarm.LIVE_ACTIVATION_AUTHORIZED is False


# --------------------------------------------------------------------------------------------
# CLI subprocess (rows 4-6; dry-run + blocked-live)
# --------------------------------------------------------------------------------------------


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_CLI), *args],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_blocked_live_exit_code_and_no_artifacts() -> None:
    report = build_dry_run_report("demo")
    fp = {r.role: r.fingerprint for r in report.roles}
    result = _run_cli(
        [
            "--client-id",
            "demo",
            "--live",
            "--attempt-id",
            "subproc-blocked-01",
            "--expected-composer-model",
            _MODEL,
            "--expected-verifier-model",
            _MODEL,
            "--expected-composer-fingerprint",
            fp["composer"],
            "--expected-verifier-fingerprint",
            fp["verifier"],
        ]
    )
    assert result.returncode == 4
    assert "BLOCKED" in result.stderr
    assert "0 provider calls, 0 markers" in result.stderr
    assert not (_REPO_ROOT / ".prewarm_ledger").exists()


def test_cli_live_missing_attempt_id_is_usage_error() -> None:
    result = _run_cli(
        [
            "--client-id",
            "demo",
            "--live",
            "--expected-composer-model",
            _MODEL,
            "--expected-verifier-model",
            _MODEL,
            "--expected-composer-fingerprint",
            "x",
            "--expected-verifier-fingerprint",
            "y",
        ]
    )
    assert result.returncode == 2
    assert "--attempt-id" in result.stderr
    assert not (_REPO_ROOT / ".prewarm_ledger").exists()


def test_cli_unknown_client_rejected() -> None:
    result = _run_cli(["--client-id", "not-a-client"])
    assert result.returncode == 2
    assert "ALLOWED_CLIENTS" in result.stderr


# --------------------------------------------------------------------------------------------
# Isolation from runtime (rows 29-30; GO items 21-22): no force/reclaim/delete, no wiring
# --------------------------------------------------------------------------------------------


def test_no_force_reclaim_or_delete_mechanism() -> None:
    core_src = (_REPO_ROOT / "core" / "target_prompt_cache_prewarm.py").read_text(encoding="utf-8")
    cli_src = (_REPO_ROOT / "scripts" / "prewarm_prompt_cache.py").read_text(encoding="utf-8")
    # No filesystem-removal mechanism and no --force reopen flag anywhere in the CLI/core.
    for banned in ("os.remove", "os.unlink", "rmtree", "shutil.rmtree", '"--force"', "'--force'"):
        assert banned not in core_src, banned
        assert banned not in cli_src, banned


def test_usage_logging_reuses_existing_logger() -> None:
    core_src = (_REPO_ROOT / "core" / "target_prompt_cache_prewarm.py").read_text(encoding="utf-8")
    assert "from logging_setup import" in core_src
    assert "log_llm_usage" in core_src
    # no second usage logger defined here
    assert "def log_llm_usage" not in core_src
    assert "def usage_dict_from_completion" not in core_src


def test_prewarm_never_wired_into_runtime() -> None:
    """No app/startup/orchestration/runtime-turn file may import the prewarm core -- only the
    standalone CLI and this test suite reference it."""

    offenders: list[str] = []
    allowed = {
        _REPO_ROOT / "scripts" / "prewarm_prompt_cache.py",
        _REPO_ROOT / "core" / "target_prompt_cache_prewarm.py",
    }
    for path in _REPO_ROOT.rglob("*.py"):
        # Tests may reference the module freely (governance allowlist assertions, this suite).
        if path in allowed or "tests" in path.parts or ".prewarm_ledger" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "target_prompt_cache_prewarm" in text:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert offenders == [], offenders


def test_app_and_startup_untouched_by_prewarm() -> None:
    for rel in ("app.py", "core/startup_check.py"):
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "prewarm" not in text.lower()
