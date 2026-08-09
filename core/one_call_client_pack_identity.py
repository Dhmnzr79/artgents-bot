"""Deterministic client-pack hash and typed identity key (Stage 3A)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from core.one_call_prompt_contract import (
    ONE_CALL_MODEL_SNAPSHOT,
    ONE_CALL_PROMPT_CONTRACT_VERSION,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Authoritative client-owned pack files for ONE_CALL sales-fast path.
# Sources audited against production loaders:
# - corpus: md/**
# - service/catalog/price/facts: target_response/*
# - doctors: doctor_catalog.json
# - marketing/UI: marketing.yaml, ui.yaml, widget_config.json, video_catalog.yaml
# - contacts/configuration: brand.yaml, clinic_policies.yaml, features.yaml,
#   lead_config.yaml, tone.yaml
# Explicit allowlist only — no recursive hash of generated/temp artifacts.
_AUTHORITATIVE_STATIC_RELATIVE = (
    "brand.yaml",
    "clinic_policies.yaml",
    "features.yaml",
    "lead_config.yaml",
    "tone.yaml",
    "ui.yaml",
    "video_catalog.yaml",
    "widget_config.json",
    "doctor_catalog.json",
    "target_response/service_catalog.json",
    "target_response/brand_catalog.json",
    "target_response/marketing.yaml",
    "target_response/clinic_strategy.yaml",
    "target_response/pricebook/facts.json",
)


def authoritative_pack_relative_paths(pack_root: Path) -> tuple[str, ...]:
    """Canonical POSIX-relative paths for all authoritative pack files."""

    root = pack_root.resolve()
    paths: list[str] = []
    for relative in _AUTHORITATIVE_STATIC_RELATIVE:
        path = root / relative
        if path.is_file():
            paths.append(relative.replace("\\", "/"))

    md_root = root / "md"
    if md_root.is_dir():
        md_files = sorted(
            p.relative_to(root).as_posix()
            for p in md_root.rglob("*.md")
            if p.is_file()
        )
        paths.extend(md_files)

    services_dir = root / "target_response" / "pricebook" / "services"
    if services_dir.is_dir():
        service_files = sorted(
            p.relative_to(root).as_posix()
            for p in services_dir.glob("*.json")
            if p.is_file()
        )
        paths.extend(service_files)

    return tuple(sorted(set(paths)))


def compute_client_pack_hash(pack_root: Path) -> str:
    """SHA-256 over canonical path+content tuples; any file change yields new hash."""

    digest = hashlib.sha256()
    for relative in authoritative_pack_relative_paths(pack_root):
        path = pack_root / relative
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\n")
    return digest.hexdigest()


def build_client_pack_identity(client_id: str, pack_root: Path | None = None) -> ClientPackIdentityKey:
    root = pack_root or (_REPO_ROOT / "clients" / client_id)
    if not root.is_dir():
        raise FileNotFoundError(f"client_pack_not_found:{root}")
    return ClientPackIdentityKey(
        client_id=client_id,
        client_pack_hash=compute_client_pack_hash(root),
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        model_snapshot=ONE_CALL_MODEL_SNAPSHOT,
    )
