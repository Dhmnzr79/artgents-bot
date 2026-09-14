"""Widget presentation v1 and integration policy contract tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import app as app_module
from contracts.widget_config import (
    WidgetConfigValidationError,
    WidgetIntegrationValidationError,
    validate_widget_integration_document,
    validate_widget_presentation_document,
)
from core.client_config_loader import (
    WidgetPresentationLoadError,
    build_public_widget_config,
    load_widget_integration_v1,
    load_widget_presentation_v1,
)
from core.origin_guard import allowed_origins_for_client, validate_widget_origin

_REPO = Path(__file__).resolve().parents[1]
_DEMO = _REPO / "clients" / "demo"
_NIKADENT = _REPO / "clients" / "nikadent"
_TEMPLATE = _REPO / "clients" / "_template"

_DEMO_VISUAL = {
    "botName": "Надежда",
    "onlineLabel": "ИИ-консультант клиники. Онлайн 24/7",
    "launcherSubtitle": "Демо ИИ-консультанта клиники",
    "launcherCtaLabel": "Посмотреть демо",
    "launcherTeaser": False,
    "demoLauncher": True,
    "videoAspect": "horizontal",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _install_pack(monkeypatch: pytest.MonkeyPatch, pack_dir: Path, tenant: str = "packtenant") -> None:
    monkeypatch.setattr("core.client_config_loader.resolve_pack_client_id", lambda _cid: tenant)
    monkeypatch.setattr(
        "core.client_config_loader._pack_path",
        lambda _cid, name: str(pack_dir / name),
    )


def _seed_valid_presentation(pack_dir: Path) -> None:
    shutil.copy(_DEMO / "widget_config.json", pack_dir / "widget_config.json")


def _write_integration(pack_dir: Path, payload: dict) -> None:
    (pack_dir / "widget_integration.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_demo_presentation_valid_v1() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    out = validate_widget_presentation_document(raw, client_id="demo")
    assert out["schemaVersion"] == 1
    for key, value in _DEMO_VISUAL.items():
        assert out[key] == value


def test_nikadent_presentation_valid_v1() -> None:
    raw = _load_json(_NIKADENT / "widget_config.json")
    out = validate_widget_presentation_document(raw, client_id="nikadent")
    assert out["botName"] == "Консультант Никадент"
    assert out["demoLauncher"] is False
    assert out["welcomeText"] is None


def test_template_presentation_valid_v1_scaffold() -> None:
    raw = _load_json(_TEMPLATE / "widget_config.json")
    out = validate_widget_presentation_document(raw, client_id="_template")
    assert out["schemaVersion"] == 1
    assert out["starterPrompts"] == []


def test_rejects_snake_case_keys() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    raw["bot_name"] = "x"
    with pytest.raises(WidgetConfigValidationError) as exc:
        validate_widget_presentation_document(raw, client_id="demo")
    assert "bot_name" in str(exc.value)


def test_rejects_missing_required_key() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    del raw["botName"]
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="demo")


def test_rejects_wrong_type() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    raw["demoLauncher"] = "yes"
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="demo")


def test_rejects_unsupported_schema_version() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    raw["schemaVersion"] = 2
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="demo")


def test_rejects_unknown_key() -> None:
    raw = _load_json(_DEMO / "widget_config.json")
    raw["extraField"] = 1
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="demo")


def test_rejects_teaser_enabled_without_text() -> None:
    raw = _load_json(_NIKADENT / "widget_config.json")
    raw["launcherTeaser"] = True
    raw["launcherTeaserText"] = None
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="nikadent")


def test_presentation_file_excludes_identity_and_security() -> None:
    for tenant, path in (
        ("demo", _DEMO),
        ("nikadent", _NIKADENT),
    ):
        raw = _load_json(path / "widget_config.json")
        for forbidden in ("clientId", "packId", "apiBase", "allowedOrigins", "allowed_origins"):
            assert forbidden not in raw
        validate_widget_presentation_document(raw, client_id=tenant)


def test_public_api_hides_allowed_origins() -> None:
    client = app_module.app.test_client()
    resp = client.get(
        "/api/widget-config?client_id=demo",
        headers={"Origin": "https://artgents.ru"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "allowedOrigins" not in body
    assert "allowed_origins" not in body


def test_public_api_client_id_from_resolved_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    import config

    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    client = app_module.app.test_client()
    resp = client.get(
        "/api/widget-config?client_id=nikadent",
        headers={"Origin": "https://nikadent.bot.artgents.ru"},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("clientId") == "nikadent"


def test_invalid_presentation_not_demo_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "widget_config.json").write_text('{"schemaVersion":1}', encoding="utf-8")
    monkeypatch.setattr(
        "core.client_config_loader._pack_path",
        lambda _cid, name: str(broken / name) if name == "widget_config.json" else str(_DEMO / name),
    )
    resp = app_module.app.test_client().get(
        "/api/widget-config?client_id=demo",
        headers={"Origin": "https://artgents.ru"},
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "widget_config_invalid"


@pytest.fixture
def pack_dir(tmp_path: Path) -> Path:
    path = tmp_path / "pack"
    path.mkdir()
    _seed_valid_presentation(path)
    return path


def test_integration_missing_file_fail_closed(pack_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_pack(monkeypatch, pack_dir)
    with pytest.raises(WidgetPresentationLoadError) as exc:
        load_widget_integration_v1("packtenant")
    assert exc.value.code == "widget_integration_not_found"
    assert allowed_origins_for_client("packtenant") == set()
    with app_module.app.test_request_context(
        "/api/widget-config",
        headers={"Origin": "https://example.com"},
    ):
        assert validate_widget_origin("packtenant") == "widget_integration_not_found"


def test_integration_malformed_json_fail_closed(pack_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (pack_dir / "widget_integration.json").write_text("{not-json", encoding="utf-8")
    _install_pack(monkeypatch, pack_dir)
    with pytest.raises(WidgetPresentationLoadError) as exc:
        load_widget_integration_v1("packtenant")
    assert exc.value.code == "widget_integration_invalid"


def test_integration_unsupported_schema_version(pack_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_integration(pack_dir, {"schemaVersion": 2, "allowedOrigins": ["https://example.com"]})
    _install_pack(monkeypatch, pack_dir)
    with pytest.raises(WidgetPresentationLoadError):
        load_widget_integration_v1("packtenant")


def test_integration_snake_case_key_rejected(pack_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_integration(pack_dir, {"schemaVersion": 1, "allowed_origins": ["https://example.com"]})
    _install_pack(monkeypatch, pack_dir)
    with pytest.raises(WidgetPresentationLoadError):
        load_widget_integration_v1("packtenant")


def test_integration_unknown_key_rejected() -> None:
    raw = {"schemaVersion": 1, "allowedOrigins": ["https://example.com"], "extra": 1}
    with pytest.raises(WidgetIntegrationValidationError):
        validate_widget_integration_document(raw, client_id="demo")


@pytest.mark.parametrize(
    "origins",
    [
        [],
        ["https://*.evil.com"],
        ["artgents.ru"],
        ["https://example.com/path"],
        ["https://example.com?q=1"],
        ["https://user:pass@example.com"],
        ["https://example.com", "https://example.com/"],
    ],
)
def test_integration_invalid_origins_rejected(origins: list[str]) -> None:
    raw = {"schemaVersion": 1, "allowedOrigins": origins}
    with pytest.raises(WidgetIntegrationValidationError):
        validate_widget_integration_document(raw, client_id="demo")


def test_integration_valid_loader_and_origin_guard(pack_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_integration(pack_dir, {"schemaVersion": 1, "allowedOrigins": ["https://allowed.example"]})
    _install_pack(monkeypatch, pack_dir)
    cfg = load_widget_integration_v1("packtenant")
    assert cfg["allowedOrigins"] == ["https://allowed.example"]
    assert allowed_origins_for_client("packtenant") == {"https://allowed.example"}
    with app_module.app.test_request_context(
        "/ask",
        headers={"Origin": "https://evil.example"},
    ):
        assert validate_widget_origin("packtenant") == "origin_not_allowed"
    with app_module.app.test_request_context(
        "/ask",
        headers={"Origin": "https://allowed.example"},
    ):
        assert validate_widget_origin("packtenant") is None


def test_nikadent_not_demo_bot_name() -> None:
    cfg = build_public_widget_config("nikadent")
    assert cfg["botName"] == "Консультант Никадент"
    assert cfg["botName"] != load_widget_presentation_v1("demo")["botName"]


def test_demo_starter_prompts_preserved() -> None:
    cfg = load_widget_presentation_v1("demo")
    labels = [item["label"] for item in cfg["starterPrompts"]]
    assert labels == [
        "Я боюсь боли",
        "Расскажите про all-on-4",
        "Посмотреть видео с врачом",
    ]


def test_integration_valid_demo() -> None:
    raw = _load_json(_DEMO / "widget_integration.json")
    out = validate_widget_integration_document(raw, client_id="demo")
    assert out["schemaVersion"] == 1
    assert "https://artgents.ru" in out["allowedOrigins"]
