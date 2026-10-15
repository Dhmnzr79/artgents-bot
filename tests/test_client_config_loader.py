"""Tests for client pack config loader."""
from __future__ import annotations

from core.client_config_loader import (
    admin_client_options,
    admin_enabled,
    list_admin_client_ids,
    load_ui_bundle,
    load_widget_config,
    postgres_events_enabled,
    resolve_pack_client_id,
    tone_to_txt_dict,
    widget_logo_from_brand,
    widget_avatar_from_brand,
    widget_theme_from_brand,
)


def test_resolve_pack_default_to_demo():
    assert resolve_pack_client_id("default") == "demo"
    assert resolve_pack_client_id("demo") == "demo"


def test_tone_demo_has_submit_ok():
    txt = tone_to_txt_dict("demo")
    assert "демо-бот" in txt["lead_submit_ok"].lower()


def test_ui_demo_low_score_has_no_tax_deduction():
    demo = load_ui_bundle("demo")
    assert "налоговый вычет" not in demo.low_score.answer.lower()
    assert "бесплатная" not in demo.low_score.answer.lower()


def test_postgres_events_demo_off():
    assert postgres_events_enabled("demo") is False


def test_admin_disabled_for_demo_only_runtime():
    assert admin_enabled("demo") is False
    assert list_admin_client_ids() == []
    assert admin_client_options() == []


def test_widget_theme_from_brand_demo_palette():
    theme = widget_theme_from_brand("demo")
    assert theme == {"brand": "#0C2FE0", "promoBackground": "#F0F4FF", "promoAccent": "#6C7EA6"}


def test_widget_theme_emits_only_supported_palette(monkeypatch):
    monkeypatch.setattr("core.client_config_loader.load_brand", lambda _: {"colors": {
        "brand": "#762E94", "promo_background": "#F5EFF8", "promo_accent": "#762E94",
        "action": "#111111", "button_1": "#222222", "button_2": "#333333"}})
    assert widget_theme_from_brand("nikadent") == {
        "brand": "#762E94", "promoBackground": "#F5EFF8", "promoAccent": "#762E94"}


def test_widget_logo_from_brand_demo():
    logo = widget_logo_from_brand("demo")
    assert logo["logoUrl"] == "/static/clients/demo/logo.svg"
    assert logo["logoWidth"] == 110
    assert logo["logoHeight"] == 28


def test_widget_avatar_from_brand_demo():
    avatar = widget_avatar_from_brand("demo")
    assert avatar["avatarUrl"] == "/static/clients/demo/avatar.png"


def test_load_widget_config_merges_demo_brand():
    cfg = load_widget_config("demo")
    assert cfg["schemaVersion"] == 1
    assert cfg["botName"] == "Надежда"
    assert cfg["demoLauncher"] is True
    assert "allowed_origins" not in cfg
    assert "allowedOrigins" not in cfg
    assert "clientId" not in cfg
    assert cfg["logoUrl"] == "/static/clients/demo/logo.svg"
    assert cfg["logoWidth"] == 110
    assert cfg["logoHeight"] == 28
    assert cfg["avatarUrl"] == "/static/clients/demo/avatar.png"
    assert cfg["theme"] == {"brand": "#0C2FE0", "promoBackground": "#F0F4FF", "promoAccent": "#6C7EA6"}
    assert "demoLauncherColors" not in cfg
