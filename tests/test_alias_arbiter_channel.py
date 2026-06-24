from __future__ import annotations

from arbiter import build_compact_content_candidates, ref_from_chunk
from content_arbiter import ContentCandidates
from core.candidate_builder import alias_ref_in_unified_pool


def _chunk(file: str, h3: str = "korotko", score: float = 0.7) -> dict:
    return {
        "file": f"clients/demo/md/{file}",
        "h3_id": h3,
        "_score": score,
        "doc_type": "service",
        "text": "snippet",
    }


def test_alias_ref_in_unified_pool_matches_pool_sources() -> None:
    meta = {
        "alias_in_pool": True,
        "pool_sources": [
            {"ref": "implantation__service__classic.md#korotko", "sources": ["semantic", "alias"]},
        ],
    }
    assert alias_ref_in_unified_pool(
        meta, alias_ref="implantation__service__classic.md#korotko"
    )
    assert not alias_ref_in_unified_pool(
        meta, alias_ref="implantation__faq__pain.md#korotko"
    )


from core.candidate_builder import (
    alias_channel_suppressed_for_arbiter,
    alias_ref_in_unified_pool,
)


def test_alias_channel_suppressed_only_when_pool_winner_matches() -> None:
    meta = {
        "alias_in_pool": True,
        "pool_winner_ref": "implantation__info__bone_graft.md#korotko",
        "pool_sources": [
            {"ref": "implantation__service__zygomatic_implants.md#korotko", "sources": ["semantic", "alias"]},
            {"ref": "implantation__info__bone_graft.md#korotko", "sources": ["semantic"]},
        ],
    }
    assert not alias_channel_suppressed_for_arbiter(
        meta, alias_ref="implantation__service__zygomatic_implants.md#korotko"
    )
    meta2 = {
        "alias_in_pool": True,
        "pool_winner_ref": "implantation__service__classic.md#korotko",
        "pool_sources": [
            {"ref": "implantation__service__classic.md#korotko", "sources": ["semantic", "alias"]},
        ],
    }
    assert alias_channel_suppressed_for_arbiter(
        meta2, alias_ref="implantation__service__classic.md#korotko"
    )


def test_build_compact_suppresses_alias_when_in_unified_pool() -> None:
    ch = _chunk("implantation__service__classic.md")
    ref = ref_from_chunk(ch)
    assert ref
    cands = ContentCandidates(
        retrieval={
            "mode": "chunk",
            "chunk": ch,
            "debug_meta": {
                "alias_in_pool": True,
                "pool_winner_ref": ref,
                "pool_sources": [{"ref": ref, "sources": ["semantic", "alias"]}],
            },
        },
        catalog={"mode": "none"},
        alias={
            "leader_chunk": dict(ch),
            "alias_score": 0.88,
            "arbiter_channel": False,
            "channel_suppressed": True,
        },
        session={},
        debug_meta={},
    )
    compact = build_compact_content_candidates(cands, client_id="demo")
    kinds = [r.get("source_kind") for r in compact]
    assert "alias" not in kinds
    assert any(r.get("source_kind") == "retrieval" for r in compact)


def test_build_compact_keeps_alias_channel_when_not_in_pool() -> None:
    leader = _chunk("clinic__info__warranty.md")
    retrieval = _chunk("implantation__faq__pain.md")
    cands = ContentCandidates(
        retrieval={
            "mode": "chunk",
            "chunk": retrieval,
            "debug_meta": {"alias_in_pool": False, "pool_sources": []},
        },
        catalog={"mode": "none"},
        alias={
            "leader_chunk": leader,
            "alias_score": 0.85,
            "arbiter_channel": True,
            "channel_suppressed": False,
        },
        session={},
        debug_meta={},
    )
    compact = build_compact_content_candidates(cands, client_id="demo")
    kinds = [r.get("source_kind") for r in compact]
    assert "alias" in kinds
    assert "retrieval" in kinds
