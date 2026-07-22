"""Selected-source target follow-up materialization (S29, offline/unwired)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn

import yaml
from yaml.nodes import MappingNode

from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlan,
    TargetResponseMaterializationPlanError,
    build_target_response_materialization_plan,
)


_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)
_FENCE = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
_EXPLICIT_H3 = re.compile(
    r"^###[ \t]+(?P<label>.+?)[ \t]+\{#(?P<id>[A-Za-z0-9_-]+)\}[ \t]*$"
)


@dataclass(frozen=True, slots=True)
class TargetContentFollowup:
    id: str
    label: str
    ref: str
    source_content_ref: str


@dataclass(frozen=True, slots=True)
class TargetPriceFollowup:
    id: str
    label: str
    ref: str
    action: str
    source_offer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetResponseFollowups:
    content: tuple[TargetContentFollowup, ...]
    price: tuple[TargetPriceFollowup, ...]


class TargetResponseFollowupMaterializationError(ValueError):
    """Typed S29 validation/materialization failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class _StrictFrontmatterLoader(yaml.SafeLoader):
    """Isolated SafeLoader rejecting duplicate and merge keys."""

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
                raise yaml.YAMLError(f"duplicate_mapping_key:{key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _error(code: str, value: object, cause: BaseException | None = None) -> NoReturn:
    error = TargetResponseFollowupMaterializationError(code, value)
    if cause is None:
        raise error
    raise error from cause


def _resolved_md_root(md_root: object) -> Path:
    if not isinstance(md_root, Path):
        _error("followup_md_root_invalid", md_root)
    try:
        resolved = md_root.resolve(strict=True)
        is_dir = resolved.is_dir()
    except (OSError, RuntimeError) as exc:
        _error("followup_md_root_invalid", md_root, exc)
    if not is_dir:
        _error("followup_md_root_invalid", md_root)
    return resolved


def _canonical_plan(
    plan: object,
    materials: object,
) -> tuple[
    TargetResponseMaterializationPlan,
    TargetOfflineResponseMaterials,
]:
    if type(plan) is not TargetResponseMaterializationPlan:
        _error("followup_plan_invalid", plan)
    if type(materials) is not TargetOfflineResponseMaterials:
        _error("followup_materials_invalid", materials)
    try:
        expected = build_target_response_materialization_plan(
            materials,
            required_components=plan.required_components,
        )
    except TargetResponseMaterializationPlanError as exc:
        _error("followup_plan_invalid", plan, exc)
    if plan != expected:
        _error("followup_plan_materials_mismatch", (plan, expected))
    return plan, materials


def _selected_content_text(root: Path, content_ref: object) -> tuple[str, str]:
    if not isinstance(content_ref, str):
        _error("followup_content_ref_invalid", content_ref)
    parts = content_ref.split("/")
    if (
        not content_ref
        or "#" in content_ref
        or "\\" in content_ref
        or content_ref.startswith("/")
        or PurePosixPath(content_ref).is_absolute()
        or bool(PureWindowsPath(content_ref).drive)
        or PureWindowsPath(content_ref).is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or not content_ref.endswith(".md")
    ):
        _error("followup_content_ref_invalid", content_ref)
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _error("followup_content_read_failed", content_ref, exc)
    if not resolved.is_relative_to(root):
        _error("followup_content_ref_invalid", content_ref)
    try:
        if not resolved.is_file():
            _error("followup_content_read_failed", content_ref)
        text = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        _error("followup_content_read_failed", content_ref, exc)
    return content_ref, text


def _frontmatter_and_body(text: str, content_ref: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER.match(text)
    if match is None:
        _error("followup_frontmatter_invalid", content_ref)
    try:
        raw = yaml.load(match.group("yaml"), Loader=_StrictFrontmatterLoader)
    except yaml.YAMLError as exc:
        _error("followup_frontmatter_invalid", content_ref, exc)
    if not isinstance(raw, dict):
        _error("followup_frontmatter_invalid", content_ref)
    return raw, text[match.end() :]


def _suggestion_ids(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    if "suggest_h3" not in frontmatter:
        return ()
    raw = frontmatter["suggest_h3"]
    if type(raw) is not list:
        _error("followup_suggestions_invalid", raw)
    copied = tuple(raw)
    for value in copied:
        if type(value) is not str or not value.strip():
            _error("followup_suggestions_invalid", value)
    if len(copied) != len(set(copied)):
        _error("followup_suggestions_invalid", copied)
    return copied


def _explicit_h3_labels(body: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    fence_char: str | None = None
    fence_length = 0
    for line in body.splitlines():
        if fence_char is not None:
            close_fence = re.fullmatch(
                rf"[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
                line,
            )
            if close_fence is not None:
                fence_char = None
                fence_length = 0
            continue
        fence_match = _FENCE.match(line)
        if fence_match is not None:
            marker = fence_match.group("marker")
            fence_char = marker[0]
            fence_length = len(marker)
            continue
        heading = _EXPLICIT_H3.match(line)
        if heading is None:
            continue
        anchor_id = heading.group("id")
        if anchor_id in labels:
            _error("followup_anchor_duplicate", anchor_id)
        labels[anchor_id] = heading.group("label").strip()
    return labels


def _content_followups(
    root: Path,
    content_ref: str,
) -> tuple[TargetContentFollowup, ...]:
    ref, text = _selected_content_text(root, content_ref)
    frontmatter, body = _frontmatter_and_body(text, ref)
    suggestion_ids = _suggestion_ids(frontmatter)
    labels = _explicit_h3_labels(body)
    records: list[TargetContentFollowup] = []
    for suggestion_id in suggestion_ids:
        label = labels.get(suggestion_id)
        if label is None:
            _error("followup_suggestion_not_found", suggestion_id)
        records.append(
            TargetContentFollowup(
                id=suggestion_id,
                label=label,
                ref=f"{ref}#{suggestion_id}",
                source_content_ref=ref,
            )
        )
    return tuple(records)


def _price_followups(
    plan: TargetResponseMaterializationPlan,
    materials: TargetOfflineResponseMaterials,
) -> tuple[TargetPriceFollowup, ...]:
    offers_by_id = {offer.offer_id: offer for offer in materials.offers}
    order: list[str] = []
    payloads: dict[str, tuple[str, str, list[str]]] = {}
    for offer_id in plan.offer_ids:
        offer = offers_by_id[offer_id]
        for followup in offer.followups:
            existing = payloads.get(followup.id)
            if existing is None:
                order.append(followup.id)
                payloads[followup.id] = (
                    followup.label,
                    followup.action,
                    [offer_id],
                )
                continue
            first_label, first_action, source_ids = existing
            if (followup.label, followup.action) != (first_label, first_action):
                _error(
                    "followup_price_conflict",
                    (
                        followup.id,
                        first_label,
                        first_action,
                        followup.label,
                        followup.action,
                    ),
                )
            source_ids.append(offer_id)
    return tuple(
        TargetPriceFollowup(
            id=followup_id,
            label=payloads[followup_id][0],
            ref=f"price:{plan.service_id}/{followup_id}",
            action=payloads[followup_id][1],
            source_offer_ids=tuple(payloads[followup_id][2]),
        )
        for followup_id in order
    )


def materialize_target_response_followups(
    plan: TargetResponseMaterializationPlan,
    materials: TargetOfflineResponseMaterials,
    *,
    md_root: Path,
) -> TargetResponseFollowups:
    """Materialize separate follow-up candidates from selected sources only."""

    if type(plan) is not TargetResponseMaterializationPlan:
        _error("followup_plan_invalid", plan)
    if type(materials) is not TargetOfflineResponseMaterials:
        _error("followup_materials_invalid", materials)
    root = _resolved_md_root(md_root)
    plan, materials = _canonical_plan(plan, materials)

    content: tuple[TargetContentFollowup, ...] = ()
    if (
        "content" in plan.required_components
        and "content" not in plan.unfulfilled_components
    ):
        content = _content_followups(root, plan.primary_content_ref)  # type: ignore[arg-type]

    price: tuple[TargetPriceFollowup, ...] = ()
    if "price" in plan.required_components and "price" not in plan.unfulfilled_components:
        price = _price_followups(plan, materials)

    return TargetResponseFollowups(content=content, price=price)
