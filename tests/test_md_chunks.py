"""Unit tests for direct md chunk resolution (core/md_chunks.py)."""

from __future__ import annotations

from core.md_chunks import CONTACTS_CHUNK_REF, get_chunk_by_ref


def test_contacts_korotko_ref():
    chunk = get_chunk_by_ref(CONTACTS_CHUNK_REF, client_id="demo")
    assert isinstance(chunk, dict)
    assert chunk.get("doc_type") == "contacts"
    assert "Москва" in str(chunk.get("text") or "")
    assert (chunk.get("h3_id") or "").lower() == "korotko"


def test_pain_faq_korotko_ref():
    chunk = get_chunk_by_ref("implantation__faq__pain.md#korotko", client_id="demo")
    assert isinstance(chunk, dict)
    assert "имплант" in str(chunk.get("text") or "").lower()


def test_invalid_ref_returns_none():
    assert get_chunk_by_ref("", client_id="demo") is None
    assert get_chunk_by_ref("no-such-doc.md#korotko", client_id="demo") is None
