"""Price scope / patient scope for implant price routing (MVP)."""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Literal

from core.patient_scope_cues import (
    ALL_ON_4_ONLY_RX,
    ALL_ON_6_ONLY_RX,
    IMPLANT_PRICE_RX,
    ONE_STAGE_PRICE_RX,
    ONE_TOOTH_EXPLICIT_RX,
    ONE_TOOTH_SITUATION_RX,
    PROSTHETIC_STAGE_RX,
    PTERYGOID_RX,
    ZYGOMATIC_RX,
    has_price_intent,
    is_one_tooth_situation_cue,
)
from core.price_offers import (
    is_full_jaw_implant_price_query,
    is_generic_implant_price_query,
    is_one_stage_price_query,
    is_upper_jaw_restoration_price_query,
)
from core.pricebook_loader import pricebook_services_dir

PriceScopeKind = Literal[
    "none",
    "one_tooth",
    "full_jaw",
    "upper_jaw",
    "generic_implantation",
    "specific_protocol",
    "prosthetic_stage",
]

_CACHE_LOCK = threading.Lock()
_UNIT_CACHE: dict[str, dict[str, str | None]] = {}


@dataclass(frozen=True)
class PriceScopeResult:
    kind: PriceScopeKind
    group_id: str | None = None
    protocol_service_id: str | None = None
    blocked_service_ids: frozenset[str] = frozenset()

    @staticmethod
    def none() -> PriceScopeResult:
        return PriceScopeResult(kind="none")


def _load_service_units(client_id: str | None) -> dict[str, str | None]:
    key = str(client_id or "")
    with _CACHE_LOCK:
        if key in _UNIT_CACHE:
            return dict(_UNIT_CACHE[key])
    units: dict[str, str | None] = {}
    services_dir = pricebook_services_dir(client_id)
    if os.path.isdir(services_dir):
        for name in os.listdir(services_dir):
            if not name.endswith(".json"):
                continue
            sid = name[:-5]
            path = os.path.join(services_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh) or {}
                unit = raw.get("default_unit")
                units[sid] = str(unit).strip() if unit else None
            except (OSError, json.JSONDecodeError, ValueError):
                units[sid] = None
    with _CACHE_LOCK:
        _UNIT_CACHE[key] = dict(units)
    return units


def service_ids_with_default_units(
    client_id: str | None, units: frozenset[str]
) -> frozenset[str]:
    mapping = _load_service_units(client_id)
    return frozenset(sid for sid, unit in mapping.items() if unit in units)


def default_unit_for_service(client_id: str | None, service_id: str) -> str | None:
    return _load_service_units(client_id).get(str(service_id or "").strip())


def jaw_arch_service_ids(client_id: str | None) -> frozenset[str]:
    jaw = service_ids_with_default_units(client_id, frozenset({"jaw"}))
    return jaw | frozenset({"zygomatic_implants", "pterygoid_implants"})


def one_tooth_implant_service_ids(client_id: str | None) -> frozenset[str]:
    return service_ids_with_default_units(client_id, frozenset({"one_tooth"}))


def _is_prosthetic_stage_price(text: str) -> bool:
    if not text or not has_price_intent(text):
        return False
    if not PROSTHETIC_STAGE_RX.search(text):
        return False
    if re.search(r"протезирован|коронк|абатмент", text, re.I | re.U):
        return True
    return bool(re.search(r"сколько|цена|стоим|стоит", text, re.I | re.U))


def detect_price_scope(q: str, *, client_id: str | None = None) -> PriceScopeResult:
    text = (q or "").strip()
    if not text or not has_price_intent(text):
        return PriceScopeResult.none()

    jaw_arch = jaw_arch_service_ids(client_id)
    one_tooth_ids = one_tooth_implant_service_ids(client_id)

    if _is_prosthetic_stage_price(text):
        blocked = one_tooth_ids | jaw_arch | frozenset({"classic", "one_stage"})
        return PriceScopeResult(
            kind="prosthetic_stage",
            protocol_service_id="implant_supported_prosthetics",
            blocked_service_ids=blocked - frozenset({"implant_supported_prosthetics"}),
        )

    if is_one_stage_price_query(text) or ONE_STAGE_PRICE_RX.search(text):
        return PriceScopeResult(
            kind="specific_protocol",
            protocol_service_id="one_stage",
            blocked_service_ids=jaw_arch,
        )

    if ALL_ON_4_ONLY_RX.search(text) and not ALL_ON_6_ONLY_RX.search(text):
        return PriceScopeResult(
            kind="specific_protocol",
            protocol_service_id="all_on_4",
            blocked_service_ids=one_tooth_ids,
        )

    if ALL_ON_6_ONLY_RX.search(text) and not ALL_ON_4_ONLY_RX.search(text):
        return PriceScopeResult(
            kind="specific_protocol",
            protocol_service_id="all_on_6",
            blocked_service_ids=one_tooth_ids,
        )

    if ZYGOMATIC_RX.search(text) and IMPLANT_PRICE_RX.search(text):
        return PriceScopeResult(
            kind="specific_protocol",
            protocol_service_id="zygomatic_implants",
            blocked_service_ids=one_tooth_ids | frozenset({"all_on_4", "all_on_6"}),
        )

    if PTERYGOID_RX.search(text) and IMPLANT_PRICE_RX.search(text):
        return PriceScopeResult(
            kind="specific_protocol",
            protocol_service_id="pterygoid_implants",
            blocked_service_ids=jaw_arch - frozenset({"pterygoid_implants"}),
        )

    if is_upper_jaw_restoration_price_query(text):
        return PriceScopeResult(
            kind="upper_jaw",
            group_id="upper_jaw",
            blocked_service_ids=one_tooth_ids,
        )

    if is_full_jaw_implant_price_query(text):
        return PriceScopeResult(
            kind="full_jaw",
            group_id="full_jaw",
            blocked_service_ids=one_tooth_ids,
        )

    if is_one_tooth_situation_cue(text):
        return PriceScopeResult(
            kind="one_tooth",
            blocked_service_ids=jaw_arch,
        )

    if is_generic_implant_price_query(text):
        return PriceScopeResult(
            kind="generic_implantation",
            group_id="implantation",
        )

    return PriceScopeResult.none()


def scope_catalog_excludes(scope: PriceScopeResult) -> frozenset[str]:
    return scope.blocked_service_ids


def scope_implant_topic(scope: PriceScopeResult) -> str | None:
    if scope.kind in {
        "one_tooth",
        "full_jaw",
        "upper_jaw",
        "generic_implantation",
        "specific_protocol",
    }:
        return "implantation"
    return None
