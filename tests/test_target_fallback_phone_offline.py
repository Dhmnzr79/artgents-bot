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


def test_internal_error_uses_explicit_client_contacts() -> None:
    demo_phone = canonical_contact_phone("demo")
    nika_phone = canonical_contact_phone("nikadent")
    demo_resp = internal_error_response(client_id="demo")
    nika_resp = internal_error_response(client_id="nikadent")
    assert demo_phone in demo_resp["answer"]
    assert demo_phone not in nika_resp["answer"]
    assert nika_phone in nika_resp["answer"]
    assert demo_resp["meta"]["attribution_kind"] == "plain"


def test_internal_error_without_client_is_neutral_no_demo_phone() -> None:
    demo_phone = canonical_contact_phone("demo")
    resp = internal_error_response()
    assert demo_phone not in resp["answer"]
    assert "Что-то пошло не так" in resp["answer"]
    assert resp["meta"]["attribution_kind"] == "plain"


def test_internal_error_survives_unavailable_contact_source(monkeypatch) -> None:
    import yaml

    def _yaml_fail(_path: object) -> object:
        raise yaml.YAMLError("corrupt policies")

    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts_from_policies_path",
        _yaml_fail,
    )
    resp = internal_error_response(client_id="nikadent")
    assert resp["meta"]["error"] == "internal"
    assert "Что-то пошло не так" in resp["answer"]
    assert "+7 (495) 128-47-60" not in resp["answer"]
