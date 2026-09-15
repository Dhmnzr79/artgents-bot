"""Frozen contract for P0 Phase 2B Qwen 3.8 Flash streaming opportunity measurement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MEASUREMENT_ID = "p0_phase2b_qwen38_flash_streaming"
MAX_LIVE_PROVIDER_CALLS = 60

CONTROL_MODEL_ID = "qwen3.7-plus-2026-05-26"
CANDIDATE_MODEL_ID = "qwen3.8-flash"

REQUIRED_BASELINE_COMMIT = "9157150d706a454a07924b9ea84159f1ac0742e5"

CaseCategory = Literal[
    "faq_safe",
    "service",
    "price",
    "payment",
    "contacts",
    "doctor",
    "ambiguous",
    "admin_like",
    "follow_up",
    "pain",
    "nika",
]


@dataclass(frozen=True, slots=True)
class Phase2BCase:
    case_id: str
    client_id: str
    user_message: str
    category: CaseCategory
    repeat_eligible: bool
    session_prefix: tuple[tuple[str, str], ...] = ()
    critical_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    expected_route: str | None = None


FROZEN_PHASE2B_CASES: tuple[Phase2BCase, ...] = (
    Phase2BCase(
        case_id="d01_parking",
        client_id="demo",
        user_message="Есть ли у клиники парковка для пациентов?",
        category="faq_safe",
        repeat_eligible=True,
        critical_terms=("парков",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d02_implant_service",
        client_id="demo",
        user_message="Расскажите про имплантацию зубов",
        category="service",
        repeat_eligible=True,
        critical_terms=("имплант",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d03_implant_price",
        client_id="demo",
        user_message="Сколько стоит классическая имплантация Implantium на один зуб?",
        category="price",
        repeat_eligible=True,
        critical_terms=("76",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d04_payment",
        client_id="demo",
        user_message="Можно ли оплатить имплантацию в рассрочку?",
        category="payment",
        repeat_eligible=True,
        critical_terms=("рассроч",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d05_contacts",
        client_id="demo",
        user_message="Как до вас добраться и какой телефон клиники?",
        category="contacts",
        repeat_eligible=True,
        critical_terms=("телефон",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d06_doctors",
        client_id="demo",
        user_message="Кто у вас делает имплантацию и какой у врачей опыт?",
        category="doctor",
        repeat_eligible=True,
        critical_terms=("врач",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d07_ambiguous",
        client_id="demo",
        user_message="Хочу полечить зуб, не понимаю с чего начать",
        category="ambiguous",
        repeat_eligible=False,
        expected_route="CLARIFY",
    ),
    Phase2BCase(
        case_id="d08_admin_like",
        client_id="demo",
        user_message="Вы мошенники, верните деньги за лечение немедленно!",
        category="admin_like",
        repeat_eligible=False,
        expected_route="ADMIN",
    ),
    Phase2BCase(
        case_id="d09_follow_up",
        client_id="demo",
        user_message="А сколько это займёт по времени?",
        category="follow_up",
        repeat_eligible=False,
        session_prefix=(("Сколько стоит классическая имплантация Implantium на один зуб?", "demo"),),
        critical_terms=("имплант",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="d10_pain",
        client_id="demo",
        user_message="Боюсь, что имплантация будет очень больной",
        category="pain",
        repeat_eligible=True,
        critical_terms=("без боли", "анестез"),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="n01_allon4_price",
        client_id="nikadent",
        user_message="Сколько стоит All-on-4 на одну челюсть?",
        category="nika",
        repeat_eligible=False,
        critical_terms=("318",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="n02_aprf",
        client_id="nikadent",
        user_message="Используете ли вы технологию APRF?",
        category="nika",
        repeat_eligible=False,
        critical_terms=("APRF",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="n03_doctors",
        client_id="nikadent",
        user_message="Кто у вас делает имплантацию?",
        category="nika",
        repeat_eligible=False,
        critical_terms=("врач",),
        expected_route="ANSWER",
    ),
    Phase2BCase(
        case_id="n04_installment",
        client_id="nikadent",
        user_message="Есть ли рассрочка на лечение?",
        category="nika",
        repeat_eligible=False,
        critical_terms=("рассроч",),
        expected_route="ANSWER",
    ),
)


def build_call_plan(
    *,
    include_canary: bool = True,
    repeat_pass: bool = True,
) -> list[tuple[str, str, str, int]]:
    """Return rows of (model_id, case_id, client_id, attempt_index)."""

    rows: list[tuple[str, str, str, int]] = []
    if include_canary:
        rows.append((CONTROL_MODEL_ID, "canary_control", "demo", 0))
        rows.append((CANDIDATE_MODEL_ID, "canary_candidate", "demo", 0))
    for case in FROZEN_PHASE2B_CASES:
        for model in (CONTROL_MODEL_ID, CANDIDATE_MODEL_ID):
            rows.append((model, case.case_id, case.client_id, 1))
            if repeat_pass and case.repeat_eligible:
                rows.append((model, case.case_id, case.client_id, 2))
    return rows


def assert_call_plan_within_budget(plan: list[tuple[str, str, str, int]]) -> None:
    if len(plan) > MAX_LIVE_PROVIDER_CALLS:
        raise RuntimeError(
            f"phase2b_call_plan_exceeds_budget:{len(plan)}>{MAX_LIVE_PROVIDER_CALLS}"
        )
