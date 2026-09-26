"""CP5-C1: assembled A03/A04/B04/B15 through the common D2 route.

Demo voice (D2-091): informational answers and direct warranty use model_prose
grounded in an md content_ref plus that material's source UI. Code still owns
prices/promos/packages. Direct warranty is not implant_warranty fact form.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 14, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="c1-content-lookup")
PAIN_KOROTKO = "Страх боли при имплантации — нормальная реакция"
PAIN_LIVE = (
    "Понимаю этот страх — при имплантации работаем с анестезией, "
    "и обычно всё терпимее, чем кажется заранее."
)
PAIN_SEDATION = "Седация и наркоз"
PAIN_ANESTHESIA_LIVE = (
    "Для имплантации обычно хватает местной анестезии; "
    "седацию или наркоз обсуждают отдельно, если так спокойнее."
)
PAIN_ANESTHESIA = "Какую анестезию используют"
WARRANTY_LIVE = (
    "Да, гарантия есть: на работу врача — год, на Nobel и Impro — пожизненно, "
    "на Implantium — пять лет. Условия фиксируем в договоре."
)
WARRANTY_ALSO = "Гарантия на работу врача и импланты фиксируется в договоре."
WARRANTY_BOOSTER = "Условия гарантии фиксируются в договоре."
WARRANTY_FACT = (
    "Гарантия на работу врача — 1 год (корректировки и помощь бесплатно). "
    "На импланты Impro и Nobel — пожизненная, на Implantium — 5 лет."
)
IMPLANT_SHORT = "Скидка до 15% при оплате в день обращения."
CONSULT_SHORT = "Бесплатная консультация до 31.12.2026."
COMPARISON_READY = "Ни один метод не «лучше всегда»"
CLASSIC_FACT = "Классическая имплантация проводится в два этапа"
ONE_STAGE_FACT = "удаление зуба и установка импланта за один визит"
GAP = "недостаточно информации"
PAIN_VIDEO = "pain-doctor-explains"
PAIN_FOLLOW = "implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut"
PAIN_FOLLOW_AFTER = "implantation__faq__pain.md#chto-chuvstvuetsya-posle-ustanovki"


def _content_part(
    *,
    request_id: str = "r1",
    content_ref: str | None,
    service_id: str | None,
    topic_id: str | None,
    section_refs: list[str] | None = None,
    realization: str = "authored",
    text: str = "Смысловой текст модели не является источником ответа.",
    fallback: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": request_id,
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "topic_id": topic_id,
        "service_id": service_id,
        "statement_mode": "question",
        "situation": None,
        "content_text": text if content_ref is not None or realization == "model_prose" else None,
        "content_ref": content_ref,
        "content_realization": realization,
        "content_section_refs": section_refs or [],
        "content_fallback_section_ref": fallback,
    }
    return payload


def _raw(
    *parts: dict[str, object],
    commercial_intent: str = "none",
    scenario: str = "none",
    direct_fact_ids: list[str] | None = None,
) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent=commercial_intent,
            promotion_scope="none",
            scenario=scenario,
            primary_price_request_id=None,
            patient_text=None,
            references={"direct_fact_ids": direct_fact_ids or []},
            request_understanding={"subjects": [], "requests": list(parts)},
        ),
        ensure_ascii=False,
    )


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-C1")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@contextmanager
def observed_common_route():
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_",
            "core.target_composer",
            "core.target_runtime_",
            "core.response_plan_composer_executor",
            "core.target_session_selection",
            "core.one_call_runtime",
            "core.one_call_presentation",
            "core.response_plan_session",
            "core.target_offer_projection",
            "core.target_service_selection",
            "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        assert module != "core.target_marketing_selector", "legacy marketing selector called"
        if module == "session":
            assert frame.f_code.co_name == "current_session_client_id", (
                f"unexpected session use on ordinary D2 route: {frame.f_code.co_name}"
            )
            return

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def _run(
    tmp_path: Path,
    raw: str,
    *,
    key: SessionKey = KEY,
    message: str = "Вопрос",
    now: datetime = NOW,
    store_path: Path | None = None,
    clients: Path | None = None,
) -> tuple[object, object, object, list, Path]:
    clients = clients if clients is not None else _clients(tmp_path)
    provider = RawFakeProvider(raw)
    db = store_path or (tmp_path / "dialogue.sqlite")
    with observed_common_route() as calls:
        with D2DialogueStore(db) as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=clients,
                store=store,
                now=now,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls, clients


def test_a03_pain_fear_is_ordinary_content_with_source_ui_and_short_promo(tmp_path: Path) -> None:
    first, saved, _, calls, clients = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=PAIN_LIVE,
                fallback="a:korotko",
            ),
            scenario="pain_fear",
        ),
        message="Я боюсь боли при имплантации",
    )

    text = first.response.rendered_text
    ui = first.response.ui_projection
    resolved = first.response.resolved
    assert PAIN_LIVE in text
    assert resolved.d2_request_parts[0].content_publication == "model_prose"
    assert resolved.d2_result_status == "complete"
    assert resolved.terminal_text is None
    assert resolved.d2_price_block is None
    assert resolved.d2_price_booster_block is None
    assert resolved.d2_also_list_block is None
    assert [block.display_text for block in resolved.promo_blocks] == [IMPLANT_SHORT, CONSULT_SHORT]
    assert WARRANTY_ALSO not in text
    assert "Также" not in text
    assert resolved.ui_plan.source_content_ref == "implantation__faq__pain.md"
    assert ui.video is not None and ui.video.video_id == PAIN_VIDEO
    assert [item.reply_id for item in ui.quick_replies] == [PAIN_FOLLOW]
    assert [item.button_id for item in ui.buttons] == ["consult"]
    assert saved.state.accumulated_shown_ids.secondary_ref_ids == (PAIN_VIDEO, PAIN_FOLLOW)
    assert saved.state.terminal_state == "none"

    follow, saved_follow, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:kakuyu-anesteziyu-ispolzuyut"],
                realization="model_prose",
                text=PAIN_ANESTHESIA_LIVE,
                fallback="a:kakuyu-anesteziyu-ispolzuyut",
            )
        ),
        message="Какую анестезию используют?",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    follow_ui = follow.response.ui_projection
    assert PAIN_ANESTHESIA_LIVE in follow.response.rendered_text
    assert follow_ui.video is None
    assert PAIN_FOLLOW not in {item.reply_id for item in follow_ui.quick_replies}
    assert PAIN_FOLLOW_AFTER in {item.reply_id for item in follow_ui.quick_replies}
    assert [item.button_id for item in follow_ui.buttons] == ["consult"]

    back, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=PAIN_LIVE,
                fallback="a:korotko",
            )
        ),
        message="Ещё раз про боль",
        now=NOW.replace(minute=2),
        clients=clients,
    )
    back_ui = back.response.ui_projection
    assert PAIN_LIVE in back.response.rendered_text
    assert back_ui.video is None
    assert PAIN_FOLLOW not in {item.reply_id for item in back_ui.quick_replies}
    assert PAIN_FOLLOW_AFTER not in {item.reply_id for item in back_ui.quick_replies}
    assert [item.button_id for item in back_ui.buttons] == ["consult"]
    assert sum(name == "select_target_marketing" for _, name in calls) == 0
    assert saved_follow.state.accumulated_shown_ids.promo_fact_ids


def test_a04_direct_warranty_uses_md_document_not_also_package(tmp_path: Path) -> None:
    standalone, _, _, calls, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=WARRANTY_LIVE,
                fallback="a:korotko",
            )
        ),
        message="А гарантия у вас есть?",
        key=SessionKey(client_id="demo", sid="c1-warranty"),
    )
    text = standalone.response.rendered_text
    resolved = standalone.response.resolved
    ui = standalone.response.ui_projection
    assert WARRANTY_LIVE in text
    assert resolved.d2_request_parts[0].content_publication == "model_prose"
    assert resolved.requested_fact_blocks == ()
    assert WARRANTY_FACT not in text
    assert WARRANTY_ALSO not in text
    assert WARRANTY_BOOSTER not in text
    assert "Также" not in text
    assert resolved.d2_also_list_block is None
    assert resolved.d2_price_booster_block is None
    assert resolved.promo_blocks == ()
    assert resolved.d2_price_block is None
    assert GAP not in text
    assert resolved.ui_plan.source_content_ref == "clinic__info__warranty.md"
    assert [item.reply_id for item in ui.quick_replies] == [
        "clinic__info__warranty.md#chto-delat-esli-voznikla-problema"
    ]
    assert [item.button_id for item in ui.buttons] == ["booking"]
    assert sum(name == "select_target_marketing" for _, name in calls) == 0

    first, _, _, _, clients = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=PAIN_LIVE,
                fallback="a:korotko",
            )
        ),
        message="Я боюсь боли при имплантации",
        key=SessionKey(client_id="demo", sid="c1-warranty-after"),
    )
    after, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=WARRANTY_LIVE,
                fallback="a:korotko",
            )
        ),
        message="А гарантия у вас есть?",
        key=SessionKey(client_id="demo", sid="c1-warranty-after"),
        now=NOW.replace(minute=1),
        clients=clients,
    )
    assert PAIN_LIVE in first.response.rendered_text
    assert WARRANTY_LIVE in after.response.rendered_text
    assert WARRANTY_ALSO not in after.response.rendered_text
    assert after.response.resolved.requested_fact_blocks == ()
    assert after.response.resolved.promo_blocks == ()


def test_b04_comparison_ready_two_materials_and_missing_side(tmp_path: Path) -> None:
    ready, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="comparison__classic_vs_one_stage.md",
                service_id=None,
                topic_id="implantation",
                section_refs=["a:korotko"],
            )
        ),
        message="Классическая или одномоментная?",
        key=SessionKey(client_id="demo", sid="c1-compare-ready"),
    )
    ready_ui = ready.response.ui_projection
    assert COMPARISON_READY in ready.response.rendered_text
    assert ready.response.resolved.ui_plan.source_content_ref == "comparison__classic_vs_one_stage.md"
    assert ready_ui.quick_replies
    assert [item.button_id for item in ready_ui.buttons] == ["consult"]

    two, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                request_id="r1",
                content_ref="implantation__service__classic.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
            ),
            _content_part(
                request_id="r2",
                content_ref="implantation__service__one_stage.md",
                service_id="one_stage",
                topic_id="implantation",
                section_refs=["a:korotko"],
            ),
        ),
        message="Сравните классическую и одномоментную",
        key=SessionKey(client_id="demo", sid="c1-compare-two"),
    )
    two_text = two.response.rendered_text
    two_ui = two.response.ui_projection
    assert CLASSIC_FACT in two_text
    assert ONE_STAGE_FACT in two_text
    assert COMPARISON_READY not in two_text
    assert "рекомендую" not in two_text.lower()
    assert two_ui.quick_replies == ()
    assert two_ui.video is None
    assert two.response.resolved.d2_result_status == "complete"

    missing, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                request_id="r1",
                content_ref="implantation__service__classic.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
            ),
            _content_part(
                request_id="r2",
                content_ref=None,
                service_id="one_stage",
                topic_id="implantation",
            ),
        ),
        message="Сравните классическую и отсутствующий метод",
        key=SessionKey(client_id="demo", sid="c1-compare-gap"),
    )
    missing_text = missing.response.rendered_text
    assert CLASSIC_FACT in missing_text
    assert ONE_STAGE_FACT not in missing_text
    assert COMPARISON_READY not in missing_text
    assert GAP in missing_text
    assert missing.response.ui_projection.quick_replies == ()
    assert missing.response.resolved.d2_request_parts[1].status == "unavailable"
    assert missing.response.resolved.d2_request_parts[1].failure_reason == "d2_content_source_missing"
    assert missing.response.resolved.d2_result_status == "degraded"


def test_b04_two_independent_information_questions_keep_both_answers_without_source_ui(tmp_path: Path) -> None:
    outcome, saved, provider, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                request_id="r1",
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=PAIN_LIVE,
                fallback="a:korotko",
            ),
            _content_part(
                request_id="r2",
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=WARRANTY_LIVE,
                fallback="a:korotko",
            ),
        ),
        message="Больно ли ставить имплант и какая у вас гарантия?",
        key=SessionKey(client_id="demo", sid="c1-two-info"),
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert text.index(PAIN_LIVE) < text.index(WARRANTY_LIVE)
    assert [part.status for part in outcome.response.resolved.d2_request_parts] == ["answered", "answered"]
    assert outcome.response.resolved.d2_result_status == "complete"
    assert ui.video is None and ui.quick_replies == ()
    assert saved is not None and len(provider.inputs) == 1


def test_b04_two_independent_questions_same_topic_distinct_services_have_no_source_ui(tmp_path: Path) -> None:
    outcome, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                request_id="r1",
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:korotko"],
                realization="model_prose",
                text=PAIN_LIVE,
                fallback="a:korotko",
            ),
            _content_part(
                request_id="r2",
                content_ref="implantation__service__one_stage.md",
                service_id="one_stage",
                topic_id="implantation",
                section_refs=["a:korotko"],
            ),
        ),
        message="Больно ли при классической имплантации и как проходит одномоментная?",
        key=SessionKey(client_id="demo", sid="c1-two-info-same-topic"),
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert PAIN_LIVE in text and ONE_STAGE_FACT in text
    assert [part.status for part in outcome.response.resolved.d2_request_parts] == ["answered", "answered"]
    assert ui.video is None and ui.quick_replies == ()


def test_b15_section_without_korotko_and_irrelevant_fallback(tmp_path: Path) -> None:
    clients = _clients(tmp_path)
    (clients / "demo" / "md" / "implantation__info__hygiene.md").write_text(
        "---\n"
        "doc_id: implantation__info__hygiene\n"
        "doc_type: info\n"
        "topic: implantation\n"
        "subtopic: hygiene\n"
        "cta_key: consult\n"
        "cta_action: lead\n"
        "---\n"
        "## Гигиена после имплантации\n"
        "### Как ухаживать {#kak-uhazhivat}\n"
        "Чистить зону импланта мягкой щёткой и ирригатором по рекомендации врача.\n",
        encoding="utf-8",
        newline="\n",
    )

    section, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:sedatsiya-i-narkoz"],
            )
        ),
        message="Нужен ли наркоз при имплантации?",
        key=SessionKey(client_id="demo", sid="c1-b15-section"),
        clients=clients,
    )
    assert PAIN_SEDATION in section.response.rendered_text
    assert PAIN_KOROTKO not in section.response.rendered_text
    assert section.response.resolved.d2_request_parts[0].content_section_refs == (
        "a:sedatsiya-i-narkoz",
    )
    assert section.response.resolved.ui_plan.source_content_ref == "implantation__faq__pain.md"
    assert section.response.ui_projection.video is not None

    no_korotko, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__info__hygiene.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:kak-uhazhivat"],
            )
        ),
        message="Как ухаживать после имплантации?",
        key=SessionKey(client_id="demo", sid="c1-b15-no-korotko"),
        clients=clients,
    )
    assert "ирригатором" in no_korotko.response.rendered_text
    assert "Коротко" not in no_korotko.response.rendered_text
    assert no_korotko.response.resolved.d2_result_status == "complete"

    recovered, _, _, _, _ = _run(
        tmp_path,
        _raw(
            _content_part(
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                section_refs=["a:sedatsiya-i-narkoz", "a:korotko"],
                realization="model_prose",
                text="Наркоз стоит 5 000 ₽ и это общий абзац.",
                fallback="a:korotko",
            )
        ),
        message="Нужен ли наркоз?",
        key=SessionKey(client_id="demo", sid="c1-b15-fallback"),
        clients=clients,
    )
    recovered_text = recovered.response.rendered_text
    assert "Наркоз стоит 5 000 ₽ и это общий абзац." in recovered_text
    assert PAIN_SEDATION not in recovered_text
    assert PAIN_KOROTKO not in recovered_text
    assert recovered.response.resolved.d2_request_parts[0].status == "answered"
    assert recovered.response.resolved.information_blocks[0].source_section_refs == (
        "a:sedatsiya-i-narkoz",
        "a:korotko",
    )
