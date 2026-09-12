from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.response_schema import TargetService
from contracts.service_consultation import (
    ServiceConsultationRefError,
    ServiceConsultationValue,
    validate_service_consultation_refs,
)
from core import service_consultation_source
from core.service_consultation_source import (
    DuplicateConsultationFrontmatterKeyError,
    ServiceConsultationSourceError,
    build_service_consultation_values,
)


def _write(root: Path, relative_path: str, text: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _service(
    *,
    content_ref: str | None,
    option_content_ref: str | None = None,
) -> TargetService:
    options = []
    if option_content_ref is not None:
        options.append(
            {
                "option_id": "variant",
                "name": "Variant",
                "content_ref": option_content_ref,
            }
        )
    return TargetService.model_validate(
        {
            "name": "Service",
            "family": "implantology",
            "content_ref": content_ref,
            "selection": {"mode": "direct"},
            "options": options,
        }
    )


def _assert_source_error(
    exc_info: pytest.ExceptionInfo[ServiceConsultationSourceError],
    *,
    code: str,
    path: Path,
    cause_type: type[BaseException],
) -> None:
    error = exc_info.value
    assert error.code == code
    assert error.path == path
    assert isinstance(error.__cause__, cause_type)


def test_reads_optional_same_md_values_in_lexical_order(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "zeta.md",
        "---\ndoc_type: service\nconsultation_value: >\n"
        "  Врач проверит исходные данные.\n---\n## Zeta\n",
    )
    _write(
        tmp_path,
        "folder/alpha.md",
        "---\ndoc_type: service\nconsultation_value: Alpha value\n---\n## Alpha\n",
    )

    assert build_service_consultation_values(tmp_path) == (
        ServiceConsultationValue(
            content_ref="folder/alpha.md",
            value="Alpha value",
        ),
        ServiceConsultationValue(
            content_ref="zeta.md",
            value="Врач проверит исходные данные.",
        ),
    )


def test_body_headings_suggest_h3_and_absent_frontmatter_do_not_create_values(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "frontmatter_without_value.md",
        "---\ndoc_type: service\nsuggest_h3:\n  - consultation-value\n---\n"
        "### Что даст консультация {#consultation-value}\nТекст тела.\n",
    )
    _write(
        tmp_path,
        "body_only.md",
        "## Service\nconsultation_value: body text is not metadata\n",
    )
    _write(
        tmp_path,
        "body_prefix.md",
        "---not-frontmatter\nconsultation_value: body text is not metadata\n",
    )
    _write(
        tmp_path,
        "ignored.MD",
        "---\ndoc_type: service\nconsultation_value: ignored\n---\n",
    )

    assert build_service_consultation_values(tmp_path) == ()


@pytest.mark.parametrize("doc_type", ["faq", "info", "comparison", None, 1])
def test_rejects_consultation_value_outside_service_document(
    tmp_path: Path,
    doc_type: object,
) -> None:
    rendered = "" if doc_type is None else f"doc_type: {doc_type}\n"
    _write(
        tmp_path,
        "wrong.md",
        f"---\n{rendered}consultation_value: value\n---\n",
    )

    with pytest.raises(ServiceConsultationSourceError) as exc_info:
        build_service_consultation_values(tmp_path)

    _assert_source_error(
        exc_info,
        code="consultation_doc_type_invalid",
        path=Path("wrong.md"),
        cause_type=ValueError,
    )


@pytest.mark.parametrize(
    "yaml_value",
    ["''", "'   '", "null", "1", "[]", "{}"],
)
def test_rejects_empty_or_non_string_values(tmp_path: Path, yaml_value: str) -> None:
    _write(
        tmp_path,
        "invalid.md",
        "---\ndoc_type: service\n"
        f"consultation_value: {yaml_value}\n"
        "---\n",
    )

    with pytest.raises(ServiceConsultationSourceError) as exc_info:
        build_service_consultation_values(tmp_path)

    _assert_source_error(
        exc_info,
        code="consultation_value_invalid",
        path=Path("invalid.md"),
        cause_type=ValidationError,
    )


def test_rejects_malformed_duplicate_and_non_mapping_frontmatter(tmp_path: Path) -> None:
    cases = (
        (
            "malformed.md",
            "---\ndoc_type: [service\nconsultation_value: value\n---\n",
            "frontmatter_invalid",
            Exception,
        ),
        (
            "duplicate.md",
            "---\ndoc_type: service\nconsultation_value: one\n"
            "consultation_value: two\n---\n",
            "duplicate_key",
            DuplicateConsultationFrontmatterKeyError,
        ),
        (
            "sequence.md",
            "---\n- doc_type\n- service\n---\n",
            "frontmatter_type_invalid",
            TypeError,
        ),
        (
            "delimiter.md",
            "---\ndoc_type: service\nconsultation_value: value\n",
            "frontmatter_invalid",
            ValueError,
        ),
    )

    for name, text, code, cause_type in cases:
        root = tmp_path / name.removesuffix(".md")
        root.mkdir()
        _write(root, name, text)
        with pytest.raises(ServiceConsultationSourceError) as exc_info:
            build_service_consultation_values(root)
        _assert_source_error(
            exc_info,
            code=code,
            path=Path(name),
            cause_type=cause_type,
        )


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
    with pytest.raises(ServiceConsultationSourceError) as exc_info:
        build_service_consultation_values(root)  # type: ignore[arg-type]

    _assert_source_error(
        exc_info,
        code="md_root_invalid",
        path=Path("."),
        cause_type=cause_type,
    )


def test_invalid_utf8_and_constructed_content_ref_are_typed(tmp_path: Path) -> None:
    invalid_utf8_root = tmp_path / "utf8"
    invalid_utf8_root.mkdir()
    (invalid_utf8_root / "broken.md").write_bytes(b"\xff")
    with pytest.raises(ServiceConsultationSourceError) as exc_info:
        build_service_consultation_values(invalid_utf8_root)
    _assert_source_error(
        exc_info,
        code="file_read_failed",
        path=Path("broken.md"),
        cause_type=UnicodeDecodeError,
    )

    invalid_ref_root = tmp_path / "ref"
    invalid_ref_root.mkdir()
    _write(
        invalid_ref_root,
        "bad#doc.md",
        "---\ndoc_type: service\nconsultation_value: value\n---\n",
    )
    with pytest.raises(ServiceConsultationSourceError) as exc_info:
        build_service_consultation_values(invalid_ref_root)
    _assert_source_error(
        exc_info,
        code="consultation_value_invalid",
        path=Path("bad#doc.md"),
        cause_type=ValidationError,
    )


@pytest.mark.parametrize(
    "content_ref",
    [
        "",
        " service.md",
        "service.md ",
        "/service.md",
        "C:/service.md",
        "folder\\service.md",
        "folder//service.md",
        "./service.md",
        "folder/../service.md",
        "service.MD",
        "service.txt",
        "service.md#chunk",
        "service.md?x=1",
    ],
)
def test_model_rejects_invalid_content_refs(content_ref: str) -> None:
    with pytest.raises(ValidationError):
        ServiceConsultationValue(content_ref=content_ref, value="value")


def test_model_is_strict_frozen_extra_forbid_and_normalizes_outer_space() -> None:
    record = ServiceConsultationValue(
        content_ref="nested/service.md",
        value="  line one\nline two  ",
    )
    assert record.value == "line one\nline two"

    with pytest.raises(ValidationError):
        ServiceConsultationValue(content_ref=1, value="value")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ServiceConsultationValue(
            content_ref="service.md",
            value="value",
            extra=True,
        )  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        record.value = "changed"


def test_calls_are_stateless_lexical_and_do_not_write(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write(
        first,
        "b.md",
        "---\ndoc_type: service\nconsultation_value: b\n---\n",
    )
    _write(
        first,
        "a.md",
        "---\ndoc_type: service\nconsultation_value: a\n---\n",
    )
    _write(
        second,
        "only.md",
        "---\ndoc_type: service\nconsultation_value: only\n---\n",
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert [record.content_ref for record in build_service_consultation_values(first)] == [
        "a.md",
        "b.md",
    ]
    assert [record.value for record in build_service_consultation_values(second)] == [
        "only"
    ]
    assert [record.value for record in build_service_consultation_values(first)] == [
        "a",
        "b",
    ]
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_cross_ref_accepts_service_option_shared_ref_and_optional_absence() -> None:
    records = (
        ServiceConsultationValue(content_ref="service.md", value="service"),
        ServiceConsultationValue(content_ref="option.md", value="option"),
    )
    services = {
        "one": _service(content_ref="service.md", option_content_ref="option.md"),
        "shared": _service(content_ref="service.md"),
        "optional": _service(content_ref=None),
    }

    assert validate_service_consultation_refs(records, services) is None
    assert validate_service_consultation_refs((), services) is None


def test_cross_ref_reports_all_orphans_once_in_sorted_order() -> None:
    records = (
        ServiceConsultationValue(content_ref="z.md", value="z"),
        ServiceConsultationValue(content_ref="owned.md", value="owned"),
        ServiceConsultationValue(content_ref="a.md", value="a"),
        ServiceConsultationValue(content_ref="z.md", value="duplicate ref"),
    )

    with pytest.raises(ServiceConsultationRefError) as exc_info:
        validate_service_consultation_refs(
            records,
            {"owned": _service(content_ref="owned.md")},
        )

    error = exc_info.value
    assert error.code == "consultation_content_refs_orphaned"
    assert error.orphan_content_refs == ("a.md", "z.md")


def test_source_module_has_only_offline_foundation_imports_and_no_write_calls() -> None:
    source = inspect.getsource(service_consultation_source)
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
        "contracts.service_consultation",
        "pathlib",
        "pydantic",
        "re",
        "typing",
        "yaml",
        "yaml.nodes",
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
