"""Load PriceBook v2 client pack (manifest, facts, services)."""

from __future__ import annotations



import json

import os

import threading

from datetime import date, datetime

from typing import Any



from pydantic import ValidationError



from contracts.price_offer import PriceOffer, PaymentStage

from contracts.pricebook import (

    PricebookManifest,

    PricebookServiceEntry,

    PriceVariant,

    PricingFactsFile,

    PricingFact,

    SimplePrice,

)

from core.client_runtime import client_pack_dir
from logging_setup import get_logger

logger = get_logger("bot")



_CACHE_LOCK = threading.Lock()

_MANIFEST_CACHE: dict[str, PricebookManifest | None] = {}

_MANIFEST_MTIME: dict[str, float] = {}

_FACTS_CACHE: dict[str, PricingFactsFile | None] = {}

_FACTS_MTIME: dict[str, float] = {}

_SERVICE_CACHE: dict[str, dict[str, PricebookServiceEntry]] = {}

_SERVICE_MTIME: dict[str, float] = {}





def pricebook_dir(client_id: str | None) -> str:

    return os.path.join(client_pack_dir(client_id), "pricebook")





def pricebook_services_dir(client_id: str | None) -> str:

    return os.path.join(pricebook_dir(client_id), "services")





def _read_json(path: str) -> dict[str, Any] | None:

    if not os.path.isfile(path):

        return None

    try:

        with open(path, "r", encoding="utf-8") as fh:

            raw = json.load(fh)

        return raw if isinstance(raw, dict) else None

    except (OSError, json.JSONDecodeError):

        return None





def _file_mtime(path: str) -> float:

    try:

        return os.path.getmtime(path) if os.path.isfile(path) else 0.0

    except OSError:

        return 0.0





def _services_dir_mtime(client_id: str | None) -> float:

    svc_dir = pricebook_services_dir(client_id)

    if not os.path.isdir(svc_dir):

        return 0.0

    mtimes = [_file_mtime(svc_dir)]

    try:

        for name in os.listdir(svc_dir):

            if name.endswith(".json"):

                mtimes.append(_file_mtime(os.path.join(svc_dir, name)))

    except OSError:

        pass

    return max(mtimes) if mtimes else 0.0





def infer_brand_group(brand_label: str) -> str | None:

    bl = (brand_label or "").lower()

    if "коре" in bl:

        return "korean"

    if "герман" in bl:

        return "german"

    if "швейц" in bl:

        return "swiss"

    return None





def variant_to_price_offer(service_id: str, variant: PriceVariant) -> PriceOffer:

    return PriceOffer(

        offer_id=variant.offer_id,

        service_id=service_id,

        unit=variant.unit,

        brand=variant.brand,

        brand_label=variant.brand_label,

        recommended=variant.recommended,

        total=variant.total,

        currency=variant.currency,

        payment_stages=list(variant.payment_stages),

        includes=list(variant.includes),

        excludes=list(variant.excludes),

    )





def load_pricebook_manifest(client_id: str | None, *, force_reload: bool = False) -> PricebookManifest | None:

    path = os.path.join(pricebook_dir(client_id), "manifest.json")

    mtime = _file_mtime(path)

    key = path

    with _CACHE_LOCK:

        if not force_reload and key in _MANIFEST_CACHE and _MANIFEST_MTIME.get(key) == mtime:

            return _MANIFEST_CACHE[key]

    raw = _read_json(path)

    parsed: PricebookManifest | None = None

    if raw:

        try:

            parsed = PricebookManifest.model_validate(raw)

        except ValidationError:

            parsed = None

    with _CACHE_LOCK:

        _MANIFEST_CACHE[key] = parsed

        _MANIFEST_MTIME[key] = mtime

    return parsed





def load_pricing_facts(client_id: str | None, *, force_reload: bool = False) -> PricingFactsFile | None:

    path = os.path.join(pricebook_dir(client_id), "facts.json")

    mtime = _file_mtime(path)

    key = path

    with _CACHE_LOCK:

        if not force_reload and key in _FACTS_CACHE and _FACTS_MTIME.get(key) == mtime:

            return _FACTS_CACHE[key]

    raw = _read_json(path)

    parsed: PricingFactsFile | None = None

    if raw:

        try:

            parsed = PricingFactsFile.model_validate(raw)

        except ValidationError:

            parsed = None

    with _CACHE_LOCK:

        _FACTS_CACHE[key] = parsed

        _FACTS_MTIME[key] = mtime

    return parsed





def _load_all_service_files(client_id: str | None, *, force_reload: bool = False) -> dict[str, PricebookServiceEntry]:

    svc_dir = pricebook_services_dir(client_id)

    mtime = _services_dir_mtime(client_id)

    key = svc_dir

    with _CACHE_LOCK:

        if not force_reload and key in _SERVICE_CACHE and _SERVICE_MTIME.get(key) == mtime:

            return dict(_SERVICE_CACHE[key])

    out: dict[str, PricebookServiceEntry] = {}

    if os.path.isdir(svc_dir):

        for name in sorted(os.listdir(svc_dir)):

            if not name.endswith(".json"):

                continue

            raw = _read_json(os.path.join(svc_dir, name))

            if not raw:

                continue

            try:

                entry = PricebookServiceEntry.model_validate(raw)

                out[entry.service_id] = entry

            except ValidationError as exc:

                logger.warning(
                    "pricebook_service_skip client=%s file=%s errors=%s",
                    client_id,
                    name,
                    exc.error_count(),
                )
                continue

    with _CACHE_LOCK:

        _SERVICE_CACHE[key] = out

        _SERVICE_MTIME[key] = mtime

    return dict(out)





def load_pricebook_service(

    client_id: str | None,

    service_id: str,

    *,

    force_reload: bool = False,

) -> PricebookServiceEntry | None:

    sid = (service_id or "").strip()

    if not sid:

        return None

    services = _load_all_service_files(client_id, force_reload=force_reload)

    return services.get(sid)





def list_pricebook_service_ids(client_id: str | None, *, force_reload: bool = False) -> list[str]:

    return sorted(_load_all_service_files(client_id, force_reload=force_reload).keys())





def pricebook_has_services(client_id: str | None) -> bool:

    return bool(_load_all_service_files(client_id))





def _fact_active(fact: PricingFact, *, today: date | None = None) -> bool:

    until = (fact.active_until or "").strip()

    if not until:

        return True

    try:

        end = datetime.strptime(until, "%Y-%m-%d").date()

    except ValueError:

        return True

    ref = today or date.today()

    return ref <= end





def resolve_fact_refs(

    client_id: str | None,

    fact_refs: list[str],

    *,

    usable_in: str = "price_answer",

    today: date | None = None,

) -> list[PricingFact]:

    facts_file = load_pricing_facts(client_id)

    if not facts_file:

        return []

    out: list[PricingFact] = []

    for ref_id in fact_refs:

        fid = str(ref_id or "").strip()

        if not fid:

            continue

        fact = facts_file.facts.get(fid)

        if not fact:

            continue

        if usable_in and usable_in not in (fact.usable_in or []):

            continue

        if not _fact_active(fact, today=today):

            continue

        out.append(fact)

    return out





def offers_from_service_entry(entry: PricebookServiceEntry) -> list[PriceOffer]:

    if entry.price_model == "complex" and entry.variants:

        return [variant_to_price_offer(entry.service_id, v) for v in entry.variants]

    return []





def default_unit_for_service_entry(entry: PricebookServiceEntry | None) -> str | None:

    if not entry:

        return None

    if entry.default_unit:

        return entry.default_unit

    if entry.variants:

        return entry.variants[0].unit

    return None


