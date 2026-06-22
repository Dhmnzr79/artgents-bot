#!/usr/bin/env python3

"""Lint PriceBook v2 client pack (stage 3.5)."""

from __future__ import annotations



import json

import re

import sys

from datetime import date, datetime

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from contracts.pricebook import PricebookManifest, PricebookServiceEntry, PricingFactsFile

from pydantic import ValidationError



_RUB_RX = re.compile(r"\d[\d\s]*\s*₽|₽", re.U)





def _load_json(path: Path) -> dict | None:

    if not path.is_file():

        return None

    try:

        raw = json.loads(path.read_text(encoding="utf-8"))

        return raw if isinstance(raw, dict) else None

    except (OSError, json.JSONDecodeError):

        return None





def lint_services(services_dir: Path) -> list[str]:

    errors: list[str] = []

    if not services_dir.is_dir():

        return errors

    for path in sorted(services_dir.glob("*.json")):

        raw = _load_json(path)

        if not raw:

            errors.append(f"{path}: invalid JSON")

            continue

        try:

            entry = PricebookServiceEntry.model_validate(raw)

        except ValidationError as exc:

            errors.append(f"{path}: schema {exc}")

            continue

        for variant in entry.variants:

            if variant.payment_stages:

                stage_sum = sum(s.amount for s in variant.payment_stages)

                if stage_sum != variant.total:

                    errors.append(

                        f"{path}: {variant.offer_id} stages sum {stage_sum} != total {variant.total}"

                    )

    return errors





def lint_manifest_vs_services(manifest_path: Path, services_dir: Path) -> list[str]:

    errors: list[str] = []

    raw = _load_json(manifest_path)

    if not raw:

        return errors

    try:

        manifest = PricebookManifest.model_validate(raw)

    except ValidationError as exc:

        return [f"{manifest_path}: schema {exc}"]

    service_mins: dict[str, int] = {}

    if services_dir.is_dir():

        for path in services_dir.glob("*.json"):

            raw_s = _load_json(path)

            if not raw_s:

                continue

            try:

                entry = PricebookServiceEntry.model_validate(raw_s)

            except ValidationError:

                continue

            if entry.variants:

                service_mins[entry.service_id] = min(v.total for v in entry.variants)

            elif entry.price is not None:

                service_mins[entry.service_id] = entry.price.value

    for gid, group in manifest.groups.items():

        for member in group.members:

            expected = service_mins.get(member.service_id)

            if expected is not None and member.from_total is not None and member.from_total != expected:

                errors.append(

                    f"manifest group {gid}: {member.service_id} from_total {member.from_total} "

                    f"!= min variant {expected}"

                )

    return errors





def lint_facts_active(facts_path: Path, *, today: date | None = None) -> list[str]:

    warnings: list[str] = []

    raw = _load_json(facts_path)

    if not raw:

        return warnings

    try:

        facts = PricingFactsFile.model_validate(raw)

    except ValidationError:

        return warnings

    ref = today or date.today()

    for fid, fact in facts.facts.items():

        until = (fact.active_until or "").strip()

        if not until:

            continue

        try:

            end = datetime.strptime(until, "%Y-%m-%d").date()

        except ValueError:

            warnings.append(f"facts: {fid} bad active_until {until!r}")

            continue

        if end < ref:

            warnings.append(f"facts: {fid} active_until {until} is in the past")

    return warnings





def lint_pricing_md(md_dir: Path) -> list[str]:

    errors: list[str] = []

    if not md_dir.is_dir():

        return errors

    for path in sorted(md_dir.glob("*__pricing__*.md")):

        text = path.read_text(encoding="utf-8")

        if _RUB_RX.search(text):

            errors.append(f"{path}: contains ₽ (PriceBook is source of sums)")

    return errors





def lint_catalog_coverage(catalog_path: Path, services_dir: Path) -> list[str]:
    errors: list[str] = []
    raw = _load_json(catalog_path)
    if not raw:
        return errors
    service_ids: set[str] = set()
    if services_dir.is_dir():
        for path in services_dir.glob("*.json"):
            raw_s = _load_json(path)
            if not raw_s:
                continue
            try:
                entry = PricebookServiceEntry.model_validate(raw_s)
            except ValidationError:
                continue
            service_ids.add(entry.service_id)
    for sid, entry in raw.items():
        if not isinstance(entry, dict) or not bool(entry.get("active", True)):
            continue
        price_key = str(entry.get("price_key") or "").strip()
        if not price_key:
            continue
        if price_key not in service_ids:
            errors.append(
                f"service_catalog: {sid} price_key={price_key!r} missing in pricebook/services"
            )
    return errors


def lint_client(client_dir: Path) -> tuple[list[str], list[str]]:

    pb = client_dir / "pricebook"

    errors: list[str] = []

    warnings: list[str] = []

    errors.extend(lint_services(pb / "services"))

    errors.extend(lint_manifest_vs_services(pb / "manifest.json", pb / "services"))

    errors.extend(lint_catalog_coverage(client_dir / "service_catalog.json", pb / "services"))

    warnings.extend(lint_facts_active(pb / "facts.json"))

    errors.extend(lint_pricing_md(client_dir / "md"))

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

    print(f"OK: pricebook lint passed ({len(warnings)} warning(s))")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


