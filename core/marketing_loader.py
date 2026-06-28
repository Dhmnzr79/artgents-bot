"""Load per-client marketing settings without applying them to answers yet."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import yaml

from core.client_config_loader import resolve_pack_client_id


@dataclass(frozen=True)
class MarketingLimits:
    max_text_ingredients: int = 1
    max_cta: int = 1
    promo_cooldown_turns: int = 3
    proof_cooldown_turns: int = 3


@dataclass(frozen=True)
class MarketingServiceConfig:
    clinic_proof: tuple[str, ...] = ()
    consult_reasons: tuple[str, ...] = ()
    primary_cta_key: str | None = None


@dataclass(frozen=True)
class MarketingPromo:
    key: str
    active: bool = False
    active_until: str | None = None
    fact_ref: str | None = None
    allowed_service_ids: tuple[str, ...] = ()
    allowed_routes: tuple[str, ...] = ()
    allowed_aspects: tuple[str, ...] = ()
    blocked_aspects: tuple[str, ...] = ()
    cta_key: str | None = None


@dataclass(frozen=True)
class MarketingConfig:
    version: int = 1
    limits: MarketingLimits = MarketingLimits()
    blocked_aspects_for_promo: tuple[str, ...] = ()
    service_marketing: dict[str, MarketingServiceConfig] | None = None
    promo_rules: dict[str, MarketingPromo] | None = None

    @property
    def promos(self) -> dict[str, MarketingPromo] | None:
        """Legacy alias; client-facing YAML key is `promo_rules`."""
        return self.promo_rules

    def service(self, service_id: str | None) -> MarketingServiceConfig | None:
        sid = str(service_id or "").strip()
        if not sid:
            return None
        return (self.service_marketing or {}).get(sid)

    def promo(self, promo_key: str | None) -> MarketingPromo | None:
        key = str(promo_key or "").strip()
        if not key:
            return None
        return (self.promo_rules or {}).get(key)


_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, MarketingConfig]] = {}


def marketing_yaml_path(client_id: str | None) -> str:
    pack = resolve_pack_client_id(client_id)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "clients", pack, "marketing.yaml")


def _file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path) if os.path.isfile(path) else 0.0
    except OSError:
        return 0.0


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return tuple(out)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_limits(raw: Any) -> MarketingLimits:
    cfg = raw if isinstance(raw, dict) else {}
    return MarketingLimits(
        max_text_ingredients=_positive_int(cfg.get("max_text_ingredients"), 1),
        max_cta=_positive_int(cfg.get("max_cta"), 1),
        promo_cooldown_turns=_positive_int(cfg.get("promo_cooldown_turns"), 3),
        proof_cooldown_turns=_positive_int(cfg.get("proof_cooldown_turns"), 3),
    )


def _parse_service_marketing(raw: Any) -> dict[str, MarketingServiceConfig]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, MarketingServiceConfig] = {}
    for service_id, cfg_raw in raw.items():
        sid = str(service_id or "").strip()
        if not sid or not isinstance(cfg_raw, dict):
            continue
        cta_key = str(cfg_raw.get("primary_cta_key") or "").strip() or None
        out[sid] = MarketingServiceConfig(
            clinic_proof=_string_tuple(cfg_raw.get("clinic_proof")),
            consult_reasons=_string_tuple(cfg_raw.get("consult_reasons")),
            primary_cta_key=cta_key,
        )
    return out


def _parse_promos(raw: Any) -> dict[str, MarketingPromo]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, MarketingPromo] = {}
    for promo_key, cfg_raw in raw.items():
        key = str(promo_key or "").strip()
        if not key or not isinstance(cfg_raw, dict):
            continue
        active_until = str(cfg_raw.get("active_until") or "").strip() or None
        fact_ref = str(cfg_raw.get("fact_ref") or "").strip() or None
        cta_key = str(cfg_raw.get("cta_key") or "").strip() or None
        out[key] = MarketingPromo(
            key=key,
            active=bool(cfg_raw.get("active")),
            active_until=active_until,
            fact_ref=fact_ref,
            allowed_service_ids=_string_tuple(cfg_raw.get("allowed_service_ids")),
            allowed_routes=_string_tuple(cfg_raw.get("allowed_routes")),
            allowed_aspects=_string_tuple(cfg_raw.get("allowed_aspects")),
            blocked_aspects=_string_tuple(cfg_raw.get("blocked_aspects")),
            cta_key=cta_key,
        )
    return out


def _parse_marketing_config(raw: Any) -> MarketingConfig:
    cfg = raw if isinstance(raw, dict) else {}
    # Client-facing key is `promo_rules`: texts live in PriceBook facts,
    # this section only controls whether/where those facts may be shown.
    promo_rules = cfg.get("promo_rules")
    if promo_rules is None:
        promo_rules = cfg.get("promos")
    return MarketingConfig(
        version=_positive_int(cfg.get("version"), 1),
        limits=_parse_limits(cfg.get("limits")),
        blocked_aspects_for_promo=_string_tuple(cfg.get("blocked_aspects_for_promo")),
        service_marketing=_parse_service_marketing(cfg.get("service_marketing")),
        promo_rules=_parse_promos(promo_rules),
    )


def load_marketing_config(
    client_id: str | None,
    *,
    force_reload: bool = False,
) -> MarketingConfig:
    """Read clients/{id}/marketing.yaml; missing or invalid files become defaults."""
    pack = resolve_pack_client_id(client_id)
    path = marketing_yaml_path(pack)
    mtime = _file_mtime(path)
    if not force_reload:
        with _LOCK:
            cached = _CACHE.get(pack)
            if cached and cached[0] == mtime:
                return cached[1]

    raw: Any = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            raw = {}
    parsed = _parse_marketing_config(raw)
    with _LOCK:
        _CACHE[pack] = (mtime, parsed)
    return parsed
