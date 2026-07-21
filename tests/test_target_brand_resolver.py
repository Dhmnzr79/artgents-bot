from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from contracts.response_schema import TargetBrandCatalog
from core.target_brand_resolver import (
    TargetBrandResolution,
    TargetBrandResolutionError,
    resolve_target_brand_term,
)


def _catalog() -> TargetBrandCatalog:
    return TargetBrandCatalog.model_validate(
        {
            "version": 1,
            "brands": {
                "nobel_biocare": {
                    "canonical_name": "Nobel Biocare",
                    "country": "Switzerland",
                    "aliases": ["Nobel", "Нобель", "Нобел"],
                },
                "impro": {
                    "canonical_name": "Impro",
                    "country": "Germany",
                    "aliases": ["ИМПРО", "impro"],
                },
                "strasse": {
                    "canonical_name": "Straße",
                    "country": "Germany",
                    "aliases": [],
                },
            },
        }
    )


def _collision_catalog() -> TargetBrandCatalog:
    return TargetBrandCatalog.model_validate(
        {
            "version": 1,
            "brands": {
                "brand_a": {
                    "canonical_name": "Brand A",
                    "country": "Country A",
                    "aliases": ["shared", "brand_b"],
                },
                "brand_b": {
                    "canonical_name": "Shared",
                    "country": "Country B",
                    "aliases": ["second"],
                },
                "brand_c": {
                    "canonical_name": "Brand C",
                    "country": "Country C",
                    "aliases": ["shared"],
                },
            },
        }
    )


def test_exact_shape_and_canonical_record_are_detached() -> None:
    catalog = _catalog()
    result = resolve_target_brand_term(catalog, "Nobel")

    assert result is not None
    assert [field.name for field in fields(TargetBrandResolution)] == [
        "brand_id",
        "brand",
    ]
    assert result.brand_id == "nobel_biocare"
    assert result.brand.model_dump() == catalog.brands["nobel_biocare"].model_dump()
    assert result.brand is not catalog.brands["nobel_biocare"]
    assert result.brand.aliases is not catalog.brands["nobel_biocare"].aliases
    with pytest.raises(FrozenInstanceError):
        result.brand_id = "other"  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize("term", [None, 7, True, "", " \t "])
def test_invalid_term_has_stable_error(term: object) -> None:
    with pytest.raises(TargetBrandResolutionError) as exc_info:
        resolve_target_brand_term(_catalog(), term)  # type: ignore[arg-type]

    error = exc_info.value
    assert error.code == "brand_resolution_term_invalid"
    assert error.value == term
    assert error.candidate_brand_ids == ()
    assert str(error) == f"brand_resolution_term_invalid: {term!r}"


@pytest.mark.parametrize(
    ("term", "expected_id"),
    [
        ("nobel_biocare", "nobel_biocare"),
        ("Nobel Biocare", "nobel_biocare"),
        ("Nobel", "nobel_biocare"),
        ("Нобель", "nobel_biocare"),
        ("Нобел", "nobel_biocare"),
        ("impro", "impro"),
        ("Impro", "impro"),
        ("ИМПРО", "impro"),
    ],
)
def test_id_canonical_name_and_every_alias_resolve(
    term: str, expected_id: str
) -> None:
    result = resolve_target_brand_term(_catalog(), term)

    assert result is not None
    assert result.brand_id == expected_id


@pytest.mark.parametrize(
    ("term", "expected_id"),
    [
        ("  NOBEL BIOCARE  ", "nobel_biocare"),
        ("\tнОбЕлЬ\n", "nobel_biocare"),
        ("STRASSE", "strasse"),
    ],
)
def test_only_outer_whitespace_and_unicode_casefold_are_normalized(
    term: str, expected_id: str
) -> None:
    result = resolve_target_brand_term(_catalog(), term)

    assert result is not None
    assert result.brand_id == expected_id


@pytest.mark.parametrize(
    "term",
    [
        "Nobel!",
        "сколько стоит Nobel",
        "имплант Nobel Biocare",
        "Nobe",
        "Нобелем",
        "Нобэл",
        "Нобель Биокаре",
        "Straumann",
        "brand-a",
    ],
)
def test_unknown_phrase_punctuation_typo_and_morphology_never_fuzzy_match(
    term: str,
) -> None:
    assert resolve_target_brand_term(_catalog(), term) is None


def test_same_brand_id_canonical_and_alias_matches_are_deduplicated() -> None:
    result = resolve_target_brand_term(_catalog(), "IMPRO")

    assert result is not None
    assert result.brand_id == "impro"


@pytest.mark.parametrize(
    ("term", "expected_ids"),
    [
        ("shared", ("brand_a", "brand_b", "brand_c")),
        ("brand_b", ("brand_a", "brand_b")),
    ],
)
def test_cross_brand_collision_fails_closed_in_catalog_order(
    term: str, expected_ids: tuple[str, ...]
) -> None:
    with pytest.raises(TargetBrandResolutionError) as exc_info:
        resolve_target_brand_term(_collision_catalog(), term)

    error = exc_info.value
    assert error.code == "brand_resolution_ambiguous"
    assert error.value == term
    assert error.candidate_brand_ids == expected_ids
    assert str(error) == f"brand_resolution_ambiguous: {term!r}"


def test_repeated_calls_are_stateless_and_do_not_mutate_catalog() -> None:
    catalog = _catalog()
    before = catalog.model_dump()

    first = resolve_target_brand_term(catalog, "Nobel")
    assert first is not None
    first.brand.canonical_name = "Output only"
    first.brand.aliases.append("output alias")
    second = resolve_target_brand_term(catalog, "Nobel")

    assert second is not None
    assert second.brand.canonical_name == "Nobel Biocare"
    assert second.brand.aliases == ["Nobel", "Нобель", "Нобел"]
    assert catalog.model_dump() == before


def test_exact_signature_and_import_firewall() -> None:
    signature = inspect.signature(resolve_target_brand_term)
    assert list(signature.parameters) == ["brand_catalog", "brand_term"]

    tree = ast.parse(Path("core/target_brand_resolver.py").read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "contracts.response_schema",
    }
    forbidden_calls = {
        "find",
        "search",
        "match",
        "fullmatch",
        "split",
        "translate",
        "skip",
        "skipif",
        "xfail",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
        for node in ast.walk(tree)
    )
