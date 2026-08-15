from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import yaml

from contracts.authored_service_alternative import AuthoredServiceAlternative
from core.client_config_loader import resolve_pack_client_id
from core.target_contact_authority import canonical_contact_phone


@dataclass(frozen=True)
class ClinicPolicy:
    key: str
    triggers: tuple[str, ...]
    answer: str


@dataclass(frozen=True)
class ServiceAlternative:
    match_keywords: tuple[str, ...]
    mention: str
    note: str
    suggest_ref: str | None


@dataclass(frozen=True)
class ClinicPoliciesBundle:
    contact_phone_display: str
    policies: tuple[ClinicPolicy, ...]
    service_alternatives: tuple[ServiceAlternative, ...]
    service_not_offered_template: str
    hard_stop_template: str
    manual_contact_template: str
    manual_contact_urgent_suffix: str


_LOCK = threading.Lock()
_CACHE: dict[str, ClinicPoliciesBundle] = {}
_AUTHORED_ALTS_CACHE: dict[str, tuple[AuthoredServiceAlternative, ...]] = {}


def _policies_path(client_id: str) -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "clients", client_id, "clinic_policies.yaml")


def load_clinic_policies(client_id: str) -> ClinicPoliciesBundle | None:
    cid = resolve_pack_client_id(client_id)
    with _LOCK:
        if cid in _CACHE:
            return _CACHE[cid]
    path = _policies_path(cid)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        return None
    phone = canonical_contact_phone(cid)

    policies_out: list[ClinicPolicy] = []
    policies_raw = raw.get("policies")
    if isinstance(policies_raw, dict):
        for key, body in policies_raw.items():
            if not isinstance(body, dict):
                continue
            triggers = body.get("triggers")
            answer = str(body.get("answer") or "").strip()
            if not answer:
                continue
            trig_list = (
                [str(t).strip().lower() for t in triggers if str(t).strip()]
                if isinstance(triggers, list)
                else []
            )
            if trig_list:
                policies_out.append(
                    ClinicPolicy(key=str(key), triggers=tuple(trig_list), answer=answer)
                )

    alts_out: list[ServiceAlternative] = []
    alts_raw = raw.get("service_alternatives")
    if isinstance(alts_raw, list):
        for row in alts_raw:
            if not isinstance(row, dict):
                continue
            mk = row.get("match_keywords")
            mention = str(row.get("mention") or "").strip()
            note = str(row.get("note") or "").strip()
            suggest_ref = str(row.get("suggest_ref") or row.get("ref") or "").strip() or None
            kw = (
                [str(x).strip().lower() for x in mk if str(x).strip()]
                if isinstance(mk, list)
                else []
            )
            if kw and note:
                alts_out.append(
                    ServiceAlternative(
                        match_keywords=tuple(kw),
                        mention=mention,
                        note=note,
                        suggest_ref=suggest_ref,
                    )
                )

    bundle = ClinicPoliciesBundle(
        contact_phone_display=phone,
        policies=tuple(policies_out),
        service_alternatives=tuple(alts_out),
        service_not_offered_template=str(
            raw.get("service_not_offered_template") or ""
        ).strip(),
        hard_stop_template=str(raw.get("hard_stop_template") or "").strip(),
        manual_contact_template=str(raw.get("manual_contact_template") or "").strip(),
        manual_contact_urgent_suffix=str(
            raw.get("manual_contact_urgent_suffix") or ""
        ).strip(),
    )
    with _LOCK:
        _CACHE[cid] = bundle
    return bundle


def _parse_authored_service_alternatives(raw: object) -> tuple[AuthoredServiceAlternative, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[AuthoredServiceAlternative] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        requested_service_id = str(row.get("requested_service_id") or "").strip()
        if not requested_service_id:
            continue
        alt_ids_raw = row.get("alternative_service_ids")
        approved_text = str(row.get("approved_text") or "").strip()
        alt_ids = (
            [str(x).strip() for x in alt_ids_raw if str(x).strip()]
            if isinstance(alt_ids_raw, list)
            else []
        )
        if not alt_ids or not approved_text:
            continue
        deduped: list[str] = []
        for alt_id in alt_ids:
            if alt_id == requested_service_id or alt_id in deduped:
                continue
            deduped.append(alt_id)
            if len(deduped) >= 2:
                break
        if not deduped:
            continue
        out.append(
            AuthoredServiceAlternative(
                requested_service_id=requested_service_id,
                alternative_service_ids=tuple(deduped),
                approved_text=approved_text,
            )
        )
    return tuple(out)


def load_authored_service_alternatives(client_id: str) -> tuple[AuthoredServiceAlternative, ...]:
    cid = resolve_pack_client_id(client_id)
    with _LOCK:
        if cid in _AUTHORED_ALTS_CACHE:
            return _AUTHORED_ALTS_CACHE[cid]
    path = _policies_path(cid)
    if not os.path.isfile(path):
        authored: tuple[AuthoredServiceAlternative, ...] = ()
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        authored = _parse_authored_service_alternatives(raw.get("service_alternatives"))
    with _LOCK:
        _AUTHORED_ALTS_CACHE[cid] = authored
    return authored


def match_clinic_policy_key(text: str, client_id: str) -> str | None:
    """Deterministic policy match; first matching policy wins."""
    bundle = load_clinic_policies(client_id)
    if bundle is None:
        return None
    low = (text or "").strip().lower().replace("ё", "е")
    if not low:
        return None
    for pol in bundle.policies:
        for trig in pol.triggers:
            if trig in low:
                return pol.key
    return None


def policy_answer(client_id: str, policy_key: str) -> str | None:
    bundle = load_clinic_policies(client_id)
    if bundle is None:
        return None
    for pol in bundle.policies:
        if pol.key == policy_key:
            return pol.answer
    return None


def find_service_alternative(text: str, client_id: str) -> ServiceAlternative | None:
    bundle = load_clinic_policies(client_id)
    if bundle is None:
        return None
    low = (text or "").strip().lower().replace("ё", "е")
    if not low:
        return None
    for alt in bundle.service_alternatives:
        for kw in alt.match_keywords:
            if kw in low:
                return alt
    return None


def find_service_alternative_note(text: str, client_id: str) -> str | None:
    alt = find_service_alternative(text, client_id)
    return alt.note if alt else None


def service_alternative_quick_replies(text: str, client_id: str) -> list[dict[str, str]]:
    alt = find_service_alternative(text, client_id)
    if alt is None or not alt.suggest_ref:
        return []
    label = f"Про {alt.mention}" if alt.mention else "Подробнее"
    return [{"label": label, "ref": alt.suggest_ref}]


def build_service_not_offered_answer(
    client_id: str,
    *,
    question: str = "",
    requested_service: str | None = None,
) -> str:
    alt = find_service_alternative_note(question, client_id)
    if alt:
        return alt.strip()
    bundle = load_clinic_policies(client_id)
    tmpl = (bundle.service_not_offered_template if bundle else "") or ""
    svc = (requested_service or "").strip() or "эту услугу"
    if tmpl:
        return tmpl.format(requested_service=svc)
    return (
        "К сожалению, такую услугу в нашей клинике не оказываем. "
        "Могу подсказать по направлениям, которые у нас есть."
    )
