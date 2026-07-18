from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from core import response_schema_kb_index
from core.response_schema_kb_index import (
    ResponseSchemaKbIndexError,
    build_response_schema_kb_refs,
)


def _write(root: Path, relative_path: str, text: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _assert_error(
    exc_info: pytest.ExceptionInfo[ResponseSchemaKbIndexError],
    *,
    code: str,
    path: Path,
    cause_type: type[BaseException],
) -> None:
    error = exc_info.value
    assert error.code == code
    assert error.path == path
    assert isinstance(error.__cause__, cause_type)


def test_builds_exact_nested_refs_in_lexical_order(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "zeta.md",
        "### Detail {#detail_two}\n## Overview {#Zeta.1}\n",
    )
    _write(
        tmp_path,
        "folder/alpha.md",
        "### Approved {#Alpha-one}\n",
    )

    assert build_response_schema_kb_refs(tmp_path) == (
        "kb:folder/alpha.md#Alpha-one",
        "kb:zeta.md#Zeta.1",
        "kb:zeta.md#detail_two",
    )


def test_ignores_non_target_headings_anchors_and_suffixes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "visible.md",
        "# H1 {#one}\n## No anchor\n#### H4 {#four}\n"
        "<a id=\"html\"></a>\n## Auto slug\n",
    )
    _write(tmp_path, "ignored.MD", "### Upper {#upper}\n")
    _write(tmp_path, "ignored.txt", "### Text {#text}\n")

    assert build_response_schema_kb_refs(tmp_path) == ()


def test_fence_subset_is_deterministic(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "fences.md",
        "```python\n"
        "### Hidden backtick {#hidden_backtick}\n"
        "~~~\n"
        "``\n"
        " ```\n"
        "```\n"
        "### Visible one {#visible_one}\n"
        "~~~ info\n"
        "### Hidden tilde {#hidden_tilde}\n"
        "```\n"
        "~~\n"
        " ~~~\n"
        "~~~~\t\n"
        "### Visible two {#visible_two}\n"
        "``` unclosed\n"
        "### Hidden to EOF {#hidden_eof}\n",
    )

    assert build_response_schema_kb_refs(tmp_path) == (
        "kb:fences.md#visible_one",
        "kb:fences.md#visible_two",
    )


def test_empty_root_returns_empty_tuple(tmp_path: Path) -> None:
    assert build_response_schema_kb_refs(tmp_path) == ()


@pytest.mark.parametrize(
    ("root_factory", "cause_type"),
    [
        (lambda root: str(root), TypeError),
        (lambda root: root / "missing", FileNotFoundError),
        (lambda root: _write(root, "file.md", ""), NotADirectoryError),
    ],
)
def test_rejects_invalid_roots(
    tmp_path: Path,
    root_factory: object,
    cause_type: type[BaseException],
) -> None:
    root = root_factory(tmp_path)  # type: ignore[operator]
    with pytest.raises(ResponseSchemaKbIndexError) as exc_info:
        build_response_schema_kb_refs(root)  # type: ignore[arg-type]

    _assert_error(
        exc_info,
        code="md_root_invalid",
        path=Path("."),
        cause_type=cause_type,
    )


def test_invalid_utf8_has_typed_relative_error(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "broken.md"
    path.parent.mkdir()
    path.write_bytes(b"\xff")

    with pytest.raises(ResponseSchemaKbIndexError) as exc_info:
        build_response_schema_kb_refs(tmp_path)

    _assert_error(
        exc_info,
        code="file_read_failed",
        path=Path("nested/broken.md"),
        cause_type=UnicodeDecodeError,
    )


@pytest.mark.parametrize(
    "heading",
    [
        "### Empty {#}",
        "### Missing close {#bad",
        "### Invalid ID {#bad id}",
        "### Text after {#id} text",
        "### No separator{#id}",
        "### Multiple {#one} {#two}",
        "###  {#id}",
    ],
)
def test_rejects_malformed_anchor_forms(tmp_path: Path, heading: str) -> None:
    _write(tmp_path, "nested/bad.md", f"{heading}\n")

    with pytest.raises(ResponseSchemaKbIndexError) as exc_info:
        build_response_schema_kb_refs(tmp_path)

    _assert_error(
        exc_info,
        code="chunk_anchor_invalid",
        path=Path("nested/bad.md"),
        cause_type=ValueError,
    )


def test_duplicate_anchor_and_bad_file_order_are_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "z_bad.md", "## Z {#dup}\n### Z2 {#dup}\n")
    _write(tmp_path, "a_bad.md", "## A {#dup}\n### A2 {#dup}\n")

    with pytest.raises(ResponseSchemaKbIndexError) as exc_info:
        build_response_schema_kb_refs(tmp_path)

    _assert_error(
        exc_info,
        code="chunk_anchor_duplicate",
        path=Path("a_bad.md"),
        cause_type=ValueError,
    )


def test_calls_are_stateless_and_do_not_write_files(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write(first, "one.md", "### One {#one}\n")
    _write(second, "two.md", "### Two {#two}\n")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert build_response_schema_kb_refs(first) == ("kb:one.md#one",)
    assert build_response_schema_kb_refs(second) == ("kb:two.md#two",)
    assert build_response_schema_kb_refs(first) == ("kb:one.md#one",)
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_real_s1_validation_is_wrapped_for_invalid_constructed_ref(tmp_path: Path) -> None:
    _write(tmp_path, "bad#doc.md", "### Chunk {#chunk}\n")

    with pytest.raises(ResponseSchemaKbIndexError) as exc_info:
        build_response_schema_kb_refs(tmp_path)

    _assert_error(
        exc_info,
        code="source_ref_invalid",
        path=Path("bad#doc.md"),
        cause_type=ValidationError,
    )


def test_module_has_only_foundation_imports_and_no_side_effect_calls() -> None:
    source = inspect.getsource(response_schema_kb_index)
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert imported_modules <= {
        "__future__",
        "contracts.response_schema",
        "pathlib",
        "pydantic",
        "re",
        "typing",
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_attributes.isdisjoint(
        {
            "mkdir",
            "open",
            "rename",
            "replace",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
    )
    assert "open" not in called_names
