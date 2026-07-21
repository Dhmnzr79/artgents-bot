from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import yaml

from contracts.response_schema import TargetService
from contracts.service_consultation import validate_service_consultation_refs
from core.service_consultation_source import build_service_consultation_values


DEMO_ROOT = Path("clients/demo")
MD_ROOT = DEMO_ROOT / "md"
SERVICE_CATALOG_PATH = DEMO_ROOT / "target_response/service_catalog.json"

EXPECTED = {
    "implantation__service__all_on_4.md": {
        "service_id": "all_on_4",
        "doc_id": "implantation__service__all_on_4",
        "subtopic": "all_on_4",
        "value": (
            "На консультации врач оценит КТ и поможет понять, подходит ли протокол "
            "All-on-4 или лучше рассмотреть другой вариант восстановления."
        ),
        "suggest_h3": [
            "komu-podhodit-all-on-4",
            "kak-rabotaet-metod-all-on-4",
            "ogranicheniya-i-uhod",
        ],
        "body_sha256": "efa435bafef8f5400a5b01f93ea5109b3d538ee0f64951d60edeb4107f43ec27",
    },
    "implantation__service__classic.md": {
        "service_id": "classic",
        "doc_id": "implantation__service__classic",
        "subtopic": "classic",
        "value": (
            "На консультации врач оценит состояние кости и соседних зубов, сравнит "
            "подходящие системы имплантов и составит поэтапный план восстановления."
        ),
        "suggest_h3": [
            "pochemu-vybirayut-klassicheskuyu",
            "sroki-i-ogranicheniya",
        ],
        "body_sha256": "cbd72f3339cfb91456a7ef19a5a87ea2b59214f732650253b454ca42658b6cb1",
    },
    "implantation__service__one_stage.md": {
        "service_id": "one_stage",
        "doc_id": "implantation__service__one_stage",
        "subtopic": "one_stage",
        "value": (
            "На консультации врач проверит, можно ли удалить зуб и установить имплант "
            "в один день именно в вашей ситуации."
        ),
        "suggest_h3": [
            "kogda-ne-podhodit-odnomomentnaya",
            "v-chem-osobennost-metoda",
        ],
        "body_sha256": "478ecab092824ef29b82433c0ee84a4bb59568a67a69290ddc9f19969bc09800",
    },
}


def _frontmatter_and_body(path: Path) -> tuple[dict[str, object], str]:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    assert len(parts) == 3
    assert parts[0] == ""
    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict)
    return frontmatter, parts[2]


def _target_services() -> dict[str, TargetService]:
    raw = json.loads(SERVICE_CATALOG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {
        service_id: TargetService.model_validate(payload)
        for service_id, payload in raw.items()
    }


def test_real_demo_has_exact_three_approved_consultation_values() -> None:
    records = build_service_consultation_values(MD_ROOT)

    assert {record.content_ref: record.value for record in records} == {
        content_ref: expected["value"]
        for content_ref, expected in EXPECTED.items()
    }


def test_frontmatter_metadata_and_bodies_are_preserved() -> None:
    for content_ref, expected in EXPECTED.items():
        frontmatter, body = _frontmatter_and_body(MD_ROOT / content_ref)

        assert frontmatter["doc_id"] == expected["doc_id"]
        assert frontmatter["doc_type"] == "service"
        assert frontmatter["topic"] == "implantation"
        assert frontmatter["subtopic"] == expected["subtopic"]
        assert frontmatter["consultation_value"] == expected["value"]
        assert frontmatter["suggest_h3"] == expected["suggest_h3"]
        assert frontmatter["cta_key"] == "plan"
        assert frontmatter["cta_action"] == "lead"
        assert frontmatter["situation_allowed"] is True

        assert hashlib.sha256(body.encode()).hexdigest() == expected["body_sha256"]
        assert str(expected["value"]) not in body
        assert "consultation_value" not in body
        assert "#consultation-value" not in body
        assert "consultation-value" not in frontmatter["suggest_h3"]


def test_exact_target_service_content_refs_and_s18_cross_ref() -> None:
    services = _target_services()

    for content_ref, expected in EXPECTED.items():
        service = services[str(expected["service_id"])]
        assert service.content_ref == content_ref

    records = build_service_consultation_values(MD_ROOT)
    assert validate_service_consultation_refs(records, services) is None


def test_no_other_demo_markdown_has_consultation_value() -> None:
    authored_paths: list[str] = []
    for path in sorted(MD_ROOT.rglob("*.md")):
        frontmatter, _body = _frontmatter_and_body(path)
        if "consultation_value" in frontmatter:
            authored_paths.append(path.relative_to(MD_ROOT).as_posix())

    assert authored_paths == sorted(EXPECTED)


def test_acceptance_module_has_no_product_runtime_or_write_calls() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
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
        "ast",
        "contracts.response_schema",
        "contracts.service_consultation",
        "core.service_consultation_source",
        "hashlib",
        "json",
        "pathlib",
        "yaml",
    }

    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
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
