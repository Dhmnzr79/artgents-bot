from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.response_schema import TargetStrategyMatch
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from core.target_runtime_client_context import load_target_runtime_client_context
from core.target_runtime_followup_nav import (
    TargetRuntimeFollowupItem,
    resolve_target_followup_navigation,
)
from core.target_runtime_session import read_target_runtime_session
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.turn_frame_shadow import SHADOW_STATUS_OK
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from orchestration.resolver_turn import ResolverTurnOutcome
from session import mem_reset
from tests.test_target_boundary_enforced_fullcontext_response import (
    PAIN_GROUNDED_TEXT,
    PRICE_TEXT,
    PERSONAL_MEDICAL_REJECT_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)


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
        allowed_topics=frozenset({"implantation", "doctors", "aesthetics", "prosthetics"}),
        allowed_service_ids=frozenset({"all_on_4", "veneers"}),
    )


def _install_turn_frame(frame) -> None:
    request.ctx["turn_frame_shadow"] = frame.model_dump()
    request.ctx["turn_frame_shadow_status"] = SHADOW_STATUS_OK


def _fake_backends():
    return (
        RecordingComposerBackend(PRICE_TEXT),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(BackendPayload(decision="none", confidence=0.95)),
    )


def _pre_resolver(data: dict, *, target_mode: bool):
    return run_pre_resolver_turn(
        data,
        resolve_client_id=lambda *a, **k: "demo",
        bind_chat_ctx=lambda *a, **k: None,
        resolve_ip=lambda: "127.0.0.1",
        client_txt=lambda cid: {},
        service_payload=lambda **k: {},
        get_last_content_ui_payload=lambda sid: None,
        target_fullcontext_mode=target_mode,
    )


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_strategy_all_on_4_has_authored_extent() -> None:
    ctx = load_target_runtime_client_context("demo")
    match = resolve_target_runtime_strategy_context(ctx.bundle, service_id="all_on_4")
    assert match.family == "implantology"
    assert match.extent == "full_arch"


def test_strategy_veneers_not_implantology_full_arch() -> None:
    ctx = load_target_runtime_client_context("demo")
    match = resolve_target_runtime_strategy_context(ctx.bundle, service_id="veneers")
    assert match.family == "aesthetics"
    assert match.extent is None


def test_strategy_none_service_is_empty() -> None:
    ctx = load_target_runtime_client_context("demo")
    match = resolve_target_runtime_strategy_context(ctx.bundle, service_id=None)
    assert match == TargetStrategyMatch(family=None, extent=None)


def test_effective_cta_on_price_materialized(flask_ctx) -> None:
    _install_turn_frame(_turn_frame(primary_aspect="price", aspects=["price"]))
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-cta-price",
        user_message="Сколько стоит All-on-4?",
        composer_backend=RecordingComposerBackend(PRICE_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )
    assert outcome.widget.kind == "materialized"
    meta = outcome.widget.payload.get("meta") or {}
    assert outcome.widget.payload.get("cta") is not None or meta.get("cta_key")


def test_medical_handoff_has_no_cta(flask_ctx) -> None:
    _install_turn_frame(_turn_frame(service_id=None, aspects=["pain"], primary_aspect=None))
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-cta-pain",
        user_message="Больно ли?",
        composer_backend=RecordingComposerBackend(PAIN_GROUNDED_TEXT),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="medical_handoff", confidence=0.9)
        ),
    )
    assert outcome.widget.kind == "materialized"
    assert outcome.widget.payload.get("cta") is None


def test_session_merges_selected_fact_ids(flask_ctx) -> None:
    sid = f"s-freq-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _install_turn_frame(_turn_frame(primary_aspect="price", aspects=["price"]))
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
    after = read_target_runtime_session(sid)
    assert after.last_service_id == "all_on_4"
    assert isinstance(after.shown_fact_ids, tuple)


def test_target_mode_skips_price_ref(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    price_mock = MagicMock()
    monkeypatch.setattr("orchestration.pre_resolver_turn.orchestrate_price_widget_ref", price_mock)
    _pre_resolver({"q": "", "ref": "price:all_on_4", "sid": "s1"}, target_mode=True)
    price_mock.assert_not_called()


def test_target_mode_skips_chunk_ref(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    chunk_mock = MagicMock(return_value={"id": "chunk"})
    monkeypatch.setattr("orchestration.pre_resolver_turn.get_chunk_by_ref", chunk_mock)
    _pre_resolver({"q": "test", "ref": "kb:foo.md#bar", "sid": "s2"}, target_mode=True)
    chunk_mock.assert_not_called()


def test_target_mode_skips_promo(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    promo_mock = MagicMock(return_value={"answer": "promo"})
    monkeypatch.setattr("orchestration.pre_resolver_turn.build_promo_overview_payload", promo_mock)
    monkeypatch.setattr("orchestration.pre_resolver_turn.is_direct_promo_question", lambda q: True)
    _pre_resolver({"q": "акции", "sid": "s3"}, target_mode=True)
    promo_mock.assert_not_called()


def test_followup_nav_maps_ref_to_label() -> None:
    nav = resolve_target_followup_navigation(
        ref="price:all_on_4/stages",
        q="",
        followups=(
            TargetRuntimeFollowupItem(ref="price:all_on_4/stages", label="Этапы оплаты"),
        ),
    )
    assert nav is not None
    assert nav.user_message == "Этапы оплаты"
    assert nav.matched_ref == "price:all_on_4/stages"


def test_http_ask_flag_off_legacy_not_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", False)
    target = MagicMock(side_effect=AssertionError("target must not run"))
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
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    monkeypatch.setattr(app_module, "orchestrate_routing_after_resolver", legacy)
    monkeypatch.setattr(
        app_module,
        "run_pre_resolver_turn",
        lambda *a, **k: MagicMock(q="q", sid="sid", client_id="demo", st={}, data={}),
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "test", "sid": "sid-http-off", "client_id": "demo"})
    assert resp.status_code == 200
    target.assert_not_called()
    legacy.assert_called_once()


def test_http_ask_flag_on_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", True)
    legacy = MagicMock(side_effect=AssertionError("legacy must not run"))
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        app = Flask(__name__)
        with app.test_request_context():
            request.ctx = {}
            _install_turn_frame(_turn_frame())
            outcome = run_target_fullcontext_runtime_turn(
                client_id=kwargs["client_id"],
                sid=kwargs["sid"],
                user_message=kwargs["q"],
                composer_backend=composer,
                semantic_backend=semantic,
                boundary_backend=boundary,
            )
        payload = outcome.widget.payload
        return AskOrchestrationResult(
            kind="service_reply",
            q=kwargs["q"],
            sid=kwargs["sid"],
            client_id=kwargs["client_id"],
            service_payload=payload,
            service_route=str((payload.get("meta") or {}).get("service_route", "target")),
        )

    monkeypatch.setattr(app_module, "orchestrate_routing_after_resolver", legacy)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_pre_resolver_turn",
        lambda *a, **k: MagicMock(q="Сколько?", sid="sid-on", client_id="demo", st={}, data={}),
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "Сколько?", "sid": "sid-on", "client_id": "demo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "318" in body.get("answer", "")
    legacy.assert_not_called()


def test_http_stream_flag_on_batch_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "TARGET_FULLCONTEXT_DEV", True)
    monkeypatch.setattr(
        app_module,
        "_orchestrate_ask_turn",
        lambda data: AskOrchestrationResult(
            kind="service_reply",
            q="q",
            sid="sid-stream",
            client_id="demo",
            service_payload={
                "answer": "verified",
                "quick_replies": [],
                "meta": {"service_route": "target_fullcontext_materialized"},
            },
            service_route="target_fullcontext_materialized",
        ),
    )
    client = app_module.app.test_client()
    resp = client.post("/ask/stream", json={"q": "q", "sid": "sid-stream", "client_id": "demo"})
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "event: ui" in text
    assert "event: done" in text
    assert "verified" in text


def test_verifier_block_gives_controlled_response(flask_ctx) -> None:
    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    _install_turn_frame(_turn_frame())
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid="s-block",
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    assert outcome.widget.kind == "error"
    assert "консультац" in outcome.widget.payload["answer"].lower()
