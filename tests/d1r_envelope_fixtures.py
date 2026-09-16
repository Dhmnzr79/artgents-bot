"""D1R request_understanding envelope fixtures for offline HTTP tests."""

from __future__ import annotations

from core.one_call_envelope_protocol import dumps_production_envelope


def envelope_clinic_policy_only(policy_key: str) -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "clinic_policy",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [policy_key],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                }
            ],
        },
    )


def envelope_content_only(text: str) -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": text,
                }
            ],
        },
    )


def envelope_pediatric_policy_plus_contact(hostile: str) -> str:
    return dumps_production_envelope(
        patient_text=hostile,
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "clinic_policy",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": ["no_pediatric_dentistry"],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                },
                {
                    "request_id": "r2",
                    "kind": "contact",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": ["contact_address"],
                    "content_text": None,
                },
            ],
        },
    )


def envelope_adult_price_cleaning(model_line: str) -> str:
    return dumps_production_envelope(
        patient_text=None,
        commercial_intent="none",
        request_understanding={
            "subjects": [
                {"subject_id": "s1", "relation": "self", "age_group": "adult"},
            ],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": model_line,
                }
            ],
        },
    )


def envelope_adult_booking_only() -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [
                {"subject_id": "s1", "relation": "self", "age_group": "adult"},
            ],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "booking",
                    "subject_id": "s1",
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                }
            ],
        },
    )


def envelope_child_booking_blocked() -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [
                {"subject_id": "s1", "relation": "other", "age_group": "child"},
            ],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "booking",
                    "subject_id": "s1",
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                }
            ],
        },
    )


def envelope_no_subjects_contact_address() -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    "request_id": "r2",
                    "kind": "contact",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": ["contact_address"],
                    "content_text": None,
                }
            ],
        },
    )


def envelope_booking_plus_contact() -> str:
    return dumps_production_envelope(
        patient_text=None,
        request_understanding={
            "subjects": [
                {"subject_id": "s1", "relation": "self", "age_group": "adult"},
            ],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "booking",
                    "subject_id": "s1",
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                },
                {
                    "request_id": "r2",
                    "kind": "contact",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": ["contact_address"],
                    "content_text": None,
                },
            ],
        },
    )
