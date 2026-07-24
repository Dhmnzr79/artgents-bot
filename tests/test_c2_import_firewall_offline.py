"""C2 product import firewall — active product must not import shadow module."""

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
