"""BOT-COMMERCIAL-CONTRACT-STAGE-B-1 — code-owned commercial blocks."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import config
import pytest

import app as app_module
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from contracts.turn_frame import TurnFrame
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_offer_commercial_blocks import (
    build_package_contents_block,
    render_offer_commercial_blocks,
    resolve_auto_microfacts,
    resolve_requested_commercial_topics,
)
from core.one_call_payment_stages_policy import payment_stages_materialization_allowed
from core.one_call_price_microfacts import load_price_microfact_assignments, resolve_price_microfacts
from core.one_call_presentation_pass import build_one_call_presentation_result
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.target_client_data import load_target_client_data
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import restore_session_snapshot
from session import bind_session_client, mem_reset, session_client_scope
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
_TARGET_ROOT = _REPO / "clients/demo/target_response"
_DEMO_BUNDLE = load_target_client_data("demo").bundle
_LIVE_ARTIFACT = (
    _REPO
    / "evals/v5/artifacts/bot_cleanup_live_1/bot_cleanup_live_1_2026-09-04-live-01"
)
_LIVE_SNAPSHOT_PRC_06_T1 = _LIVE_ARTIFACT / "session_snapshots" / "PRC-06-T1.json"
_SKIP_LIVE_SNAPSHOT_PRC_06_T1 = pytest.mark.skipif(
    not _LIVE_SNAPSHOT_PRC_06_T1.is_file(),
    reason="requires local LIVE snapshot PRC-06-T1 (not committed to git)",
)


def _offer(offer_id: str):
    return next(item for item in _DEMO_BUNDLE.offers if item.offer_id == offer_id)


def _semantic(**kwargs) -> SalesOnePlusSemanticFrame:
    base = {
        "route": "ANSWER",
        "commercial_intent": "price",
        "promotion_scope": "none",
        "scenario": "cost",
        "service_id": "classic",
        "service_id_provenance": "envelope",
        "extent": None,
        "extent_provenance": "null",
        "jaw": None,
        "jaw_provenance": "null",
        "stage": None,
        "stage_provenance": "null",
        "clarify_axis": None,
        "clarify_service_options": None,
        "service_reference_status": "resolved",
        "requested_service_id": "classic",
        "availability_status": "none",
        "direct_fact_ids": (),
    }
    base.update(kwargs)
    return SalesOnePlusSemanticFrame.model_validate(base)


def _turn_frame(**kwargs) -> TurnFrame:
    del kwargs  # turn_frame is not used by topic resolver in Stage B unit tests
    from tests.target_runtime_test_support import _turn_frame as _support_turn_frame

    return _support_turn_frame(topic="implantation", aspects=["price"], primary_aspect="price")


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    patch_runtime = patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    patch_session = patch("session.sqlite_path_for_client", _sqlite_path)
    patch_runtime.start()
    patch_session.start()
    bind_session_client("demo")
    try:
        yield
    finally:
        patch_session.stop()
        patch_runtime.stop()


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self.output


def _restore_snapshot(turn_id: str) -> str:
    snapshot = json.loads(
        (_LIVE_ARTIFACT / "session_snapshots" / f"{turn_id}.json").read_text(encoding="utf-8")
    )
    restore_session_snapshot(snapshot)
    return str(snapshot["session_sid"])


@pytest.fixture
def flask_app():
    return app_module.app


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
) -> tuple[dict, _Backend]:
    backend = _Backend(envelope_json)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )
    if reset_session:
        mem_reset(sid, client_id="demo")
    with session_client_scope("demo"):
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = {"turn_t0_monotonic": 0.0}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
    payload = dict(outcome.widget.payload or {})
    payload["_backend_calls"] = backend.call_count
    return payload, backend


def test_exact_classic_implantium_package_block() -> None:
    offer = _offer("classic.one_tooth.implantium")
    block, excludes_rendered = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=(offer,),
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert "В предложение входят:" in block
    assert "имплант с документами" in block
    assert "Отдельно оплачиваются:" in block
    assert "КТ при необходимости" in block
    assert excludes_rendered


def test_all_on_4_package_block_lists_implants() -> None:
    offer = _offer("all_on_4.jaw.implantium")
    block, _ = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=(offer,),
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert "4 импланта" in block
    assert "костная пластика" in block


def test_multiple_offers_shared_package_once() -> None:
    offers = (
        _offer("classic.one_tooth.implantium"),
        _offer("classic.one_tooth.impro"),
    )
    block, _ = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=offers,
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert block.count("В предложение входят:") == 1
    assert "Implantium" not in block


def test_payment_stages_not_from_direct_fact_ids_only() -> None:
    semantic = _semantic(
        commercial_intent="price",
        direct_fact_ids=("payment_stages",),
    )
    allowed = payment_stages_materialization_allowed(
        semantic=semantic,
        user_message="Сколько стоит классическая имплантация?",
    )
    assert not allowed


def test_payment_stages_explicit_question_allowed() -> None:
    semantic = _semantic(
        commercial_intent="payment_stages",
        direct_fact_ids=(),
    )
    allowed = payment_stages_materialization_allowed(
        semantic=semantic,
        user_message="Как платить по этапам?",
    )
    assert allowed


def test_payment_stages_typed_intent_without_user_regex() -> None:
    semantic = _semantic(
        commercial_intent="payment_stages",
        direct_fact_ids=(),
    )
    allowed = payment_stages_materialization_allowed(
        semantic=semantic,
        user_message="Какие суммы вносить сначала и потом?",
    )
    assert allowed


def test_microfacts_from_offer_fact_refs_not_yaml(tmp_path: Path) -> None:
    offer = _offer("classic.one_tooth.implantium")
    yaml_path = tmp_path / "price_microfacts.yaml"
    yaml_path.write_text(
        "version: 1\nservices:\n  classic:\n    - professional_whitening_discount\n",
        encoding="utf-8",
    )
    facts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=tmp_path,
        service_id="classic",
        displayed_offers=(offer,),
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    assert facts
    assert all(item.fact_id in offer.fact_refs for item in facts)
    assert all(item.fact_id != "professional_whitening_discount" for item in facts)


def test_auto_microfacts_max_two_from_fact_refs() -> None:
    offer = _offer("all_on_4.jaw.implantium")
    pairs = resolve_auto_microfacts(
        bundle=_DEMO_BUNDLE,
        offers=(offer,),
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
    )
    assert 1 <= len(pairs) <= 2
    assert all(fact_id in offer.fact_refs for fact_id, _ in pairs)


def test_detailed_installment_suppresses_matching_microfact() -> None:
    offer = _offer("all_on_4.jaw.implantium")
    result = render_offer_commercial_blocks(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(offer,),
        topics=frozenset({"price", "installment"}),
        presentation_mode="exact",
        price_line="Стоимость — 318 000 ₽.",
        price_visible=True,
        payment_stages_allowed=False,
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
    )
    assert "installment_12" in result.rendered_fact_ids
    assert "installment_12" not in result.microfact_fact_ids
    assert any("рассрочк" in block.casefold() for block in result.text_blocks)


def test_price_microfacts_yaml_is_dormant_for_active_resolver(tmp_path: Path) -> None:
    offer = _offer("classic.one_tooth.implantium")
    assignments = load_price_microfact_assignments(_TARGET_ROOT)
    assert "classic" in assignments
    mutated = tmp_path / "price_microfacts.yaml"
    mutated.write_text(
        "version: 1\nservices:\n  classic:\n    - professional_whitening_discount\n",
        encoding="utf-8",
    )
    baseline = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="classic",
        displayed_offers=(offer,),
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    changed = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=mutated,
        service_id="classic",
        displayed_offers=(offer,),
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    assert tuple(item.fact_id for item in baseline) == tuple(item.fact_id for item in changed)


@_SKIP_LIVE_SNAPSHOT_PRC_06_T1
def test_included_turn_preserves_model_owned_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = _restore_snapshot("PRC-06-T1")
    payload, _backend = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="КТ входит?",
        envelope_json=answer_envelope(
            "КТ входит в стоимость.",
            commercial_intent="included",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert payload.get("_backend_calls") == 1
    assert "кт входит в стоимость" in answer.casefold()


def test_price_plus_contents_model_owned(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    package_phrase = "В пакет включены импланты, анестезия, временный протез."
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid="stage-b-price-contents",
        user_message="Сколько стоит All-on-4 на Implantium и что входит?",
        envelope_json=dumps_production_envelope(
            patient_text=package_phrase,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318" in answer.replace("\u00a0", "").replace(" ", "")
    assert package_phrase.casefold() in answer.casefold()


def test_implant_supported_package_block() -> None:
    offer = _offer("implant_supported_prosthetics.default")
    block, _ = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=(offer,),
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert "абатмент" in block.casefold()
    assert "хирургическая установка импланта" in block


def test_sinus_lift_package_block() -> None:
    offer = _offer("sinus_lift.one_site.open")
    block, _ = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=(offer,),
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert "синус" in block.casefold() or "костн" in block.casefold()
    assert "имплант" in block.casefold()


def test_differing_packages_get_labeled_blocks() -> None:
    offers = (
        _offer("sinus_lift.one_site.open"),
        _offer("sinus_lift.one_site.closed"),
    )
    block, _ = build_package_contents_block(
        bundle=_DEMO_BUNDLE,
        offers=offers,
        include_includes=True,
        include_excludes=True,
    )
    assert block is not None
    assert "Открытый" in block or "Закрытый" in block


def test_price_conditions_skip_when_package_shows_excludes() -> None:
    offer = _offer("classic.one_tooth.implantium")
    result = render_offer_commercial_blocks(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(offer,),
        topics=frozenset({"price", "package_contents", "excluded_items"}),
        presentation_mode="exact",
        price_line="Стоимость — 76 200 ₽.",
        price_visible=True,
        payment_stages_allowed=False,
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    joined = "\n".join(result.text_blocks)
    assert "В предложение входят:" in joined
    assert "Отдельно оплачиваются:" in joined
    assert joined.count("КТ при необходимости") == 1
    assert result.skip_price_mandatory_exclusion


def test_payment_stages_explicit_e2e(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "stage-b-stages-explicit"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит классическая имплантация на Implantium?",
        envelope_json=dumps_production_envelope(
            patient_text="Implantium.",
            commercial_intent="price",
            scenario="cost",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
            references={"direct_fact_ids": []},
        ),
    )
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Как оплачивается по этапам?",
        envelope_json=dumps_production_envelope(
            patient_text="Этапы оплаты.",
            commercial_intent="payment_stages",
            scenario="cost",
            service_id=None,
            service_reference_status="none",
            price_text=None,
            references={"direct_fact_ids": []},
        ),
        reset_session=False,
    )
    digits = str(payload.get("answer") or "").replace("\u00a0", "").replace(" ", "")
    assert "45200" in digits
    assert "31000" in digits


def test_free_explanation_topic_from_pochemu() -> None:
    semantic = _semantic(service_id="all_on_4", requested_service_id="all_on_4")
    from tests.target_runtime_test_support import _turn_frame as _support_turn_frame

    topics = resolve_requested_commercial_topics(
        semantic=semantic,
        turn_frame=_support_turn_frame(topic="implantation", aspects=["price"], primary_aspect="price"),
        user_message="Сколько стоит All-on-4 и почему используются четыре импланта?",
        payment_stages_allowed=False,
    ).topics
    assert "price" in topics
    assert "free_explanation" in topics


def test_microfacts_limited_to_selected_offer_fact_refs() -> None:
    implantium = _offer("classic.one_tooth.implantium")
    nobel = _offer("classic.one_tooth.nobel")
    assert "implant_same_day_discount" in implantium.fact_refs
    nobel_facts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="classic",
        displayed_offers=(nobel,),
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    assert all(item.fact_id in nobel.fact_refs for item in nobel_facts)
    implantium_facts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="classic",
        displayed_offers=(implantium,),
        authoritative_service_id="classic",
        today=date(2026, 8, 10),
    )
    assert tuple(item.fact_id for item in implantium_facts) == tuple(
        item.fact_id for item in nobel_facts
    )


def test_pure_price_microfact_order() -> None:
    offer = _offer("all_on_4.jaw.implantium")
    facts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="all_on_4",
        displayed_offers=(offer,),
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
    )
    assert [item.fact_id for item in facts] == [
        "installment_12",
        "implant_same_day_discount",
    ]
