"""Stage 5.2 terminal callback idempotency acceptance (parser + widget integration).

Delegates DOM lifecycle proof to the Chrome CDP harness. This module adds
explicit classification tests and guards against accidental provider usage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.test_one_call_stage52_widget_sse_offline_harness import (
    _HARNESS,
    _chrome_available,
    _offline_subprocess_env,
    _run_harness,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _stage52_offline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "OPENAI_API_KEY",
        "CHAT_API_KEY",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "CHAT_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("STAGE52_OFFLINE", "1")


def test_provider_transport_remains_blocked_under_stage52_env() -> None:
    import llm as llm_module

    with pytest.raises(Exception) as exc:
        llm_module.chat_client.chat.completions.create(model="blocked", messages=[])
    assert "BLOCKED" in str(exc.value)


def test_harness_subprocess_has_no_provider_credentials() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    env = _offline_subprocess_env()
    assert "OPENAI_API_KEY" not in env
    assert "CHAT_API_KEY" not in env
    assert "DASHSCOPE_API_KEY" not in env


def test_parser_reader_error_after_ui_finalizes_once_node_level() -> None:
    proc = subprocess.run(
        ["node", str(_HARNESS), "--test-parser-b1"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PARSER_B1:" in proc.stdout


def test_duplicate_done_parser_and_widget_single_bubble() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E3")[0]
    assert ev["callbacks"]["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["provider_calls"] == 0


def test_duplicate_ui_keeps_first_authoritative_payload() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E4")[0]
    assert ev["callbacks"]["ui"] == 1
    assert ev["final_text"] == "Ответ A"
    assert ev["dom"]["after"]["finalTurns"] == 1


def test_eof_without_done_single_finalize() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E5")[0]
    assert ev["callbacks"]["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1


def test_stream_fallback_duplicate_done_single_bubble() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E3b")[0]
    assert ev["callbacks"]["done"] == 1
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Только стрим"


def test_reader_error_after_ui_widget_single_bubble() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E7")[0]
    assert ev["callbacks"]["ui"] == 1
    assert ev["callbacks"]["done"] == 1
    assert ev["callbacks"]["error"] == 0
    assert ev["dom"]["after"]["finalTurns"] == 1
    assert ev["final_text"] == "Ответ A"


def test_invalid_ui_then_valid_ui_single_bubble() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    ev = _run_harness("E10")[0]
    assert ev["callbacks"]["ui"] == 1
    assert ev["final_text"] == "Ответ B"


def test_classification_observed_whitening_not_proven() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    e1 = _run_harness("E1")[0]
    assert e1["dom"]["after"]["totalBotBubbles"] == 1


def test_classification_terminal_idempotency_gap_fixed() -> None:
    if not _chrome_available():
        pytest.skip("CHROME_NOT_FOUND")
    e3 = _run_harness("E3")[0]
    assert e3["callbacks"]["done"] == 1
    assert e3["dom"]["after"]["finalTurns"] == 1


def test_node_harness_entrypoint_importable() -> None:
    assert _HARNESS.is_file()
    proc = subprocess.run(
        ["node", "--check", str(_HARNESS)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
