"""Canonical captured YAML contacts ground ordinary model answers."""
from tests.d2_ci_http import bind_copied_tenant
import json
import shutil
from pathlib import Path

import pytest
import yaml

from core.d2_live_provider import build_d2_d1r_messages
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from tests.d2_ci_http import FakeProvider, http_env, send


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_ordinary_prompt_receives_canonical_contact_facts(http_env, transport):
    client, _, use, root = http_env
    policies = yaml.safe_load((root / "clients/demo/clinic_policies.yaml").read_text(encoding="utf-8"))
    expected = policies["contact"]
    fake = use(FakeProvider("Расскажу об условиях посещения."))
    result = send(client, transport, q="Есть парковка и как добраться?")
    assert result["answer"] == "Расскажу об условиях посещения."
    assert len(fake.inputs) == 1
    request = fake.inputs[0]
    facts = json.loads(request.model_view.clinic_policy_catalog_json)["contact_facts"]
    system, _ = build_d2_d1r_messages(request)
    for field in ("phone_display", "whatsapp_display", "address_display", "hours_display", "parking_display"):
        assert facts[field] == expected[field]
        assert expected[field] in system["content"]
    assert "Пушкинская" in facts["address_display"]
    assert "5 мин пешком" in facts["address_display"]
    assert expected["parking_display"] not in request.model_view.approved_md_corpus


def test_contacts_use_captured_snapshot_and_do_not_leak_between_tenants(tmp_path):
    root = tmp_path / "clients"
    for tenant in ("demo", "other"):
        shutil.copytree(Path("clients/demo"), root / tenant)
        bind_copied_tenant(root / tenant, tenant)
    first = load_d2_tenant_snapshot("demo", clients_root=root)
    original = json.loads(build_d2_model_view(first).clinic_policy_catalog_json)["contact_facts"]
    for tenant in ("demo", "other"):
        path = root / tenant / "clinic_policies.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["contact"]["parking_display"] = tenant + " parking marker"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert json.loads(build_d2_model_view(first).clinic_policy_catalog_json)["contact_facts"] == original
    for tenant in ("demo", "other"):
        view = build_d2_model_view(load_d2_tenant_snapshot(tenant, clients_root=root))
        facts = json.loads(view.clinic_policy_catalog_json)["contact_facts"]
        assert facts["parking_display"] == tenant + " parking marker"
        assert ("other" if tenant == "demo" else "demo") + " parking marker" not in view.clinic_policy_catalog_json


def test_branch_contact_facts_keep_their_branch_binding(tmp_path):
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    path = root / "demo/clinic_policies.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["contact"] = {"branches": [
        {"branch_id": "north", "label": "Северный", "aliases": ["север"],
         "address_display": "Адрес северного, метро Северная", "phone_displays": ["+7 (495) 111-11-11"],
         "hours_display": "09:00–18:00", "parking_display": "Парковка северного"},
        {"branch_id": "south", "label": "Южный", "aliases": ["юг"],
         "address_display": "Адрес южного", "phone_displays": ["+7 (495) 222-22-22"],
         "hours_display": "10:00–20:00"},
    ]}
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    view = build_d2_model_view(load_d2_tenant_snapshot("demo", clients_root=root))
    facts = json.loads(view.clinic_policy_catalog_json)["contact_facts"]
    assert facts["address_display"] is None
    assert facts["parking_display"] is None
    north, south = facts["branches"]
    assert north["branch_id"] == "north"
    assert north["parking_display"] == "Парковка северного"
    assert south["branch_id"] == "south"
    assert south["parking_display"] is None
