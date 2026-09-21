"""CP5-M1: D2 commercial data contract is loaded through the tenant snapshot."""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
from pathlib import Path

import pytest
import yaml

from core.d2_tenant_snapshot import D2TenantSnapshotError, build_d2_model_view, load_d2_tenant_snapshot


def _copy_named(tmp_path: Path, name: str) -> Path:
    root = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", root / name)
    return root


def _commercial_path(root: Path, name: str = "demo") -> Path:
    return root / name / "target_response" / "d2_commercial.json"


def _read_commercial(root: Path, name: str = "demo") -> dict[str, object]:
    return json.loads(_commercial_path(root, name).read_text(encoding="utf-8"))


def _write_commercial(root: Path, payload: dict[str, object], name: str = "demo") -> None:
    _commercial_path(root, name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(root: Path, name: str = "demo"):
    return build_d2_model_view(load_d2_tenant_snapshot(name, clients_root=root))


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-M1")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


def test_demo_pack_loads_commercial_contract_through_snapshot(tmp_path: Path) -> None:
    root = _copy_named(tmp_path, "demo")
    view = _load(root)
    commercial = view.commercial
    classic = next(item for item in commercial.service_profiles if item.service_id == "classic")
    caries = next(item for item in commercial.service_profiles if item.service_id == "caries")
    discount = next(item for item in commercial.promo_facts if item.fact_id == "implant_same_day_discount")

    assert view.client_id == "demo"
    assert len(classic.promo_refs) == 2
    assert classic.price_booster_id == "demo_payment_booster"
    assert classic.also_list_id == "demo_also_diagnostics"
    assert caries.promo_refs == ()
    assert caries.price_booster_id is None
    assert caries.also_list_id is None
    assert discount.short_text != discount.full_text
    assert len(commercial.price_booster_packages) == 2
    assert len(commercial.also_list_packages) == 2
    assert commercial.incompatibility_groups[0].explanation_text
    assert not hasattr(commercial.price_booster_packages[0], "fact_refs")


def test_empty_and_missing_packages_are_valid(tmp_path: Path) -> None:
    root = _copy_named(tmp_path, "demo")
    payload = _read_commercial(root)
    payload["price_booster_packages"] = []
    payload["also_list_packages"] = []
    payload["service_profiles"] = [{"service_id": "caries", "promo_refs": []}]
    _write_commercial(root, payload)
    view = _load(root)
    assert view.commercial.price_booster_packages == ()
    assert view.commercial.also_list_packages == ()
    assert view.commercial.service_profiles[0].price_booster_id is None

    _commercial_path(root).unlink()
    missing = _load(root)
    assert missing.commercial.service_profiles == ()
    assert missing.commercial.promo_facts == ()


@pytest.mark.parametrize(
    ("fault", "code"),
    (
        ("unknown_fact", "commercial_fact_unavailable"),
        ("foreign_tenant", "commercial_tenant_mismatch"),
        ("two_boosters", "commercial_package_not_single"),
        ("two_also", "commercial_package_not_single"),
        ("conflicting_forms", "commercial_promo_forms_conflict"),
        ("promo_cap", "commercial_promo_ref_cap"),
        ("inapplicable", "commercial_promo_inapplicable"),
        ("unknown_package", "commercial_package_unavailable"),
        ("unknown_service", "commercial_service_unavailable"),
        ("unknown_group_id", "commercial_incompatibility_ref_unavailable"),
        ("meaning_duplicate", "commercial_meaning_duplicate"),
    ),
)
def test_broken_commercial_contract_fails_closed(tmp_path: Path, fault: str, code: str) -> None:
    root = _copy_named(tmp_path, "demo")
    payload = _read_commercial(root)
    classic = next(item for item in payload["service_profiles"] if item["service_id"] == "classic")
    if fault == "unknown_fact":
        payload["promo_facts"][0]["fact_id"] = "missing_promo"
        classic["promo_refs"] = ["missing_promo", "free_implant_consult"]
    elif fault == "foreign_tenant":
        payload["client_id"] = "clinic_b"
    elif fault == "two_boosters":
        classic["price_booster_id"] = ["demo_payment_booster", "demo_warranty_booster"]
    elif fault == "two_also":
        classic["also_list_id"] = ["demo_also_diagnostics", "demo_also_followup"]
    elif fault == "conflicting_forms":
        payload["promo_facts"][0]["short_text"] = "Другая короткая форма."
    elif fault == "promo_cap":
        classic["promo_refs"] = [
            "implant_same_day_discount",
            "free_implant_consult",
            "professional_whitening_discount",
        ]
    elif fault == "inapplicable":
        classic["promo_refs"] = ["professional_whitening_discount"]
    elif fault == "unknown_package":
        classic["price_booster_id"] = "missing_package"
    elif fault == "unknown_service":
        classic["service_id"] = "missing_service"
    elif fault == "unknown_group_id":
        payload["incompatibility_groups"][0]["offer_or_fact_ids"] = [
            "implant_same_day_discount",
            "missing_offer",
        ]
    else:
        payload["also_list_packages"][0]["body_text"] = payload["promo_facts"][0]["short_text"]
    _write_commercial(root, payload)

    with pytest.raises(D2TenantSnapshotError, match=code):
        _load(root)


def test_tenants_do_not_share_commercial_packages(tmp_path: Path) -> None:
    root = _copy_named(tmp_path, "clinic_a")
    shutil.copytree(Path("clients") / "demo", root / "clinic_b")
    payload = _read_commercial(root, "clinic_b")
    payload["price_booster_packages"][0]["package_id"] = "clinic_b_only_booster"
    for profile in payload["service_profiles"]:
        if profile.get("price_booster_id") == "demo_payment_booster":
            profile["price_booster_id"] = "clinic_b_only_booster"
    _write_commercial(root, payload, "clinic_b")

    view_a = _load(root, "clinic_a")
    view_b = _load(root, "clinic_b")
    assert view_a.client_id == "clinic_a"
    assert view_b.client_id == "clinic_b"
    assert "clinic_b_only_booster" not in {item.package_id for item in view_a.commercial.price_booster_packages}
    assert "clinic_b_only_booster" in {item.package_id for item in view_b.commercial.price_booster_packages}


def test_legacy_marketing_lists_are_not_d2_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_named(tmp_path, "demo")
    marketing = root / "demo" / "target_response" / "marketing.yaml"
    payload = yaml.safe_load(marketing.read_text(encoding="utf-8"))
    payload["service_automatic_commercial"]["classic"]["price"]["ordered_promo_refs"] = []
    payload["service_automatic_commercial"]["classic"]["price"]["ordered_amplifier_refs"] = [
        "fact:tax_deduction"
    ]
    payload["scenario_rules"]["cost"]["ordered_amplifier_refs"] = ["fact:tax_deduction"]
    marketing.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    import core.target_marketing_selector as selector

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy marketing selector is not D2 authority")

    for name in (
        "_ordered_automatic_promo_refs_for_context",
        "_ordered_direct_promo_refs_for_context",
        "_ordered_promo_refs_for_context",
        "_filter_promo_refs",
        "_reserve_promo_refs",
    ):
        monkeypatch.setattr(selector, name, forbidden)

    view = _load(root)
    classic = next(item for item in view.commercial.service_profiles if item.service_id == "classic")
    assert classic.promo_refs == ("implant_same_day_discount", "free_implant_consult")
    assert classic.price_booster_id == "demo_payment_booster"
    assert classic.also_list_id == "demo_also_diagnostics"
    assert all(package.package_id != "fact:installment_12" for package in view.commercial.price_booster_packages)
    assert os.environ["BOT_LOG_DIR"].startswith(str(tmp_path))
