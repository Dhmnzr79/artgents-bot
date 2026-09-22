"""CP5-SPAM: deterministic garbage one-chance → hard-stop on the common D2 route.

D2-040 / D2-071 narrow slice: empty, short, link-only, obvious noise / mash.
Not FAQ, not medical terminal, not lead, not polite off-topic refuse.
"""

from __future__ import annotations

import re
from typing import Literal

import yaml

from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.response_plan import (
    CodeOwnedTerminalCandidate,
    DeterministicBypassRouteAuthority,
    PreComposerPlan,
    PricePlan,
    ResponseMode,
    RouteModePair,
    SessionKey,
    UiPlanCandidates,
)
from contracts.response_plan_materialization import (
    MaterializationTrace,
    MaterializedResponseOutcome,
)
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.local_problem_gate import decide_local_problem_gate
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from orchestration.route_guards import is_obvious_noise

SpamGateKind = Literal["warn", "closed"]

_LINK_ONLY_RE = re.compile(
    r"^(?:https?://\S+|www\.\S+)$",
    re.IGNORECASE,
)
_KNOWN_MASH = frozenset(
    {
        "asdf",
        "asdfg",
        "asdfgh",
        "qwer",
        "qwert",
        "qwerty",
        "qwertyuiop",
        "zxcv",
        "zxcvb",
        "йцук",
        "йцукен",
        "фыва",
        "фывап",
        "ячсм",
        "aaaa",
        "aaaaa",
        "abc",
        "abcd",
        "abcde",
        "test",
        "testing",
        "xxx",
        "xxxx",
        "zzz",
    }
)
_DEFAULT_WARN = (
    "Напишите, пожалуйста, понятный вопрос по стоматологии — так я смогу помочь."
)
_DEFAULT_CLOSED = (
    "Диалог завершён. Чтобы задать новый вопрос, начните новый чат."
)


def is_d2_garbage_message(text: str) -> bool:
    """True for consecutive-garbage inputs in the narrow D2-040 slice."""
    if not isinstance(text, str):
        return True
    raw = text.strip()
    if not raw:
        return True
    # Contact-only / privacy-stripped inputs stay on the privacy fail path, not spam.
    if _looks_like_contact_only(raw):
        return False
    if len(raw) <= 2 and not any(ch.isalpha() for ch in raw):
        return True
    if is_obvious_noise(raw):
        return True
    if decide_local_problem_gate(raw).decision == "spam":
        return True
    if _LINK_ONLY_RE.fullmatch(raw):
        return True
    compact = re.sub(r"[\s\-_.]+", "", raw).casefold().replace("ё", "е")
    if compact in _KNOWN_MASH:
        return True
    if re.fullmatch(r"(.)\1{3,}", compact):
        return True
    return False


def _looks_like_contact_only(raw: str) -> bool:
    """Phone/email-shaped strings are privacy inputs, not consecutive garbage."""
    if "@" in raw:
        return True
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 10 and re.fullmatch(r"[\d+\s().\-]+", raw):
        return True
    return False


def _policies_raw(snapshot: D2TenantSnapshot) -> dict[str, object]:
    payload = dict(snapshot.files).get("clinic_policies.yaml")
    if payload is None:
        return {}
    value = yaml.safe_load(payload.decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _spam_template(snapshot: D2TenantSnapshot, *, key: str, default: str) -> str:
    text = str(_policies_raw(snapshot).get(key) or "").strip()
    return " ".join((text or default).split())


def build_d2_spam_gate_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    kind: SpamGateKind,
) -> MaterializedResponseOutcome:
    """Authored spam warn/closed stub: no CTA, menu, price, or medical content."""
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_spam_client_mismatch")
    mode: ResponseMode = "spam_warn" if kind == "warn" else "spam_closed"
    text = (
        _spam_template(snapshot, key="spam_one_chance_template", default=_DEFAULT_WARN)
        if kind == "warn"
        else _spam_template(snapshot, key="spam_closed_template", default=_DEFAULT_CLOSED)
    )
    terminal = CodeOwnedTerminalCandidate(
        source_client_id=snapshot.client_id,
        route="ADMIN",
        mode=mode,
        authority="deterministic_policy_terminal",
        display_text=text,
        canonical_contact=None,
    )
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=DeterministicBypassRouteAuthority(
            route_mode=RouteModePair(route="ADMIN", mode=mode),
            terminal_candidate=terminal,
        ),
        response_scope="clinic",
        selected_service_id=None,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(),
        transport_kind="blocking",
    )
    resolved = resolve_response_plan(plan, None)
    return MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        materialization_diagnostics=(),
        selection_diagnostics=(),
        adapter_diagnostics=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        trace=MaterializationTrace(None, (), (), ()),
    )
