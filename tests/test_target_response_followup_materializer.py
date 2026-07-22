from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from contracts.response_schema import TargetOffer, TargetService, TargetStrategyMatch
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
    TargetResponseFollowupMaterializationError,
    TargetResponseFollowups,
    materialize_target_response_followups,
)
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    build_target_response_materialization_plan,
)


def _offer(
    offer_id: str,
    followups: list[tuple[str, str, str]],
) -> TargetOffer:
    return TargetOffer.model_validate(
        {
            "offer_id": offer_id,
            "service_id": "service_one",
            "active": True,
            "price": {
                "mode": "fixed",
                "amount": 100_000,
                "currency": "RUB",
                "billing_unit": "jaw",
            },
            "package": {"label": "Package", "includes": []},
            "payment_stages": (
                [{"label": "Stage", "amount": 100_000, "currency": "RUB"}]
                if any(item[0] == "stages" for item in followups)
                else None
            ),
            "fact_refs": [],
            "followups": [
                {"id": item_id, "label": label, "action": action}
                for item_id, label, action in followups
            ],
        }
    )


def _materials(
    *,
    content_ref: str | None = "service.md",
    offers: tuple[TargetOffer, ...] | None = None,
) -> TargetOfflineResponseMaterials:
    if offers is None:
        common = [
            ("stages", "Payment stages", "price_aspect"),
            ("includes", "What is included", "price_aspect"),
        ]
        offers = (_offer("offer_b", common), _offer("offer_a", common))
    service = TargetService.model_validate(
        {
            "name": "Service One",
            "aliases": ["one"],
            "family": "implantology",
            "roles": ["protocol"],
            "active": True,
            "content_ref": content_ref,
            "selection": {"mode": "direct"},
            "options": [],
        }
    )
    return TargetOfflineResponseMaterials(
        service_id="service_one",
        service=service,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=3,
        offers=offers,
        doctors=(),
        selected_content_ref=content_ref,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="plan",
        ),
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
    )


def _plan(
    materials: TargetOfflineResponseMaterials,
    components: tuple[str, ...],
) -> TargetResponseMaterializationPlan:
    return build_target_response_materialization_plan(
        materials,
        required_components=components,
    )


def _doc(
    root: Path,
    *,
    frontmatter: str = "suggest_h3:\n  - second\n  - first",
    body: str = (
        "### First label {#first}\nFirst body.\n\n"
        "```md\n### Fake {#second}\n```\n\n"
        "### Second label {#second}\nSecond body.\n"
    ),
    name: str = "service.md",
) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return path


def _materialize(
    root: Path,
    *,
    materials: TargetOfflineResponseMaterials | None = None,
    components: tuple[str, ...] = ("content", "price"),
    plan: object | None = None,
) -> TargetResponseFollowups:
    materials = materials or _materials()
    actual_plan = plan if plan is not None else _plan(materials, components)
    return materialize_target_response_followups(
        actual_plan,  # type: ignore[arg-type]
        materials,
        md_root=root,
    )


def test_exact_frozen_shapes_and_separate_candidate_tuples(tmp_path: Path) -> None:
    _doc(tmp_path)
    result = _materialize(tmp_path)

    assert [field.name for field in fields(TargetContentFollowup)] == [
        "id", "label", "ref", "source_content_ref"
    ]
    assert [field.name for field in fields(TargetPriceFollowup)] == [
        "id", "label", "ref", "action", "source_offer_ids"
    ]
    assert [field.name for field in fields(TargetResponseFollowups)] == [
        "content", "price"
    ]
    assert isinstance(result.content, tuple) and isinstance(result.price, tuple)
    with pytest.raises(FrozenInstanceError):
        result.content = ()  # type: ignore[misc]


def test_fixed_input_precedence_and_exact_root_errors(tmp_path: Path) -> None:
    materials = _materials()
    plan = _plan(materials, ("content",))
    missing_root = tmp_path / "missing"

    with pytest.raises(TargetResponseFollowupMaterializationError) as bad_plan:
        materialize_target_response_followups(
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            md_root=missing_root,
        )
    assert bad_plan.value.code == "followup_plan_invalid"
    assert type(bad_plan.value.value) is object

    with pytest.raises(TargetResponseFollowupMaterializationError) as bad_materials:
        materialize_target_response_followups(
            plan,
            object(),  # type: ignore[arg-type]
            md_root=missing_root,
        )
    assert bad_materials.value.code == "followup_materials_invalid"

    for root in ("not-a-path", missing_root, tmp_path / "file.md"):
        if isinstance(root, Path) and root.suffix:
            root.write_text("x", encoding="utf-8")
        with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
            materialize_target_response_followups(
                plan,
                materials,
                md_root=root,  # type: ignore[arg-type]
            )
        assert exc_info.value.code == "followup_md_root_invalid"
        assert exc_info.value.value == root


def test_canonical_rebuild_rejects_forged_component_and_whole_plan_mismatch(
    tmp_path: Path,
) -> None:
    materials = _materials()
    plan = _plan(materials, ("content",))
    forged_components = replace(
        plan,
        required_components=("bad",),  # type: ignore[arg-type]
    )
    with pytest.raises(TargetResponseFollowupMaterializationError) as invalid:
        _materialize(tmp_path, materials=materials, plan=forged_components)
    assert invalid.value.code == "followup_plan_invalid"
    assert invalid.value.value is forged_components

    forged = replace(plan, cta_key="other")
    with pytest.raises(TargetResponseFollowupMaterializationError) as mismatch:
        _materialize(tmp_path, materials=materials, plan=forged)
    assert mismatch.value.code == "followup_plan_materials_mismatch"
    assert mismatch.value.value == (forged, plan)
    assert str(mismatch.value) == f"followup_plan_materials_mismatch: {(forged, plan)!r}"


def test_content_uses_only_selected_file_exact_order_labels_and_refs(tmp_path: Path) -> None:
    _doc(tmp_path)
    _doc(
        tmp_path,
        frontmatter="suggest_h3:\n  - other",
        body="### Other label {#other}\nOther.",
        name="other.md",
    )
    result = _materialize(tmp_path, components=("content",))

    assert [(item.id, item.label, item.ref) for item in result.content] == [
        ("second", "Second label", "service.md#second"),
        ("first", "First label", "service.md#first"),
    ]
    assert all(item.source_content_ref == "service.md" for item in result.content)
    assert result.price == ()


@pytest.mark.parametrize("frontmatter", ["doc_type: service", "suggest_h3: []"])
def test_missing_or_empty_suggestions_are_empty(
    tmp_path: Path,
    frontmatter: str,
) -> None:
    _doc(tmp_path, frontmatter=frontmatter)
    assert _materialize(tmp_path, components=("content",)).content == ()


@pytest.mark.parametrize(
    "content_ref",
    ["service.txt", "service.md#first", "../service.md", "a/./service.md", "a\\service.md", "/service.md"],
)
def test_invalid_content_refs_fail_before_read(
    tmp_path: Path,
    content_ref: str,
) -> None:
    materials = _materials(content_ref=content_ref)
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, materials=materials, components=("content",))
    assert exc_info.value.code == "followup_content_ref_invalid"
    assert exc_info.value.value == content_ref


def test_windows_drive_absolute_ref_is_invalid_even_when_basename_exists(
    tmp_path: Path,
) -> None:
    _doc(tmp_path)
    content_ref = "C:/service.md"
    materials = _materials(content_ref=content_ref)
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, materials=materials, components=("content",))
    assert exc_info.value.code == "followup_content_ref_invalid"
    assert exc_info.value.value == content_ref


def test_forged_empty_selected_content_ref_is_invalid(tmp_path: Path) -> None:
    materials = replace(_materials(), selected_content_ref="")
    plan = _plan(materials, ("content",))
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, materials=materials, plan=plan)
    assert exc_info.value.code == "followup_content_ref_invalid"
    assert exc_info.value.value == ""


def test_missing_and_non_utf8_selected_file_are_read_failed(tmp_path: Path) -> None:
    materials = _materials(content_ref="missing.md")
    with pytest.raises(TargetResponseFollowupMaterializationError) as missing:
        _materialize(tmp_path, materials=materials, components=("content",))
    assert missing.value.code == "followup_content_read_failed"
    assert missing.value.value == "missing.md"

    (tmp_path / "service.md").write_bytes(b"\xff\xfe")
    with pytest.raises(TargetResponseFollowupMaterializationError) as non_utf8:
        _materialize(tmp_path, components=("content",))
    assert non_utf8.value.code == "followup_content_read_failed"
    assert non_utf8.value.value == "service.md"


@pytest.mark.parametrize(
    "text",
    [
        "No frontmatter.\n### One {#one}",
        "---\nsuggest_h3: []\nNo close.",
        "---\n- list\n---\n### One {#one}",
        "---\nsuggest_h3: []\nsuggest_h3: []\n---\n### One {#one}",
        "---\nbase: &base {x: 1}\nmerged: {<<: *base}\n---\n### One {#one}",
    ],
)
def test_strict_frontmatter_failures_use_selected_ref(
    tmp_path: Path,
    text: str,
) -> None:
    (tmp_path / "service.md").write_text(text, encoding="utf-8")
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, components=("content",))
    assert exc_info.value.code == "followup_frontmatter_invalid"
    assert exc_info.value.value == "service.md"


@pytest.mark.parametrize(
    ("frontmatter", "expected_value"),
    [
        ("suggest_h3: one", "one"),
        ("suggest_h3:\n  - ''", ""),
        ("suggest_h3:\n  - 7", 7),
        ("suggest_h3:\n  - one\n  - one", ("one", "one")),
    ],
)
def test_invalid_suggestions_have_exact_value(
    tmp_path: Path,
    frontmatter: str,
    expected_value: object,
) -> None:
    _doc(tmp_path, frontmatter=frontmatter)
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, components=("content",))
    assert exc_info.value.code == "followup_suggestions_invalid"
    assert exc_info.value.value == expected_value


def test_duplicate_anchor_precedes_missing_suggestion(tmp_path: Path) -> None:
    _doc(
        tmp_path,
        frontmatter="suggest_h3:\n  - missing",
        body="### One {#same}\nA.\n### Two {#same}\nB.",
    )
    with pytest.raises(TargetResponseFollowupMaterializationError) as duplicate:
        _materialize(tmp_path, components=("content",))
    assert duplicate.value.code == "followup_anchor_duplicate"
    assert duplicate.value.value == "same"

    _doc(
        tmp_path,
        frontmatter="suggest_h3:\n  - missing",
        body="### One {#one}\nA.",
    )
    with pytest.raises(TargetResponseFollowupMaterializationError) as missing:
        _materialize(tmp_path, components=("content",))
    assert missing.value.code == "followup_suggestion_not_found"
    assert missing.value.value == "missing"


@pytest.mark.parametrize("marker", ["```", "~~~"])
def test_info_suffixed_marker_does_not_close_fenced_code(
    tmp_path: Path,
    marker: str,
) -> None:
    _doc(
        tmp_path,
        frontmatter="suggest_h3:\n  - real",
        body=(
            f"{marker}python\n"
            f"{marker}still-code\n"
            "### Fake {#fake}\n"
            f"{marker}\n"
            "### Real label {#real}\n"
        ),
    )
    result = _materialize(tmp_path, components=("content",))
    assert [(item.id, item.label) for item in result.content] == [
        ("real", "Real label")
    ]


def test_price_aggregates_selected_offer_sources_in_exact_order(tmp_path: Path) -> None:
    result = _materialize(tmp_path, components=("price",))

    assert result.content == ()
    assert [(item.id, item.label, item.ref, item.action) for item in result.price] == [
        ("stages", "Payment stages", "price:service_one/stages", "price_aspect"),
        ("includes", "What is included", "price:service_one/includes", "price_aspect"),
    ]
    assert [item.source_offer_ids for item in result.price] == [
        ("offer_b", "offer_a"),
        ("offer_b", "offer_a"),
    ]


def test_price_conflict_has_exact_payload(tmp_path: Path) -> None:
    materials = _materials(
        offers=(
            _offer("offer_a", [("includes", "First", "price_aspect")]),
            _offer("offer_b", [("includes", "Second", "price_aspect")]),
        )
    )
    with pytest.raises(TargetResponseFollowupMaterializationError) as exc_info:
        _materialize(tmp_path, materials=materials, components=("price",))
    assert exc_info.value.code == "followup_price_conflict"
    assert exc_info.value.value == (
        "includes", "First", "price_aspect", "Second", "price_aspect"
    )


def test_unrequested_or_unfulfilled_components_do_not_read_or_fallback(tmp_path: Path) -> None:
    price_only = _materialize(tmp_path, components=("price",))
    assert price_only.content == () and price_only.price

    materials = _materials(content_ref=None, offers=())
    plan = _plan(materials, ("content", "price"))
    assert plan.unfulfilled_components == ("content", "price")
    result = _materialize(tmp_path, materials=materials, plan=plan)
    assert result == TargetResponseFollowups(content=(), price=())


def test_repeated_calls_read_only_signature_errors_and_import_firewall(tmp_path: Path) -> None:
    _doc(tmp_path)
    materials = _materials()
    plan = _plan(materials, ("content", "price"))
    before = tuple(offer.model_dump() for offer in materials.offers)
    assert _materialize(tmp_path, materials=materials, plan=plan) == _materialize(
        tmp_path, materials=materials, plan=plan
    )
    assert tuple(offer.model_dump() for offer in materials.offers) == before

    signature = inspect.signature(materialize_target_response_followups)
    assert list(signature.parameters) == ["plan", "materials", "md_root"]
    tree = ast.parse(
        Path("core/target_response_followup_materializer.py").read_text(encoding="utf-8")
    )
    codes = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("followup_")
    }
    assert codes == {
        "followup_plan_invalid",
        "followup_materials_invalid",
        "followup_md_root_invalid",
        "followup_plan_materials_mismatch",
        "followup_content_ref_invalid",
        "followup_content_read_failed",
        "followup_frontmatter_invalid",
        "followup_suggestions_invalid",
        "followup_anchor_duplicate",
        "followup_suggestion_not_found",
        "followup_price_conflict",
    }
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(("app", "config", "orchestration", "routes", "session"))
        for module in imported_modules
    )
    source = Path("core/target_response_followup_materializer.py").read_text(encoding="utf-8")
    assert ".resolve(strict=True)" in source
    assert ".is_relative_to(root)" in source
