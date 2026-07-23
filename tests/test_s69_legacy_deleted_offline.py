"""S69 Checkpoint B offline acceptance: legacy modules deleted, product import audit."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged
from evals.v5.s66_default_authority_live_contract import assert_frozen_s63_live_artifacts_unchanged
from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged

_REPO_ROOT = Path(__file__).resolve().parents[1]

DELETED_MODULES = (
    "chunk_responder",
    "orchestration.ask_turn",
    "source_routing",
    "orchestration.composer_flow",
    "orchestration.price_flow",
    "orchestration.catalog_flow",
    "orchestration.patient_playbook_flow",
    "core.answer_plan_apply",
    "core.answer_packet",
    "core.answer_packet_materialize",
    "core.answer_packet_snapshot",
)

FORBIDDEN_SYMBOLS = (
    "TARGET_FULLCONTEXT_DEV",
    "orchestrate_routing_after_resolver",
)


def test_deleted_modules_not_importable() -> None:
    for module_name in DELETED_MODULES:
        spec = importlib.util.find_spec(module_name)
        assert spec is None, f"deleted module still importable: {module_name}"


def test_product_py_has_no_legacy_imports() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
import_patterns = [
    re.compile(r"^\\s*import\\s+chunk_responder\\b"),
    re.compile(r"^\\s*from\\s+chunk_responder\\b"),
    re.compile(r"^\\s*import\\s+source_routing\\b"),
    re.compile(r"^\\s*from\\s+source_routing\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\.ask_turn\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\s+import\\s+ask_turn\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\.composer_flow\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\.price_flow\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\.catalog_flow\\b"),
    re.compile(r"^\\s*from\\s+orchestration\\.patient_playbook_flow\\b"),
    re.compile(r"^\\s*from\\s+core\\.answer_plan_apply\\b"),
    re.compile(r"^\\s*from\\s+core\\.answer_packet\\b"),
    re.compile(r"^\\s*from\\s+core\\.answer_packet_materialize\\b"),
    re.compile(r"^\\s*from\\s+core\\.answer_packet_snapshot\\b"),
]
symbol_patterns = [
    re.compile(r"\\bTARGET_FULLCONTEXT_DEV\\b"),
    re.compile(r"\\borchestrate_routing_after_resolver\\b"),
]
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for pat in import_patterns:
            if pat.search(line):
                offenders.append(f"{{rel}}:{{lineno}}:{{line.strip()}}")
        for pat in symbol_patterns:
            if pat.search(line):
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


def test_config_has_no_kill_switch_flag() -> None:
    text = (_REPO_ROOT / "config.py").read_text(encoding="utf-8")
    for symbol in FORBIDDEN_SYMBOLS:
        assert symbol not in text


def test_app_has_no_legacy_dispatch_symbols() -> None:
    text = (_REPO_ROOT / "app.py").read_text(encoding="utf-8")
    for symbol in FORBIDDEN_SYMBOLS:
        assert symbol not in text
    assert 'kind="chunk"' not in text
    assert 'kind="composer"' not in text


def test_frozen_s62_s63_s66_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    _assert_frozen_s66_artifacts_unchanged()
