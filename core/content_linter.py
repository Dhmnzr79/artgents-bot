"""Frontmatter and ref checks for client md packs (Metadata-First v1)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

from core.client_runtime import client_md_dir, list_buildable_client_ids

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_H2_RX = re.compile(r"^##\s+.+?(?:\s*\{#([a-z0-9\-_]+)\})?\s*$", re.I | re.M)
_H3_RX = re.compile(r"^###\s+.+?(?:\s*\{#([a-z0-9\-_]+)\})?\s*$", re.I | re.M)

VALID_DOC_TYPES = frozenset(
    {"service", "faq", "info", "pricing", "doctor", "contacts", "comparison"}
)
REQUIRED_FIELDS = ("doc_id", "doc_type", "topic", "subtopic")
MIN_ALIAS_NORM_LEN = 3
REF_SPECIAL_ANCHORS = frozenset({"", "overview", "korotko"})

LintLevel = Literal["error", "warning"]


@dataclass
class LintIssue:
    level: LintLevel
    code: str
    message: str
    path: str
    field: str | None = None


@dataclass
class LintResult:
    client_id: str
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _norm_alias_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\{#.*?\}", " ", s)
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip()


def expected_doc_type(basename: str) -> str | None:
    """Infer doc_type from filename per METADATA_FIRST_V1 Doc Type Rules."""
    name = basename if basename.endswith(".md") else f"{basename}.md"
    stem = name.removesuffix(".md")
    if name == "clinic__info__contacts.md":
        return "contacts"
    if stem.startswith("comparison__"):
        return "comparison"
    if stem.startswith("doctors__doctor__"):
        return "doctor"
    parts = stem.split("__")
    if len(parts) >= 2:
        seg = parts[1]
        mapping = {
            "service": "service",
            "faq": "faq",
            "info": "info",
            "pricing": "pricing",
        }
        if seg in mapping:
            return mapping[seg]
    return None


def _parse_frontmatter(path: str) -> tuple[dict[str, Any], str]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(fm, dict):
        return {}, text
    return fm, text


def _anchors_in_md(body: str) -> set[str]:
    ids: set[str] = set(REF_SPECIAL_ANCHORS)
    for rx in (_H2_RX, _H3_RX):
        for m in rx.finditer(body):
            aid = (m.group(1) or "").strip().lower()
            if aid:
                ids.add(aid)
    return ids


def _split_body(body: str) -> str:
    m = _FM_RE.match(body)
    return body[m.end() :] if m else body


def _parse_ref(raw: str) -> tuple[str | None, str | None]:
    s = (raw or "").strip()
    if not s:
        return None, None
    if isinstance(raw, dict):
        s = str(raw.get("ref") or raw.get("href") or "").strip()
    if not s or "#" not in s:
        return None, None
    fname, anchor = s.split("#", 1)
    base = os.path.basename(fname.strip())
    if base and not base.endswith(".md"):
        base = f"{base}.md"
    return base or None, (anchor or "").strip().lower()


def _collect_ref_targets(fm: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in fm.get("suggest_refs") or []:
        if isinstance(item, dict):
            ref = str(item.get("ref") or "").strip()
            field = "suggest_refs"
        elif isinstance(item, str):
            ref = item.strip()
            field = "suggest_refs"
        else:
            continue
        if ref:
            out.append((field, ref))
    for key in ("followups",):
        for item in fm.get(key) or []:
            if isinstance(item, dict) and item.get("ref"):
                out.append((key, str(item["ref"]).strip()))
            elif isinstance(item, str) and item.strip():
                out.append((key, item.strip()))
    return out


def _alias_strings(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("aliases") or []
    if not isinstance(raw, list):
        return []
    return [str(a).strip() for a in raw if isinstance(a, str) and str(a).strip()]


def lint_md_file(
    path: str,
    *,
    client_id: str,
    known_basenames: set[str],
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    basename = os.path.basename(path)
    stem = basename.removesuffix(".md")

    fm, full_text = _parse_frontmatter(path)
    if not fm:
        issues.append(
            LintIssue(
                "error",
                "missing_frontmatter",
                "YAML frontmatter required",
                path,
            )
        )
        return issues

    raw_doc_id = fm.get("doc_id")
    if raw_doc_id is None or not str(raw_doc_id).strip():
        doc_id = ""
    else:
        doc_id = str(raw_doc_id).strip()

    doc_type = str(fm.get("doc_type") or "").strip()
    topic = str(fm.get("topic") or "").strip()
    subtopic = str(fm.get("subtopic") or "").strip()

    for fld, val in [
        ("doc_id", doc_id),
        ("doc_type", doc_type),
        ("topic", topic),
        ("subtopic", subtopic),
    ]:
        if not val:
            issues.append(
                LintIssue(
                    "error",
                    "missing_field",
                    f"Missing required field: {fld}",
                    path,
                    fld,
                )
            )

    if doc_id and doc_id != stem:
        issues.append(
            LintIssue(
                "error",
                "doc_id_mismatch",
                f"doc_id '{doc_id}' must match filename stem '{stem}'",
                path,
                "doc_id",
            )
        )

    if doc_type and doc_type not in VALID_DOC_TYPES:
        issues.append(
            LintIssue(
                "error",
                "unknown_doc_type",
                f"Unknown doc_type: {doc_type!r}",
                path,
                "doc_type",
            )
        )

    exp = expected_doc_type(basename)
    if exp and doc_type and doc_type != exp:
        issues.append(
            LintIssue(
                "error",
                "doc_type_mismatch",
                f"doc_type {doc_type!r} does not match path rule (expected {exp!r})",
                path,
                "doc_type",
            )
        )
    if exp is None and doc_type:
        issues.append(
            LintIssue(
                "warning",
                "doc_type_unmapped_path",
                f"Could not infer doc_type from filename; declared {doc_type!r}",
                path,
                "doc_type",
            )
        )

    body = _split_body(full_text)
    anchors = _anchors_in_md(body)

    for h3 in fm.get("suggest_h3") or []:
        aid = str(h3 or "").strip().lower()
        if not aid:
            continue
        if aid not in anchors:
            issues.append(
                LintIssue(
                    "error",
                    "broken_ref",
                    f"suggest_h3 anchor #{aid} not found in document",
                    path,
                    "suggest_h3",
                )
            )

    for field_name, ref in _collect_ref_targets(fm):
        fb, anchor = _parse_ref(ref)
        if not fb:
            issues.append(
                LintIssue(
                    "error",
                    "broken_ref",
                    f"Invalid ref format: {ref!r}",
                    path,
                    field_name,
                )
            )
            continue
        if fb not in known_basenames:
            issues.append(
                LintIssue(
                    "error",
                    "broken_ref",
                    f"Target file not found: {fb}",
                    path,
                    field_name,
                )
            )
            continue
        target_path = os.path.join(os.path.dirname(path), fb)
        if fb == basename:
            target_anchors = anchors
        else:
            _, target_body = _parse_frontmatter(target_path)
            target_anchors = _anchors_in_md(_split_body(target_body))
        if anchor and anchor not in target_anchors:
            issues.append(
                LintIssue(
                    "error",
                    "broken_ref",
                    f"Anchor #{anchor} not found in {fb}",
                    path,
                    field_name,
                )
            )

    seen_alias: set[str] = set()
    for alias in _alias_strings(fm):
        nk = _norm_alias_key(alias)
        if len(nk) < MIN_ALIAS_NORM_LEN:
            issues.append(
                LintIssue(
                    "error",
                    "alias_too_short",
                    f"Alias too short after normalize: {alias!r}",
                    path,
                    "aliases",
                )
            )
        if nk in seen_alias:
            issues.append(
                LintIssue(
                    "error",
                    "duplicate_alias",
                    f"Duplicate alias in document: {alias!r}",
                    path,
                    "aliases",
                )
            )
        seen_alias.add(nk)

    if doc_type == "service":
        from core.routing_loader import load_thresholds

        slot_cfg = load_thresholds().answer_slots
        slot_limits = {
            "clinic_note": slot_cfg.clinic_note_max_chars,
            "consult_value": slot_cfg.consult_value_max_chars,
        }
        for field_name, max_len in slot_limits.items():
            raw = fm.get(field_name)
            if raw is None:
                continue
            text = str(raw).strip()
            if text and len(text) > max_len:
                issues.append(
                    LintIssue(
                        "warning",
                        "answer_slot_too_long",
                        f"{field_name} length {len(text)} exceeds {max_len}",
                        path,
                        field_name,
                    )
                )
        promo = fm.get("promo_note")
        promo_text = ""
        if isinstance(promo, dict):
            promo_text = str(promo.get("text") or "").strip()
        elif isinstance(promo, str):
            promo_text = promo.strip()
        if promo_text and len(promo_text) > slot_cfg.promo_note_max_chars:
            issues.append(
                LintIssue(
                    "warning",
                    "answer_slot_too_long",
                    f"promo_note length {len(promo_text)} exceeds {slot_cfg.promo_note_max_chars}",
                    path,
                    "promo_note",
                )
            )
        overrides = fm.get("h3_overrides") or {}
        if isinstance(overrides, dict):
            for h3_key in overrides:
                aid = str(h3_key or "").strip().lower()
                if aid and aid not in anchors:
                    issues.append(
                        LintIssue(
                            "error",
                            "broken_ref",
                            f"h3_overrides anchor #{aid} not found in document",
                            path,
                            "h3_overrides",
                        )
                    )

    return issues


def lint_client_pack(client_id: str) -> LintResult:
    md_root = client_md_dir(client_id)
    result = LintResult(client_id=client_id)
    if not os.path.isdir(md_root):
        result.issues.append(
            LintIssue(
                "error",
                "missing_md_dir",
                f"No md directory: {md_root}",
                md_root,
            )
        )
        return result

    paths = []
    for root, _, files in os.walk(md_root):
        for name in sorted(files):
            if name.endswith(".md"):
                paths.append(os.path.join(root, name))

    known = {os.path.basename(p) for p in paths}
    for path in paths:
        result.issues.extend(
            lint_md_file(path, client_id=client_id, known_basenames=known)
        )
    return result


def lint_all_clients(client_ids: list[str] | None = None) -> list[LintResult]:
    ids = client_ids or list_buildable_client_ids()
    return [lint_client_pack(cid) for cid in ids]


def alias_collision_report(client_id: str) -> dict[str, list[str]]:
    """alias_norm -> list of 'basename' where it appears (cross-doc duplicates)."""
    md_root = client_md_dir(client_id)
    index: dict[str, list[str]] = {}
    if not os.path.isdir(md_root):
        return index
    for root, _, files in os.walk(md_root):
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            fm, _ = _parse_frontmatter(path)
            for alias in _alias_strings(fm):
                nk = _norm_alias_key(alias)
                if len(nk) < MIN_ALIAS_NORM_LEN:
                    continue
                index.setdefault(nk, [])
                if name not in index[nk]:
                    index[nk].append(name)
    return {k: v for k, v in sorted(index.items()) if len(v) > 1}


def format_lint_report(results: list[LintResult]) -> str:
    lines: list[str] = []
    for res in results:
        lines.append(f"## {res.client_id}")
        if res.ok and not res.warnings:
            lines.append("- OK (no issues)")
            continue
        for issue in res.issues:
            rel = issue.path
            try:
                rel = os.path.relpath(issue.path, start=os.getcwd())
            except ValueError:
                pass
            fld = f" [{issue.field}]" if issue.field else ""
            lines.append(f"- **{issue.level}** `{issue.code}`{fld}: {issue.message} (`{rel}`)")
    return "\n".join(lines) + "\n"
