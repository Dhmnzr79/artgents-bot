"""C2e: final orphan legacy modules must stay deleted from product path."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

C2E_DELETED_MODULES = (
    "core.aspect_arbitration",
    "core.consult_nudge",
    "contracts.retrieval_candidate",
)

_BANNED_SYMBOLS = (
    "build_answer_plan",
    "publish_answer_plan",
    "answer_plan_from_ctx",
    "plan_consult_nudge",
    "record_consult_nudge_after_answer",
    "reset_consult_nudge_on_route",
)


def test_c2e_deleted_modules_not_importable() -> None:
    for module_name in C2E_DELETED_MODULES:
        spec = importlib.util.find_spec(module_name)
        assert spec is None, f"C2e deleted module still importable: {module_name}"


def test_c2e_product_py_has_no_deleted_module_imports() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
modules = {list(C2E_DELETED_MODULES)!r}
patterns = [
    re.compile(r"^\\s*from\\s+" + re.escape(m).replace(".", r"\\.") + r"\\b")
    for m in modules
] + [
    re.compile(r"^\\s*import\\s+" + re.escape(m).replace(".", r"\\.") + r"\\b")
    for m in modules
]
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/", "orchestration/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if any(p.search(line) for p in patterns):
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


def test_c2e_answer_planner_has_no_legacy_plan_api() -> None:
    import core.answer_planner as mod

    for name in ("build_answer_plan", "publish_answer_plan", "answer_plan_from_ctx"):
        assert not hasattr(mod, name), f"legacy API still exported: {name}"
    assert hasattr(mod, "detect_aspects")


def test_c2e_product_py_has_no_legacy_plan_or_consult_symbols() -> None:
    script = f"""
import pathlib
root = pathlib.Path({str(_REPO_ROOT)!r})
needles = {list(_BANNED_SYMBOLS)!r}
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/", "orchestration/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if any(n in line for n in needles):
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
