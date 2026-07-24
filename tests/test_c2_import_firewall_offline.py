"""C2 product import firewall — active product must not import shadow/resolver legacy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_c2_product_py_has_no_turn_frame_shadow_imports() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
pattern = re.compile(r"^\\s*(from\\s+core\\.turn_frame_shadow\\b|import\\s+core\\.turn_frame_shadow\\b)")
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
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


def test_c2b_product_py_has_no_resolver_turn_or_adapter_imports() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
patterns = [
    re.compile(r"^\\s*from\\s+orchestration\\.resolver_turn\\b"),
    re.compile(r"^\\s*from\\s+core\\.turn_frame_adapter\\b"),
    re.compile(r"^\\s*import\\s+orchestration\\.resolver_turn\\b"),
]
skip_prefixes = ("evals/", "tests/", "docs/", "archive/", "tools/", "resolver.py")
offenders = []
for path in sorted(root.rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    if any(rel.startswith(p) for p in skip_prefixes):
        continue
    if rel == "resolver.py":
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


def test_c2c_product_modules_have_no_last_subject_or_pending_clarify_reads() -> None:
    script = f"""
import pathlib
import re
root = pathlib.Path({str(_REPO_ROOT)!r})
files = [
    "core/turn_planner_llm.py",
    "core/target_runtime_session.py",
    "core/dialog_focus.py",
    "core/follow_up_rewrite.py",
    "query_selector.py",
    "core/answer_planner.py",
]
patterns = [
    re.compile(r'\\.get\\("last_subject"\\)'),
    re.compile(r'\\["last_subject"\\]'),
    re.compile(r"\\bget_last_subject\\b"),
    re.compile(r"\\bset_last_subject\\b"),
    re.compile(r"\\bclear_last_subject\\b"),
    re.compile(r"\\bget_pending_clarify\\b"),
    re.compile(r"\\bset_pending_clarify\\b"),
    re.compile(r"\\bfocus_from_legacy_session\\b"),
]
offenders = []
for rel in files:
    path = root / rel
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in patterns:
            if pattern.search(line):
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
