"""Strict explicit-root reader for service consultation frontmatter (S18, unwired)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NoReturn

import yaml
from pydantic import ValidationError
from yaml.nodes import MappingNode

from contracts.service_consultation import ServiceConsultationValue


_FRONTMATTER = re.compile(
    r"^---[ \t]*\n(?P<body>.*?)\n---[ \t]*(?:\n|$)",
    re.DOTALL,
)
_FRONTMATTER_OPENER = re.compile(r"^---[ \t]*(?:\n|$)")


class DuplicateConsultationFrontmatterKeyError(ValueError):
    """A frontmatter mapping repeats a key before contract validation."""


class ServiceConsultationSourceError(Exception):
    """Typed fail-closed error for one Markdown consultation source."""

    def __init__(self, code: str, path: Path) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path.as_posix()}")


def _raise_source_error(code: str, path: Path, cause: BaseException) -> NoReturn:
    raise ServiceConsultationSourceError(code, path) from cause


class _ConsultationSafeLoader(yaml.SafeLoader):
    """Isolated SafeLoader that rejects duplicate and merge keys."""

    yaml_implicit_resolvers = {
        key: list(resolvers)
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"expected a mapping node, but found {node.id}",
                node.start_mark,
            )
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            if key_node.value == "<<" or key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.YAMLError("yaml_merge_key_forbidden")
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise DuplicateConsultationFrontmatterKeyError(
                    f"duplicate_mapping_key:{key!r}"
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _require_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _raise_source_error(
            "md_root_invalid",
            Path("."),
            TypeError("md_root_must_be_pathlib_path"),
        )
    try:
        exists = md_root.exists()
        is_dir = md_root.is_dir()
    except OSError as exc:
        _raise_source_error("md_root_invalid", Path("."), exc)
    if not exists:
        _raise_source_error(
            "md_root_invalid",
            Path("."),
            FileNotFoundError(str(md_root)),
        )
    if not is_dir:
        _raise_source_error(
            "md_root_invalid",
            Path("."),
            NotADirectoryError(str(md_root)),
        )
    return md_root


def _discover_markdown_files(md_root: Path) -> list[tuple[Path, Path]]:
    try:
        paths = list(md_root.rglob("*"))
    except OSError as exc:
        _raise_source_error("file_read_failed", Path("."), exc)
    files = [path for path in paths if path.is_file() and path.suffix == ".md"]
    return sorted(
        ((path, path.relative_to(md_root)) for path in files),
        key=lambda item: item[1].as_posix(),
    )


def _read_utf8(path: Path, relative_path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        _raise_source_error("file_read_failed", relative_path, exc)


def _frontmatter_mapping(text: str, relative_path: Path) -> dict[str, Any] | None:
    if _FRONTMATTER_OPENER.match(text) is None:
        return None
    match = _FRONTMATTER.match(text)
    if match is None:
        _raise_source_error(
            "frontmatter_invalid",
            relative_path,
            ValueError("frontmatter_delimiter_invalid"),
        )
    try:
        raw = yaml.load(match.group("body"), Loader=_ConsultationSafeLoader)
    except DuplicateConsultationFrontmatterKeyError as exc:
        _raise_source_error("duplicate_key", relative_path, exc)
    except yaml.YAMLError as exc:
        _raise_source_error("frontmatter_invalid", relative_path, exc)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        _raise_source_error(
            "frontmatter_type_invalid",
            relative_path,
            TypeError("frontmatter_must_be_mapping"),
        )
    return raw


def build_service_consultation_values(
    md_root: Path,
) -> tuple[ServiceConsultationValue, ...]:
    """Read optional consultation values from one explicit Markdown root."""

    root = _require_md_root(md_root)
    records: list[ServiceConsultationValue] = []
    for path, relative_path in _discover_markdown_files(root):
        raw = _read_utf8(path, relative_path)
        frontmatter = _frontmatter_mapping(raw, relative_path)
        if frontmatter is None or "consultation_value" not in frontmatter:
            continue
        if frontmatter.get("doc_type") != "service":
            _raise_source_error(
                "consultation_doc_type_invalid",
                relative_path,
                ValueError("consultation_value_requires_service_doc_type"),
            )
        try:
            records.append(
                ServiceConsultationValue(
                    content_ref=relative_path.as_posix(),
                    value=frontmatter["consultation_value"],
                )
            )
        except ValidationError as exc:
            _raise_source_error("consultation_value_invalid", relative_path, exc)
    return tuple(records)
