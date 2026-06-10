"""Tests for client pack config loader."""
from __future__ import annotations

from core.client_config_loader import (
    admin_client_options,
    admin_enabled,
    consult_nudge_enabled,
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
    assert resolve_pack_client_id("cesi") == "cesi"


def test_tone_demo_has_submit_ok():
    txt = tone_to_txt_dict("demo")
    assert "демо-бот" in txt["lead_submit_ok"].lower()


def test_tone_cesi_no_demo_disclaimer():
    txt = tone_to_txt_dict("cesi")
    assert "демо-бот" not in txt["lead_submit_ok"].lower()


def test_ui_cesi_low_score_differs_from_demo():
    demo = load_ui_bundle("demo")
    cesi = load_ui_bundle("cesi")
    assert demo.low_score.answer != cesi.low_score.answer
    assert "бесплатная" in demo.low_score.answer.lower()
    assert "бесплатная" not in cesi.low_score.answer.lower()
    assert "бесплатн" not in cesi.anti_spam_soft_redirect.lower()


def test_postgres_events_demo_off():
    assert postgres_events_enabled("demo") is False
    assert postgres_events_enabled("cesi") is True


def test_consult_nudge_enabled_default():
    assert consult_nudge_enabled("demo") is True


def test_admin_enabled_prod_clients():
    assert admin_enabled("demo") is False
    assert admin_enabled("cesi") is True
    assert admin_enabled("nikadent") is True


def test_list_admin_client_ids():
    ids = list_admin_client_ids()
    assert "cesi" in ids
    assert "nikadent" in ids
    assert "demo" not in ids


def test_admin_client_options_labels():
    opts = admin_client_options()
    by_id = {item["client_id"]: item["label"] for item in opts}
    assert by_id.get("cesi") == "ЦЭСИ"
    assert by_id.get("nikadent") == "НикаДент"


def test_widget_theme_from_brand_cesi_palette():
    theme = widget_theme_from_brand("cesi")
    assert theme["brand"] == "#23BFCF"
    assert theme["action"] == "#0B7A86"
    assert theme["button_1"] == "#23BFCF"
    assert theme["button_2"] == "#1E6FD9"


def test_widget_logo_from_brand_cesi():
    logo = widget_logo_from_brand("cesi")
    assert logo["logoUrl"] == "/static/clients/cesi/logo.svg"
    assert logo["logoWidth"] == 64
    assert logo["logoHeight"] == 65


def test_widget_logo_from_brand_demo():
    logo = widget_logo_from_brand("demo")
    assert logo["logoUrl"] == "/static/clients/demo/logo.svg"
    assert logo["logoWidth"] == 124
    assert logo["logoHeight"] == 32


def test_widget_avatar_from_brand_cesi():
    avatar = widget_avatar_from_brand("cesi")
    assert avatar["avatarUrl"] == "/static/clients/cesi/avatar.png"


def test_load_widget_config_merges_brand_theme():
    cfg = load_widget_config("cesi")
    assert cfg["theme"]["brand"] == "#23BFCF"
    assert cfg["theme"]["action"] == "#0B7A86"
    assert cfg["theme"]["button_1"] == "#23BFCF"
    assert cfg["theme"]["button_2"] == "#1E6FD9"
    assert cfg["clinicName"] == "ЦЭСИ"
    assert cfg["logoUrl"] == "/static/clients/cesi/logo.svg"
    assert cfg["logoWidth"] == 64
    assert cfg["logoHeight"] == 65
    assert cfg["avatarUrl"] == "/static/clients/cesi/avatar.png"


def test_load_widget_config_merges_demo_logo():
    cfg = load_widget_config("demo")
    assert cfg["logoUrl"] == "/static/clients/demo/logo.svg"
    assert cfg["logoWidth"] == 124
    assert cfg["logoHeight"] == 32
    assert cfg["avatarUrl"] == "/static/clients/demo/avatar.png"
