from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from contracts.response_schema import ResponseSchemaBundle
from core import response_schema_loader
from core.response_schema_loader import (
    DuplicateKeyError,
    ResponseSchemaLoadError,
    YamlMergeKeyError,
    load_response_schema_bundle,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _service_payload(*, name: str = "Service One") -> dict[str, object]:
    return {
        "name": name,
        "aliases": ["First service"],
        "family": "implantology",
        "roles": ["protocol"],
        "active": True,
        "content_ref": "service_one.md",
        "selection": {"mode": "scope", "extent": ["one_tooth"]},
        "options": [
            {
                "option_id": "option_one",
                "name": "Option One",
                "selection": {"extent": ["one_tooth"]},
            }
        ],
    }


def _offer_payload(offer_id: str, *, option: bool) -> dict[str, object]:
    return {
        "offer_id": offer_id,
        "service_id": "service_one",
        "option_id": "option_one" if option else None,
        "brand_id": "brand_one",
        "active": True,
        "price": {
            "mode": "fixed",
            "amount": 120_000 if option else 90_000,
            "currency": "RUB",
            "billing_unit": "tooth_package",
        },
        "package": {"label": "one package", "includes": ["part one"]},
        "fact_refs": ["consultation_offer"],
        "followups": [
            {"id": "includes", "label": "What is included", "action": "price_aspect"}
        ],
    }


def _write_pack(root: Path) -> Path:
    _write_json(root / "service_catalog.json", {"service_one": _service_payload()})
    _write_json(
        root / "brand_catalog.json",
        {
            "version": 1,
            "brands": {
                "brand_one": {
                    "canonical_name": "Brand One",
                    "country": "Country One",
                    "aliases": ["B1"],
                }
            },
        },
    )
    _write_json(
        root / "pricebook" / "facts.json",
        {
            "consultation_offer": {
                "id": "consultation_offer",
                "kind": "consultation",
                "text_fact": "  Exact source text stays unchanged.  ",
                "render_mode": "strict",
                "active": True,
                "active_from": "2026-07-01",
                "active_until": "2026-07-31",
                "allowed_service_ids": ["service_one"],
                "detail_ref": "clinic.md#consultation",
                "incompatible_with": [],
            }
        },
    )
    services_dir = root / "pricebook" / "services"
    _write_json(services_dir / "a-later-id.json", _offer_payload("offer_z", option=True))
    _write_json(services_dir / "z-earlier-id.json", _offer_payload("offer_a", option=False))
    (root / "clinic_strategy.yaml").write_text(
        """version: 1
default_max_options: 3
rules:
  - id: 2026-07-01
    match:
      family: implantology
      extent: one_tooth
    max_options: 2
    service_priorities:
      service_one: 100
    offer_priorities:
      offer_z: 90
      offer_a: 80
""",
        encoding="utf-8",
    )
    (root / "marketing.yaml").write_text(
        """version: 1
limits:
  max_marketing_facts_per_turn: 3
  max_amplifiers_per_turn: 2
  max_scenarios_per_turn: 2
initial_commercial_blocks:
  service_context:
    ordered_fact_refs:
      - fact:consultation_offer
scenario_rules:
  cost:
    ordered_amplifier_refs:
      - fact:consultation_offer
      - kb:Service.md#Exact_Chunk
      - doctor:doctor_one
    allowed_semantic_contexts: [service_context]
cta_contexts:
  service_context: consult
  default: callback
""",
        encoding="utf-8",
    )
    return root


def _captured_error(root: object) -> ResponseSchemaLoadError:
    with pytest.raises(ResponseSchemaLoadError) as exc_info:
        load_response_schema_bundle(root)  # type: ignore[arg-type]
    return exc_info.value


def test_complete_pack_loads_exact_source_values_and_external_refs(tmp_path: Path) -> None:
    bundle = load_response_schema_bundle(_write_pack(tmp_path / "pack"))

    assert isinstance(bundle, ResponseSchemaBundle)
    assert bundle.facts["consultation_offer"].text_fact == "  Exact source text stays unchanged.  "
    assert bundle.marketing.scenario_rules["cost"].ordered_amplifier_refs == [
        "fact:consultation_offer",
        "kb:Service.md#Exact_Chunk",
        "doctor:doctor_one",
    ]


def test_offer_order_uses_filename_without_deriving_offer_id(tmp_path: Path) -> None:
    bundle = load_response_schema_bundle(_write_pack(tmp_path / "pack"))

    assert [offer.offer_id for offer in bundle.offers] == ["offer_z", "offer_a"]


@pytest.mark.parametrize(
    ("root_factory", "cause_type"),
    [
        (lambda tmp: tmp / "missing", FileNotFoundError),
        (lambda tmp: (tmp / "pack-file"), NotADirectoryError),
    ],
)
def test_invalid_pack_root_is_typed(
    tmp_path: Path,
    root_factory,
    cause_type: type[BaseException],
) -> None:
    root = root_factory(tmp_path)
    if cause_type is NotADirectoryError:
        root.write_text("not a directory", encoding="utf-8")

    error = _captured_error(root)

    assert error.code == "pack_root_invalid"
    assert error.path == Path(".")
    assert isinstance(error.__cause__, cause_type)


def test_non_path_root_is_not_coerced() -> None:
    error = _captured_error("pack")

    assert error.code == "pack_root_invalid"
    assert error.path == Path(".")
    assert isinstance(error.__cause__, TypeError)


@pytest.mark.parametrize(
    ("relative_path", "replacement_kind", "cause_type"),
    [
        (Path("brand_catalog.json"), "missing", FileNotFoundError),
        (Path("service_catalog.json"), "directory", IsADirectoryError),
        (Path("pricebook/services"), "missing", FileNotFoundError),
        (Path("pricebook/services"), "file", NotADirectoryError),
    ],
)
def test_required_path_failures_are_typed(
    tmp_path: Path,
    relative_path: Path,
    replacement_kind: str,
    cause_type: type[BaseException],
) -> None:
    root = _write_pack(tmp_path / "pack")
    target = root / relative_path
    if target.is_dir():
        for child in target.iterdir():
            child.unlink()
        target.rmdir()
    else:
        target.unlink()
    if replacement_kind == "directory":
        target.mkdir()
    elif replacement_kind == "file":
        target.write_text("not a directory", encoding="utf-8")

    error = _captured_error(root)

    assert error.code == "required_path_missing"
    assert error.path == relative_path
    assert isinstance(error.__cause__, cause_type)


def test_malformed_json_and_yaml_have_distinct_errors(tmp_path: Path) -> None:
    root = _write_pack(tmp_path / "json-pack")
    (root / "service_catalog.json").write_text("{broken", encoding="utf-8")
    json_error = _captured_error(root)
    assert json_error.code == "json_invalid"
    assert json_error.path == Path("service_catalog.json")
    assert isinstance(json_error.__cause__, json.JSONDecodeError)

    root = _write_pack(tmp_path / "yaml-pack")
    (root / "marketing.yaml").write_text("limits: [broken", encoding="utf-8")
    yaml_error = _captured_error(root)
    assert yaml_error.code == "yaml_invalid"
    assert yaml_error.path == Path("marketing.yaml")
    assert isinstance(yaml_error.__cause__, yaml.YAMLError)


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        (Path("service_catalog.json"), '{"service_one": {}, "service_one": {}}'),
        (
            Path("brand_catalog.json"),
            '{"version": 1, "brands": {"brand_one": {"country": "A", "country": "B"}}}',
        ),
        (Path("clinic_strategy.yaml"), "version: 1\nversion: 2\nrules: []\n"),
        (
            Path("marketing.yaml"),
            "version: 1\nlimits:\n  max_marketing_facts_per_turn: 3\n  max_marketing_facts_per_turn: 2\n",
        ),
    ],
)
def test_duplicate_json_and_yaml_keys_fail_before_schema(
    tmp_path: Path, relative_path: Path, content: str
) -> None:
    root = _write_pack(tmp_path / "pack")
    (root / relative_path).write_text(content, encoding="utf-8")

    error = _captured_error(root)

    assert error.code == "duplicate_key"
    assert error.path == relative_path
    assert isinstance(error.__cause__, DuplicateKeyError)


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        (Path("service_catalog.json"), "[]"),
        (Path("pricebook/services/a-later-id.json"), "[]"),
        (Path("clinic_strategy.yaml"), "plain-scalar\n"),
    ],
)
def test_top_level_sources_must_be_mappings(
    tmp_path: Path, relative_path: Path, content: str
) -> None:
    root = _write_pack(tmp_path / "pack")
    (root / relative_path).write_text(content, encoding="utf-8")

    error = _captured_error(root)

    assert error.code == "top_level_type_invalid"
    assert error.path == relative_path
    assert isinstance(error.__cause__, TypeError)


@pytest.mark.parametrize(
    ("mutation", "token"),
    [
        ("invalid_family", "literal_error"),
        ("dangling_service", "bundle_offer_service_missing"),
    ],
)
def test_schema_and_cross_reference_failures_keep_s1_cause(
    tmp_path: Path, mutation: str, token: str
) -> None:
    root = _write_pack(tmp_path / "pack")
    if mutation == "invalid_family":
        _write_json(
            root / "service_catalog.json",
            {"service_one": {**_service_payload(), "family": "medical"}},
        )
    else:
        offer = _offer_payload("offer_z", option=True)
        offer["service_id"] = "missing"
        _write_json(root / "pricebook/services/a-later-id.json", offer)

    error = _captured_error(root)

    assert error.code == "schema_invalid"
    assert error.path == Path(".")
    assert isinstance(error.__cause__, ValidationError)
    assert token in str(error.__cause__)


def test_target_yaml_keeps_date_like_id_without_mutating_safe_load(tmp_path: Path) -> None:
    before = yaml.safe_load("id: 2026-07-01\n")["id"]
    bundle = load_response_schema_bundle(_write_pack(tmp_path / "pack"))
    after = yaml.safe_load("id: 2026-07-01\n")["id"]

    assert isinstance(before, date)
    assert bundle.strategy.rules[0].id == "2026-07-01"
    assert isinstance(after, date)


def test_merge_key_is_forbidden_instead_of_applied(tmp_path: Path) -> None:
    root = _write_pack(tmp_path / "pack")
    (root / "clinic_strategy.yaml").write_text(
        """defaults: &defaults
  version: 1
<<: *defaults
default_max_options: 3
rules: []
""",
        encoding="utf-8",
    )

    error = _captured_error(root)

    assert error.code == "yaml_invalid"
    assert error.path == Path("clinic_strategy.yaml")
    assert isinstance(error.__cause__, YamlMergeKeyError)
    assert isinstance(error.__cause__, yaml.YAMLError)


def test_non_json_and_nested_service_entries_are_not_scanned(tmp_path: Path) -> None:
    root = _write_pack(tmp_path / "pack")
    services_dir = root / "pricebook/services"
    (services_dir / "notes.txt").write_text("not an offer", encoding="utf-8")
    nested = services_dir / "nested"
    nested.mkdir()
    (nested / "broken.json").write_text("{broken", encoding="utf-8")

    bundle = load_response_schema_bundle(root)

    assert [offer.offer_id for offer in bundle.offers] == ["offer_z", "offer_a"]


def test_second_load_observes_changed_source_without_cache(tmp_path: Path) -> None:
    root = _write_pack(tmp_path / "pack")
    first = load_response_schema_bundle(root)
    _write_json(
        root / "service_catalog.json",
        {"service_one": _service_payload(name="Changed Service Name")},
    )
    second = load_response_schema_bundle(root)

    assert first.services["service_one"].name == "Service One"
    assert second.services["service_one"].name == "Changed Service Name"


def test_invalid_utf8_is_file_read_failure(tmp_path: Path) -> None:
    root = _write_pack(tmp_path / "pack")
    (root / "service_catalog.json").write_bytes(b"\xff\xfe")

    error = _captured_error(root)

    assert error.code == "file_read_failed"
    assert error.path == Path("service_catalog.json")
    assert isinstance(error.__cause__, UnicodeDecodeError)


def test_loader_source_has_no_runtime_client_environment_network_or_write_dependencies() -> None:
    source_path = Path(response_schema_loader.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    identifier_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert imported_modules <= {
        "__future__",
        "json",
        "pathlib",
        "typing",
        "yaml",
        "pydantic",
        "yaml.nodes",
        "contracts.response_schema",
    }
    assert not ({"write_text", "write_bytes", "open", "getenv"} & called_attributes)
    assert not ({"client_id", "DEFAULT_CLIENT_ID", "environ", "requests"} & identifier_names)
