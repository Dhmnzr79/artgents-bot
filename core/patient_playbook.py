"""Patient situation marketing playbook — option selection + LLM context (multiclient-safe)."""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any

import yaml

from contracts.patient_playbook import (
    PatientOption,
    PatientOptionsResult,
    PatientPlaybookAnswerStyle,
    PatientPlaybookRuleConfig,
    PatientPlaybookSituationConfig,
)
from contracts.decision_frame import DecisionFrameConfidence
from contracts.patient_situation import PatientSituationResult
from core import patient_scope_cues as psc
from core.client_runtime import client_pack_dir
from core.pricebook_loader import load_pricebook_service
from core.routing_loader import THRESHOLDS

_LOCK = threading.Lock()
_PLAYBOOK_CACHE: dict[str, dict[str, PatientPlaybookSituationConfig] | None] = {}
_PLAYBOOK_RULES_CACHE: dict[str, list[PatientPlaybookRuleConfig] | None] = {}

_OPTIONS_OVERVIEW_RX = re.compile(
    r"(?:"
    r"что\s+делать|что\s+можно|какие\s+вариант|что\s+(?:мне\s+)?подойд|"
    r"как\s+восстанов|что\s+лучше|какой\s+вариант|чем\s+лучше|как\s+лучше|посовет\w*|"
    r"что\s+дальше|с\s+чего\s+начать|как\s+быть"
    r")",
    re.I | re.U,
)
_SPECIFIC_SERVICE_RX = re.compile(
    r"all[\s-]?on[\s-]?[46]|all-on|съёмн\w*\s+протез|скулов\w*|"
    r"zygomatic|классическ\w*\s+имплант|одномомент|имплант\s+с\s+коронк",
    re.I | re.U,
)
_EXPLAIN_SERVICE_RX = re.compile(r"что\s+такое|расскаж\w*|объясн\w*", re.I | re.U)


def _playbook_path(client_id: str | None) -> str:
    cid = (client_id or "demo").strip() or "demo"
    return os.path.join(client_pack_dir(cid), "patient_playbook.yaml")


def _read_service_catalog(client_id: str | None) -> dict[str, Any]:
    path = os.path.join(client_pack_dir(client_id), "service_catalog.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _service_available(client_id: str | None, service_id: str) -> bool:
    sid = (service_id or "").strip()
    if not sid:
        return False
    catalog = _read_service_catalog(client_id)
    entry = catalog.get(sid)
    if isinstance(entry, dict) and entry.get("active") is False:
        return False
    if isinstance(entry, dict):
        return True
    return load_pricebook_service(client_id, sid) is not None


def _display_name_for_service(
    client_id: str | None,
    service_id: str,
    *,
    fallback_label: str | None = None,
) -> str:
    sid = (service_id or "").strip()
    catalog = _read_service_catalog(client_id)
    entry = catalog.get(sid) if sid else None
    if isinstance(entry, dict):
        title = str(entry.get("title") or "").strip()
        if title:
            return title
    pb = load_pricebook_service(client_id, sid) if sid else None
    if pb is not None:
        dn = str(getattr(pb, "display_name", None) or "").strip()
        if dn:
            return dn
    fb = str(fallback_label or "").strip()
    return fb or sid


def _factual_snippets_for_service(client_id: str | None, service_id: str) -> list[str]:
    sid = (service_id or "").strip()
    snippets: list[str] = []
    catalog = _read_service_catalog(client_id)
    entry = catalog.get(sid) if sid else None
    if isinstance(entry, dict):
        facts = entry.get("facts")
        if isinstance(facts, list):
            for item in facts[:3]:
                text = str(item or "").strip()
                if text:
                    snippets.append(text)
    pb = load_pricebook_service(client_id, sid) if sid else None
    if pb is not None:
        intro = str(getattr(pb, "intro_text", None) or "").strip()
        if intro and intro not in snippets:
            snippets.insert(0, intro)
    return snippets[:4]


def load_patient_playbook(client_id: str | None) -> dict[str, PatientPlaybookSituationConfig] | None:
    """Load client playbook; None if file missing or empty."""
    cid = (client_id or "demo").strip() or "demo"
    with _LOCK:
        if cid in _PLAYBOOK_CACHE:
            return _PLAYBOOK_CACHE[cid]

    path = _playbook_path(cid)
    parsed: dict[str, PatientPlaybookSituationConfig] | None = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        situations = raw.get("patient_situations") if isinstance(raw, dict) else None
        if isinstance(situations, dict) and situations:
            parsed = {}
            for kind, cfg in situations.items():
                if not isinstance(cfg, dict):
                    continue
                parsed[str(kind).strip()] = PatientPlaybookSituationConfig.model_validate(cfg)
    except (OSError, yaml.YAMLError, ValueError):
        parsed = None

    with _LOCK:
        _PLAYBOOK_CACHE[cid] = parsed
    return parsed


def load_patient_playbook_rules(client_id: str | None) -> list[PatientPlaybookRuleConfig] | None:
    """Load composable playbook rules; None when no rule section exists."""
    cid = (client_id or "demo").strip() or "demo"
    with _LOCK:
        if cid in _PLAYBOOK_RULES_CACHE:
            return _PLAYBOOK_RULES_CACHE[cid]

    path = _playbook_path(cid)
    parsed: list[PatientPlaybookRuleConfig] | None = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        rules = raw.get("rules") if isinstance(raw, dict) else None
        if isinstance(rules, list) and rules:
            parsed = []
            for cfg in rules:
                if not isinstance(cfg, dict):
                    continue
                parsed.append(PatientPlaybookRuleConfig.model_validate(cfg))
    except (OSError, yaml.YAMLError, ValueError):
        parsed = None

    with _LOCK:
        _PLAYBOOK_RULES_CACHE[cid] = parsed
    return parsed


def _show_when_matches(
    show_when: str,
    *,
    situation: PatientSituationResult,
    q: str,
) -> bool:
    sw = (show_when or "default").strip()
    if sw == "default":
        return True
    if sw == "bone_deficit_or_upper_jaw":
        cues = situation.cues
        if situation.patient_scope == "upper_jaw":
            return True
        if situation.kind in {"upper_jaw_missing_or_complex", "bone_deficit_or_grafting"}:
            return True
        if "upper_jaw" in cues.anatomy or "bone" in cues.anatomy:
            return True
        if "bone_deficit" in cues.state:
            return True
        if psc.UPPER_JAW_RX.search(q) or psc.BONE_DEFICIT_RX.search(q):
            return True
        return False
    if sw == "extraction_context":
        if situation.kind == "extraction_then_implant":
            return True
        if "extracted" in situation.cues.state:
            return True
        return bool(psc.EXTRACTION_IMPLANT_RX.search(q))
    return True


def _rule_matches(rule: PatientPlaybookRuleConfig, situation: PatientSituationResult) -> bool:
    match = rule.match
    if match.kind and match.kind != situation.kind:
        return False
    if match.problem and match.problem != situation.problem:
        return False
    if match.extent and match.extent != situation.extent:
        return False
    if match.jaw and match.jaw != situation.jaw:
        return False
    if match.intent and match.intent != situation.cues.intent:
        return False
    modifiers = set(situation.modifiers or [])
    modifiers.update(situation.cues.state or [])
    modifiers.update(situation.cues.anatomy or [])
    for item in match.modifiers:
        if item not in modifiers:
            return False
    return True


def _rule_specificity(rule: PatientPlaybookRuleConfig) -> int:
    match = rule.match
    score = 0
    for value in (match.kind, match.problem, match.extent, match.jaw, match.intent):
        if value:
            score += 1
    score += len(match.modifiers) * 2
    return score


def _select_patient_rule(
    situation: PatientSituationResult,
    client_id: str | None,
) -> PatientPlaybookRuleConfig | None:
    rules = load_patient_playbook_rules(client_id) or []
    best: PatientPlaybookRuleConfig | None = None
    best_score = -1
    for rule in rules:
        if not rule.options or not _rule_matches(rule, situation):
            continue
        score = _rule_specificity(rule)
        if score > best_score:
            best = rule
            best_score = score
    return best


def _legacy_situation_config(
    situation: PatientSituationResult,
    client_id: str | None,
) -> PatientPlaybookSituationConfig | None:
    playbook = load_patient_playbook(client_id)
    if not playbook:
        return None
    kind = str(situation.kind or "unknown")
    return playbook.get(kind)


def select_patient_options(
    situation: PatientSituationResult,
    q: str,
    client_id: str | None,
) -> PatientOptionsResult | None:
    """Pick playbook options for situation; None if playbook missing or no valid options."""
    cfg = _select_patient_rule(situation, client_id)
    matched_rule_id = str(cfg.id).strip() if cfg is not None else None
    if cfg is None:
        cfg = _legacy_situation_config(situation, client_id)
    if cfg is None or not cfg.options:
        return None

    skipped: list[str] = []
    candidates: list[PatientOption] = []
    for opt_cfg in sorted(cfg.options, key=lambda o: -int(o.priority)):
        sid = str(opt_cfg.service_id or "").strip()
        if not sid:
            continue
        if not _show_when_matches(opt_cfg.show_when, situation=situation, q=q):
            skipped.append(sid)
            continue
        if not _service_available(client_id, sid):
            skipped.append(sid)
            continue
        candidates.append(
            PatientOption(
                service_id=sid,
                display_name=_display_name_for_service(
                    client_id, sid, fallback_label=opt_cfg.label
                ),
                role=str(opt_cfg.role or "").strip(),
                positioning=str(opt_cfg.positioning or "").strip(),
                priority=int(opt_cfg.priority),
                factual_snippets=_factual_snippets_for_service(client_id, sid),
            )
        )

    if not candidates:
        return None

    max_opts = max(1, int(cfg.max_options))
    style = cfg.answer_style
    if style.max_options:
        max_opts = min(max_opts, int(style.max_options))
    selected = candidates[:max_opts]
    return PatientOptionsResult(
        situation_kind=situation.kind,
        patient_scope=situation.patient_scope,
        options=selected,
        primary_cta=str(cfg.primary_cta or "consult").strip(),
        strategy=str(cfg.strategy or "").strip(),
        answer_style=cfg.answer_style,
        source="patient_playbook",
        option_service_ids=[o.service_id for o in selected],
        skipped_options=skipped,
        matched_rule_id=matched_rule_id or None,
    )


def build_patient_options_llm_context(
    result: PatientOptionsResult,
    *,
    client_id: str | None,
) -> dict[str, Any]:
    """Structured context for LLM — no canned marketing paragraphs."""
    return {
        "patient_situation_kind": result.situation_kind,
        "patient_scope": result.patient_scope,
        "strategy": result.strategy,
        "matched_rule_id": result.matched_rule_id,
        "primary_cta": result.primary_cta,
        "answer_style": result.answer_style.model_dump(),
        "selected_options": [
            {
                "service_id": o.service_id,
                "display_name": o.display_name,
                "role": o.role,
                "positioning": o.positioning,
                "priority": o.priority,
                "factual_snippets": list(o.factual_snippets),
            }
            for o in result.options
        ],
        "skipped_service_ids": list(result.skipped_options),
        "client_id": client_id,
    }


def build_synthetic_patient_options_chunk(
    result: PatientOptionsResult,
    *,
    client_id: str | None,
) -> dict[str, Any]:
    """Synthetic chunk body for Generator (like doctors_list)."""
    context = build_patient_options_llm_context(result, client_id=client_id)
    body = json.dumps(context, ensure_ascii=False, indent=2)
    text = (
        "РОЛЬ: PATIENT_OPTIONS_OVERVIEW — составь ответ по инструкции из вопроса.\n"
        "Структурированный контекст playbook (JSON, используй только факты из factual_snippets):\n"
        + body
    )
    return {
        "file": "implantation__info__methods_overview.md",
        "h2": "",
        "h3": "",
        "h2_id": None,
        "h3_id": "patient_options",
        "text": text,
        "_score": 1.0,
        "client_id": client_id,
        "meta": {
            "doc_id": "implantation__info__methods_overview",
            "doc_type": "info",
            "subtype": "patient_options_overview",
        },
    }


def build_patient_options_llm_question(*, user_question: str, result: PatientOptionsResult) -> str:
    """Generator instruction — live wording, not YAML copy."""
    q0 = (user_question or "").strip()
    style = result.answer_style
    lines = [
        f"Вопрос пациента: {q0}" if q0 else "Вопрос пациента: (ситуация / выбор вариантов)",
        "",
        "Задача: пациент описывает ситуацию, а не конкретную услугу.",
        "Дай краткий обзор вариантов из selected_options в материале (JSON).",
        "Формулируй живым разговорным языком — не копируй текст дословно и не используй шаблонные маркетинговые абзацы.",
        f"Покажи до {len(result.options)} вариантов в порядке selected_options — это уже приоритет клиники (strategy={result.strategy or 'default'}).",
        "Не меняй порядок вариантов и не добавляй услуги, которых нет в selected_options.",
    ]
    if style.avoid_single_winner:
        lines.append("Не представляй один вариант как единственно правильный для всех.")
    if style.avoid_medical_promise:
        lines.append(
            "Не обещай медицинский результат; используй формулировки «обычно рассматривают», "
            "«может подойти», «зависит от снимка и осмотра»."
        )
    if style.mention_consult_ct:
        lines.append(
            "В конце предложи КТ и консультацию как разумный следующий шаг для выбора варианта."
        )
    lines.append(
        "Используй display_name вариантов и factual_snippets как опору; не добавляй факты вне snippets."
    )
    return "\n".join(lines)


def _decision_service_confidence(decision: Any | None) -> float:
    if decision is None:
        return 0.0
    conf = getattr(decision, "confidence", None)
    if isinstance(conf, DecisionFrameConfidence):
        return float(conf.service)
    if isinstance(conf, dict):
        return float(conf.get("service") or 0)
    try:
        return float(conf or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_specific_service_query(q: str, decision: Any | None) -> bool:
    text = (q or "").strip()
    if psc.has_price_intent(text):
        return True
    if decision is not None:
        svc = str(getattr(decision, "service_id", None) or "").strip()
        conf = _decision_service_confidence(decision)
        min_conf = float(THRESHOLDS.metadata_first.service_id_min_confidence)
        if svc and svc.lower() not in {"", "unknown", "none"} and conf >= min_conf:
            return True
        qm = str(getattr(decision, "query_mode", None) or "").strip().lower()
        if qm == "specific" and svc and svc.lower() not in {"", "unknown", "none"}:
            return True
    if _EXPLAIN_SERVICE_RX.search(text) and _SPECIFIC_SERVICE_RX.search(text):
        return True
    if _SPECIFIC_SERVICE_RX.search(text) and not _OPTIONS_OVERVIEW_RX.search(text):
        return True
    return False


def _has_patient_options_overview_signal(
    q: str,
    situation: PatientSituationResult,
) -> bool:
    text = q or ""
    min_conf = float(THRESHOLDS.patient_situation.min_confidence_for_routing)
    if situation.cues.intent in {"choose_solution", "restore"}:
        return True
    if _OPTIONS_OVERVIEW_RX.search(text):
        return True
    if float(situation.confidence or 0) >= min_conf:
        if psc.ALL_TEETH_MISSING_RX.search(text) or psc.FULL_JAW_RESTORE_RX.search(text):
            return True
        if psc.FULL_ARCH_RX.search(text) and situation.extent == "full_arch":
            return True
    return False


def _has_playbook_config_for(
    situation: PatientSituationResult,
    client_id: str | None,
) -> bool:
    if _select_patient_rule(situation, client_id) is not None:
        return True
    return _legacy_situation_config(situation, client_id) is not None


def should_use_patient_options_overview(
    q: str,
    situation: PatientSituationResult,
    *,
    decision: Any | None,
    intent: str,
    client_id: str | None = None,
) -> bool:
    """True when playbook overview should replace single-doc content retrieval."""
    if situation.kind == "unknown":
        return False
    if not _has_playbook_config_for(situation, client_id):
        return False

    ri = ""
    if decision is not None:
        ri = str(getattr(decision, "route_intent", None) or "").strip().lower()
    effective_intent = ri or str(intent or "").strip().lower()
    if effective_intent == "price_lookup" or str(intent or "").strip().lower() == "price_lookup":
        return False
    if situation.cues.intent == "price":
        return False
    has_overview_signal = _has_patient_options_overview_signal(q, situation)
    if _is_specific_service_query(q, decision) and not has_overview_signal:
        return False

    return has_overview_signal


def patient_options_quick_replies(
    result: PatientOptionsResult,
    *,
    client_id: str | None = None,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for opt in result.options:
        label = (opt.display_name or opt.service_id).strip()
        sid = (opt.service_id or "").strip()
        if not label or not sid:
            continue
        ref = _patient_option_ref(sid, client_id=client_id)
        if not ref:
            continue
        out.append(
            {"label": _patient_option_label(label), "ref": ref, "source": "patient_option"}
        )
    return out


def _patient_option_ref(service_id: str, *, client_id: str | None = None) -> str | None:
    catalog = _read_service_catalog(client_id)
    entry = catalog.get((service_id or "").strip())
    if not isinstance(entry, dict):
        return None
    ref = str(entry.get("md_entry_ref") or "").strip()
    if not ref:
        return None
    base, anchor = ref.split("#", 1) if "#" in ref else (ref, "korotko")
    if not base.endswith(".md"):
        base = f"{base}.md"
    return f"{base}#{anchor or 'korotko'}"


def _patient_option_label(label: str) -> str:
    text = (label or "").strip()
    if text.lower().startswith("имплантация "):
        text = text[len("Имплантация "):].strip()
    return text or "Подробнее"


def patient_options_telemetry(result: PatientOptionsResult) -> dict[str, Any]:
    return {
        "patient_options_overview_used": True,
        "patient_options_situation_kind": result.situation_kind,
        "patient_options_service_ids": list(result.option_service_ids),
        "patient_options_source": result.source,
        "patient_options_skipped": list(result.skipped_options),
        "patient_options_strategy": result.strategy,
        "patient_options_rule_id": result.matched_rule_id,
    }


def record_patient_options_ctx(
    result: PatientOptionsResult,
    *,
    client_id: str | None = None,
) -> None:
    try:
        from flask import has_request_context, request
    except ImportError:
        return
    if not has_request_context() or not hasattr(request, "ctx"):
        return
    for key, value in patient_options_telemetry(result).items():
        request.ctx[key] = value
    request.ctx["patient_options_quick_replies"] = patient_options_quick_replies(
        result,
        client_id=client_id,
    )
