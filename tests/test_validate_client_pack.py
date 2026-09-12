"""Tests for scripts/validate_client_pack.py."""

from __future__ import annotations

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
