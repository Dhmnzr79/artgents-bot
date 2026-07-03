"""Tests for client pack resolution."""
from __future__ import annotations

from core.client_config_loader import resolve_pack_client_id


def test_resolve_pack_client_id_alias():
    assert resolve_pack_client_id("default") == "demo"
