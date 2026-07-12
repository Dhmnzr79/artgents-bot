"""Client-configurable topic taxonomy from MD frontmatter (A4)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import frontmatter
import yaml

from core.client_runtime import client_md_dir


class TopicTaxonomyFrontmatterError(Exception):
    """Malformed or invalid topic field in client MD frontmatter."""

    def __init__(
        self,
        path: str,
        *,
        cause: Exception | None = None,
        reason: str = "malformed frontmatter",
    ) -> None:
        self.path = path
        self.cause = cause
        self.reason = reason
        message = f"{reason} in {path}"
        if cause is not None:
            message = f"{message}: {cause}"
        super().__init__(message)


def _parse_topic_field(path: str, raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise TopicTaxonomyFrontmatterError(path, reason="invalid topic field type")
    normalized = raw.strip().lower()
    return normalized or None


def _iter_md_files(md_root: str) -> list[str]:
    root = Path(md_root)
    if not root.is_dir():
        return []
    return sorted(str(path) for path in root.rglob("*.md") if path.is_file())


def _load_topics_from_md_dir(md_root: str) -> frozenset[str]:
    topics: set[str] = set()
    for path in _iter_md_files(md_root):
        try:
            with open(path, encoding="utf-8-sig") as handle:
                post = frontmatter.load(handle)
        except yaml.YAMLError as exc:
            raise TopicTaxonomyFrontmatterError(path, cause=exc) from exc
        except OSError as exc:
            raise TopicTaxonomyFrontmatterError(path, cause=exc) from exc
        except Exception as exc:
            raise TopicTaxonomyFrontmatterError(path, cause=exc) from exc

        normalized = _parse_topic_field(path, post.metadata.get("topic"))
        if normalized is not None:
            topics.add(normalized)
    return frozenset(topics)


@lru_cache(maxsize=None)
def _cached_topics_for_md_dir(md_root: str) -> frozenset[str]:
    return _load_topics_from_md_dir(os.path.abspath(md_root))


def load_client_topic_taxonomy(client_id: str | None) -> frozenset[str]:
    """Return normalized topic names declared in client MD frontmatter."""
    md_dir = os.path.abspath(client_md_dir(client_id))
    return _cached_topics_for_md_dir(md_dir)


def clear_topic_taxonomy_cache() -> None:
    """Clear cached taxonomy (for tests)."""
    _cached_topics_for_md_dir.cache_clear()
