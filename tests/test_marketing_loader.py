from __future__ import annotations

from pathlib import Path

from core.marketing_loader import (
    MarketingConfig,
    load_marketing_config,
    marketing_yaml_path,
)


def test_load_demo_marketing_defaults_are_safe():
    cfg = load_marketing_config("demo", force_reload=True)

    assert isinstance(cfg, MarketingConfig)
    assert cfg.version == 1
    assert cfg.limits.max_text_ingredients == 1
    assert cfg.limits.max_cta == 1
    assert "free_implant_consult" in (cfg.promo_rules or {})
    classic = cfg.service("classic")
    assert classic is not None
    assert classic.consult_reasons
    assert classic.clinic_proof
    assert "pain" in cfg.blocked_aspects_for_promo


def test_default_client_uses_demo_marketing_file():
    assert marketing_yaml_path("default") == marketing_yaml_path("demo")


def test_missing_marketing_file_returns_empty_config():
    cfg = load_marketing_config("__missing_client__", force_reload=True)

    assert cfg.version == 1
    assert cfg.promo_rules == {}
    assert cfg.service_marketing == {}
    assert cfg.blocked_aspects_for_promo == ()


def test_loader_parses_service_marketing_and_promo_rules(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    pack = root / "clients" / "custom"
    pack.mkdir(parents=True)
    (pack / "marketing.yaml").write_text(
        """
version: 1
limits:
  max_text_ingredients: 1
  promo_cooldown_turns: 4
blocked_aspects_for_promo:
  - pain
service_marketing:
  all_on_4:
    clinic_proof:
      - 3D planning
    consult_reasons:
      - compare options
    primary_cta_key: plan
promo_rules:
  free_consult:
    active: true
    active_until: "2026-12-31"
    fact_ref: free_implant_consult
    allowed_service_ids:
      - all_on_4
    allowed_routes:
      - price_lookup
    allowed_aspects:
      - overview
    blocked_aspects:
      - safety
    cta_key: consult
""",
        encoding="utf-8",
    )

    import core.marketing_loader as loader

    monkeypatch.setattr(loader, "marketing_yaml_path", lambda _cid: str(pack / "marketing.yaml"))
    cfg = load_marketing_config("custom", force_reload=True)

    svc = cfg.service("all_on_4")
    promo = cfg.promo("free_consult")

    assert cfg.limits.promo_cooldown_turns == 4
    assert svc is not None
    assert svc.clinic_proof == ("3D planning",)
    assert svc.consult_reasons == ("compare options",)
    assert svc.primary_cta_key == "plan"
    assert promo is not None
    assert promo.active is True
    assert promo.allowed_service_ids == ("all_on_4",)
    assert promo.allowed_routes == ("price_lookup",)
    assert promo.blocked_aspects == ("safety",)


def test_loader_keeps_legacy_promos_key_as_fallback(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    pack = root / "clients" / "custom"
    pack.mkdir(parents=True)
    (pack / "marketing.yaml").write_text(
        """
version: 1
promos:
  legacy_consult:
    active: true
    fact_ref: free_implant_consult
""",
        encoding="utf-8",
    )

    import core.marketing_loader as loader

    monkeypatch.setattr(loader, "marketing_yaml_path", lambda _cid: str(pack / "marketing.yaml"))
    cfg = load_marketing_config("custom", force_reload=True)

    promo = cfg.promo("legacy_consult")
    assert promo is not None
    assert promo.active is True
    assert promo.fact_ref == "free_implant_consult"


def test_demo_marketing_yaml_controls_pricebook_promo_facts():
    raw = Path("clients/demo/marketing.yaml").read_text(encoding="utf-8")

    assert "promo_rules:" in raw
    assert "promos:" not in raw
    assert "fact_ref: free_implant_consult" in raw
    assert "allowed_routes:" in raw
    assert "price_lookup" in raw
    assert "promo_overview" in raw
