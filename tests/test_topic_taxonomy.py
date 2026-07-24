from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from core.client_runtime import client_md_dir
from core.topic_taxonomy import (
    TopicTaxonomyFrontmatterError,
    clear_topic_taxonomy_cache,
    load_client_topic_taxonomy,
)

_LOADER_MODULE = Path("core/topic_taxonomy.py")

# Canonical runtime import surface (C2e governance-delta):
# - turn_planner_llm: planner prompt + TurnFrame topic sanitization (A7)
# - target_runtime_client_context: FullContext bootstrap allowed_topics (S61)
_RUNTIME_TOPIC_TAXONOMY_IMPORT_ALLOWLIST: dict[str, frozenset[str]] = {
    "core/turn_planner_llm.py": frozenset({"load_client_topic_taxonomy"}),
    "core/target_runtime_client_context.py": frozenset({"load_client_topic_taxonomy"}),
}


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    clear_topic_taxonomy_cache()
    yield
    clear_topic_taxonomy_cache()


def test_loader_returns_demo_frontmatter_topics():
    topics = load_client_topic_taxonomy("demo")

    assert "implantation" in topics
    assert "clinic" in topics
    assert "doctors" in topics


def test_loader_values_are_normalized_nonempty_and_deterministic():
    first = load_client_topic_taxonomy("demo")
    second = load_client_topic_taxonomy("demo")

    assert first == second
    assert first
    assert all(topic == topic.strip().lower() for topic in first)
    assert all(topic for topic in first)


def test_loader_does_not_infer_from_doc_id_subtopic_or_filename(tmp_path, monkeypatch):
    md_dir = tmp_path / "md"
    md_dir.mkdir()
    (md_dir / "implantation__faq__osseointegration.md").write_text(
        "---\n"
        "doc_id: implantation__faq__osseointegration\n"
        "topic: implantation\n"
        "subtopic: osseointegration\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    (md_dir / "no_topic_field.md").write_text("# no frontmatter topic\n", encoding="utf-8")

    monkeypatch.setattr("core.topic_taxonomy.client_md_dir", lambda _cid: str(md_dir))

    topics = load_client_topic_taxonomy("demo")

    assert topics == frozenset({"implantation"})
    assert "osseointegration" not in topics
    assert "implantation__faq__osseointegration" not in topics


def test_cache_is_bound_to_resolved_client_pack(tmp_path, monkeypatch):
    client_a = tmp_path / "client_a" / "md"
    client_b = tmp_path / "client_b" / "md"
    client_a.mkdir(parents=True)
    client_b.mkdir(parents=True)
    (client_a / "a.md").write_text("---\ntopic: alpha\n---\n", encoding="utf-8")
    (client_b / "b.md").write_text("---\ntopic: beta\n---\n", encoding="utf-8")

    def _md_dir(client_id: str | None) -> str:
        if client_id == "client_a":
            return str(client_a)
        if client_id == "client_b":
            return str(client_b)
        raise AssertionError(f"unexpected client_id: {client_id}")

    monkeypatch.setattr("core.topic_taxonomy.client_md_dir", _md_dir)

    topics_a = load_client_topic_taxonomy("client_a")
    topics_b = load_client_topic_taxonomy("client_b")

    assert topics_a == frozenset({"alpha"})
    assert topics_b == frozenset({"beta"})


def test_production_loader_has_no_hardcoded_topic_names():
    source = Path("core/topic_taxonomy.py").read_text(encoding="utf-8").lower()
    banned = (
        "implantation",
        "prosthetics",
        "clinic",
        "doctors",
        "orthodontics",
        "periodontology",
        "extraction",
        "whitening",
        "treatment",
    )
    hits = [name for name in banned if re.search(rf'["\']{re.escape(name)}["\']', source)]
    assert hits == []


def test_malformed_frontmatter_raises_distinct_error(tmp_path, monkeypatch):
    md_dir = tmp_path / "md"
    md_dir.mkdir()
    bad_path = md_dir / "broken.md"
    bad_path.write_text("---\ntopic: [unclosed\n---\nbody\n", encoding="utf-8")

    monkeypatch.setattr("core.topic_taxonomy.client_md_dir", lambda _cid: str(md_dir))

    with pytest.raises(TopicTaxonomyFrontmatterError) as exc_info:
        load_client_topic_taxonomy("demo")

    assert str(bad_path) in str(exc_info.value)
    assert exc_info.value.reason == "malformed frontmatter"


@pytest.mark.parametrize(
    "topic_yaml",
    [
        "topic: [implantation, clinic]\n",
        "topic: {name: implantation}\n",
        "topic: 42\n",
        "topic: true\n",
    ],
    ids=["list", "dict", "int", "bool"],
)
def test_non_string_topic_raises_without_string_pseudo_topic(
    tmp_path, monkeypatch, topic_yaml: str
):
    md_dir = tmp_path / "md"
    md_dir.mkdir()
    bad_path = md_dir / "bad_topic_type.md"
    bad_path.write_text(f"---\n{topic_yaml}---\nbody\n", encoding="utf-8")

    monkeypatch.setattr("core.topic_taxonomy.client_md_dir", lambda _cid: str(md_dir))

    with pytest.raises(TopicTaxonomyFrontmatterError) as exc_info:
        load_client_topic_taxonomy("demo")

    err = exc_info.value
    assert err.reason == "invalid topic field type"
    assert str(bad_path) in str(err)
    assert "implantation" not in str(err).lower()
    assert "body" not in str(err).lower()


def _iter_runtime_py_files() -> list[Path]:
    paths: list[Path] = []
    for root_name in ("core", "orchestration"):
        root = Path(root_name)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == _LOADER_MODULE.resolve():
                continue
            paths.append(path)
    return paths


def _imports_topic_taxonomy(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"core.topic_taxonomy", "topic_taxonomy"}:
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "core.topic_taxonomy":
                for alias in node.names:
                    hits.append(f"from {module} import {alias.name}")
            elif module == "core" and any(alias.name == "topic_taxonomy" for alias in node.names):
                hits.append("from core import topic_taxonomy")
    return sorted(hits)


def _runtime_relative_path(path: Path) -> str:
    return path.as_posix()


def _imported_symbols(path: Path) -> frozenset[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "core.topic_taxonomy":
            for alias in node.names:
                symbols.add(alias.name)
    return frozenset(symbols)


def test_runtime_topic_taxonomy_import_surface_is_allowlisted():
    """Only canonical FullContext/planner consumers may import the taxonomy loader."""
    scanned = _iter_runtime_py_files()
    assert scanned, "expected runtime python files under core/ and orchestration/"

    actual_imports: dict[str, list[str]] = {}
    actual_symbols: dict[str, frozenset[str]] = {}
    for path in scanned:
        rel = _runtime_relative_path(path)
        imports = _imports_topic_taxonomy(path)
        if imports:
            actual_imports[rel] = imports
            actual_symbols[rel] = _imported_symbols(path)

    expected_imports = {
        rel: sorted(f"from core.topic_taxonomy import {symbol}" for symbol in sorted(symbols))
        for rel, symbols in _RUNTIME_TOPIC_TAXONOMY_IMPORT_ALLOWLIST.items()
    }

    assert actual_imports == expected_imports
    assert set(actual_symbols) == set(_RUNTIME_TOPIC_TAXONOMY_IMPORT_ALLOWLIST)
    for rel, symbols in actual_symbols.items():
        assert symbols == _RUNTIME_TOPIC_TAXONOMY_IMPORT_ALLOWLIST[rel]


def test_demo_md_dir_exists_for_integration_sanity():
    assert Path(client_md_dir("demo")).is_dir()
