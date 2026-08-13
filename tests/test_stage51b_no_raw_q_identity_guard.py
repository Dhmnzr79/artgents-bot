"""Static guard: Stage 5.1B identity modules must not import keyword helpers."""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

_STAGE_51B_MODULES = (
    "contracts/ui_service_action.py",
    "contracts/authored_service_alternative.py",
    "contracts/service_reference.py",
    "core/service_reference_catalog.py",
    "core/target_ui_service_action.py",
    "core/service_availability_presentation.py",
    "core/sales_one_plus_semantic_authority.py",
    "core/one_call_envelope_protocol.py",
    "core/one_call_presentation_pass.py",
)

_FORBIDDEN_SYMBOLS = frozenset(
    {
        "find_service_alternative",
        "find_service_alternative_note",
        "service_alternative_quick_replies",
        "build_service_not_offered_answer",
        "match_service_from_bundle",
        "match_service_from_target_catalog",
        "resolve_target_service_term",
    }
)


def _imported_and_called_names(path: Path) -> tuple[set[str], set[str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[-1])
                if alias.asname:
                    imported.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
                if alias.asname:
                    imported.add(alias.asname)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
    return imported, called


def test_stage51b_modules_do_not_import_keyword_helpers() -> None:
    offenders: list[str] = []
    for relative in _STAGE_51B_MODULES:
        path = _REPO / relative
        imported, called = _imported_and_called_names(path)
        hits = sorted(_FORBIDDEN_SYMBOLS & (imported | called))
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == []
