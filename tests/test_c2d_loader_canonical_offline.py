"""C2d-D2: canonical pricebook loaders only — no legacy JSON product reads."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_LEGACY_JSON_PATTERNS = (
  "prices.json",
  "price_offers.json",
  "load_price_offers",
  "prices_json",
)

_BANNED_LEGACY_MODULES = (
  "core.patient_playbook",
  "core.answer_lens",
  "core.service_node",
  "core.numeric_fact_gate",
  "contracts.patient_playbook",
)


def test_c2d_product_py_has_no_legacy_price_json_reads() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
needles = {list(_LEGACY_JSON_PATTERNS)!r}
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/", "scripts/", "contracts/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if any(n in line for n in needles):
            if "family_prices.json" in line:
                continue
            offenders.append(f"{{rel}}:{{lineno}}:{{stripped}}")
assert not offenders, offenders
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_c2d_deleted_legacy_modules_not_importable() -> None:
    for mod in _BANNED_LEGACY_MODULES:
        script = f"import importlib; importlib.import_module({mod!r})"
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, f"expected import failure for {mod}: {proc.stdout}{proc.stderr}"


def test_c2d_startup_check_requires_pricebook_only() -> None:
    from core import startup_check

    source = Path(startup_check.__file__).read_text(encoding="utf-8")
    assert "prices.json" not in source
    assert "load_target_client_data" in source
