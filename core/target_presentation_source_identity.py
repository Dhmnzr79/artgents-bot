"""Validated MD source identity for FullContext presentation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode

_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)


class _StrictFrontmatterLoader(yaml.SafeLoader):
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
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "duplicate key",
                    key_node.start_mark,
                    str(key),
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _md_root(md_root: Path) -> Path:
    resolved = md_root.resolve()
    if not resolved.is_dir():
        raise ValueError("presentation_md_root_invalid")
    return resolved


def normalize_content_ref(raw: object) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    if not text or "/" in text or ".." in text:
        return None
    if not text.endswith(".md"):
        text = f"{text}.md"
    return text


def is_valid_content_ref(md_root: Path, content_ref: str) -> bool:
    ref = normalize_content_ref(content_ref)
    if ref is None:
        return False
    root = _md_root(md_root)
    candidate = (root / ref).resolve()
    try:
        return candidate.is_relative_to(root) and candidate.is_file()
    except (OSError, ValueError):
        return False


def validate_used_content_refs(
    md_root: Path,
    refs: tuple[str, ...],
) -> tuple[str, ...]:
    validated: list[str] = []
    seen: set[str] = set()
    for raw in refs:
        ref = normalize_content_ref(raw)
        if ref is None or ref in seen:
            continue
        if not is_valid_content_ref(md_root, ref):
            continue
        seen.add(ref)
        validated.append(ref)
    return tuple(validated)


def read_doc_presentation_meta(
    md_root: Path,
    content_ref: str,
) -> dict[str, Any]:
    ref = normalize_content_ref(content_ref)
    if ref is None or not is_valid_content_ref(md_root, ref):
        return {}
    root = _md_root(md_root)
    text = (root / ref).read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        return {}
    try:
        frontmatter = yaml.load(match.group("yaml"), Loader=_StrictFrontmatterLoader)
    except yaml.YAMLError:
        return {}
    if not isinstance(frontmatter, dict):
        return {}
    return frontmatter
