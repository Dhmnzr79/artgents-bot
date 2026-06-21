from __future__ import annotations

import uuid

from core.price_ref_routing import orchestrate_price_widget_ref, parse_price_widget_ref


def test_parse_price_widget_ref_service():
    assert parse_price_widget_ref("price:classic") == {
        "service_id": "classic",
        "group_id": None,
        "aspect": None,
    }


def test_parse_price_widget_ref_overview():
    assert parse_price_widget_ref("price:implantation/overview") == {
        "service_id": None,
        "group_id": "implantation",
        "aspect": "overview",
    }


def test_unit_clarify_quick_replies_use_price_ref():
    from core.price_group_overview import group_overview_quick_replies

    refs = [r["ref"] for r in group_overview_quick_replies("demo")]
    assert refs == ["price:classic", "price:one_stage", "price:all_on_4", "price:all_on_6"]


def test_price_ref_click_classic_offers(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-price-ref-classic-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:classic", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    meta = body.get("meta") or {}
    assert meta.get("price_offers_applied") is True
    assert meta.get("matched_service_id") == "classic"
    assert "76 200" in (body.get("answer") or "")
    assert "классическ" in (body.get("answer") or "").lower()


def test_parse_price_widget_ref_aspect_stages():
    assert parse_price_widget_ref("price:all_on_4/stages") == {
        "service_id": "all_on_4",
        "group_id": None,
        "aspect": "stages",
    }


def test_price_ref_click_all_on_4_stages_aspect(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-price-ref-a4-stages-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4/stages", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    answer = body.get("answer") or ""
    meta = body.get("meta") or {}
    assert meta.get("pricebook_aspect") == "stages"
    assert "220 800" in answer
    assert "318 000" not in answer
    assert "Актуальные пакеты" not in answer
    refs = [r.get("ref") for r in body.get("quick_replies") or []]
    assert "price:all_on_4/stages" not in refs
    labels = [r.get("label") for r in body.get("quick_replies") or []]
    assert "Оплата по этапам" not in labels


def test_price_ref_click_all_on_4_compact(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-price-ref-a4-compact-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    answer = body.get("answer") or ""
    assert "318 000" in answer
    assert "Актуальные пакеты" not in answer
    assert "**Оплата по этапам**" not in answer
