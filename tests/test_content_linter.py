from __future__ import annotations

import os
import tempfile

import pytest

from core.content_linter import (
    expected_doc_type,
    lint_client_pack,
    lint_md_file,
)


def test_expected_doc_type_rules() -> None:
    assert expected_doc_type("clinic__info__contacts.md") == "contacts"
    assert expected_doc_type("comparison__implant_vs_bridge.md") == "comparison"
    assert expected_doc_type("doctors__doctor__overview.md") == "doctor"
    assert expected_doc_type("implantation__faq__cost.md") == "faq"
    assert expected_doc_type("implantation__service__classic.md") == "service"


def test_lint_all_buildable_clients_pass() -> None:
    from core.client_runtime import list_buildable_client_ids

    for cid in list_buildable_client_ids():
        res = lint_client_pack(cid)
        assert res.ok, f"{cid}: {[i.message for i in res.errors]}"


def test_lint_missing_doc_id(tmp_path) -> None:
    md = tmp_path / "implantation__faq__cost.md"
    md.write_text(
        "---\ndoc_type: faq\ntopic: implantation\nsubtopic: cost\n---\n",
        encoding="utf-8",
    )
    issues = lint_md_file(str(md), client_id="demo", known_basenames={md.name})
    assert any(i.code == "missing_field" and i.field == "doc_id" for i in issues)


def test_lint_missing_doc_type(tmp_path) -> None:
    md = tmp_path / "implantation__faq__cost.md"
    md.write_text(
        "---\ndoc_id: implantation__faq__cost\ntopic: implantation\nsubtopic: cost\n---\n",
        encoding="utf-8",
    )
    issues = lint_md_file(str(md), client_id="demo", known_basenames={md.name})
    codes = {i.code for i in issues}
    assert "missing_field" in codes


def test_lint_broken_suggest_ref(tmp_path) -> None:
    md = tmp_path / "implantation__faq__cost.md"
    md.write_text(
        "---\n"
        "doc_id: implantation__faq__cost\n"
        "doc_type: faq\n"
        "topic: implantation\n"
        "subtopic: cost\n"
        'suggest_refs:\n  - { label: "x", ref: "missing.md#korotko" }\n'
        "---\n### Коротко {#korotko}\n",
        encoding="utf-8",
    )
    issues = lint_md_file(str(md), client_id="demo", known_basenames={md.name})
    assert any(i.code == "broken_ref" for i in issues)
