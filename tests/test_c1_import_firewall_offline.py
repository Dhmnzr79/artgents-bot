"""C1 product import firewall — deleted legacy modules must not be imported."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

C1_DELETED_MODULES = (
    "core.catalog_resolution",
    "core.knowledge_base",
    "core.living_frame",
    "core.price_brand_money",
    "core.price_symptom_consult",
    "core.price_group_overview",
    "core.rewrite_policy",
    "contracts.answer_packet",
)


def test_c1_deleted_modules_not_importable() -> None:
    for module_name in C1_DELETED_MODULES:
        spec = importlib.util.find_spec(module_name)
        assert spec is None, f"C1 deleted module still importable: {module_name}"


def test_c1_product_py_has_no_deleted_imports() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
patterns = [
    re.compile(r"^\\s*from\\s+core\\.catalog_resolution\\b"),
    re.compile(r"^\\s*from\\s+core\\.knowledge_base\\b"),
    re.compile(r"^\\s*from\\s+core\\.living_frame\\b"),
    re.compile(r"^\\s*from\\s+core\\.price_brand_money\\b"),
    re.compile(r"^\\s*from\\s+core\\.price_symptom_consult\\b"),
    re.compile(r"^\\s*from\\s+core\\.price_group_overview\\b"),
    re.compile(r"^\\s*from\\s+core\\.rewrite_policy\\b"),
    re.compile(r"^\\s*from\\s+contracts\\.answer_packet\\b"),
    re.compile(r"^\\s*from\\s+llm\\s+import\\s+.*rewrite_query_for_retrieval"),
    re.compile(r"^\\s*from\\s+llm\\s+import\\s+.*generate_answer_from_packet"),
]
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for pat in patterns:
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
