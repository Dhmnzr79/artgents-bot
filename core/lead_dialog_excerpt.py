"""Deterministic lead-email dialog excerpt from tenant-bound session history."""

from __future__ import annotations

import re

from logging_setup import redact_text
from session import RECENT_DIALOG_MAX_MESSAGES, recent_dialog_history, session_client_scope

LEAD_DIALOG_EXCERPT_MAX_CHARS = 1200
_ROLE_LABELS = {"user": "Пациент", "assistant": "Бот"}
_EMAIL_RX = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])"
)


def mask_email_in_text(value: str) -> str:
    """Technical PII mask for email addresses in free text (not semantic filtering)."""
    return _EMAIL_RX.sub("[email скрыт]", str(value or ""))


def sanitize_dialog_line(value: str) -> str:
    return mask_email_in_text(redact_text(value or ""))


def _fit_excerpt_lines(lines: list[str], *, max_chars: int) -> str:
    if not lines:
        return ""
    working = list(lines)
    while len(working) > 1 and sum(len(x) + 1 for x in working) > max_chars:
        working.pop(0)
    joined_len = sum(len(x) + 1 for x in working) - 1 if working else 0
    if joined_len <= max_chars:
        return "\n".join(working)
    last = working[-1]
    if ":" in last:
        label, _, text = last.partition(":")
        prefix = f"{label}: "
        budget = max_chars - len(prefix)
        if budget <= 0:
            return last[:max_chars]
        trimmed = text[-budget:] if len(text) > budget else text
        return f"{prefix}{trimmed}"
    return last[-max_chars:]


def build_lead_dialog_excerpt(
    client_id: str,
    sid: str,
    *,
    max_messages: int = RECENT_DIALOG_MAX_MESSAGES,
) -> str:
    """Last substantive turns for lead email; empty string if no history."""
    session_id = (sid or "").strip()
    tenant = (client_id or "").strip()
    if not session_id or not tenant:
        return ""
    with session_client_scope(tenant):
        raw = recent_dialog_history(session_id, max_messages=max(4, min(int(max_messages), 6)))
    if not (raw or "").strip():
        return ""

    lines: list[str] = []
    for line in raw.splitlines():
        if ":" not in line:
            continue
        role_raw, _, content_raw = line.partition(":")
        role = role_raw.strip().lower()
        content = sanitize_dialog_line(content_raw.strip())
        if not content:
            continue
        label = _ROLE_LABELS.get(role, role_raw.strip() or role)
        lines.append(f"{label}: {content}")

    return _fit_excerpt_lines(lines, max_chars=LEAD_DIALOG_EXCERPT_MAX_CHARS)


def format_lead_dialog_excerpt_block(excerpt: str) -> str:
    body = (excerpt or "").strip()
    if not body:
        return "—"
    return body


def sanitize_dialog_excerpt_for_email(excerpt: str) -> str:
    """Defensive contact mask at email boundary (builder already sanitizes lines)."""
    if not (excerpt or "").strip() or excerpt.strip() == "—":
        return excerpt or "—"
    lines = []
    for line in str(excerpt).splitlines():
        if ":" in line:
            label, _, text = line.partition(":")
            lines.append(f"{label}:{sanitize_dialog_line(text)}")
        else:
            lines.append(sanitize_dialog_line(line))
    return "\n".join(lines)
