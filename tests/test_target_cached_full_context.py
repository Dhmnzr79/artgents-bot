from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
from pathlib import Path

import pytest

import core.target_policy_bound_verified_response_pipeline as s40_module
import core.target_turn_frame_bound_response as s41_module
import core.target_verified_response_pipeline as s39_module
from contracts.target_cached_full_context import TargetCachedFullContext
from core.target_cached_full_context import (
    TargetCachedFullContextError,
    build_target_cached_full_context,
)


def _cached_module():
    return importlib.import_module("core.target_cached_full_context")


def _write_md(root: Path, relative: str, body: str) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _minimal_frontmatter(doc_id: str, title: str) -> str:
    return (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {title}\n"
        "topics:\n"
        "  - implantation\n"
        "---\n\n"
        f"# {title}\n"
    )


def test_build_includes_every_md_once_with_stable_order_and_boundaries(tmp_path: Path) -> None:
    _write_md(
        tmp_path,
        "z_last/service_z.md",
        _minimal_frontmatter("service_z", "Z") + "Z body.\n",
    )
    _write_md(
        tmp_path,
        "a_first/service_a.md",
        _minimal_frontmatter("service_a", "A") + "A body with ё.\n",
    )
    _write_md(
        tmp_path,
        "doctors__doctor__sample.md",
        _minimal_frontmatter("doctor_sample", "Doctor") + "Doctor profile text.\n",
    )

    first = build_target_cached_full_context(tmp_path)
    second = build_target_cached_full_context(tmp_path)

    assert first == second
    assert first.document_count == 3
    assert first.document_paths == (
        "a_first/service_a.md",
        "doctors__doctor__sample.md",
        "z_last/service_z.md",
    )
    assert first.sha256 == hashlib.sha256(first.corpus_text.encode("utf-8")).hexdigest()
    for path in first.document_paths:
        assert f"---BEGIN DOC:{path}---" in first.corpus_text
        assert f"---END DOC:{path}---" in first.corpus_text
    assert first.corpus_text.count("---BEGIN DOC:") == 3
    assert first.corpus_text.count("---END DOC:") == 3
    assert "Doctor profile text." in first.corpus_text
    assert "ё" in first.corpus_text


def test_build_rejects_non_path_md_root() -> None:
    cached = _cached_module()
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(object())  # type: ignore[arg-type]
    assert caught.value.code == "full_context_md_root_invalid"


def test_build_rejects_missing_md_root(tmp_path: Path) -> None:
    cached = _cached_module()
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(tmp_path / "missing")
    assert caught.value.code == "full_context_md_root_invalid"


def test_build_rejects_file_md_root(tmp_path: Path) -> None:
    cached = _cached_module()
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(file_path)
    assert caught.value.code == "full_context_md_root_invalid"


def test_build_rejects_empty_corpus(tmp_path: Path) -> None:
    cached = _cached_module()
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(tmp_path)
    assert caught.value.code == "full_context_corpus_empty"


def test_build_rejects_empty_document(tmp_path: Path) -> None:
    cached = _cached_module()
    _write_md(tmp_path, "empty.md", "   \n")
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(tmp_path)
    assert caught.value.code == "full_context_document_empty"


def test_unreadable_document_fail_closed(tmp_path: Path) -> None:
    cached = _cached_module()
    _write_md(
        tmp_path,
        "broken/read.md",
        _minimal_frontmatter("broken", "Broken") + "Readable prefix.\n",
    )
    broken = tmp_path / "broken/read.md"
    broken.write_bytes(b"\xff\xfe")
    with pytest.raises(cached.TargetCachedFullContextError) as caught:
        cached.build_target_cached_full_context(tmp_path)
    assert caught.value.code == "full_context_document_unreadable"


DEMO_MD_ROOT = Path("clients/demo/md")


def test_demo_corpus_document_count_and_doctors_inclusion() -> None:
    context = build_target_cached_full_context(DEMO_MD_ROOT)
    assert context.document_count == 55
    assert len(context.document_paths) == 55
    doctor_paths = [path for path in context.document_paths if path.startswith("doctors__")]
    assert len(doctor_paths) == 7
    assert "doctors__doctor__kuznetsov.md" in context.document_paths
    for sample in (
        "clinic__info__contacts.md",
        "comparison__implant_vs_bridge.md",
        "implantation__service__all_on_4.md",
        "doctors__doctor__overview.md",
    ):
        assert sample in context.document_paths
        assert f"---BEGIN DOC:{sample}---" in context.corpus_text
    assert "doctors__" in context.corpus_text
    assert context.sha256 == hashlib.sha256(context.corpus_text.encode("utf-8")).hexdigest()


def test_pipeline_accepts_prebuilt_context_without_calling_builder() -> None:
    prebuilt = build_target_cached_full_context(DEMO_MD_ROOT)

    s39_source = Path("core/target_verified_response_pipeline.py").read_text(encoding="utf-8")
    s40_source = Path("core/target_policy_bound_verified_response_pipeline.py").read_text(
        encoding="utf-8"
    )
    s41_source = Path("core/target_turn_frame_bound_response.py").read_text(encoding="utf-8")
    assert "build_target_cached_full_context" not in s39_source
    assert "build_target_cached_full_context" not in s40_source
    assert "build_target_cached_full_context" not in s41_source
    assert "rglob" not in s39_source
    assert "rglob" not in s40_source
    assert "rglob" not in s41_source

    s39_params = list(inspect.signature(s39_module.run_target_offline_verified_response_pipeline).parameters)
    s40_params = list(
        inspect.signature(s40_module.run_target_offline_policy_bound_verified_response_pipeline).parameters
    )
    s41_params = list(inspect.signature(s41_module.run_target_offline_turn_frame_bound_response).parameters)
    assert "cached_full_context" in s39_params
    assert "cached_full_context" in s40_params
    assert "cached_full_context" in s41_params
    assert prebuilt.document_count == 55


def test_import_firewall_excludes_legacy_runtime_and_llm() -> None:
    source = Path("core/target_cached_full_context.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    forbidden = (
        "knowledge_base",
        "llm",
        "orchestration",
        "openai",
        "router",
        "session",
        "retriev",
        "search",
    )
    assert all(token not in import_lines for token in forbidden)
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_target_cached_full_context"
    )
    assert not any(isinstance(node, ast.Try) for node in ast.walk(function))
    assert "pytest.skip" not in source
    assert "xfail" not in source
