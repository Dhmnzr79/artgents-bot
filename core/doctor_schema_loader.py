"""Strict offline JSON loader for the future doctor catalog (S8, unwired)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn

from pydantic import ValidationError

from contracts.doctor_schema import TargetDoctorCatalog


class DuplicateDoctorCatalogKeyError(ValueError):
    """A doctor-catalog JSON mapping repeats a key before schema validation."""


class DoctorCatalogLoadError(Exception):
    """Typed fail-closed error for one explicit doctor-catalog source."""

    def __init__(self, code: str, path: Path) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path.as_posix()}")


def _raise_load_error(code: str, path: Path, cause: BaseException) -> NoReturn:
    raise DoctorCatalogLoadError(code, path) from cause


def _require_catalog_file(catalog_path: object) -> Path:
    if not isinstance(catalog_path, Path):
        _raise_load_error(
            "catalog_path_invalid",
            Path("."),
            TypeError("catalog_path_must_be_pathlib_path"),
        )

    try:
        exists = catalog_path.exists()
    except OSError as exc:
        _raise_load_error("catalog_path_invalid", catalog_path, exc)
    if not exists:
        _raise_load_error(
            "catalog_path_invalid",
            catalog_path,
            FileNotFoundError(str(catalog_path)),
        )

    try:
        is_file = catalog_path.is_file()
        is_directory = catalog_path.is_dir()
    except OSError as exc:
        _raise_load_error("catalog_path_invalid", catalog_path, exc)
    if not is_file:
        cause: OSError
        if is_directory:
            cause = IsADirectoryError(str(catalog_path))
        else:
            cause = OSError("catalog_path_must_be_regular_file")
        _raise_load_error("catalog_path_invalid", catalog_path, cause)
    return catalog_path


def _read_utf8(catalog_path: Path) -> str:
    try:
        return catalog_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        _raise_load_error("file_read_failed", catalog_path, exc)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key, value in pairs:
        if key in mapping:
            raise DuplicateDoctorCatalogKeyError(f"duplicate_mapping_key:{key!r}")
        mapping[key] = value
    return mapping


def _read_json_mapping(catalog_path: Path) -> dict[str, Any]:
    text = _read_utf8(catalog_path)
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except DuplicateDoctorCatalogKeyError as exc:
        _raise_load_error("duplicate_key", catalog_path, exc)
    except json.JSONDecodeError as exc:
        _raise_load_error("json_invalid", catalog_path, exc)
    if not isinstance(raw, dict):
        _raise_load_error(
            "top_level_type_invalid",
            catalog_path,
            TypeError("doctor_catalog_top_level_must_be_mapping"),
        )
    return raw


def load_doctor_catalog(catalog_path: Path) -> TargetDoctorCatalog:
    """Load one explicit S5 doctor catalog without fallback or shared state."""

    path = _require_catalog_file(catalog_path)
    raw = _read_json_mapping(path)
    try:
        return TargetDoctorCatalog.model_validate(raw)
    except ValidationError as exc:
        _raise_load_error("schema_invalid", path, exc)
