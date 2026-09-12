"""Dual-view user text privacy: local raw vs provider/observability-safe (no Flask/DB/provider)."""

from __future__ import annotations

import re

from name_gate import accept_lead_name

PHONE_PLACEHOLDER = "[телефон скрыт]"
EMAIL_PLACEHOLDER = "[email скрыт]"

EMAIL_RX = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])"
)
PHONE_TEXT_RX = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{8,}\d)(?!\d)")

_GREETING_RX = re.compile(
    r"^(?:здравствуйте|добрый день|добрый вечер|привет)[,.\s]+",
    re.I,
)
_MENYA_ZOVUT_RX = re.compile(
    r"^(?:меня зовут|меня звать|мо[её] имя)\s+(.+?)[,.]\s*(.+)$",
    re.I | re.S,
)
_YA_INTRO_RX = re.compile(r"^я\s+(.+?),\s*(.+)$", re.I | re.S)
_INTRO_COMMA_RX = re.compile(r"^(.{2,60}?),\s*(.+)$", re.U)
_MENYA_ZOVUT_ONLY_RX = re.compile(
    r"^(?:меня зовут|меня звать|мо[её] имя)\s+(.+)$",
    re.I,
)

_PLACEHOLDER_RX = re.compile(
    rf"(?:{re.escape(PHONE_PLACEHOLDER)}|{re.escape(EMAIL_PLACEHOLDER)})"
)


def mask_phones_in_text(value: str) -> str:
    return PHONE_TEXT_RX.sub(PHONE_PLACEHOLDER, str(value or ""))


def mask_emails_in_text(value: str) -> str:
    return EMAIL_RX.sub(EMAIL_PLACEHOLDER, str(value or ""))


def _strip_explicit_self_introduction(text: str, *, profile_name: str = "") -> str:
    s = (text or "").strip()
    if not s:
        return s
    s = _GREETING_RX.sub("", s).strip()
    prof = (profile_name or "").strip()

    only_intro = _MENYA_ZOVUT_ONLY_RX.match(s)
    if only_intro:
        tail = only_intro.group(1).strip()
        maybe_only = accept_lead_name(tail)
        if maybe_only and maybe_only.casefold() == tail.casefold():
            return ""

    match = _MENYA_ZOVUT_RX.match(s)
    if match:
        maybe = accept_lead_name(match.group(1).strip())
        rest = match.group(2).strip()
        if maybe and rest and (not prof or maybe.casefold() == prof.casefold()):
            return rest

    match = _YA_INTRO_RX.match(s)
    if match:
        maybe = accept_lead_name(match.group(1).strip())
        rest = match.group(2).strip()
        if maybe and rest and (not prof or maybe.casefold() == prof.casefold()):
            return rest

    intro = _INTRO_COMMA_RX.match(s)
    if intro:
        maybe_name = accept_lead_name(intro.group(1).strip())
        rest = intro.group(2).strip()
        if maybe_name and rest and (not prof or maybe_name.casefold() == prof.casefold()):
            return rest

    return s


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip(" ,."))


def provider_safe_user_text(raw: str, *, profile_name: str = "") -> str:
    """User message safe for Qwen / provider-visible history (not clinic corpus)."""
    text = mask_emails_in_text(raw or "")
    text = mask_phones_in_text(text)
    text = _strip_explicit_self_introduction(text, profile_name=profile_name)
    return _normalize_spaces(text)


def observability_safe_user_text(raw: str, *, max_len: int | None = None) -> str:
    """User message safe for JSONL / PostgreSQL / admin previews."""
    out = provider_safe_user_text(raw or "", profile_name="")
    if max_len is not None and max_len > 0 and len(out) > max_len:
        return out[:max_len]
    return out


def observability_safe_bot_text(raw: str, *, max_len: int | None = None) -> str:
    """Bot/clinic answer text for observability (clinic contacts preserved)."""
    out = str(raw or "")
    if max_len is not None and max_len > 0 and len(out) > max_len:
        return out[:max_len]
    return out


def _phone_digit_runs(raw: str) -> list[str]:
    runs: list[str] = []
    for match in PHONE_TEXT_RX.finditer(raw or ""):
        digits = "".join(ch for ch in match.group() if ch.isdigit())
        if len(digits) >= 10:
            runs.append(digits)
    return runs


def _contains_leaked_phone_digits(cleaned: str, raw: str) -> bool:
    compact = re.sub(r"\D", "", cleaned or "")
    if not compact:
        return False
    for run in _phone_digit_runs(raw):
        for width in range(4, len(run) + 1):
            for idx in range(len(run) - width + 1):
                chunk = run[idx : idx + width]
                if chunk in compact:
                    return True
    return False


def provider_message_has_substance(
    text: str,
    *,
    raw_source: str | None = None,
    reject_lone_personal_name: bool = False,
) -> bool:
    """True when text still carries a non-contact question for the provider."""
    s = _normalize_spaces(text)
    if not s:
        return False
    if len(s) < 3:
        return False
    if re.fullmatch(r"[\d+\s().\-]+", s):
        return False
    stripped = _PLACEHOLDER_RX.sub(" ", s)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if not stripped:
        return False
    if not re.search(r"[\u0400-\u04FFa-zA-Z]", stripped):
        return False
    if "@" in stripped:
        return False
    if re.search(r"\*{2,}", stripped):
        return False
    if raw_source and _contains_leaked_phone_digits(stripped, raw_source):
        return False
    if reject_lone_personal_name:
        lone_name = accept_lead_name(stripped)
        if lone_name and stripped.casefold() == lone_name.casefold():
            return False
    return True


def sanitize_dialog_history_line(role: str, content: str, *, profile_name: str = "") -> str:
    role_l = (role or "").strip().lower()
    body = (content or "").strip()
    if role_l == "user":
        return provider_safe_user_text(body, profile_name=profile_name)
    return body


def format_hist_messages_for_provider(
    messages: list[dict],
    *,
    profile_name: str = "",
) -> str:
    """Build provider dialog tail from structured hist (sanitizes each user content)."""
    lines: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        role = str(m.get("role") or "").strip().lower()
        if role == "user":
            content = sanitize_dialog_history_line("user", content, profile_name=profile_name)
            if not content:
                continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _flush_pending_user_continuation(
    out_lines: list[str],
    pending_user_extra: list[str],
) -> None:
    if not pending_user_extra or not out_lines or not out_lines[-1].startswith("user:"):
        pending_user_extra.clear()
        return
    role_raw, _, content_raw = out_lines[-1].partition(":")
    merged = content_raw.strip() + "\n" + "\n".join(pending_user_extra)
    pending_user_extra.clear()
    safe_content = sanitize_dialog_history_line(role_raw, merged)
    out_lines[-1] = f"{role_raw.strip()}: {safe_content}"


def sanitize_dialog_history_for_provider(dialog_history: str) -> str:
    """Defense-in-depth on preformatted history (prefer format_hist_messages_for_provider)."""
    if not (dialog_history or "").strip():
        return ""
    out_lines: list[str] = []
    pending_user_extra: list[str] = []
    for line in dialog_history.splitlines():
        if ":" not in line:
            if out_lines and out_lines[-1].startswith("user:"):
                pending_user_extra.append(line)
            else:
                out_lines.append(line)
            continue
        _flush_pending_user_continuation(out_lines, pending_user_extra)
        role_raw, _, content_raw = line.partition(":")
        safe_content = sanitize_dialog_history_line(role_raw, content_raw.strip())
        out_lines.append(f"{role_raw.strip()}: {safe_content}")
    _flush_pending_user_continuation(out_lines, pending_user_extra)
    return "\n".join(out_lines)
