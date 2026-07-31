"""Implementation tests for FINAL_LOCAL_LEXICAL_PARAGRAPH_INDEX / PERF-7A.

Covers: deterministic recursive MD discovery, frontmatter/body separation, H2/H3 section and
fence-aware block splitting, the 40-char minimum-unit merge rule, deterministic paragraph IDs/
ordering/fingerprint, add/change/delete corpus reactivity (via ``tmp_path`` fixtures only -- never
``clients/**``), lexical search ranking (exact/prefix/ё-е normalization/tie-breaking), input
validation, an honest Russian-language lexical miss inventory, and the module's own isolation
guarantees (no SQLite/FTS5/embeddings/network, no aliases/synonym dictionary, no runtime imports,
no logging of queries or raw hit text).

Only synthetic fixtures and ``tmp_path`` are used to exercise the splitting/ranking rules --
never real user-log text. A handful of tests build the real ``clients/demo/md`` corpus (read-only)
to prove the module works end-to-end on real data, but assert nothing that requires guessing a
literal historical document count.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from core.target_lexical_paragraph_index import (  # noqa: E402
    TargetLexicalParagraphIndex,
    TargetLexicalParagraphIndexError,
    build_target_lexical_paragraph_index,
    search_target_lexical_paragraph_index,
)

MODULE_PATH = _REPO_ROOT / "core" / "target_lexical_paragraph_index.py"
GOVERNANCE_BASELINE_HEAD = "1d5bda6"


def _write_md(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


_BASE_FRONTMATTER = """---
doc_id: {doc_id}
doc_type: {doc_type}
topic: {topic}
---
"""


def _md(doc_id: str, doc_type: str, topic: str, body: str) -> str:
    return _BASE_FRONTMATTER.format(doc_id=doc_id, doc_type=doc_type, topic=topic) + body


# --------------------------------------------------------------------------------------------
# 1. Deterministic recursive discovery
# --------------------------------------------------------------------------------------------


def test_deterministic_recursive_discovery(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"))
    _write_md(tmp_path, "nested/b.md", _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n"))
    _write_md(tmp_path, "nested/deeper/c.md", _md("c", "info", "clinic", "## H\n\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n"))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.document_count == 3
    paths = sorted({p.document_path for p in index.paragraphs})
    assert paths == ["a.md", "nested/b.md", "nested/deeper/c.md"]


def test_non_md_files_ignored(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"))
    (tmp_path / "notes.txt").write_text("not markdown", encoding="utf-8")
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.document_count == 1


def test_empty_corpus_raises_typed_error(tmp_path: Path) -> None:
    with pytest.raises(TargetLexicalParagraphIndexError) as excinfo:
        build_target_lexical_paragraph_index(tmp_path)
    assert excinfo.value.code == "lexical_index_corpus_empty"


def test_missing_md_root_raises_typed_error(tmp_path: Path) -> None:
    with pytest.raises(TargetLexicalParagraphIndexError) as excinfo:
        build_target_lexical_paragraph_index(tmp_path / "does_not_exist")
    assert excinfo.value.code == "lexical_index_md_root_invalid"


# --------------------------------------------------------------------------------------------
# 2. Frontmatter excluded from searchable body / 3. doc_id/doc_type/topic / 4. missing metadata
# --------------------------------------------------------------------------------------------


def test_frontmatter_excluded_from_searchable_text(tmp_path: Path) -> None:
    body = "## Раздел\n\nСодержимое документа про слонов и жирафов действительно длинное.\n"
    content = (
        "---\n"
        "doc_id: frontmatter_probe\n"
        "doc_type: info\n"
        "topic: clinic\n"
        "aliases:\n"
        "  - \"уникальныйфронтматтертокен\"\n"
        "---\n" + body
    )
    _write_md(tmp_path, "doc.md", content)
    index = build_target_lexical_paragraph_index(tmp_path)
    combined = " ".join(p.normalized_searchable_text for p in index.paragraphs)
    assert "уникальныйфронтматтертокен" not in combined
    assert "слонов" in combined


def test_doc_id_doc_type_topic_extracted(tmp_path: Path) -> None:
    _write_md(
        tmp_path,
        "doc.md",
        _md("my_doc_id", "faq", "implantation", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"),
    )
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraphs[0].document_identity == "my_doc_id"
    assert index.paragraphs[0].document_type == "faq"
    assert index.paragraphs[0].topic == "implantation"


def test_missing_optional_metadata_is_none_not_error(tmp_path: Path) -> None:
    _write_md(tmp_path, "doc.md", "---\ndoc_id: only_id\n---\n## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n")
    index = build_target_lexical_paragraph_index(tmp_path)
    paragraph = index.paragraphs[0]
    assert paragraph.document_identity == "only_id"
    assert paragraph.document_type is None
    assert paragraph.topic is None
    # Search must still work with metadata missing.
    hits = search_target_lexical_paragraph_index(index, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", limit=5)
    assert len(hits) == 1


def test_no_frontmatter_at_all_is_not_an_error(tmp_path: Path) -> None:
    _write_md(tmp_path, "doc.md", "## H\n\nContent without any frontmatter block at all here.\n")
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.document_count == 1
    assert index.paragraphs[0].document_identity is None


# --------------------------------------------------------------------------------------------
# 5. H2/H3 sections / 6. fenced headings ignored / 7. paragraph+list blocks
# --------------------------------------------------------------------------------------------


def test_h2_h3_create_section_boundaries(tmp_path: Path) -> None:
    body = (
        "## Первый раздел\n\n"
        "Текст первого раздела достаточно длинный чтобы не сливаться с соседями вообще.\n\n"
        "### Второй подраздел\n\n"
        "Текст второго подраздела тоже достаточно длинный чтобы не сливаться ни с чем.\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    headings = [p.heading for p in index.paragraphs]
    assert headings == ["Первый раздел", "Второй подраздел"]


def test_h1_does_not_count_as_section_heading(tmp_path: Path) -> None:
    body = (
        "# Заголовок документа верхнего уровня\n\n"
        "Текст под H1 длинный достаточно чтобы остаться отдельным блоком без слияния тут.\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraphs[0].heading is None


def test_heading_anchor_suffix_stripped_from_heading_label(tmp_path: Path) -> None:
    body = (
        "### Коротко {#korotko}\n\n"
        "Содержимое раздела с явным якорем в заголовке достаточно длинное для теста тут.\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraphs[0].heading == "Коротко"


def test_heading_marker_inside_fenced_code_is_not_a_section_boundary(tmp_path: Path) -> None:
    body = (
        "## Реальный раздел\n\n"
        "```\n"
        "## Это не заголовок, это код внутри ограждения тройными обратными кавычками\n"
        "```\n\n"
        "### Настоящий подраздел после ограждения кода идёт тут длинным текстом вот\n\n"
        "Содержимое настоящего подраздела достаточно длинное чтобы не сливаться никак.\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    headings = [p.heading for p in index.paragraphs]
    assert "Это не заголовок, это код внутри ограждения тройными обратными кавычками" not in headings
    assert any(h == "Реальный раздел" for h in headings)
    fence_paragraph = next(p for p in index.paragraphs if "```" in p.text)
    assert "## Это не заголовок" in fence_paragraph.text


def test_paragraph_and_list_blocks_split_separately(tmp_path: Path) -> None:
    body = (
        "## Раздел со списком\n\n"
        "Вводный абзац перед списком достаточно длинный чтобы остаться отдельным блоком.\n\n"
        "- Первый пункт списка длинный сам по себе\n"
        "- Второй пункт списка тоже длинный сам по себе\n"
        "- Третий пункт списка тоже длинный сам по себе\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraph_count == 2
    assert "Вводный абзац" in index.paragraphs[0].text
    assert index.paragraphs[1].text.count("\n") == 2  # three list lines joined


# --------------------------------------------------------------------------------------------
# 8. Short meaningful fact not dropped (40-char minimum-unit merge rule)
# --------------------------------------------------------------------------------------------


def test_short_block_merges_forward_and_is_not_dropped(tmp_path: Path) -> None:
    body = (
        "## Раздел\n\n"
        "Коротко.\n\n"  # 8 chars -- below the 40-char minimum
        "Второй, гораздо более длинный абзац который точно длиннее сорока символов сам.\n"
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraph_count == 1
    assert "Коротко." in index.paragraphs[0].text
    assert "Второй, гораздо более длинный" in index.paragraphs[0].text


def test_short_trailing_block_merges_backward_and_is_not_dropped(tmp_path: Path) -> None:
    body = (
        "## Раздел\n\n"
        "Первый, гораздо более длинный абзац который точно длиннее сорока символов сам.\n\n"
        "Хвост.\n"  # 6 chars -- below the 40-char minimum, last block in the section
    )
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraph_count == 1
    assert "Первый, гораздо более длинный" in index.paragraphs[0].text
    assert "Хвост." in index.paragraphs[0].text


def test_lone_short_block_kept_whole_as_entire_section(tmp_path: Path) -> None:
    body = "## Раздел\n\nКоротко.\n"  # single block, only 8 chars, nothing to merge into
    _write_md(tmp_path, "doc.md", _md("d", "info", "clinic", body))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert index.paragraph_count == 1
    assert index.paragraphs[0].text == "Коротко."


# --------------------------------------------------------------------------------------------
# 9. Stable unique paragraph IDs / 10. deterministic ordering / 11. deterministic fingerprint
# --------------------------------------------------------------------------------------------


def test_paragraph_ids_unique_and_reference_document_not_absolute_path(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n"))
    index = build_target_lexical_paragraph_index(tmp_path)
    ids = [p.paragraph_id for p in index.paragraphs]
    assert len(ids) == len(set(ids))
    for paragraph_id in ids:
        assert str(tmp_path) not in paragraph_id
        assert not paragraph_id.startswith("/")
        assert paragraph_id.startswith("a.md#p")


def test_build_is_deterministic_across_repeated_calls(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"))
    _write_md(tmp_path, "b.md", _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n"))
    first = build_target_lexical_paragraph_index(tmp_path)
    second = build_target_lexical_paragraph_index(tmp_path)
    assert first.fingerprint == second.fingerprint
    assert tuple(p.paragraph_id for p in first.paragraphs) == tuple(p.paragraph_id for p in second.paragraphs)


# --------------------------------------------------------------------------------------------
# 12-14. Add / change / delete corpus reactivity
# --------------------------------------------------------------------------------------------


def test_new_md_automatically_included_on_next_build(tmp_path: Path) -> None:
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"))
    before = build_target_lexical_paragraph_index(tmp_path)
    assert before.document_count == 1
    _write_md(tmp_path, "b.md", _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n"))
    after = build_target_lexical_paragraph_index(tmp_path)
    assert after.document_count == 2
    assert after.fingerprint != before.fingerprint
    assert any(p.document_path == "b.md" for p in after.paragraphs)


def test_changed_md_changes_fingerprint_and_content(tmp_path: Path) -> None:
    path = _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nOriginal content long enough to survive merge rule easily here.\n"))
    before = build_target_lexical_paragraph_index(tmp_path)
    path.write_text(_md("a", "info", "clinic", "## H\n\nModified content long enough to survive merge rule easily too.\n"), encoding="utf-8")
    after = build_target_lexical_paragraph_index(tmp_path)
    assert after.fingerprint != before.fingerprint
    assert before.paragraphs[0].content_hash != after.paragraphs[0].content_hash
    assert "Modified" in after.paragraphs[0].text


def test_deleted_md_disappears_from_next_build(tmp_path: Path) -> None:
    path_b = _write_md(tmp_path, "b.md", _md("b", "info", "clinic", "## H\n\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n"))
    _write_md(tmp_path, "a.md", _md("a", "info", "clinic", "## H\n\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"))
    before = build_target_lexical_paragraph_index(tmp_path)
    assert before.document_count == 2
    path_b.unlink()
    after = build_target_lexical_paragraph_index(tmp_path)
    assert after.document_count == 1
    assert all(p.document_path != "b.md" for p in after.paragraphs)
    assert after.fingerprint != before.fingerprint


# --------------------------------------------------------------------------------------------
# 15-19. Lexical search ranking
# --------------------------------------------------------------------------------------------


def _ranking_fixture_index(tmp_path: Path) -> TargetLexicalParagraphIndex:
    _write_md(
        tmp_path,
        "exact.md",
        _md("exact", "faq", "clinic", "## H\n\nВопрос про стерилизацию инструментов в клинике описан здесь подробно.\n"),
    )
    _write_md(
        tmp_path,
        "prefixonly.md",
        _md("prefixonly", "faq", "clinic", "## H\n\nСтерилизационное оборудование клиники соответствует высоким стандартам всегда.\n"),
    )
    _write_md(
        tmp_path,
        "unrelated.md",
        _md("unrelated", "faq", "clinic", "## H\n\nЭтот документ вообще не имеет отношения к теме запроса совсем никак.\n"),
    )
    return build_target_lexical_paragraph_index(tmp_path)


def test_exact_token_ranks_above_prefix_only(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    hits = search_target_lexical_paragraph_index(index, "стерилизацию", limit=5)
    assert len(hits) >= 1
    assert hits[0].paragraph.document_path == "exact.md"
    assert hits[0].exact_token_matches == 1
    assert hits[0].prefix_token_matches == 0


def test_prefix_matching_recovers_same_root_word_form(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    hits = search_target_lexical_paragraph_index(index, "стерилизац", limit=5)
    paths = {h.paragraph.document_path for h in hits}
    assert "exact.md" in paths
    assert "prefixonly.md" in paths
    prefix_hit = next(h for h in hits if h.paragraph.document_path == "prefixonly.md")
    assert prefix_hit.prefix_token_matches == 1
    assert prefix_hit.exact_token_matches == 0


def test_short_query_token_does_not_prefix_match(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    # "сте" is 3 chars, below the minimum prefix length -- must not match "стерилизацию"/"стерилизационное".
    hits = search_target_lexical_paragraph_index(index, "сте", limit=5)
    assert hits == ()


def test_unrelated_paragraph_never_scores(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    hits = search_target_lexical_paragraph_index(index, "стерилизацию", limit=5)
    assert all(h.paragraph.document_path != "unrelated.md" for h in hits)


def test_yo_ye_normalization_matches_both_directions(tmp_path: Path) -> None:
    _write_md(tmp_path, "yo.md", _md("yo", "info", "clinic", "## H\n\nЁжик и ёлка стоят рядом в приёмном отделении клиники давно уже тут.\n"))
    index = build_target_lexical_paragraph_index(tmp_path)
    assert "ё" not in index.paragraphs[0].normalized_searchable_text
    hits_from_yo_query = search_target_lexical_paragraph_index(index, "ёлка", limit=5)
    hits_from_ye_query = search_target_lexical_paragraph_index(index, "елка", limit=5)
    assert len(hits_from_yo_query) == 1
    assert len(hits_from_ye_query) == 1
    assert hits_from_yo_query[0].paragraph.paragraph_id == hits_from_ye_query[0].paragraph.paragraph_id


def test_punctuation_and_case_normalization(tmp_path: Path) -> None:
    _write_md(
        tmp_path,
        "case.md",
        _md("case", "info", "clinic", "## H\n\nИМПЛАНТАЦИЯ, — это серьёзная процедура; требующая: внимания! точно.\n"),
    )
    index = build_target_lexical_paragraph_index(tmp_path)
    normalized = index.paragraphs[0].normalized_searchable_text
    for punct in (",", "—", ";", ":", "!"):
        assert punct not in normalized
    hits = search_target_lexical_paragraph_index(index, "имплантация", limit=5)
    assert len(hits) == 1


def test_deterministic_tie_breaking_on_equal_score(tmp_path: Path) -> None:
    _write_md(tmp_path, "z.md", _md("z", "info", "clinic", "## H\n\nОдинаковый текст запроса тест тест тест тест тест тест дважды тут.\n"))
    _write_md(tmp_path, "y.md", _md("y", "info", "clinic", "## H\n\nОдинаковый текст запроса тест тест тест тест тест тест дважды тут.\n"))
    index = build_target_lexical_paragraph_index(tmp_path)
    hits_1 = search_target_lexical_paragraph_index(index, "одинаковый текст", limit=5)
    hits_2 = search_target_lexical_paragraph_index(index, "одинаковый текст", limit=5)
    assert [h.paragraph.paragraph_id for h in hits_1] == [h.paragraph.paragraph_id for h in hits_2]
    assert hits_1[0].score == hits_1[1].score
    assert hits_1[0].paragraph.paragraph_id < hits_1[1].paragraph.paragraph_id  # y.md before z.md


# --------------------------------------------------------------------------------------------
# 20-21. limit / empty-query validation
# --------------------------------------------------------------------------------------------


def test_limit_one_returns_single_top_hit(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    hits = search_target_lexical_paragraph_index(index, "стерилизацию", limit=1)
    assert len(hits) == 1


@pytest.mark.parametrize("bad_limit", [0, -1, -100])
def test_non_positive_limit_raises_typed_error(tmp_path: Path, bad_limit: int) -> None:
    index = _ranking_fixture_index(tmp_path)
    with pytest.raises(TargetLexicalParagraphIndexError) as excinfo:
        search_target_lexical_paragraph_index(index, "стерилизацию", limit=bad_limit)
    assert excinfo.value.code == "lexical_index_search_limit_invalid"


def test_non_int_limit_raises_typed_error(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    with pytest.raises(TargetLexicalParagraphIndexError):
        search_target_lexical_paragraph_index(index, "стерилизацию", limit=1.5)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_query", ["", "   ", "\t\n"])
def test_empty_query_raises_typed_error_never_returns_silently(tmp_path: Path, bad_query: str) -> None:
    index = _ranking_fixture_index(tmp_path)
    with pytest.raises(TargetLexicalParagraphIndexError) as excinfo:
        search_target_lexical_paragraph_index(index, bad_query, limit=5)
    assert excinfo.value.code == "lexical_index_search_query_empty"


def test_non_string_query_raises_typed_error(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    with pytest.raises(TargetLexicalParagraphIndexError):
        search_target_lexical_paragraph_index(index, 12345, limit=5)  # type: ignore[arg-type]


def test_query_producing_zero_tokens_is_empty_result_not_error(tmp_path: Path) -> None:
    index = _ranking_fixture_index(tmp_path)
    hits = search_target_lexical_paragraph_index(index, "???!!!", limit=5)
    assert hits == ()


# --------------------------------------------------------------------------------------------
# Honest Russian-language lexical miss inventory (synthetic fixtures only)
# --------------------------------------------------------------------------------------------


def test_honest_russian_lexical_capability_inventory(tmp_path: Path) -> None:
    """Records, with assertions (not just prose), what this simple token-overlap+prefix approach
    does and does not cover on Russian text. A miss here is not a product defect -- it is exactly
    the signal a future EvidencePackageBuilder must treat as a FullContext-fallback trigger, per
    the PERF-7 seam audit §11. Nothing here is tuned/patched to make a specific case pass --
    misses are asserted as misses, honestly."""

    _write_md(
        tmp_path,
        "doc.md",
        _md(
            "doc",
            "faq",
            "clinic",
            "## H\n\n"
            "Имплантация зубов проводится опытными врачами клиники по современным протоколам всегда.\n",
        ),
    )
    index = build_target_lexical_paragraph_index(tmp_path)

    # COVERED: exact match.
    assert search_target_lexical_paragraph_index(index, "имплантация", limit=5) != ()
    # COVERED: case-insensitive.
    assert search_target_lexical_paragraph_index(index, "ИМПЛАНТАЦИЯ", limit=5) != ()
    # COVERED: prefix/common-root word-form variation (nominative "имплантация" vs genitive-ish stem).
    assert search_target_lexical_paragraph_index(index, "имплантаци", limit=5) != ()
    # COVERED: mixed Cyrillic/Latin query still tokenizes and finds the Cyrillic hit.
    assert search_target_lexical_paragraph_index(index, "имплантация ABC123", limit=5) != ()

    # NOT COVERED (honest miss): a word form whose stem is shared but the shared prefix is very
    # short is deliberately not prefix-matched (avoids over-matching) -- "зуб" (3 chars) will not
    # prefix-match "зубов" even though a human reader would consider them related.
    assert search_target_lexical_paragraph_index(index, "зуб", limit=5) == ()

    # NOT COVERED (honest miss): a fully paraphrased question sharing no lexical tokens with the
    # source paragraph at all -- exactly the case a future Builder must resolve via FullContext
    # fallback, not via this index. (Deliberately avoids any word already present in the source
    # paragraph -- "зубов"/"клиники"/"протоколам"/etc -- so this is a genuine zero-overlap probe,
    # not an accidental partial match.)
    assert (
        search_target_lexical_paragraph_index(
            index, "расскажите про восстановление отсутствующих элементов альтернативным способом", limit=5
        )
        == ()
    )


# --------------------------------------------------------------------------------------------
# 27-29. Real demo corpus (read-only) end-to-end proof
# --------------------------------------------------------------------------------------------

_DEMO_MD_ROOT = _REPO_ROOT / "clients" / "demo" / "md"


def test_demo_index_builds_successfully_from_all_current_md() -> None:
    index = build_target_lexical_paragraph_index(_DEMO_MD_ROOT)
    assert index.paragraph_count > 0
    assert index.document_count > 0


def test_demo_document_count_matches_live_recursive_discovery_not_hardcoded() -> None:
    expected = len(list(_DEMO_MD_ROOT.rglob("*.md")))
    index = build_target_lexical_paragraph_index(_DEMO_MD_ROOT)
    assert index.document_count == expected


def test_demo_search_hit_returns_document_and_paragraph_identity_not_anonymous_chunk() -> None:
    index = build_target_lexical_paragraph_index(_DEMO_MD_ROOT)
    hits = search_target_lexical_paragraph_index(index, "имплантация", limit=3)
    assert hits != ()
    for hit in hits:
        assert hit.paragraph.document_path
        assert hit.paragraph.document_path.endswith(".md")
        assert hit.paragraph.paragraph_id.startswith(hit.paragraph.document_path)


# --------------------------------------------------------------------------------------------
# 22-25, 30. Isolation guarantees -- no aliases dict, no SQLite/FTS5, no embeddings/network,
# no runtime imports, no logging of queries/raw text.
# --------------------------------------------------------------------------------------------


def _module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _module_ast() -> ast.Module:
    return ast.parse(_module_source())


def test_no_alias_or_synonym_dictionary_in_module() -> None:
    source = _module_source().lower()
    for forbidden in ("alias", "synonym", "словар"):
        assert forbidden not in source, forbidden


def test_no_sqlite_or_fts5_imported_or_referenced() -> None:
    """No executable SQLite/FTS5 usage -- the module's own docstring legitimately *discusses* why
    FTS5 was not chosen (PERF-7 seam audit rationale), so this checks actual code shapes, not the
    English word "fts5" appearing anywhere in prose."""

    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] == "sqlite3" for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] != "sqlite3"
    source = _module_source().lower()
    for forbidden in ("create virtual table", "sqlite3.connect", ".execute(", "bm25("):
        assert forbidden not in source, forbidden


def test_no_embeddings_network_or_llm_imports() -> None:
    tree = _module_ast()
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "urllib",
        "socket",
        "numpy",
        "torch",
        "sentence_transformers",
        "sklearn",
        "faiss",
    }
    assert not (imported & forbidden), imported & forbidden
    assert imported <= {"__future__", "hashlib", "re", "unicodedata", "dataclasses", "pathlib", "typing", "frontmatter"}


def test_no_new_third_party_dependency_beyond_already_used_frontmatter() -> None:
    tree = _module_ast()
    third_party_imports: set[str] = set()
    stdlib = {"__future__", "hashlib", "re", "unicodedata", "dataclasses", "pathlib", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            third_party_imports.update(
                alias.name.split(".")[0] for alias in node.names if alias.name.split(".")[0] not in stdlib
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top not in stdlib:
                third_party_imports.add(top)
    assert third_party_imports == {"frontmatter"}


def test_no_global_mutable_cache_in_module() -> None:
    # __all__ is the standard static export list, not a cache -- explicitly exempt.
    exempt_names = {"__all__"}
    tree = _module_ast()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id not in exempt_names
                    and isinstance(node.value, (ast.Dict, ast.List, ast.Set))
                ):
                    raise AssertionError(f"unexpected module-level mutable global: {target.id}")


def test_no_logging_or_print_calls_in_module() -> None:
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "print"
        if isinstance(node, ast.Attribute) and node.attr in {
            "info",
            "warning",
            "error",
            "debug",
            "emit_bot_event",
        }:
            raise AssertionError(f"unexpected logging-shaped call: {node.attr}")
    source = _module_source().lower()
    assert "import logging" not in source
    assert "get_logger" not in source


def test_module_not_imported_by_any_real_runtime_path() -> None:
    """Only real Python ``import``/``from ... import`` statements count as a runtime import --
    prose mentions in TASK.md/the seam audit/the governance checker's existence assertions are
    expected and must not fail this check.

    PERF-7B correction: this originally asserted that *no* module besides this file's own pair
    imported ``target_lexical_paragraph_index`` at all. That went stale the moment PERF-7B shipped
    -- ``core/target_evidence_package_builder.py`` legitimately imports it through its public
    ``search_target_lexical_paragraph_index`` API (that dependency is the entire point of PERF-7B),
    and PERF-7C's own offline eval runner/contract test legitimately import it too. None of those
    three are wired to any real runtime path either (proven by their own equivalent isolation
    tests) -- so the invariant that actually matters, and the one this test now checks, is that no
    *real runtime* module (``app.py``, the Composer/Verifier/pipeline chain, session handling,
    ``TurnFrame`` handling) imports this module -- not that the module has exactly zero non-runtime
    consumers, which was always going to grow as PERF-7 progressed."""

    proc = subprocess.run(
        ["git", "grep", "-nE", r"^\s*(from|import)\s+.*target_lexical_paragraph_index", "--", "*.py"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode not in (0, 1):
        pytest.skip(f"git grep unavailable: {proc.stderr.strip()}")
    hits = [line for line in proc.stdout.splitlines() if line.strip()]
    allowed_files = {
        "core/target_lexical_paragraph_index.py",
        "tests/test_final_local_lexical_paragraph_index_implementation.py",
        # PERF-7B: the Builder legitimately consumes the public search API -- still unwired to
        # runtime itself (see tests/test_final_local_evidence_package_builder_implementation.py's
        # own "not imported by any runtime path" proof).
        "core/target_evidence_package_builder.py",
        "tests/test_final_local_evidence_package_builder_implementation.py",
        # PERF-7C: the offline eval runner and its contract test build the index directly.
        "evals/v5/run_perf7c_local_evidence_package_eval.py",
        "tests/test_final_local_evidence_package_eval_contract.py",
    }
    real_runtime_files = {
        "app.py",
        "session.py",
        "core/target_composer_executor.py",
        "core/target_response_verifier.py",
        "core/target_verified_response_pipeline.py",
        "core/target_policy_bound_verified_response_pipeline.py",
        "core/target_composer_request.py",
        "contracts/turn_frame.py",
    }
    unexpected = [
        line
        for line in hits
        if not any(line.startswith(f"{path}:") for path in allowed_files)
    ]
    runtime_hits = [line for line in hits if any(line.startswith(f"{path}:") for path in real_runtime_files)]
    assert runtime_hits == [], runtime_hits
    # Any import from a file outside both the allowed and known-runtime sets is a new consumer
    # this test has not been told about yet -- surfaced explicitly rather than silently ignored,
    # so a future milestone's own governance work updates this list deliberately.
    assert unexpected == [], unexpected


def test_no_import_cycle_target_composer_request_does_not_import_this_module() -> None:
    composer_request_source = (_REPO_ROOT / "core" / "target_composer_request.py").read_text(encoding="utf-8")
    assert "target_lexical_paragraph_index" not in composer_request_source


# --------------------------------------------------------------------------------------------
# 26. No clients/** changes from this milestone
# --------------------------------------------------------------------------------------------


def test_no_client_pack_files_touched() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD", "--", "clients/"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    assert changed == [], changed


def test_no_runtime_flag_files_touched() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    forbidden_paths = {
        "config.py",
        "app.py",
        "core/target_composer_executor.py",
        "core/target_response_verifier.py",
        "core/target_composer_request.py",
        "core/target_verified_response_pipeline.py",
        "core/target_policy_bound_verified_response_pipeline.py",
        "contracts/turn_frame.py",
    }
    assert not (changed & forbidden_paths), changed & forbidden_paths
