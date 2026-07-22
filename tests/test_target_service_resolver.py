from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from contracts.response_schema import TargetService
from core.target_service_resolver import (
    TargetServiceResolution,
    TargetServiceResolutionError,
    resolve_target_service_term,
)


def _service(
    name: str,
    *,
    aliases: list[str],
    active: bool = True,
) -> TargetService:
    return TargetService.model_validate(
        {
            "name": name,
            "aliases": aliases,
            "family": "implantology",
            "roles": ["protocol"],
            "active": active,
            "content_ref": "implantation__service__sample.md",
            "selection": {
                "mode": "scope",
                "extent": ["full_arch"],
                "jaw": ["upper", "lower"],
            },
            "options": [
                {
                    "option_id": "option_one",
                    "name": "Option One",
                    "aliases": ["first option"],
                    "content_ref": "implantation__service__sample.md#option-one",
                    "selection": {"jaw": ["upper"]},
                }
            ],
        }
    )


def _catalog() -> dict[str, TargetService]:
    return {
        "all_on_4": _service(
            "Implantation All-on-4",
            aliases=["All-on-4", "all_on_4", "Все на четырёх"],
        ),
        "strasse_service": _service("Straße Service", aliases=[]),
        "inactive_service": _service(
            "Inactive Service",
            aliases=["inactive", "All-on-4"],
            active=False,
        ),
    }


def _collision_catalog() -> dict[str, TargetService]:
    return {
        "service_a": _service("Service A", aliases=["shared", "service_b"]),
        "service_b": _service("Shared", aliases=["second"]),
        "service_c": _service("Service C", aliases=["shared"]),
        "inactive_shared": _service(
            "Shared",
            aliases=["service_b"],
            active=False,
        ),
    }


def test_exact_shape_and_nested_service_record_are_deep_detached() -> None:
    catalog = _catalog()
    result = resolve_target_service_term(catalog, "All-on-4")

    assert result is not None
    assert [field.name for field in fields(TargetServiceResolution)] == [
        "service_id",
        "service",
    ]
    assert result.service_id == "all_on_4"
    assert result.service.model_dump() == catalog["all_on_4"].model_dump()
    assert result.service is not catalog["all_on_4"]
    assert result.service.aliases is not catalog["all_on_4"].aliases
    assert result.service.selection is not catalog["all_on_4"].selection
    assert result.service.options[0] is not catalog["all_on_4"].options[0]
    with pytest.raises(FrozenInstanceError):
        result.service_id = "other"  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


class _CatalogSubclass(dict[str, TargetService]):
    pass


@pytest.mark.parametrize(
    ("catalog", "expected_value"),
    [
        ([], []),
        (_CatalogSubclass(), _CatalogSubclass()),
        ({7: _service("Seven", aliases=[])}, 7),
        ({"": _service("Blank", aliases=[])}, ""),
        ({"bad": "not a service"}, "not a service"),
    ],
)
def test_invalid_catalog_has_stable_error(
    catalog: object, expected_value: object
) -> None:
    with pytest.raises(TargetServiceResolutionError) as exc_info:
        resolve_target_service_term(catalog, "anything")  # type: ignore[arg-type]

    error = exc_info.value
    assert error.code == "service_resolution_catalog_invalid"
    assert error.value == expected_value
    assert error.candidate_service_ids == ()
    assert str(error) == f"service_resolution_catalog_invalid: {expected_value!r}"


@pytest.mark.parametrize("term", [None, 7, True, "", " \t "])
def test_invalid_term_has_stable_error(term: object) -> None:
    with pytest.raises(TargetServiceResolutionError) as exc_info:
        resolve_target_service_term(_catalog(), term)  # type: ignore[arg-type]

    error = exc_info.value
    assert error.code == "service_resolution_term_invalid"
    assert error.value == term
    assert error.candidate_service_ids == ()
    assert str(error) == f"service_resolution_term_invalid: {term!r}"


@pytest.mark.parametrize(
    "term",
    [
        "all_on_4",
        "Implantation All-on-4",
        "All-on-4",
        "all_on_4",
        "Все на четырёх",
    ],
)
def test_active_id_name_and_every_alias_resolve_exact_service(term: str) -> None:
    result = resolve_target_service_term(_catalog(), term)

    assert result is not None
    assert result.service_id == "all_on_4"


@pytest.mark.parametrize(
    ("term", "expected_id"),
    [
        ("  ALL-ON-4  ", "all_on_4"),
        ("\tвСе На ЧеТыРёХ\n", "all_on_4"),
        ("STRASSE SERVICE", "strasse_service"),
    ],
)
def test_only_outer_whitespace_and_unicode_casefold_are_normalized(
    term: str, expected_id: str
) -> None:
    result = resolve_target_service_term(_catalog(), term)

    assert result is not None
    assert result.service_id == expected_id


@pytest.mark.parametrize(
    "term",
    [
        "All-on-4!",
        "расскажите про All-on-4",
        "сколько стоит All-on-4",
        "All-on-",
        "All on four",
        "всем на четырёх",
        "олл он фор",
        "unknown service",
    ],
)
def test_phrase_punctuation_typo_morphology_and_unknown_never_fuzzy_match(
    term: str,
) -> None:
    assert resolve_target_service_term(_catalog(), term) is None


@pytest.mark.parametrize(
    "term",
    ["inactive_service", "Inactive Service", "inactive"],
)
def test_inactive_exact_labels_return_none_without_active_fallback(term: str) -> None:
    assert resolve_target_service_term(_catalog(), term) is None


def test_inactive_alias_collision_does_not_make_active_result_ambiguous() -> None:
    result = resolve_target_service_term(_catalog(), "All-on-4")

    assert result is not None
    assert result.service_id == "all_on_4"


@pytest.mark.parametrize(
    ("term", "expected_ids"),
    [
        ("shared", ("service_a", "service_b", "service_c")),
        ("service_b", ("service_a", "service_b")),
    ],
)
def test_cross_active_service_collision_fails_closed_in_catalog_order(
    term: str, expected_ids: tuple[str, ...]
) -> None:
    with pytest.raises(TargetServiceResolutionError) as exc_info:
        resolve_target_service_term(_collision_catalog(), term)

    error = exc_info.value
    assert error.code == "service_resolution_ambiguous"
    assert error.value == term
    assert error.candidate_service_ids == expected_ids
    assert str(error) == f"service_resolution_ambiguous: {term!r}"


def test_selection_options_and_content_refs_are_preserved_not_applied() -> None:
    source = _catalog()["all_on_4"]
    result = resolve_target_service_term({"all_on_4": source}, "all_on_4")

    assert result is not None
    assert result.service.selection.model_dump() == source.selection.model_dump()
    assert [option.model_dump() for option in result.service.options] == [
        option.model_dump() for option in source.options
    ]
    assert result.service.content_ref == "implantation__service__sample.md"


def test_repeated_calls_are_stateless_and_do_not_mutate_catalog() -> None:
    catalog = _catalog()
    before = {key: value.model_dump() for key, value in catalog.items()}

    first = resolve_target_service_term(catalog, "All-on-4")
    assert first is not None
    first.service.name = "Output only"
    first.service.aliases.append("output alias")
    first.service.options[0].name = "Output option"
    second = resolve_target_service_term(catalog, "All-on-4")

    assert second is not None
    assert second.service.name == "Implantation All-on-4"
    assert second.service.options[0].name == "Option One"
    assert {key: value.model_dump() for key, value in catalog.items()} == before


def test_exact_signature_and_import_firewall() -> None:
    signature = inspect.signature(resolve_target_service_term)
    assert list(signature.parameters) == ["services", "service_term"]

    tree = ast.parse(Path("core/target_service_resolver.py").read_text(encoding="utf-8"))
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
