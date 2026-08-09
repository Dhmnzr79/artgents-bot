"""Typed client-pack identity for ONE_CALL cached FullContext prefix."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PACK_HASH_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ClientPackIdentityKey:
    """Immutable cache identity — never cache by client_id alone."""

    client_id: str
    client_pack_hash: str
    prompt_contract_version: int
    model_snapshot: str

    def __post_init__(self) -> None:
        client_id = (self.client_id or "").strip()
        if not client_id or client_id != self.client_id:
            raise ValueError("client_pack_identity_client_id_invalid")
        if not _PACK_HASH_RE.fullmatch(self.client_pack_hash or ""):
            raise ValueError("client_pack_identity_hash_invalid")
        if self.prompt_contract_version <= 0:
            raise ValueError("client_pack_identity_prompt_version_invalid")
        model_snapshot = (self.model_snapshot or "").strip()
        if not model_snapshot or model_snapshot != self.model_snapshot:
            raise ValueError("client_pack_identity_model_snapshot_invalid")

    def cache_key(self) -> str:
        return (
            f"{self.client_id}:{self.client_pack_hash}:"
            f"p{self.prompt_contract_version}:m{self.model_snapshot}"
        )

    def prefix_fingerprint(self) -> str:
        return self.cache_key()
