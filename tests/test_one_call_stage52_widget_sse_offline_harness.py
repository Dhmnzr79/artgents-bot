"""Stage 5.2 offline Widget/SSE acceptance harness (browser/CDP).

Executes real static/widget/api.js + widget.js in headless Chrome via
tests/js/stage52_widget_sse_harness.mjs. No Flask/provider path in harness.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HARNESS = _REPO_ROOT / "tests" / "js" / "stage52_widget_sse_harness.mjs"
_CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

_WHITENING_FINAL = (
    "Профессиональное отбеливание проводится без боли. Стоимость от 15 000 ₽."
)


class Stage52HarnessError(RuntimeError):
    pass


def _chrome_available() -> bool:
    return any(p.is_file() for p in _CHROME_CANDIDATES)


def _offline_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "OPENAI_API_KEY",
        "CHAT_API_KEY",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "CHAT_BASE_URL",
    ):
        env.pop(key, None)
    env["STAGE52_OFFLINE"] = "1"
    return env


def _run_harness(scenarios: str) -> list[dict]:
    if not _HARNESS.is_file():
        raise Stage52HarnessError(f"missing harness: {_HARNESS}")
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND: headless Chrome/Edge required for Stage 5.2 DOM harness")

    proc = subprocess.run(
        ["node", str(_HARNESS), scenarios],
        cwd=str(_REPO_ROOT),
        env=_offline_subprocess_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise Stage52HarnessError(
            "harness_failed\n"
            f"stdout={proc.stdout[-4000:]}\n"
            f"stderr={proc.stderr[-4000:]}"
        )
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("STAGE52_EVIDENCE:"):
            return json.loads(line[len("STAGE52_EVIDENCE:") :])
    raise Stage52HarnessError(f"no evidence line in stdout:\n{proc.stdout[-2000:]}")


def _one(scenario: str) -> dict:
    items = _run_harness(scenario)
    assert len(items) == 1
    item = items[0]
    assert item.get("provider_calls", 0) == 0
    assert item.get("network_attempts", 0) == 0
    return item


@pytest.fixture(scope="module")
def stage52_all_evidence() -> list[dict]:
    return _run_harness("all")


def test_harness_infrastructure_available() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    assert _HARNESS.is_file()


# T1 — normal whitening
def test_t1_normal_whitening_single_bubble() -> None:
    ev = _one("E1")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["dom"]["after"]["live"] == 0
    assert ev["dom"]["after"]["totalBotBubbles"] == 1
    assert ev["final_visible_text"] == _WHITENING_FINAL
    assert ev["control_metadata_visible"] is False


# T2 — partial live stream
def test_t2_partial_whitening_stream_replaced_by_final() -> None:
    ev = _one("E2")
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["dom"]["after"]["live"] == 0
    assert ev["final_text"] == _WHITENING_FINAL
    assert ev["partial_not_concatenated"] is True
    assert ev["dom"].get("during") is not None
    assert ev["dom"]["during"]["totalBotBubbles"] <= 1


# T3 — duplicate done with ui payload
def test_t3_duplicate_done_single_bubble() -> None:
    ev = _one("E3")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["dom"]["after"]["totalBotBubbles"] == 1


# T3b — duplicate done with streamed fallback only
def test_t3b_duplicate_done_stream_fallback_single_bubble() -> None:
    ev = _one("E3b")
    cb = ev["callbacks"]
    assert cb["ui"] == 0
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Только стрим"


# T4 — duplicate ui, first authoritative
def test_t4_duplicate_ui_first_payload_wins() -> None:
    ev = _one("E4")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Ответ A"


# T5 — EOF after accepted UI
def test_t5_eof_after_ui_single_finalize() -> None:
    ev = _one("E5")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert cb["error"] == 0
    assert ev["dom"]["after"]["finalTurns"] == 1


# T6 — late terminal events
def test_t6_late_terminal_events_do_not_add_second_message() -> None:
    ev = _one("E6")
    e6a = ev["subcases"]["E6a"]
    e6b = ev["subcases"]["E6b"]
    assert e6a["callbacks"]["ui"] == 1
    assert e6a["callbacks"]["done"] == 1
    assert e6a["dom"]["finalTurns"] == 1
    assert e6a["final_text"] == "Final A"
    assert e6b["dom"]["finalTurns"] == 1


# T7 — reader/network error after accepted UI
def test_t7_reader_error_after_accepted_ui_safe_finalize() -> None:
    ev = _one("E7")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert cb["error"] == 0
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["dom"]["after"]["live"] == 0
    assert ev["final_text"] == "Ответ A"
    assert ev["pending_cleared"] is True


# T8 — invalid UI then valid UI
def test_t8_invalid_ui_then_valid_ui_single_bubble() -> None:
    ev = _one("E10")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Ответ B"


# T9 — chunking / CRLF / duplicate done
def test_t9_crlf_chunking_duplicate_done_single_bubble() -> None:
    ev = _one("E9")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "X"


# T10 — public pending flow unchanged
def test_t10_concurrency_pending_guard() -> None:
    ev = _one("E8")
    assert ev["after_first_turn"]["finalTurns"] == 1
    assert ev["pending_while_slow"]["sendDisabled"] is True
    assert ev["followup_while_pending"] is None
    assert ev["followup_blocked_reason"] == "links_dismissed_on_composer_send"
    assert ev["final_dom"]["finalTurns"] == 2


# TJson — JSON fallback
def test_tjson_json_fallback_single_bubble() -> None:
    ev = _one("EJson")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1


def test_error_before_ui_no_final_bubble() -> None:
    ev = _one("E11")
    cb = ev["callbacks"]
    assert cb["ui"] == 0
    assert cb["done"] == 0
    assert cb["error"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 0
    assert ev["pending_cleared"] is True


def test_error_after_final_unchanged_single_bubble() -> None:
    ev = _one("E12")
    cb = ev["callbacks"]
    assert cb["ui"] == 1
    assert cb["done"] == 1
    assert cb["error"] == 0
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Final A"


def test_observed_whitening_issue_remains_not_proven(stage52_all_evidence: list[dict]) -> None:
    e1 = next(x for x in stage52_all_evidence if x["scenario"] == "E1")
    e2 = next(x for x in stage52_all_evidence if x["scenario"] == "E2")
    assert e1["dom"]["after"]["finalTurns"] == 1
    assert e2["dom"]["after"]["finalTurns"] == 1


def test_terminal_idempotency_gap_fixed(stage52_all_evidence: list[dict]) -> None:
    e3 = next(x for x in stage52_all_evidence if x["scenario"] == "E3")
    e3b = next(x for x in stage52_all_evidence if x["scenario"] == "E3b")
    assert e3["callbacks"]["done"] == 1
    assert e3["dom"]["after"]["finalTurns"] == 1
    assert e3b["callbacks"]["done"] == 1
    assert e3b["dom"]["after"]["finalTurns"] == 1
