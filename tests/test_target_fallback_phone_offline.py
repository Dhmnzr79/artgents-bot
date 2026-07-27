"""Offline tests for fallback/handoff canonical phone injection."""

from __future__ import annotations

from core.target_contact_authority import canonical_contact_phone
from core.target_runtime_widget import materialize_target_error_payload
from ux_builder import internal_error_response


def test_verifier_block_payload_has_phone_only() -> None:
    phone = canonical_contact_phone("demo")
    payload = materialize_target_error_payload(
        client_id="demo",
        sid="s1",
        error_code="target_verifier_semantic_rejected",
    ).payload
    assert phone in payload["answer"]
    assert payload["quick_replies"] == []
    assert payload["cta"] is None
    assert payload["video"] is None
    assert payload["situation"]["show"] is False
    assert payload["meta"]["attribution_kind"] == "plain"


def test_internal_error_plain_attribution() -> None:
    resp = internal_error_response()
    assert resp["meta"]["attribution_kind"] == "plain"
    assert canonical_contact_phone("demo") in resp["answer"]
