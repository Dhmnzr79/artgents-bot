from __future__ import annotations

from core.knowledge_base import assemble_client_knowledge_base, clear_knowledge_base_cache


def setup_function() -> None:
    clear_knowledge_base_cache()


def test_knowledge_base_includes_non_implantation_pain_and_duration():
    kb = assemble_client_knowledge_base("demo").lower()
    assert "отбеливание" in kb
    assert "чувствительность" in kb or "дискомфорт" in kb
    assert "винир" in kb
    assert "10–15 лет" in kb or "10-15 лет" in kb


def test_knowledge_base_excludes_doctors_and_service_markup():
    kb = assemble_client_knowledge_base("demo")
    low = kb.lower()
    assert "орлов никита владимирович" not in low
    assert "doc_id:" not in low
    assert "<!-- aliases:" not in kb
    assert "cta_key:" not in kb
