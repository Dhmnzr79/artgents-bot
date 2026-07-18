"""Strict offline loader for the future response-data target pack (S2).

The loader accepts an explicit trusted directory and returns the frozen S1 aggregate.
It is intentionally not connected to client resolution, caches, or product runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn

import yaml
from pydantic import ValidationError
from yaml.nodes import MappingNode

from contracts.response_schema import ResponseSchemaBundle


class DuplicateKeyError(ValueError):
    """A JSON/YAML mapping repeats a key before schema validation."""


class YamlMergeKeyError(yaml.YAMLError):
    """Target YAML forbids merge-key semantics."""


class ResponseSchemaLoadError(Exception):
    """Typed fail-closed error for one relative target-pack source."""

    def __init__(self, code: str, path: Path) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path.as_posix()}")


def _raise_load_error(code: str, path: Path, cause: BaseException) -> NoReturn:
    raise ResponseSchemaLoadError(code, path) from cause


class _TargetSafeLoader(yaml.SafeLoader):
    """SafeLoader variant with isolated resolver state and strict mappings."""

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
                raise YamlMergeKeyError("yaml_merge_key_forbidden")
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
                raise DuplicateKeyError(f"duplicate_mapping_key:{key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


for _resolver_key, _resolver_entries in list(_TargetSafeLoader.yaml_implicit_resolvers.items()):
    _TargetSafeLoader.yaml_implicit_resolvers[_resolver_key] = [
        entry
        for entry in _resolver_entries
        if entry[0] != "tag:yaml.org,2002:timestamp"
    ]


_SERVICE_CATALOG = Path("service_catalog.json")
_BRAND_CATALOG = Path("brand_catalog.json")
_CLINIC_STRATEGY = Path("clinic_strategy.yaml")
_MARKETING = Path("marketing.yaml")
_FACTS = Path("pricebook/facts.json")
_SERVICES_DIR = Path("pricebook/services")


def _require_pack_root(pack_root: object) -> Path:
    if not isinstance(pack_root, Path):
        _raise_load_error(
            "pack_root_invalid",
            Path("."),
            TypeError("pack_root_must_be_pathlib_path"),
        )
    if not pack_root.exists():
        _raise_load_error(
            "pack_root_invalid",
            Path("."),
            FileNotFoundError(str(pack_root)),
        )
    if not pack_root.is_dir():
        _raise_load_error(
            "pack_root_invalid",
            Path("."),
            NotADirectoryError(str(pack_root)),
        )
    return pack_root


def _require_file(pack_root: Path, relative_path: Path) -> Path:
    path = pack_root / relative_path
    if not path.exists():
        _raise_load_error(
            "required_path_missing",
            relative_path,
            FileNotFoundError(str(path)),
        )
    if not path.is_file():
        _raise_load_error(
            "required_path_missing",
            relative_path,
            IsADirectoryError(str(path)),
        )
    return path


def _require_directory(pack_root: Path, relative_path: Path) -> Path:
    path = pack_root / relative_path
    if not path.exists():
        _raise_load_error(
            "required_path_missing",
            relative_path,
            FileNotFoundError(str(path)),
        )
    if not path.is_dir():
        _raise_load_error(
            "required_path_missing",
            relative_path,
            NotADirectoryError(str(path)),
        )
    return path


def _read_utf8(path: Path, relative_path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        _raise_load_error("file_read_failed", relative_path, exc)


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key, value in pairs:
        if key in mapping:
            raise DuplicateKeyError(f"duplicate_mapping_key:{key!r}")
        mapping[key] = value
    return mapping


def _read_json_mapping(path: Path, relative_path: Path) -> dict[str, Any]:
    text = _read_utf8(path, relative_path)
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_json_pairs)
    except DuplicateKeyError as exc:
        _raise_load_error("duplicate_key", relative_path, exc)
    except json.JSONDecodeError as exc:
        _raise_load_error("json_invalid", relative_path, exc)
    if not isinstance(raw, dict):
        _raise_load_error(
            "top_level_type_invalid",
            relative_path,
            TypeError("json_top_level_must_be_mapping"),
        )
    return raw


def _read_yaml_mapping(path: Path, relative_path: Path) -> dict[str, Any]:
    text = _read_utf8(path, relative_path)
    try:
        raw = yaml.load(text, Loader=_TargetSafeLoader)
    except DuplicateKeyError as exc:
        _raise_load_error("duplicate_key", relative_path, exc)
    except yaml.YAMLError as exc:
        _raise_load_error("yaml_invalid", relative_path, exc)
    if not isinstance(raw, dict):
        _raise_load_error(
            "top_level_type_invalid",
            relative_path,
            TypeError("yaml_top_level_must_be_mapping"),
        )
    return raw


def _list_offer_files(pack_root: Path, services_dir: Path) -> list[tuple[Path, Path]]:
    try:
        entries = list(services_dir.iterdir())
    except OSError as exc:
        _raise_load_error("file_read_failed", _SERVICES_DIR, exc)
    files = sorted(
        (entry for entry in entries if entry.is_file() and entry.suffix == ".json"),
        key=lambda entry: entry.name,
    )
    return [(entry, entry.relative_to(pack_root)) for entry in files]


def load_response_schema_bundle(pack_root: Path) -> ResponseSchemaBundle:
    """Load and validate one explicit target pack without fallback or shared state."""

    root = _require_pack_root(pack_root)

    service_catalog_path = _require_file(root, _SERVICE_CATALOG)
    brand_catalog_path = _require_file(root, _BRAND_CATALOG)
    facts_path = _require_file(root, _FACTS)
    strategy_path = _require_file(root, _CLINIC_STRATEGY)
    marketing_path = _require_file(root, _MARKETING)
    services_dir = _require_directory(root, _SERVICES_DIR)

    services = _read_json_mapping(service_catalog_path, _SERVICE_CATALOG)
    brands = _read_json_mapping(brand_catalog_path, _BRAND_CATALOG)
    facts = _read_json_mapping(facts_path, _FACTS)
    strategy = _read_yaml_mapping(strategy_path, _CLINIC_STRATEGY)
    marketing = _read_yaml_mapping(marketing_path, _MARKETING)
    offers = [
        _read_json_mapping(path, relative_path)
        for path, relative_path in _list_offer_files(root, services_dir)
    ]

    try:
        return ResponseSchemaBundle.model_validate(
            {
                "services": services,
                "brands": brands,
                "offers": offers,
                "facts": facts,
                "strategy": strategy,
                "marketing": marketing,
            }
        )
    except ValidationError as exc:
        _raise_load_error("schema_invalid", Path("."), exc)
