"""Unit tests for vague attribute follow-up detection."""

from __future__ import annotations

from core.attribute_followup import (
    catalog_match_is_authoritative,
    detect_vague_attribute_kinds,
    is_vague_attribute_followup,
    query_has_explicit_service_object,
)


def is_vague_price_followup(q: str) -> bool:
    return is_vague_attribute_followup(q, "price")

# --- audit phrases (stem/stop; not route→file) ---


def test_audit_strashno_pain():
    assert is_vague_attribute_followup("Страшно?", "pain")
    assert "pain" in detect_vague_attribute_kinds("Страшно?")


def test_audit_skolko_dlitsya_duration():
    assert is_vague_attribute_followup("А сколько длится?", "duration")
    assert "duration" in detect_vague_attribute_kinds("А сколько длится?")


def test_audit_pod_anesteziej_pain():
    assert is_vague_attribute_followup("А под анестезией?", "pain")
    assert "pain" in detect_vague_attribute_kinds("А под анестезией?")


def test_audit_kto_iz_vrachej_doctor():
    assert is_vague_attribute_followup("Кто из врачей?", "doctor")
    assert "doctor" in detect_vague_attribute_kinds("Кто из врачей?")


def test_chuvstvovat_not_detector_scope():
    """Смысловые формулировки — retrieval/LLM/aspect, не regex-словарь."""
    assert detect_vague_attribute_kinds("Я буду что-то чувствовать?") == []
    assert not is_vague_attribute_followup("Я буду что-то чувствовать?", "pain")


# --- core layer ---


def test_vague_price_via_attribute_layer():
    assert is_vague_attribute_followup("А что по ценам?", "price")
    assert is_vague_price_followup("А что по ценам?")


def test_vague_duration_pain_warranty():
    assert is_vague_attribute_followup("А долго?", "duration")
    assert is_vague_attribute_followup("Больно?", "pain")
    assert is_vague_attribute_followup("Гарантия какая?", "warranty")
    assert "duration" in detect_vague_attribute_kinds("А долго?")


def test_explicit_service_not_vague():
    assert not is_vague_attribute_followup(
        "Сколько длится классическая имплантация?", "duration"
    )
    assert query_has_explicit_service_object(
        "Сколько длится классическая имплантация?", kind="duration"
    )


def test_weak_catalog_not_authoritative_for_vague_duration():
    m = {
        "matched_service_id": "all_on_4",
        "match_channel": "lemma_weak",
        "is_confident": True,
        "containment_eligible": False,
    }
    assert not catalog_match_is_authoritative(m, "А долго?")


def test_doctor_detected_as_attribute_kind_not_aspect():
    kinds = detect_vague_attribute_kinds("Кто делает?")
    assert "doctor" in kinds
    assert "duration" not in kinds
