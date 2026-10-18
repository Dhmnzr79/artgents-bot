"""Page-aware welcome presentation: validation, tenant API and real browser clicks."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from contracts.widget_config import WidgetConfigValidationError, validate_widget_presentation_document

ROOT = Path(__file__).resolve().parents[1]


def presentation(tenant="nikadent"):
    return json.loads((ROOT / "clients" / tenant / "widget_config.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("change", [
    lambda d: d["pageMenus"][0].update(starterPrompts=[]),
    lambda d: d["pageMenus"][0]["starterPrompts"][0].update(q=" "),
    lambda d: d["pageMenus"][0]["starterPrompts"][0].update(videoKey="other-client-video"),
    lambda d: d["pageMenus"][0].update(welcomePromotion={"title": "override"}),
    lambda d: d["pageMenus"][0].update(clientId="demo"),
    lambda d: d.update(welcomeText=" "),
    lambda d: d["starterPrompts"][0].update(q=" "),
    lambda d: d["pageMenus"].append(copy.deepcopy(d["pageMenus"][0])),
    lambda d: d["pageMenus"][0].update(paths=["/all-on-4", "/all-on-4/"]),
])
def test_invalid_page_menus_fail_closed(change):
    raw = presentation()
    change(raw)
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="nikadent")


@pytest.mark.parametrize("path", ["https://nikadent41.ru/all-on-4/", "//other.test/a", "/*",
                                  "/all-on-4?utm_source=ad", "/a#b", "/a\\b", " /a", "/a b"])
def test_author_paths_are_exact_pathnames(path):
    raw = presentation()
    raw["pageMenus"][0]["paths"] = [path]
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id="nikadent")


def test_default_menu_keeps_authored_video_while_page_menu_has_three_questions():
    raw=presentation('demo')
    assert len(raw['starterPrompts'])==2 and raw['starterPrompts'][1]['videoKey']
    assert all(len(menu['starterPrompts'])==3 for menu in raw['pageMenus'])
    validate_widget_presentation_document(raw,client_id='demo')


def test_widget_api_projects_current_tenant_menus_without_security_fields(monkeypatch):
    import app as app_module
    import config

    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    client = app_module.app.test_client()
    for tenant, origin in [("nikadent", "https://nikadent41.ru"), ("demo", "https://artgents.ru")]:
        response = client.get(f"/api/widget-config?client_id={tenant}", headers={"Origin": origin})
        assert response.status_code == 200
        body = response.get_json()
        assert body["clientId"] == tenant
        assert "allowedOrigins" not in body
        if tenant == "nikadent":
            assert {p for m in body["pageMenus"] for p in m["paths"]} == {
                "/all-on-4", "/semnoe-protezirovanie", "/koronki-i-nesemnoe-protezirovanie"}
            assert body["welcomePromotion"] == presentation()["welcomePromotion"]
            assert "15%" not in json.dumps(body, ensure_ascii=False)
        else:
            assert {m['topicId'] for m in body['pageMenus']}=={'implantation','prosthetics','whitening'}
            assert "НикаДент" not in json.dumps(body, ensure_ascii=False)
    assert client.get("/api/widget-config?client_id=nikadent",
                      headers={"Origin": "https://unrelated.invalid"}).status_code == 403


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Chrome/Edge browser harness")
def test_real_widget_page_menus_and_click_payloads():
    assert shutil.which("node"), "Node runtime required"
    result = subprocess.run(["node", str(ROOT / "tests/js/widget_page_menus_harness.mjs")],
                            cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True,
                            encoding="utf-8", timeout=70)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
