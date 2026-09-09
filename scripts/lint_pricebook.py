#!/usr/bin/env python3

"""Lint target_response pricebook invariants for client packs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.response_schema_loader import load_response_schema_bundle

_RUB_RX = re.compile(r"\d[\d\s]*\s*₽|₽", re.U)


def _lint_pricing_md(md_dir: Path) -> list[str]:
    errors: list[str] = []
    if not md_dir.is_dir():
        return errors
    for path in sorted(md_dir.glob("*__pricing__*.md")):
        text = path.read_text(encoding="utf-8")
        if _RUB_RX.search(text):
            errors.append(f"{path}: contains ₽ (target pricebook is source of sums)")
    return errors


def _normalize_package_item(value: str) -> str:
    return value.strip().casefold()


_DEMO_STAGE_A_EXCLUDES: dict[str, tuple[str, ...]] = {
    "classic": ("КТ при необходимости", "временная коронка"),
    "one_stage": ("КТ", "лечение воспаления по показаниям", "временная коронка"),
    "all_on_4": ("КТ", "костная пластика по показаниям"),
    "all_on_6": ("КТ", "костная пластика по показаниям"),
    "implant_supported_prosthetics": (
        "хирургическая установка импланта",
        "КТ",
    ),
    "sinus_lift": ("имплант", "коронка", "КТ"),
}


def _lint_offer_payment_stages(bundle) -> list[str]:
    errors: list[str] = []
    for offer in bundle.offers:
        stages = offer.payment_stages or []
        if not stages:
            continue
        price = offer.price
        if price.mode == "fixed":
            total = price.amount
        elif price.mode == "from":
            total = price.min_amount
        else:
            continue
        if total is None:
            continue
        stage_sum = sum(stage.amount for stage in stages)
        if stage_sum != total:
            errors.append(
                f"target_response/pricebook/services/{offer.offer_id}.json: "
                f"payment_stages sum {stage_sum} != price {total}"
            )
        for index, stage in enumerate(stages, start=1):
            timing = str(stage.timing_text or "").strip()
            if not timing:
                errors.append(
                    f"target_response/pricebook/services/{offer.offer_id}.json: "
                    f"payment_stages[{index}] missing timing_text"
                )
    return errors


def _lint_demo_stage_a_excludes(bundle, client_id: str) -> list[str]:
    if client_id != "demo":
        return []
    errors: list[str] = []
    for offer in bundle.offers:
        expected = _DEMO_STAGE_A_EXCLUDES.get(offer.service_id)
        if expected is None:
            continue
        actual = tuple(offer.package.excludes)
        if actual != expected:
            errors.append(
                f"target_response/pricebook/services/{offer.offer_id}.json: "
                f"expected excludes {expected!r}, got {actual!r}"
            )
    return errors


def _lint_mandatory_exclusion_compat(bundle) -> list[str]:
    """Stage A migration: mandatory_exclusion must cover every package.excludes item."""

    errors: list[str] = []
    for offer in bundle.offers:
        metadata = offer.required_conditions_metadata
        if metadata is None:
            continue
        excludes = offer.package.excludes
        if not excludes:
            continue
        for cond in metadata.conditions:
            if cond.condition_id != "mandatory_exclusion":
                continue
            display = _normalize_package_item(cond.display_text)
            for item in excludes:
                if _normalize_package_item(item) not in display:
                    errors.append(
                        f"target_response/pricebook/services/{offer.offer_id}.json: "
                        f"mandatory_exclusion missing exclude item {item!r}"
                    )
    return errors


def lint_client(client_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    target_root = client_dir / "target_response"
    if not target_root.is_dir():
        errors.append(f"{target_root}: target_response missing")
        return errors, warnings

    try:
        bundle = load_response_schema_bundle(target_root)
    except Exception as exc:
        errors.append(f"{target_root}: load failed: {exc}")
        return errors, warnings

    if not bundle.offers:
        errors.append(f"{target_root}/pricebook/services: no offers")
    errors.extend(_lint_offer_payment_stages(bundle))
    errors.extend(_lint_demo_stage_a_excludes(bundle, client_dir.name))
    errors.extend(_lint_mandatory_exclusion_compat(bundle))
    errors.extend(_lint_pricing_md(client_dir / "md"))
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    client = argv[0] if argv else "demo"
    client_dir = ROOT / "clients" / client
    if not client_dir.is_dir():
        print(f"ERROR: client dir not found: {client_dir}", file=sys.stderr)
        return 2

    errors, warnings = lint_client(client_dir)
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"OK: target pricebook lint passed ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
