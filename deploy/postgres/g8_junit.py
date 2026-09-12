"""Parse pytest JUnit XML for fail-closed zero-skipped enforcement."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def parse_pytest_junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    if root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        raise ValueError("invalid_junit_root")

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        totals["tests"] += int(suite.attrib.get("tests", 0))
        totals["failures"] += int(suite.attrib.get("failures", 0))
        totals["errors"] += int(suite.attrib.get("errors", 0))
        totals["skipped"] += int(suite.attrib.get("skipped", 0))
    return totals


def assert_junit_exact_passed(path: Path, *, expected_passed: int) -> None:
    stats = parse_pytest_junit(path)
    if stats["skipped"] or stats["failures"] or stats["errors"]:
        raise RuntimeError(f"junit_not_clean:{stats}")
    if stats["tests"] != expected_passed:
        raise RuntimeError(f"junit_test_count_mismatch:{stats['tests']}!={expected_passed}")
