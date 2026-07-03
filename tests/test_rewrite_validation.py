"""Rewrite post-validate: session context and attribute synonyms."""

from __future__ import annotations

from llm import validated_retrieval_rewrite


def test_rewrite_accepts_attribute_synonym_duration():
    effective, reason = validated_retrieval_rewrite(
        "А долго это?",
        "All-on-6 длительность процедуры сроки лечения",
    )
    assert reason is None
    assert "all-on-6" in effective.lower()


def test_rewrite_accepts_session_context_anchor():
    effective, reason = validated_retrieval_rewrite(
        "А долго это?",
        "All-on-6 сроки лечения протокол",
        context_anchors=["all_on_6", "Имплантация All-on-6"],
    )
    assert reason is None
    assert effective.startswith("All-on-6")


def test_rewrite_rejects_unrelated_without_context():
    effective, reason = validated_retrieval_rewrite(
        "А долго это?",
        "виниры стоимость эстетика",
        context_anchors=["all_on_6"],
    )
    assert reason == "no_overlap"
    assert effective == "А долго это?"


def test_rewrite_keeps_identical_query():
    effective, reason = validated_retrieval_rewrite("А долго это?", "А долго это?")
    assert reason is None
    assert effective == "А долго это?"
