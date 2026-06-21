"""Compatibility guard unit tests (PRODUCT_WORK_PLAN stage 4a)."""

from __future__ import annotations

from core.compatibility_guard import (
    filter_compact_by_compatibility_guard,
    has_service_conflict,
    is_clinic_cross_cutting,
)


def test_warranty_passes_for_classic_focus():
    compact = [
        {
            "ref": "clinic__info__warranty.md#korotko",
            "topic": "clinic",
            "doc_type": "info",
            "score": 0.52,
        },
        {
            "ref": "implantation__service__classic.md#korotko",
            "topic": "implantation",
            "doc_type": "catalog_md",
            "score": 0.48,
        },
    ]
    focus = {
        "service_id": "classic",
        "topic": "implantation",
        "label": "классическую имплантацию",
    }
    kept, rejected, tel = filter_compact_by_compatibility_guard(
        compact,
        rewritten_query="гарантия на классическую имплантацию",
        focus=focus,
        client_id="demo",
    )
    assert len(kept) >= 1
    assert any("warranty" in r["ref"] for r in kept)
    assert tel["guard_pass_reason"] == "pass"


def test_braces_candidate_conflicts_with_classic_focus():
    row = {
        "ref": "orthodontics__service__braces.md#korotko",
        "topic": "orthodontics",
        "service_id": "braces",
        "score": 0.7,
    }
    focus = {"service_id": "classic", "topic": "implantation", "label": "classic"}
    assert has_service_conflict(row, focus) is True


def test_clinic_warranty_not_a_conflict():
    row = {
        "ref": "clinic__info__warranty.md#korotko",
        "topic": "clinic",
        "score": 0.5,
    }
    focus = {"service_id": "classic", "topic": "implantation", "label": "classic"}
    assert is_clinic_cross_cutting(row) is True
    assert has_service_conflict(row, focus) is False


def test_filter_drops_conflicting_service():
    compact = [
        {
            "ref": "orthodontics__service__braces.md#korotko",
            "topic": "orthodontics",
            "service_id": "braces",
            "score": 0.8,
        },
        {
            "ref": "clinic__info__warranty.md#korotko",
            "topic": "clinic",
            "score": 0.4,
        },
    ]
    focus = {"service_id": "classic", "topic": "implantation", "label": "classic"}
    kept, rejected, tel = filter_compact_by_compatibility_guard(
        compact,
        rewritten_query="гарантия на классическую имплантацию",
        focus=focus,
        client_id="demo",
    )
    assert not any("braces" in r["ref"] for r in kept)
    assert any(r.get("compat_reject_reason") == "service_conflict" for r in rejected)
    assert tel["compat_guard_rejected"] >= 1
