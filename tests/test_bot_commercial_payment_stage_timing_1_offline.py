"""BOT-COMMERCIAL-PAYMENT-STAGE-TIMING-1 — payment stage timing_text rendering."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

import config
import pytest

import app as app_module
from contracts.response_schema import TargetOffer, TargetPaymentStage
from core.response_schema_loader import load_response_schema_bundle
from core.sales_fast_authoritative_commerce import (
    build_offer_payment_stages_block,
    build_payment_stages_display_block,
)
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from tests.test_sales_one_plus_turn import answer_envelope

_DEMO_ROOT = Path(__file__).resolve().parents[1] / "clients" / "demo" / "target_response"
_OFFERS_DIR = _DEMO_ROOT / "pricebook" / "services"

_CLASSIC_SURGICAL_TIMING = "Оплачивается в день установки импланта."
_CLASSIC_ORTHO_TIMING = (
    "Оплачивается при установке постоянной коронки, обычно через 3–6 месяцев "
    "после хирургического этапа. Точный срок зависит от приживления импланта и плана лечения."
)
_ONE_STAGE_SURGICAL_TIMING = "Оплачивается в день удаления и установки импланта."
_ONE_STAGE_ORTHO_TIMING = _CLASSIC_ORTHO_TIMING
_ALL_ON_STAGE1_TIMING = (
    "Оплачивается при проведении хирургического этапа. "
    "Временный протез обычно устанавливают в день операции или в течение 2–3 дней."
)
_ALL_ON_STAGE2_TIMING = (
    "Оплачивается при установке постоянного протеза, обычно через 3–6 месяцев "
    "после хирургического этапа. Точный срок зависит от приживления имплантов."
)

_FAMILY_TIMING = {
    "classic": (_CLASSIC_SURGICAL_TIMING, _CLASSIC_ORTHO_TIMING),
    "one_stage": (_ONE_STAGE_SURGICAL_TIMING, _ONE_STAGE_ORTHO_TIMING),
    "all_on_4": (_ALL_ON_STAGE1_TIMING, _ALL_ON_STAGE2_TIMING),
    "all_on_6": (_ALL_ON_STAGE1_TIMING, _ALL_ON_STAGE2_TIMING),
}

_EXPECTED_OFFER_AMOUNTS = {
    "classic.one_tooth.implantium": (45200, 31000, 76200),
    "classic.one_tooth.impro": (54200, 31000, 85200),
    "classic.one_tooth.nobel": (70200, 31000, 101200),
    "one_stage.one_tooth.implantium": (52000, 34500, 86500),
    "one_stage.one_tooth.impro": (58000, 38500, 96500),
    "one_stage.one_tooth.nobel": (70000, 44500, 114500),
    "all_on_4.jaw.implantium": (190800, 127200, 318000),
    "all_on_4.jaw.impro": (220800, 147200, 368000),
    "all_on_4.jaw.nobel": (256800, 171200, 428000),
    "all_on_6.jaw.implantium": (238800, 159200, 398000),
    "all_on_6.jaw.impro": (274800, 183200, 458000),
    "all_on_6.jaw.nobel": (316800, 211200, 528000),
}


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _count_amount(answer: str, amount: int) -> int:
    return _norm_digits(answer).count(str(amount))


def _bundle():
    return load_response_schema_bundle(_DEMO_ROOT)


def _offer(offer_id: str):
    return next(item for item in _bundle().offers if item.offer_id == offer_id)


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
    from session import bind_session_client

    bind_session_client("demo")
    try:
        yield
    finally:
        patch_session.stop()
        patch_runtime.stop()


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output

    def generate(self, invocation, /):
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        on_raw_delta(self.output)
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _Backend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def test_all_twelve_demo_offers_have_consistent_timing_text_and_unchanged_amounts() -> None:
    bundle = _bundle()
    staged = [offer for offer in bundle.offers if offer.payment_stages]
    assert len(staged) == 12
    by_service: dict[str, list[TargetOffer]] = {}
    for offer in staged:
        by_service.setdefault(offer.service_id, []).append(offer)
    assert set(by_service) == {"classic", "one_stage", "all_on_4", "all_on_6"}
    assert all(len(items) == 3 for items in by_service.values())

    for offer in staged:
        assert offer.offer_id in _EXPECTED_OFFER_AMOUNTS
        stage1_amount, stage2_amount, total = _EXPECTED_OFFER_AMOUNTS[offer.offer_id]
        stages = offer.payment_stages or []
        assert len(stages) == 2
        assert stages[0].amount == stage1_amount
        assert stages[1].amount == stage2_amount
        assert stages[0].amount + stages[1].amount == total
        assert offer.price.amount == total
        assert stages[0].currency == "RUB"
        assert stages[1].currency == "RUB"
        expected = _FAMILY_TIMING[offer.service_id]
        assert stages[0].timing_text == expected[0]
        assert stages[1].timing_text == expected[1]

    for service_id, offers in by_service.items():
        first = offers[0].payment_stages or []
        for offer in offers[1:]:
            other = offer.payment_stages or []
            assert [stage.timing_text for stage in first] == [
                stage.timing_text for stage in other
            ]


def test_classic_implantium_display_has_intro_brand_dash_and_blank_stage_gap() -> None:
    bundle = _bundle()
    offer = _offer("classic.one_tooth.implantium")
    block = build_payment_stages_display_block((offer,), bundle=bundle)
    assert block is not None
    assert block.startswith("Для варианта Implantium оплата делится на два этапа:")
    assert "Хирургический этап — 45\u00a0200 ₽." in block
    assert "Ортопедический этап (коронка) — 31\u00a0000 ₽." in block
    assert _CLASSIC_SURGICAL_TIMING in block
    assert "3–6 месяцев" in block
    assert "3–4" not in block
    assert _count_amount(block, 45200) == 1
    assert _count_amount(block, 31000) == 1
    assert "\n\nХирургический этап —" in block
    assert "\n\nОртопедический этап" in block


@pytest.mark.parametrize(
    ("offer_id", "brand_label", "stage1", "stage2"),
    [
        ("classic.one_tooth.impro", "Impro", 54200, 31000),
        ("classic.one_tooth.nobel", "Nobel Biocare", 70200, 31000),
    ],
)
def test_classic_other_brands_have_correct_labels_and_timing(
    offer_id: str,
    brand_label: str,
    stage1: int,
    stage2: int,
) -> None:
    bundle = _bundle()
    offer = _offer(offer_id)
    block = build_payment_stages_display_block((offer,), bundle=bundle)
    assert block is not None
    assert block.startswith(f"Для варианта {brand_label} оплата делится на два этапа:")
    assert _count_amount(block, stage1) == 1
    assert _count_amount(block, stage2) == 1
    assert _CLASSIC_ORTHO_TIMING in block
    assert "3–4" not in block


def test_one_stage_timing_mentions_removal_day_and_three_to_six_months() -> None:
    bundle = _bundle()
    offer = _offer("one_stage.one_tooth.implantium")
    block = build_payment_stages_display_block((offer,), bundle=bundle)
    assert block is not None
    assert _ONE_STAGE_SURGICAL_TIMING in block
    assert "3–6 месяцев" in block
    assert "3–4" not in block
    assert _count_amount(block, 52000) == 1
    assert _count_amount(block, 34500) == 1


def test_all_on_four_and_six_timing_mentions_temporary_window_and_permanent_delay() -> None:
    bundle = _bundle()
    for offer_id in ("all_on_4.jaw.implantium", "all_on_6.jaw.nobel"):
        offer = _offer(offer_id)
        block = build_payment_stages_display_block((offer,), bundle=bundle)
        assert block is not None
        assert "2–3 дней" in block
        assert "3–6 месяцев" in block
        assert "в день операции вместе с хирургией и временным протезом" not in block
        stage1, stage2, total = _EXPECTED_OFFER_AMOUNTS[offer_id]
        assert _count_amount(block, stage1) == 1
        assert _count_amount(block, stage2) == 1
        assert stage1 + stage2 == total


def test_offer_without_timing_text_renders_amounts_without_invented_timing() -> None:
    payload = json.loads((_OFFERS_DIR / "classic.one_tooth.implantium.json").read_text("utf-8"))
    for stage in payload["payment_stages"]:
        stage.pop("timing_text", None)
    offer = TargetOffer.model_validate(payload)
    block = build_offer_payment_stages_block(offer)
    assert block is not None
    assert "45200" in _norm_digits(block)
    assert "31000" in _norm_digits(block)
    assert "3–6 месяцев" not in block
    assert "Оплачивается" not in block


def test_multi_brand_display_sections_are_labeled_and_do_not_mix_amounts() -> None:
    bundle = _bundle()
    offers = tuple(
        _offer(offer_id)
        for offer_id in (
            "classic.one_tooth.implantium",
            "classic.one_tooth.impro",
            "classic.one_tooth.nobel",
        )
    )
    block = build_payment_stages_display_block(offers, bundle=bundle)
    assert block is not None
    assert "Implantium:\nОплата делится на два этапа:" in block
    assert "Impro:\nОплата делится на два этапа:" in block
    assert "Nobel Biocare:\nОплата делится на два этапа:" in block
    assert _count_amount(block, 45200) == 1
    assert _count_amount(block, 54200) == 1
    assert _count_amount(block, 70200) == 1
    assert block.count("3–6 месяцев") == 3


def test_implantation_stages_http_chain_includes_formatted_answer(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    from session import mem_reset

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pst-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    client = app_module.app.test_client()
    hostile = "Первый платёж составит 99 999 ₽."

    def _post(ref: str | None, env: str, q: str = "") -> dict:
        _install_sales_fast(monkeypatch, _Backend(env))
        payload = {"q": q, "sid": sid, "client_id": "demo"}
        if ref:
            payload["ref"] = ref
        response = client.post("/ask", json=payload)
        assert response.status_code == 200
        return response.get_json()

    t1 = _post(
        None,
        answer_envelope(
            "Обзор.",
            commercial_intent="price",
            service_reference_status="none",
            scenario="cost",
        ),
        q="Сколько стоит имплантация?",
    )
    scope_ref = next(
        item["ref"] for item in t1["quick_replies"] if "one_tooth" in str(item.get("ref"))
    )
    t2 = _post(
        scope_ref,
        answer_envelope(
            "Цена.",
            commercial_intent="price",
            service_reference_status="none",
        ),
    )
    stages_ref = next(
        item["ref"] for item in t2["quick_replies"] if "/stages" in str(item.get("ref"))
    )
    t3 = _post(
        stages_ref,
        answer_envelope(
            hostile,
            commercial_intent="payment",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
    )
    answer = str(t3.get("answer") or "")
    assert answer.strip()
    assert "Для варианта Implantium оплата делится на два этапа:" in answer
    assert "Хирургический этап —" in answer
    assert _CLASSIC_SURGICAL_TIMING in answer
    assert "3–6 месяцев" in answer
    assert _count_amount(answer, 45200) == 1
    assert _count_amount(answer, 31000) == 1
    assert _count_amount(answer, 99999) == 0
    assert hostile not in answer


def test_stages_http_chain_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env_broad = answer_envelope(
        "Обзор.",
        commercial_intent="price",
        service_reference_status="none",
        scenario="cost",
    )
    env_scope = answer_envelope(
        "Цена.",
        commercial_intent="price",
        service_reference_status="none",
    )
    env_stages = answer_envelope(
        "Этапы.",
        commercial_intent="payment_stages",
        service_id="classic",
        service_reference_status="resolved",
        requested_service_id="classic",
    )
    sid_ask = f"pst-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"pst-stream-{uuid.uuid4().hex[:8]}"

    def _ask(sid: str, q: str, ref: str | None, env: str, reset: bool) -> dict:
        from session import mem_reset

        _install_sales_fast(monkeypatch, _Backend(env))
        if reset:
            mem_reset(sid, client_id="demo")
        payload = {"q": q, "sid": sid, "client_id": "demo"}
        if ref:
            payload["ref"] = ref
        return app_module.app.test_client().post("/ask", json=payload).get_json()

    def _stream(sid: str, q: str, ref: str | None, env: str, reset: bool) -> dict:
        from session import mem_reset

        _install_sales_fast(monkeypatch, _Backend(env))
        if reset:
            mem_reset(sid, client_id="demo")
        payload = {"q": q, "sid": sid, "client_id": "demo"}
        if ref:
            payload["ref"] = ref
        text = app_module.app.test_client().post("/ask/stream", json=payload).get_data(as_text=True)
        match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
        assert match is not None
        return json.loads(match.group(1))

    t1_ask = _ask(sid_ask, "Сколько стоит имплантация?", None, env_broad, True)
    t1_stream = _stream(sid_stream, "Сколько стоит имплантация?", None, env_broad, True)
    scope_ask = next(item["ref"] for item in t1_ask["quick_replies"] if "one_tooth" in item["ref"])
    scope_stream = next(
        item["ref"] for item in t1_stream["quick_replies"] if "one_tooth" in item["ref"]
    )
    t2_ask = _ask(sid_ask, "", scope_ask, env_scope, False)
    t2_stream = _stream(sid_stream, "", scope_stream, env_scope, False)
    stages_ask = next(item["ref"] for item in t2_ask["quick_replies"] if "/stages" in item["ref"])
    stages_stream = next(
        item["ref"] for item in t2_stream["quick_replies"] if "/stages" in item["ref"]
    )
    ask_payload = _ask(sid_ask, "", stages_ask, env_stages, False)
    stream_payload = _stream(sid_stream, "", stages_stream, env_stages, False)
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert "Для варианта Implantium оплата делится на два этапа:" in str(
        ask_payload.get("answer") or ""
    )
