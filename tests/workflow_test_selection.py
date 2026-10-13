"""Read the plain pytest argument files referenced by release workflows, offline only."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RE = re.compile(r"tests/release/[a-z]+\.txt")
TEST_RE = re.compile(r"tests/test_[a-zA-Z0-9_]+\.py")


def read_selection(path: Path) -> tuple[str, ...]:
    entries = tuple(path.read_text(encoding="utf-8").splitlines())
    assert entries, f"Empty release selection: {path}"
    assert len(entries) == len(set(entries)), f"Duplicate entries: {path}"
    for entry in entries:
        assert TEST_RE.fullmatch(entry), f"Not an exact test file: {entry!r}"
        assert (ROOT / entry).is_file(), f"Missing test: {entry}"
    return entries


def selected_tests(block: str) -> set[str]:
    paths = set(TEST_RE.findall(block))
    for name in set(MANIFEST_RE.findall(block)):
        paths.update(read_selection(ROOT / name))
    return paths


def with_test_selection(block: str) -> str:
    return block + "\n" + "\n".join(sorted(selected_tests(block)))
