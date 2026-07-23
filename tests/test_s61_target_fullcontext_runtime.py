from __future__ import annotations

import ast
import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.target_medical_boundary import TargetMedicalBoundaryResult
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.target_composer_executor import TargetComposerInvocation
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
)
from core.target_runtime_client_context import (
    clear_target_runtime_client_context_cache,
    load_target_runtime_client_context,
)
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.target_runtime_turn_frame_bridge import (
    TargetRuntimeTurnFrameError,
    load_runtime_turn_frame,
)
from core.target_runtime_widget import materialize_target_error_payload
from core.target_runtime_session import read_target_runtime_session
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.turn_frame_shadow import (
    SHADOW_STATUS_NOT_AVAILABLE,
    SHADOW_STATUS_OK,
    get_turn_frame_shadow_snapshot,
    get_turn_frame_shadow_status,
)
from orchestration.target_fullcontext_turn import orchestrate_target_fullcontext_turn
from tests.s59_semantic_policy_backend import S59SemanticPolicyBackend
from tests.test_target_boundary_enforced_fullcontext_response import (
    PAIN_GROUNDED_TEXT,
    PRICE_TEXT,
    PERSONAL_MEDICAL_REJECT_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _boundary,
    _frame,
)

DEMO_ROOT = Path("clients/demo")


@dataclass
class BackendPayload:
    decision: str
    confidence: float


class RecordingBoundaryBackend:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.invocations: list[object] = []

    def classify(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        return self.payload


def _issue(kind: str, span: str) -> TargetSemanticIssue:
    return TargetSemanticIssue(kind=kind, offending_span=span)  # type: ignore[arg-type]


def _turn_frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def _install_turn_frame(frame) -> None:
    request.ctx["turn_frame_shadow"] = frame.model_dump()
    request.ctx["turn_frame_shadow_status"] = SHADOW_STATUS_OK


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


@pytest.fixture(autouse=True)
def _clear_target_cache():
    clear_target_runtime_client_context_cache()
    yield
    clear_target_runtime_client_context_cache()


def test_default_flag_off_in_config() -> None:
    import config

    assert config.TARGET_FULLCONTEXT_DEV is False


def test_flag_off_uses_legacy_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", False)
    legacy = MagicMock(
        return_value=AskOrchestrationResult(
            kind="service_reply",
            q="q",
            sid="sid",
            client_id="demo",
            service_payload={"answer": "legacy"},
            service_route="legacy",
        )
    )
    target = MagicMock()
    monkeypatch.setattr(app_module, "orchestrate_routing_after_resolver", legacy)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    monkeypatch.setattr(
        app_module,
        "run_pre_resolver_turn",
        lambda *a, **k: MagicMock(q="q", sid="sid", client_id="demo", st={}, data={}),
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: MagicMock(intent="content", decision=None, scope_topic_candidate=None, resolver_bypassed_env=False),
    )
    result = app_module._orchestrate_ask_turn({"q": "test", "sid": "sid"})
    legacy.assert_called_once()
    target.assert_not_called()
    assert result.service_route == "legacy"


def test_flag_on_uses_target_orchestration_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", True)
    legacy = MagicMock(side_effect=AssertionError("legacy must not run"))
    target = MagicMock(
        return_value=AskOrchestrationResult(
            kind="service_reply",
            q="q",
            sid="sid",
            client_id="demo",
            service_payload={"answer": "target"},
            service_route="target_fullcontext_materialized",
        )
    )
    monkeypatch.setattr(app_module, "orchestrate_routing_after_resolver", legacy)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    monkeypatch.setattr(
        app_module,
        "run_pre_resolver_turn",
        lambda *a, **k: MagicMock(q="q", sid="sid", client_id="demo", st={}, data={}),
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: MagicMock(intent="content", decision=None, scope_topic_candidate=None, resolver_bypassed_env=False),
    )
    result = app_module._orchestrate_ask_turn({"q": "test", "sid": "sid"})
    target.assert_called_once()
    legacy.assert_not_called()
    assert result.service_payload["answer"] == "target"


def test_bootstrap_builds_fullcontext_once_per_client() -> None:
    build_calls = 0
    real_build = importlib.import_module("core.target_runtime_client_context").build_target_cached_full_context

    def counting_build(md_root: Path):
        nonlocal build_calls
        build_calls += 1
        return real_build(md_root)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "core.target_runtime_client_context.build_target_cached_full_context",
        counting_build,
    )
    try:
        first = load_target_runtime_client_context("demo")
        second = load_target_runtime_client_context("demo")
    finally:
        monkeypatch.undo()
    assert build_calls == 1
    assert first.cached_full_context is second.cached_full_context
    assert first.cache_key == second.cache_key


def test_invalid_pack_fail_closed(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    from core.target_runtime_client_context import TargetRuntimeClientContextError

    def _raise_invalid(client_id: str):
        raise TargetRuntimeClientContextError("target_runtime_bundle_invalid", "bad")

    monkeypatch.setattr(
        "core.target_runtime_turn.load_target_runtime_client_context",
        _raise_invalid,
    )
    _install_turn_frame(_turn_frame())
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-invalid",
        user_message="test",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "error"
    assert outcome.widget.error_code == "target_runtime_bundle_invalid"


def test_turn_frame_bridge_reads_planner_shadow(flask_ctx) -> None:
    frame = _turn_frame(service_id="all_on_4", primary_aspect="price")
    _install_turn_frame(frame)
    loaded = load_runtime_turn_frame()
    assert loaded.service_id == "all_on_4"
    assert get_turn_frame_shadow_status() == SHADOW_STATUS_OK
    assert isinstance(get_turn_frame_shadow_snapshot(), dict)


def test_missing_turn_frame_fail_closed_not_legacy(flask_ctx) -> None:
    request.ctx["turn_frame_shadow_status"] = SHADOW_STATUS_NOT_AVAILABLE
    with pytest.raises(TargetRuntimeTurnFrameError):
        load_runtime_turn_frame()


def test_s46_called_once_on_target_turn(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    import core.target_runtime_turn as runtime_turn

    calls = 0
    real = runtime_turn.run_target_offline_boundary_enforced_fullcontext_response

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(runtime_turn, "run_target_offline_boundary_enforced_fullcontext_response", counting)
    _install_turn_frame(_turn_frame())
    boundary = RecordingBoundaryBackend(BackendPayload(decision="none", confidence=0.95))
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-once",
        user_message="Сколько стоит All-on-4?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=boundary,
    )
    assert calls == 1
    assert len(boundary.invocations) == 1
    assert outcome.widget.kind == "materialized"


def test_boundary_uncertain_terminal_defer(flask_ctx) -> None:
    _install_turn_frame(_turn_frame())
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-uncertain",
        user_message="Можно ли мне?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="uncertain", confidence=0.5)
        ),
    )
    assert outcome.widget.kind == "terminal"
    assert outcome.widget.terminal_mode == "defer"
    assert "консультац" in outcome.widget.payload["answer"].lower()


def test_materialized_price_answer(flask_ctx) -> None:
    _install_turn_frame(_turn_frame(primary_aspect="price", aspects=["price"]))
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-price",
        user_message="Сколько стоит All-on-4?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "materialized"
    assert "318" in outcome.widget.payload["answer"]


def test_medical_handoff_pain_materializes(flask_ctx) -> None:
    _install_turn_frame(
        _turn_frame(service_id=None, aspects=["pain"], primary_aspect=None)
    )
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-pain",
        user_message="Больно ли?",
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=S59SemanticPolicyBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="medical_handoff", confidence=0.9)
        ),
    )
    assert outcome.widget.kind == "materialized"
    assert "анестез" in outcome.widget.payload["answer"].lower()


def test_verifier_minor_external_detail_publishes_normal_answer(flask_ctx) -> None:
    _install_turn_frame(_turn_frame())
    assessment = TargetSemanticAssessment(
        issues=(_issue("minor_external_detail", "318"),),
    )
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-minor",
        user_message="test",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "materialized"


def test_verifier_hard_block_gives_controlled_response(flask_ctx) -> None:
    _install_turn_frame(_turn_frame())
    assessment = TargetSemanticAssessment(
        issues=(_issue("personal_medical_conclusion", "вам нельзя"),),
    )
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-block",
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "error"
    assert outcome.widget.error_code == "target_verifier_semantic_rejected"
    assert "консультац" in outcome.widget.payload["answer"].lower()


def test_session_updates_after_materialized_not_after_error(flask_ctx) -> None:
    sid = "s-session-1"
    frame = _turn_frame(service_id="all_on_4", primary_aspect="price")
    _install_turn_frame(frame)
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит All-on-4?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    after_ok = read_target_runtime_session(sid)
    assert after_ok.last_service_id == "all_on_4"

    _install_turn_frame(_turn_frame(service_id="all_on_4"))
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(
            assessment=TargetSemanticAssessment(
                issues=(_issue("personal_medical_conclusion", "x"),),
            )
        ),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    after_err = read_target_runtime_session(sid)
    assert after_err.last_service_id == "all_on_4"


def test_widget_payload_hides_internal_fields(flask_ctx) -> None:
    _install_turn_frame(_turn_frame())
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-widget",
        user_message="Сколько стоит All-on-4?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    payload = outcome.widget.payload
    assert "answer" in payload
    assert "meta" in payload
    meta = payload["meta"]
    assert meta.get("answer_path") == "target_fullcontext"
    assert "verifier" not in str(payload).lower()
    assert "evidence" not in payload


def test_orchestrate_target_returns_service_reply() -> None:
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload(decision="none", confidence=0.95))
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        _install_turn_frame(_turn_frame())
        result = orchestrate_target_fullcontext_turn(
            q="Сколько стоит All-on-4?",
            sid="s-orch",
            client_id="demo",
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )
    assert result.kind == "service_reply"
    assert result.service_route.startswith("target_fullcontext")


def test_product_modules_do_not_import_evals() -> None:
    modules = [
        "core/target_runtime_client_context.py",
        "core/target_runtime_turn.py",
        "core/target_runtime_turn_frame_bridge.py",
        "core/target_runtime_widget.py",
        "core/target_runtime_session.py",
        "core/target_runtime_llm_backends.py",
        "core/target_runtime_llm_messages.py",
        "orchestration/target_fullcontext_turn.py",
    ]
    for rel in modules:
        tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("evals")
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("evals")


def test_target_runtime_does_not_import_legacy_routing() -> None:
    forbidden = ("source_routing", "route_source", "core.md_chunks")
    modules = list(Path("core").glob("target_runtime_*.py")) + [
        Path("orchestration/target_fullcontext_turn.py"),
    ]
    for path in modules:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source


def test_frozen_s53_artifacts_unchanged() -> None:
    from evals.v5.fullcontext_verifier_replay_contract import validate_frozen_s53_artifacts

    validate_frozen_s53_artifacts()


def test_error_payload_mapping() -> None:
    err = materialize_target_error_payload(
        client_id="demo",
        sid="s",
        error_code="target_verifier_semantic_rejected",
    )
    assert err.kind == "error"
    assert "консультац" in err.payload["answer"].lower()


def test_turn_frame_getters_exported() -> None:
    from core import turn_frame_shadow as mod

    assert callable(mod.get_turn_frame_shadow_status)
    assert callable(mod.get_turn_frame_shadow_snapshot)


def test_target_runtime_turn_public_entrypoint() -> None:
    sig = inspect.signature(run_target_fullcontext_runtime_turn)
    assert "composer_backend" in sig.parameters
    assert "boundary_backend" in sig.parameters
