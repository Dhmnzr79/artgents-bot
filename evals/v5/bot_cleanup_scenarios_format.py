"""Offline loader, validator and Markdown transcript formatter for bot_cleanup scenarios."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

MEASUREMENT_ID = "bot_cleanup_live_3"
SCENARIOS_VERSION = 3
EXPECTED_HEAD = "e227cd6a2ed837525271e1e5e48053fa02ba9f27"
CLIENT_ID = "demo"
FUTURE_LIVE_MODEL = "qwen3.7-plus-2026-05-26"
DEFAULT_MAX_PROVIDER_CALLS = 97
DEFAULT_MONETARY_CAP_USD = "3.00"
DEFAULT_SCENARIOS_PATH = Path(__file__).resolve().parent / "bot_cleanup_scenarios.json"

_REQUIRED_SCENARIO_KEYS = frozenset(
    {
        "id",
        "kind",
        "category",
        "title",
        "capability",
        "session_sid",
        "turns",
        "demo_data_required",
        "fixture_only",
    }
)
_REQUIRED_TURN_KEYS = frozenset({"id", "patient_message", "expect"})
_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{2,3}(?:-T\d+)?$")


class BotCleanupScenariosError(ValueError):
    """Invalid frozen scenario package."""


def load_bot_cleanup_scenarios(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_SCENARIOS_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise BotCleanupScenariosError("root_must_be_object")
    return raw


def validate_bot_cleanup_scenarios(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("measurement_id") != MEASUREMENT_ID:
        errors.append("measurement_id_mismatch")
    if int(data.get("version") or 0) != SCENARIOS_VERSION:
        errors.append("version_mismatch")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("scenarios_missing")
        return errors

    scenario_ids: set[str] = set()
    turn_ids: set[str] = set()
    session_sids: set[str] = set()

    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"scenario_{index}_not_object")
            continue
        missing = _REQUIRED_SCENARIO_KEYS - frozenset(scenario)
        if missing:
            errors.append(f"{scenario.get('id', index)}:missing:{','.join(sorted(missing))}")
        scenario_id = str(scenario.get("id") or "").strip()
        if not scenario_id:
            errors.append(f"scenario_{index}:empty_id")
            continue
        if scenario_id in scenario_ids:
            errors.append(f"duplicate_scenario_id:{scenario_id}")
        scenario_ids.add(scenario_id)

        session_sid = str(scenario.get("session_sid") or "").strip()
        if not session_sid:
            errors.append(f"{scenario_id}:empty_session_sid")
        elif session_sid in session_sids:
            errors.append(f"duplicate_session_sid:{session_sid}")
        session_sids.add(session_sid)

        kind = str(scenario.get("kind") or "")
        turns = scenario.get("turns")
        if not isinstance(turns, list) or not turns:
            errors.append(f"{scenario_id}:turns_missing")
            continue
        if kind == "single" and len(turns) != 1:
            errors.append(f"{scenario_id}:single_kind_requires_one_turn")
        if kind == "dialog" and len(turns) < 2:
            errors.append(f"{scenario_id}:dialog_kind_requires_multiple_turns")

        for turn in turns:
            if not isinstance(turn, dict):
                errors.append(f"{scenario_id}:turn_not_object")
                continue
            missing_turn = _REQUIRED_TURN_KEYS - frozenset(turn)
            if missing_turn:
                errors.append(f"{scenario_id}:turn_missing:{','.join(sorted(missing_turn))}")
            turn_id = str(turn.get("id") or "").strip()
            if not turn_id:
                errors.append(f"{scenario_id}:turn_empty_id")
            elif turn_id in turn_ids:
                errors.append(f"duplicate_turn_id:{turn_id}")
            else:
                turn_ids.add(turn_id)
            message = str(turn.get("patient_message") or "").strip()
            if not message:
                errors.append(f"{turn_id or scenario_id}:empty_patient_message")
            expect = turn.get("expect")
            if not isinstance(expect, dict):
                errors.append(f"{turn_id}:expect_not_object")
                continue
            if expect.get("for_reviewer_only") is not True:
                errors.append(f"{turn_id}:expect_must_be_reviewer_only")
            sources = expect.get("sources")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{turn_id}:sources_missing")

    return errors


def summarize_bot_cleanup_scenarios(data: Mapping[str, Any]) -> dict[str, int | str]:
    scenarios = data.get("scenarios") or []
    single = sum(1 for item in scenarios if item.get("kind") == "single")
    dialog = sum(1 for item in scenarios if item.get("kind") == "dialog")
    turns = sum(len(item.get("turns") or []) for item in scenarios)
    fixture_only = sum(1 for item in scenarios if item.get("fixture_only"))
    fixture_turns = sum(
        len(item.get("turns") or []) for item in scenarios if item.get("fixture_only")
    )
    return {
        "scenario_count": len(scenarios),
        "single_scenario_count": single,
        "dialog_chain_count": dialog,
        "model_turn_count": turns,
        "provider_eligible_turn_count": turns - fixture_turns,
        "fixture_only_count": fixture_only,
        "fixture_only_turn_count": fixture_turns,
    }


def _turn_execution_status(result: Mapping[str, Any] | None) -> str:
    if not result:
        return "not_run"
    status = str(result.get("status") or "").strip().lower()
    if status:
        return status
    if result.get("error_code") or result.get("error_message"):
        return "error"
    if "final_answer" in result:
        return "ok"
    return "not_run"


def _render_final_answer_lines(result: Mapping[str, Any]) -> list[str]:
    lines = ["", "**Ответ бота (final_answer)**", ""]
    if "final_answer" not in result:
        lines.append("_(поле final_answer отсутствует)_")
        return lines
    if result.get("final_answer") is None:
        lines.append("_(final_answer = null)_")
        return lines
    answer = str(result.get("final_answer")).strip()
    if answer:
        lines.append(answer)
    else:
        lines.append("_(пустой final_answer)_")
    return lines


def _render_turn_execution_lines(result: Mapping[str, Any] | None) -> list[str]:
    status = _turn_execution_status(result)
    lines = [f"**Статус:** `{status}`"]

    if not result:
        lines.extend(["", "**Ответ бота (final_answer)**", "", "_(ход не выполнен)_"])
        return lines

    if status in {"error", "blocked"}:
        error_code = str(result.get("error_code") or "").strip()
        error_message = str(result.get("error_message") or result.get("error") or "").strip()
        if error_code:
            lines.append(f"**Код ошибки:** `{error_code}`")
        if error_message:
            lines.extend(["", "**Причина:**", "", f"> {error_message}"])
        lines.extend(_render_final_answer_lines(result))
        return lines

    if status in {"not_run", "skipped", "pending"}:
        label = {
            "not_run": "ход не выполнен",
            "skipped": "ход пропущен",
            "pending": "ход не запускался",
        }.get(status, status)
        lines.extend(["", "**Ответ бота (final_answer)**", "", f"_({label})_"])
        return lines

    lines.extend(_render_final_answer_lines(result))
    return lines


def render_transcript_markdown(
    *,
    attempt_id: str,
    scenarios: Sequence[Mapping[str, Any]],
    turn_results: Sequence[Mapping[str, Any]],
    artifact_dir: str | Path,
) -> str:
    """Build owner-readable transcript from executed turn results (not paraphrased)."""

    by_turn_id = {
        str(item.get("turn_id") or "").strip(): item
        for item in turn_results
        if str(item.get("turn_id") or "").strip()
    }
    lines = [
        f"# BOT-CLEANUP transcript — `{attempt_id}`",
        "",
        f"- artifact_dir: `{artifact_dir}`",
        f"- scenarios: `{len(scenarios)}`",
        f"- turns executed: `{len(turn_results)}`",
        "",
        "> Текст ответа — только поле `final_answer` после кодовой сборки. Модельный `patient_text` — в сырых JSON.",
        "",
    ]
    for scenario in scenarios:
        scenario_id = str(scenario.get("id") or "")
        lines.extend(
            [
                f"## {scenario_id} — {scenario.get('title', '')}",
                "",
                f"- capability: {scenario.get('capability', '')}",
                f"- session_sid: `{scenario.get('session_sid', '')}`",
                "",
            ]
        )
        for turn in scenario.get("turns") or []:
            turn_id = str(turn.get("id") or "")
            result = by_turn_id.get(turn_id)
            lines.append(f"### {turn_id}")
            lines.append("")
            lines.append("**Вопрос пациента**")
            lines.append("")
            lines.append(f"> {turn.get('patient_message', '')}")
            lines.append("")
            lines.extend(_render_turn_execution_lines(result))
            lines.append("")
            ui = (result or {}).get("ui") or {}
            if ui:
                lines.append("**UI payload**")
                lines.append("")
                for key in ("followups", "video", "cta"):
                    if key in ui and ui[key] is not None:
                        lines.append(f"- {key}: `{ui[key]}`")
                lines.append("")
            review = str((result or {}).get("review_verdict") or "").strip()
            if review:
                lines.append(f"**Оценка:** {review}")
            quote = str((result or {}).get("issue_quote") or "").strip()
            if quote:
                lines.append("")
                lines.append("**Проблемная цитата:**")
                lines.append("")
                lines.append(f"> {quote}")
            raw_ref = str((result or {}).get("raw_turn_path") or "").strip()
            if raw_ref:
                lines.append("")
                lines.append(f"_raw: `{raw_ref}`_")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
