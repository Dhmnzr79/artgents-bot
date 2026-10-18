"""Tests for scripts/validate_client_pack.py."""

from __future__ import annotations

from tests.d2_ci_http import bind_copied_tenant

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validate_client_pack import validate_client_pack

_REPO = Path(__file__).resolve().parents[1]
_DEMO = _REPO / "clients" / "demo"
_TEMPLATE = _REPO / "clients" / "_template"


def test_demo_pack_passes_validator() -> None:
    errors = validate_client_pack(_DEMO)
    assert errors == []


def test_demo_has_no_legacy_mirrors() -> None:
    for rel in ("service_catalog.json", "marketing.yaml", "price_brand_aliases.json", "pricebook"):
        assert not (_DEMO / rel).exists()


def test_sparse_fixture_passes_validator(tmp_path: Path) -> None:
    from tests.test_final_client_pack_data_convergence_sparse_pack import _build_sparse_pack

    pack = _build_sparse_pack(tmp_path).parent
    errors = validate_client_pack(pack)
    assert errors == []


def test_validator_cli_demo_exit_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(_REPO / "scripts" / "validate_client_pack.py"), "--client-id", "demo"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_validator_reports_missing_target(tmp_path: Path) -> None:
    pack = tmp_path / "broken"
    pack.mkdir()
    (pack / "md").mkdir()
    (pack / "md" / "x.md").write_text("# x\n", encoding="utf-8")
    errors = validate_client_pack(pack)
    assert any("target_response" in err for err in errors)


@pytest.mark.parametrize("broken", [None, {"version": "v1"}, {
    "version": "v1", "checkbox_text": "Agree", "consent_url": "http://clinic.invalid/consent",
    "policy_url": "https://clinic.invalid/policy"}])
@pytest.mark.parametrize("scaffold", [False, True])
def test_validator_rejects_enabled_real_leads_without_valid_consent(tmp_path, broken, scaffold):
    import shutil
    import yaml
    pack = tmp_path / "clinic"
    shutil.copytree(_TEMPLATE, pack)
    bind_copied_tenant(pack, 'clinic')
    features = yaml.safe_load((pack / "features.yaml").read_text(encoding="utf-8"))
    features["leads"]["enabled"] = True
    (pack / "features.yaml").write_text(yaml.safe_dump(features), encoding="utf-8")
    config = yaml.safe_load((pack / "lead_config.yaml").read_text(encoding="utf-8"))
    config["consent"] = broken
    (pack / "lead_config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    assert "lead_config.yaml: consent_required_for_enabled_real_leads" in validate_client_pack(pack, scaffold=scaffold)


def test_validator_accepts_enabled_real_leads_with_consent(tmp_path):
    import shutil
    import yaml
    pack = tmp_path / "clinic"
    shutil.copytree(_TEMPLATE, pack)
    bind_copied_tenant(pack, 'clinic')
    (pack / "features.yaml").write_text("leads:\n  enabled: true\n  mode: email\n", encoding="utf-8")
    config = yaml.safe_load((pack / "lead_config.yaml").read_text(encoding="utf-8"))
    config["consent"] = {"version": "v1", "checkbox_text": "Agree",
                         "consent_url": "https://clinic.invalid/consent",
                         "policy_url": "https://clinic.invalid/policy"}
    (pack / "lead_config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    assert validate_client_pack(pack) == []


def test_validator_rejects_unbound_document_cta(tmp_path):
    import shutil
    pack = tmp_path / "clinic"
    shutil.copytree(_TEMPLATE, pack)
    bind_copied_tenant(pack, 'clinic')
    (pack / "md/sample__service__example.md").write_text(
        "---\ntopic: general\ncta_action: lead\ncta_key: unknown\n---\n# Sample\n", encoding="utf-8")
    assert "md/sample__service__example.md: cta_key_missing_in_tone" in validate_client_pack(pack)


def test_demo_doctors_use_md_without_parallel_catalog():
    assert not (_DEMO / "doctor_catalog.json").exists()
    for name in ("fedorova", "grigoriev", "kuznetsov", "morozova", "orlov", "volkov"):
        profile = _DEMO / "md" / f"doctors__doctor__{name}.md"
        text = profile.read_text(encoding="utf-8")
        assert "{#korotko}" in text
        assert len(text) > 200
    # Canonical contact facts live in clinic_policies.yaml; the contacts MD has no duplicates.
    assert validate_client_pack(_DEMO) == []


@pytest.mark.parametrize("reference", ["doctors__doctor__missing.md#korotko", "clinic__info__consultation.md#missing"])
def test_validator_rejects_unavailable_current_fact_sources(tmp_path, reference):
    import shutil
    import json
    pack = tmp_path / "demo"
    shutil.copytree(_DEMO, pack)
    baseline = validate_client_pack(pack)
    path = pack / "target_response" / "pricebook" / "facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    next(iter(data.values()))["detail_ref"] = reference
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    errors = validate_client_pack(pack)
    assert len(errors) == len(baseline) + 1
    assert any("external_ref_invalid" in error for error in errors)
