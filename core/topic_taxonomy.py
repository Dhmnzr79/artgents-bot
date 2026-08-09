"""Client-configurable topic taxonomy from MD frontmatter (A4)."""

from __future__ import annotations

import os
import threading
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


_TOPIC_CACHE: dict[str, frozenset[str]] = {}
_TOPIC_CACHE_LOCK = threading.Lock()


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


def _topic_cache_key(md_dir: str, pack_hash: str | None = None) -> str:
    return f"{os.path.abspath(md_dir)}:{pack_hash or ''}"


def evict_topic_taxonomy_cache_for_client(
    client_id: str | None,
    *,
    keep_pack_hash: str | None = None,
) -> None:
    md_dir = os.path.abspath(client_md_dir(client_id))
    keep_key = _topic_cache_key(md_dir, keep_pack_hash) if keep_pack_hash else None
    prefix = f"{md_dir}:"
    with _TOPIC_CACHE_LOCK:
        for key in list(_TOPIC_CACHE.keys()):
            if not key.startswith(prefix):
                continue
            if keep_key is not None and key == keep_key:
                continue
            del _TOPIC_CACHE[key]


def load_client_topic_taxonomy(
    client_id: str | None,
    *,
    pack_hash: str | None = None,
) -> frozenset[str]:
    """Return normalized topic names declared in client MD frontmatter."""
    md_dir = os.path.abspath(client_md_dir(client_id))
    key = _topic_cache_key(md_dir, pack_hash)
    with _TOPIC_CACHE_LOCK:
        cached = _TOPIC_CACHE.get(key)
        if cached is not None:
            return cached
        topics = _load_topics_from_md_dir(md_dir)
        _TOPIC_CACHE[key] = topics
        return topics


def clear_topic_taxonomy_cache() -> None:
    """Clear cached taxonomy (for tests)."""
    with _TOPIC_CACHE_LOCK:
        _TOPIC_CACHE.clear()
