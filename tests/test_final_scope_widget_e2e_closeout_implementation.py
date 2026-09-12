"""COMPLETION checker for FINAL_SCOPE_WIDGET_E2E_CLOSEOUT implementation."""

from __future__ import annotations

import ast
from pathlib import Path

import config
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    LIVE_RESULT_ARTIFACT_PATH,
    assert_frozen_retry4_live_artifacts_unchanged,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

_SCAN_ROOTS = (
    _REPO_ROOT / "config.py",
    _REPO_ROOT / "core",
    _REPO_ROOT / "evals" / "v5",
    _REPO_ROOT / "tests",
)

_SCAN_SKIP_PARTS = frozenset(
    {
        "artifacts",
        "__pycache__",
    }
)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py"}:
                continue
            if any(part in _SCAN_SKIP_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


def test_config_has_no_a9_patient_scope_authority_flag() -> None:
    assert not hasattr(config, "A9_PATIENT_SCOPE_AUTHORITY")


def test_product_and_harness_code_has_no_a9_flag_symbol() -> None:
    offenders: list[str] = []
    usage_markers = (
        "A9_PATIENT_SCOPE_AUTHORITY =",
        "getenv(\"A9_PATIENT_SCOPE_AUTHORITY\"",
        "setenv(\"A9_PATIENT_SCOPE_AUTHORITY\"",
        "from config import A9_PATIENT_SCOPE_AUTHORITY",
        "config.A9_PATIENT_SCOPE_AUTHORITY",
        "import A9_PATIENT_SCOPE_AUTHORITY",
    )
    for path in _iter_scan_files():
        if path.name in {
            "test_final_scope_widget_e2e_closeout_implementation.py",
            "test_final_scope_widget_e2e_closeout_governance.py",
            "test_final_scope_post_retry3_composer_action_context_governance.py",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in usage_markers):
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert not offenders, offenders


def test_resolve_effective_scope_always_merges() -> None:
    source = (_REPO_ROOT / "core" / "target_effective_scope.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_effective_scope"
    )
    fn_source = ast.get_source_segment(source, fn) or ""
    assert "merge_effective_scope_axes" in fn_source
    assert "A9_PATIENT_SCOPE_AUTHORITY" not in fn_source


def test_runtime_turn_always_projects_patient_scope() -> None:
    source = (_REPO_ROOT / "core" / "target_runtime_turn.py").read_text(encoding="utf-8")
    assert "project_patient_scope_from_turn_frame(turn_frame)" in source
    assert "A9_PATIENT_SCOPE_AUTHORITY" not in source


def test_frozen_retry4_artifacts_unchanged_after_closeout() -> None:
    assert_frozen_retry4_live_artifacts_unchanged()
    payload_text = LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8")
    assert '"final_verdict": "PENDING_MANUAL_REVIEW"' in payload_text


def test_frozen_widget_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
