"""Checkpoint A reader cutover — product modules use canonical target_response only."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_CUTOVER_MODULES = (
    "core/turn_planner_llm.py",
    "core/follow_up_rewrite.py",
    "core/dialog_focus.py",
    "core/startup_check.py",
    "ingress_gate.py",
    "doctors_lookup.py",
    "orchestration/planner_turn.py",
)


def test_checkpoint_a_loader_exists() -> None:
    assert (_REPO_ROOT / "core/target_client_data.py").is_file()
    assert (_REPO_ROOT / "core/target_query_cues.py").is_file()


def test_cutover_modules_do_not_import_legacy_price_or_query_selector() -> None:
    forbidden = (
        "core.pricebook_loader",
        "query_selector",
        "core.service_selector_llm",
        "core.marketing_loader",
        "core.price_offers",
    )
    offenders: list[str] = []
    for rel in _CUTOVER_MODULES:
        path = _REPO_ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                offenders.append(f"{rel}:from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        offenders.append(f"{rel}:import {alias.name}")
    assert offenders == []


def test_planner_turn_imports_target_query_cues_not_query_selector() -> None:
    source = (_REPO_ROOT / "orchestration/planner_turn.py").read_text(encoding="utf-8")
    assert "core.target_query_cues" in source
    assert "query_selector" not in source


def test_startup_check_validates_target_response_not_root_pricebook() -> None:
    source = (_REPO_ROOT / "core/startup_check.py").read_text(encoding="utf-8")
    assert "load_target_client_data" in source
    assert "pricebook_loader" not in source
    assert "service_catalog.json" not in source


def test_demo_target_and_legacy_service_ids_stay_aligned() -> None:
    import json

    legacy = json.loads((_REPO_ROOT / "clients/demo/service_catalog.json").read_text(encoding="utf-8"))
    target = json.loads(
        (_REPO_ROOT / "clients/demo/target_response/service_catalog.json").read_text(encoding="utf-8")
    )
    assert set(legacy) == set(target)


def test_product_py_has_no_root_service_catalog_reads_in_cutover_modules() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
files = {list(_CUTOVER_MODULES)!r}
pattern = re.compile(r"service_catalog\\.json")
offenders = []
for rel in files:
    path = root / rel
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if pattern.search(line):
            offenders.append(f"{{rel}}:{{lineno}}:{{line.strip()}}")
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
