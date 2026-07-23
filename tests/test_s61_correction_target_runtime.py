from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.response_schema import TargetStrategyMatch
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
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
from orchestration.context import AskTurnContext
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from orchestration.resolver_turn import ResolverTurnOutcome
from orchestration.target_fullcontext_turn import orchestrate_target_fullcontext_turn
from session import mem_get, mem_reset
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


def _pre_resolver(data: dict):
    return run_pre_resolver_turn(
        data,
        resolve_client_id=lambda *a, **k: "demo",
        bind_chat_ctx=lambda *a, **k: None,
        resolve_ip=lambda: "127.0.0.1",
        client_txt=lambda cid: {},
        service_payload=lambda **k: {},
        get_last_content_ui_payload=lambda sid: None,
    )


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_followups"] = [
            {"ref": item.ref, "label": item.label} for item in items
        ]
        _persist_unlocked(sid, st)


def _seed_target_runtime_state(sid: str, **fields: object) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_state"] = fields
        _persist_unlocked(sid, st)


def _price_turn_frame():
    return _turn_frame(primary_aspect="price", aspects=["price"])


def _run_materialized_turn(
    sid: str,
    *,
    user_message: str = "Сколько стоит All-on-4?",
    composer_text: str = PRICE_TEXT,
    frame=None,
):
    _install_turn_frame(frame or _price_turn_frame())
    return run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message=user_message,
        composer_backend=RecordingComposerBackend(composer_text),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(
            BackendPayload(decision="none", confidence=0.95)
        ),
    )


def _fake_target_turn_factory(composer, semantic, boundary):
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

    return target_turn


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


CONSULTATION_REF = "implantation__service__all_on_4.md"


def test_session_turn1_selects_consultation_ref(flask_ctx) -> None:
    sid = f"s-fact1-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    outcome = _run_materialized_turn(sid)
    result = outcome.pipeline_result
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.session_selection is not None
    assert result.session_selection.shown_consultation_value_refs == (CONSULTATION_REF,)
    after = read_target_runtime_session(sid)
    assert CONSULTATION_REF in after.shown_consultation_value_refs


def test_session_turn2_receives_prior_shown_ids_and_suppresses_repeat(
    monkeypatch: pytest.MonkeyPatch,
    flask_ctx,
) -> None:
    sid = f"s-fact2-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    import core.target_runtime_turn as turn_module

    captured_consult: list[tuple[str, ...]] = []
    original = turn_module.run_target_offline_boundary_enforced_fullcontext_response

    def boundary_spy(*args, **kwargs):
        captured_consult.append(
            tuple(kwargs.get("shown_consultation_value_refs") or ())
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(
        turn_module,
        "run_target_offline_boundary_enforced_fullcontext_response",
        boundary_spy,
    )

    outcome1 = _run_materialized_turn(sid)
    result1 = outcome1.pipeline_result
    assert isinstance(result1, TargetTurnFrameBoundMaterializeResponse)
    assert result1.session_selection is not None
    assert result1.session_selection.shown_consultation_value_refs == (CONSULTATION_REF,)

    outcome2 = _run_materialized_turn(sid)
    result2 = outcome2.pipeline_result
    assert isinstance(result2, TargetTurnFrameBoundMaterializeResponse)
    assert result2.session_selection is not None
    assert CONSULTATION_REF not in result2.session_selection.shown_consultation_value_refs
    assert len(captured_consult) == 2
    assert captured_consult[1] == (CONSULTATION_REF,)
    after = read_target_runtime_session(sid)
    assert after.shown_consultation_value_refs.count(CONSULTATION_REF) == 1


def test_session_stores_consultation_ref_after_materialized(flask_ctx) -> None:
    sid = f"s-consult-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    outcome = _run_materialized_turn(sid)
    result = outcome.pipeline_result
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.session_selection is not None
    assert result.session_selection.shown_consultation_value_refs == (CONSULTATION_REF,)
    after = read_target_runtime_session(sid)
    assert CONSULTATION_REF in after.shown_consultation_value_refs


def test_session_merge_dedupes_duplicate_consultation_refs(flask_ctx) -> None:
    sid = f"s-dedupe-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        shown_fact_ids=[],
        shown_amplifier_refs=[],
        shown_consultation_value_refs=[CONSULTATION_REF],
    )
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    after = read_target_runtime_session(sid)
    assert after.shown_consultation_value_refs.count(CONSULTATION_REF) == 1


def test_session_terminal_error_does_not_mutate_shown_ids(flask_ctx) -> None:
    sid = f"s-err-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _run_materialized_turn(sid)
    before = read_target_runtime_session(sid)
    assert CONSULTATION_REF in before.shown_consultation_value_refs

    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    _install_turn_frame(_price_turn_frame())
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.shown_consultation_value_refs == before.shown_consultation_value_refs
    assert after.shown_fact_ids == before.shown_fact_ids


def test_unknown_ref_returns_clarify(flask_ctx) -> None:
    sid = "s-unknown-ref"
    mem_reset(sid)
    result = _pre_resolver({"q": "", "ref": "unknown:ref", "sid": sid})
    assert isinstance(result, AskOrchestrationResult)
    assert result.service_route == "target_fullcontext_followup_unknown"
    assert "уточните" in result.service_payload["answer"].lower()


def test_known_followup_ref_maps_to_label(flask_ctx) -> None:
    sid = "s-known-ref"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref="price:all_on_4/stages", label="Этапы оплаты"),
    )
    result = _pre_resolver(
        {"q": "", "ref": "price:all_on_4/stages", "sid": sid},
    )
    assert isinstance(result, AskTurnContext)
    assert result.q == "Этапы оплаты"


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


def test_http_ask_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s-http-on-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        _fake_target_turn_factory(composer, semantic, boundary),
    )
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame",
        _turn_frame,
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "318" in body.get("answer", "")


def test_http_ask_followup_ref_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s-http-ref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref="price:all_on_4/stages", label="Этапы оплаты"),
    )
    captured: dict[str, str] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4/stages", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured["q"] == "Этапы оплаты"


def test_http_ask_two_turns_carries_session_shown_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    import core.target_runtime_turn as turn_module

    sid = f"s-http-2t-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    captured_consult: list[tuple[str, ...]] = []
    original_boundary = turn_module.run_target_offline_boundary_enforced_fullcontext_response

    def boundary_spy(*args, **kwargs):
        captured_consult.append(
            tuple(kwargs.get("shown_consultation_value_refs") or ())
        )
        return original_boundary(*args, **kwargs)

    monkeypatch.setattr(
        turn_module,
        "run_target_offline_boundary_enforced_fullcontext_response",
        boundary_spy,
    )
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame",
        _price_turn_frame,
    )
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))

    def target_turn(**kwargs):
        return orchestrate_target_fullcontext_turn(
            **kwargs,
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    client = app_module.app.test_client()
    resp1 = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp1.status_code == 200
    assert captured_consult[0] == ()
    after1 = read_target_runtime_session(sid)
    assert CONSULTATION_REF in after1.shown_consultation_value_refs

    resp2 = client.post(
        "/ask",
        json={"q": "А сколько этапов оплаты?", "sid": sid, "client_id": "demo"},
    )
    assert resp2.status_code == 200
    assert captured_consult[1] == (CONSULTATION_REF,)


def test_http_stream_batch_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

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
