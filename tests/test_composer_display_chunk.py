from __future__ import annotations

from contracts.answer_plan import AnswerPlan


def _plan(
    *,
    aspects: list[str],
    primary_aspect: str | None,
    topic: str | None,
) -> AnswerPlan:
    return AnswerPlan(
        aspects=aspects,  # type: ignore[arg-type]
        primary_aspect=primary_aspect,  # type: ignore[arg-type]
        topic=topic,
    )


def test_topic_aspect_display_chunk_restores_pain_metadata(monkeypatch):
    from chunk_responder import _composer_display_chunk, meta_for_chunk

    monkeypatch.setattr(
        "chunk_responder.answer_plan_from_ctx",
        lambda: _plan(aspects=["pain"], primary_aspect="pain", topic="implantation"),
    )

    chunk = _composer_display_chunk(
        client_id="demo",
        matched_service_id=None,
        primary_chunk_ref=None,
    )
    meta = meta_for_chunk(chunk, client_id="demo")

    assert chunk["file"] == "implantation__faq__pain.md"
    assert chunk["h3_id"] == "korotko"
    assert meta["suggest_h3"]
    assert meta["video_key"] == "pain-doctor-explains"
    assert meta["situation_allowed"] is True
    assert meta["cta_key"] == "consult"


def test_aspect_only_display_chunk_uses_unique_warranty_file(monkeypatch):
    from chunk_responder import _composer_display_chunk

    monkeypatch.setattr(
        "chunk_responder.answer_plan_from_ctx",
        lambda: _plan(aspects=["warranty"], primary_aspect="warranty", topic="implantation"),
    )

    chunk = _composer_display_chunk(
        client_id="demo",
        matched_service_id=None,
        primary_chunk_ref=None,
    )

    assert chunk["file"] == "clinic__info__warranty.md"
    assert chunk["h3_id"] == "korotko"


def test_aspect_only_display_chunk_does_not_guess_when_ambiguous(monkeypatch):
    from chunk_responder import _composer_display_chunk

    monkeypatch.setattr(
        "chunk_responder.answer_plan_from_ctx",
        lambda: _plan(aspects=["duration"], primary_aspect="duration", topic="clinic"),
    )

    chunk = _composer_display_chunk(
        client_id="demo",
        matched_service_id=None,
        primary_chunk_ref=None,
    )

    assert chunk["file"] == "composer.md"
    assert chunk["h3_id"] is None


def test_service_display_chunk_uses_catalog_md_entry_ref_for_veneers(monkeypatch):
    from chunk_responder import _composer_display_chunk

    monkeypatch.setattr("chunk_responder.answer_plan_from_ctx", lambda: None)

    chunk = _composer_display_chunk(
        client_id="demo",
        matched_service_id="veneers",
        primary_chunk_ref=None,
    )

    assert chunk["file"] == "prosthetics__service__veneers.md"
    assert chunk["h3_id"] == "korotko"


def test_primary_ref_still_wins_for_price_display_chunk(monkeypatch):
    from chunk_responder import _composer_display_chunk

    monkeypatch.setattr(
        "chunk_responder.answer_plan_from_ctx",
        lambda: _plan(aspects=["price"], primary_aspect="price", topic="implantation"),
    )

    chunk = _composer_display_chunk(
        client_id="demo",
        matched_service_id="all_on_4",
        primary_chunk_ref="implantation__faq__cost.md#korotko",
    )

    assert chunk["file"] == "implantation__faq__cost.md"
    assert chunk["h3_id"] == "korotko"
