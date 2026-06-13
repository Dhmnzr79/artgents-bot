"""Widget embed CORS and origin helpers."""
from __future__ import annotations

import pytest

from core import widget_cors
from core.origin_guard import allowed_origins_for_client, matching_widget_origin


def test_allowed_origins_for_client_demo():
    allowed = allowed_origins_for_client("demo")
    assert "https://artgents.ru" in allowed
    assert "https://demo.bot.artgents.ru" in allowed


def test_is_widget_embed_cors_path():
    assert widget_cors.is_widget_embed_cors_path("/api/widget-config")
    assert widget_cors.is_widget_embed_cors_path("/api/media/pain-doctor-explains")
    assert widget_cors.is_widget_embed_cors_path("/static/widget/embed.js")
    assert widget_cors.is_widget_embed_cors_path("/static/widget/widget.js")
    assert widget_cors.is_widget_embed_cors_path("/ask/stream")
    assert not widget_cors.is_widget_embed_cors_path("/dashboard")
    assert not widget_cors.is_widget_embed_cors_path("/static/clients/demo/logo.svg")


def test_matching_widget_origin_allows_listed(monkeypatch):
    class _Req:
        headers = {"Origin": "https://artgents.ru"}

    monkeypatch.setattr("core.origin_guard.request", _Req())
    assert matching_widget_origin("demo") == "https://artgents.ru"


def test_matching_widget_origin_rejects_unknown(monkeypatch):
    class _Req:
        headers = {"Origin": "https://evil.example"}

    monkeypatch.setattr("core.origin_guard.request", _Req())
    assert matching_widget_origin("demo") is None


def test_matching_widget_origin_no_origin_header(monkeypatch):
    class _Req:
        headers = {}

    monkeypatch.setattr("core.origin_guard.request", _Req())
    assert matching_widget_origin("demo") is None


def test_widget_cors_preflight_ignores_get(monkeypatch):
    class _Req:
        method = "GET"
        path = "/static/widget/embed.js"
        args = {}
        host = "demo.bot.artgents.ru"

    monkeypatch.setattr("core.widget_cors.request", _Req())
    assert widget_cors.widget_cors_preflight_response() is None


def test_widget_cors_preflight_allowed(monkeypatch):
    class _Req:
        method = "OPTIONS"
        path = "/api/widget-config"
        args = {"client_id": "demo"}
        host = "demo.bot.artgents.ru"

        @staticmethod
        def get_json(silent=True):
            return None

    monkeypatch.setattr("core.widget_cors.request", _Req())
    monkeypatch.setattr(
        "core.widget_cors.matching_widget_origin",
        lambda _cid: "https://artgents.ru",
    )
    monkeypatch.setattr(
        "core.widget_cors.resolve_widget_cors_client_id",
        lambda: "demo",
    )
    resp = widget_cors.widget_cors_preflight_response()
    assert resp is not None
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "https://artgents.ru"


def test_widget_cors_preflight_denied(monkeypatch):
    class _Req:
        method = "OPTIONS"
        path = "/ask"
        args = {}
        host = "demo.bot.artgents.ru"

        @staticmethod
        def get_json(silent=True):
            return None

    monkeypatch.setattr("core.widget_cors.request", _Req())
    monkeypatch.setattr("core.widget_cors.matching_widget_origin", lambda _cid: None)
    monkeypatch.setattr("core.widget_cors.resolve_widget_cors_client_id", lambda: "demo")
    resp = widget_cors.widget_cors_preflight_response()
    assert resp is not None
    assert resp.status_code == 403
