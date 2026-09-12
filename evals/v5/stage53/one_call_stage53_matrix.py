"""Load frozen Stage 5.3 multiclient matrix and SHA governance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.v5.stage53.one_call_stage53_contract import (
    EXPECTED_CASE_COUNT,
    EXPECTED_CASE_IDS,
    EXPECTED_DEMO_CASE_COUNT,
    EXPECTED_HTTP_TURN_COUNT,
    EXPECTED_MULTI_TURN_SESSION_COUNT,
    EXPECTED_NIKADENT_CASE_COUNT,
    EXPECTED_ONE_CALL_SINGLE_TURN_COUNT,
    EXPECTED_SINGLE_TURN_CASE_COUNT,
    EXPECTED_TOTAL_FAKE_PROVIDER_CALLS,
    EXPECTED_ZERO_CALL_SINGLE_TURN_COUNT,
    FROZEN_MATRIX_SHA256,
    MATRIX_JSON_REL_PATH,
    MATRIX_SCHEMA,
    NIKADENT_ACCOUNTING_CASE_IDS,
)


def account_client_for_case(case_id: str, client_id: str) -> str:
    if case_id in NIKADENT_ACCOUNTING_CASE_IDS:
        return "nikadent"
    return client_id

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MATRIX_PATH = _REPO_ROOT / MATRIX_JSON_REL_PATH.replace("/", "\\").replace("\\", "/")


@dataclass(frozen=True, slots=True)
class Stage53TurnSpec:
    user_message: str
    provider_calls: int
    sid: str | None = None
    client_id: str | None = None
    fake_envelope: dict[str, object] | None = None
    required_all: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    forbidden: tuple[str, ...] = ()
    forbidden_price_tokens: tuple[str, ...] = ()
    route: str | None = None
    service_route_contains: str | None = None
    diagnostic: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class Stage53CaseSpec:
    case_id: str
    client_id: str
    turns: tuple[Stage53TurnSpec, ...]
    session_sid: str | None = None


def matrix_json_path() -> Path:
    return _MATRIX_PATH


def load_matrix_document() -> dict[str, Any]:
    raw = matrix_json_path().read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise RuntimeError("stage53_matrix_not_object")
    return doc


def frozen_matrix_sha256() -> str:
    return hashlib.sha256(matrix_json_path().read_bytes()).hexdigest()


def assert_frozen_matrix_unchanged() -> None:
    doc = load_matrix_document()
    if doc.get("schema") != MATRIX_SCHEMA:
        raise RuntimeError(f"schema mismatch expected={MATRIX_SCHEMA} actual={doc.get('schema')}")
    cases = doc.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("stage53_matrix_cases_missing")
    case_ids = [str(row.get("case_id")) for row in cases]
    if tuple(case_ids) != EXPECTED_CASE_IDS:
        raise RuntimeError(
            f"case_id mismatch expected={EXPECTED_CASE_IDS} actual={tuple(case_ids)}"
        )
    if len(cases) != EXPECTED_CASE_COUNT:
        raise RuntimeError(
            f"case count mismatch expected={EXPECTED_CASE_COUNT} actual={len(cases)}"
        )
    if FROZEN_MATRIX_SHA256:
        actual = frozen_matrix_sha256()
        if actual != FROZEN_MATRIX_SHA256:
            raise RuntimeError(
                f"matrix sha mismatch expected={FROZEN_MATRIX_SHA256} actual={actual}"
            )


def assert_matrix_arithmetic(doc: dict[str, Any] | None = None) -> None:
    payload = doc if doc is not None else load_matrix_document()
    cases = payload["cases"]
    demo = sum(
        1
        for row in cases
        if account_client_for_case(str(row["case_id"]), str(row["client_id"])) == "demo"
    )
    nika = sum(
        1
        for row in cases
        if account_client_for_case(str(row["case_id"]), str(row["client_id"])) == "nikadent"
    )
    if demo != EXPECTED_DEMO_CASE_COUNT or nika != EXPECTED_NIKADENT_CASE_COUNT:
        raise RuntimeError(
            f"client split mismatch demo={demo} nika={nika}"
        )
    multi = sum(1 for row in cases if len(row["turns"]) > 1)
    single = len(cases) - multi
    if single != EXPECTED_SINGLE_TURN_CASE_COUNT or multi != EXPECTED_MULTI_TURN_SESSION_COUNT:
        raise RuntimeError(
            f"session shape mismatch single={single} multi={multi}"
        )
    turn_count = sum(len(row["turns"]) for row in cases)
    if turn_count != EXPECTED_HTTP_TURN_COUNT:
        raise RuntimeError(f"turn count mismatch expected={EXPECTED_HTTP_TURN_COUNT} actual={turn_count}")
    zero_single = sum(
        1
        for row in cases
        if len(row["turns"]) == 1 and int(row["turns"][0]["provider_calls"]) == 0
    )
    one_single = sum(
        1
        for row in cases
        if len(row["turns"]) == 1 and int(row["turns"][0]["provider_calls"]) == 1
    )
    if zero_single != EXPECTED_ZERO_CALL_SINGLE_TURN_COUNT:
        raise RuntimeError(f"zero-call single mismatch {zero_single}")
    if one_single != EXPECTED_ONE_CALL_SINGLE_TURN_COUNT:
        raise RuntimeError(f"one-call single mismatch {one_single}")
    total_calls = sum(int(turn["provider_calls"]) for row in cases for turn in row["turns"])
    if total_calls != EXPECTED_TOTAL_FAKE_PROVIDER_CALLS:
        raise RuntimeError(
            f"provider total mismatch expected={EXPECTED_TOTAL_FAKE_PROVIDER_CALLS} actual={total_calls}"
        )


def parse_case_specs() -> tuple[Stage53CaseSpec, ...]:
    doc = load_matrix_document()
    specs: list[Stage53CaseSpec] = []
    for row in doc["cases"]:
        turns = tuple(
            Stage53TurnSpec(
                user_message=str(turn["user_message"]),
                provider_calls=int(turn["provider_calls"]),
                sid=str(turn["sid"]) if turn.get("sid") else None,
                client_id=str(turn["client_id"]) if turn.get("client_id") else None,
                fake_envelope=(
                    dict(turn["fake_envelope"])
                    if isinstance(turn.get("fake_envelope"), dict)
                    else None
                ),
                required_all=tuple(str(x) for x in turn.get("required_all") or ()),
                required_any=tuple(
                    tuple(str(y) for y in group)
                    for group in (turn.get("required_any") or ())
                ),
                forbidden=tuple(str(x) for x in turn.get("forbidden") or ()),
                forbidden_price_tokens=tuple(
                    str(x) for x in turn.get("forbidden_price_tokens") or ()
                ),
                route=str(turn["route"]) if turn.get("route") else None,
                service_route_contains=(
                    str(turn["service_route_contains"])
                    if turn.get("service_route_contains")
                    else None
                ),
                diagnostic=(
                    dict(turn["diagnostic"])
                    if isinstance(turn.get("diagnostic"), dict)
                    else None
                ),
            )
            for turn in row["turns"]
        )
        specs.append(
            Stage53CaseSpec(
                case_id=str(row["case_id"]),
                client_id=str(row["client_id"]),
                turns=turns,
                session_sid=str(row["session_sid"]) if row.get("session_sid") else None,
            )
        )
    return tuple(specs)


def case_by_id(case_id: str) -> Stage53CaseSpec:
    for case in parse_case_specs():
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def _envelope(
    patient_text: str,
    *,
    route: str = "ANSWER",
    service_id: str | None = None,
    commercial_intent: str = "none",
    promotion_scope: str = "none",
    scenario: str = "none",
    service_reference_status: str | None = None,
    requested_service_id: str | None = None,
    extent: str | None = None,
    jaw: str | None = None,
    clarify_axis: str | None = None,
    clarify_service_options: list[str] | None = None,
) -> dict[str, object]:
    envelope: dict[str, object] = {
        "route": route,
        "patient_text": patient_text,
        "commercial_intent": commercial_intent,
        "promotion_scope": promotion_scope,
        "scenario": scenario,
        "service_id": service_id,
        "extent": extent,
        "jaw": jaw,
        "stage": None,
        "clarify_axis": clarify_axis,
        "clarify_service_options": clarify_service_options,
        "service_reference_status": service_reference_status or (
            "resolved" if service_id is not None else "none"
        ),
        "requested_service_id": requested_service_id or service_id,
    }
    return envelope


def _kno_envelope(
    patient_text: str,
    requested_service_id: str,
    *,
    commercial_intent: str = "none",
) -> dict[str, object]:
    return _envelope(
        patient_text,
        service_id=None,
        requested_service_id=requested_service_id,
        service_reference_status="resolved",
        commercial_intent=commercial_intent,
    )


def _turn(
    user_message: str,
    provider_calls: int,
    *,
    sid: str | None = None,
    client_id: str | None = None,
    fake_envelope: dict[str, object] | None = None,
    required_all: tuple[str, ...] = (),
    required_any: tuple[tuple[str, ...], ...] = (),
    forbidden: tuple[str, ...] = (),
    forbidden_price_tokens: tuple[str, ...] = (),
    route: str | None = None,
    service_route_contains: str | None = None,
    diagnostic: dict[str, object] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "user_message": user_message,
        "provider_calls": provider_calls,
        "fake_envelope": fake_envelope,
        "required_all": list(required_all),
        "required_any": [list(group) for group in required_any],
        "forbidden": list(forbidden),
        "forbidden_price_tokens": list(forbidden_price_tokens),
    }
    if sid is not None:
        row["sid"] = sid
    if client_id is not None:
        row["client_id"] = client_id
    if route is not None:
        row["route"] = route
    if service_route_contains is not None:
        row["service_route_contains"] = service_route_contains
    if diagnostic is not None:
        row["diagnostic"] = diagnostic
    return row


def _case(
    case_id: str,
    client_id: str,
    turns: list[dict[str, object]],
    *,
    session_sid: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "case_id": case_id,
        "client_id": client_id,
        "turns": turns,
    }
    if session_sid is not None:
        row["session_sid"] = session_sid
    return row


def build_matrix_document() -> dict[str, object]:
  """Return the full frozen Stage 5.3 multiclient matrix document."""

  demo_promo_15 = "При оплате в день обращения — скидка до 15% на имплантацию."
  demo_allon4_price_text = (
      "Стоимость All-on-4 на Implantium — 318 000 ₽ за одну челюсть."
  )
  nika_allon4_family_text = "Короткий ответ о стоимости All-on-4."
  pediatric_demo = (
      "Мы работаем только со взрослыми пациентами — детскую стоматологию в клинике не ведём."
  )
  pediatric_nika = (
      "Мы работаем только со взрослыми пациентами — детскую стоматологию в клинике не ведём."
  )
  osse_demo_text = "Наш результат — 99,8% приживаемости за 26 лет работы."
  osse_nika_text = "Наш результат — 99,8% приживаемости за 16 лет работы."
  aprf_demo_text = (
      "В клинике используется технология APRF (биоматериал из собственной крови): "
      "ускоряет заживление и поддерживает восстановление тканей."
  )
  nika_no_aprf_text = (
      "В материалах клиники Никадент нет информации об использовании APRF."
  )
  bone_graft_npp = (
      "Стоимость костной пластики рассчитывается после КТ и зависит от необходимого объёма."
  )
  braces_kno_text = (
      "Брекеты мы не устанавливаем. Для выравнивания зубов в клинике используются элайнеры."
  )
  aligners_price_text = "Элайнеры — от 195 000 ₽ за полный курс лечения."
  unresolved_text = (
      "Не вижу такой услуги в перечне клиники. Возможно, она называется иначе — уточните название."
  )
  nika_kno_aligners = (
      "К сожалению, услугу «Элайнеры» в нашей клинике не оказываем."
  )
  nika_kno_sedation = "К сожалению, услугу «Седация» в нашей клинике не оказываем."
  nika_kno_kt = "К сожалению, услугу «Компьютерная томография» в нашей клинике не оказываем."
  crown_family_text = "Короткий ответ о стоимости коронки."
  bridge_exact_text = "Мостовидный протез — от 10 000 ₽ за единицу."
  inlay_exact_text = "Культевая вкладка — от 7 000 ₽ за зуб."
  sinus_exact_text = "Синус-лифтинг — от 25 000 ₽ за процедуру."
  tax_text = "Можно оформить налоговый вычет 13% от оплаченного лечения."
  neutral_allon4 = "All-on-4 — протокол имплантации и протезирования на четырех имплантах."
  demo_doctors_text = "Имплантацию выполняют врачи Орлов и Волков."
  nika_doctors_text = "В клинике работают врачи Кадиев и Лавренов."
  nika_no_orlov = "В материалах клиники Никадент нет информации о враче Орлове."
  demo_promo_overview = "Расскажу об актуальных акциях клиники."
  nika_promo_overview = "Расскажу об актуальных акциях клиники."
  nika_free_ortho = (
      "Бесплатная консультация по ортопедии, имплантации и протезированию."
  )
  fear_pain_text = "Имплантация проходит под анестезией, лечение обычно безболезненное."
  fear_osse_demo = (
      "По статистике клиники приживаемость имплантов — 99,8%. "
      "Современные технологии надёжны."
  )
  fear_osse_nika = (
      "По статистике клиники приживаемость имплантов — 99,8%. "
      "Диагностика перед операцией показывает, подходит ли имплантация."
  )
  clinic_demo = "Клиника Artgents — стоматология в Москве."
  clinic_nika = (
      "Стоматологическая клиника Никадент на Камчатке — 16 лет работы, два филиала в Елизово."
  )
  branches_nika = "Два филиала: ул. Рябикова, д. 49 и ул. Пограничная, д. 27."
  diag_common = {
      "overload_manual": True,
      "naturalness_manual": True,
  }

  cases: list[dict[str, object]] = [
      _case(
          "s53_a01_demo_clinic",
          "demo",
          [
              _turn(
                  "Как называется клиника?",
                  1,
                  fake_envelope=_envelope(clinic_demo),
                  required_all=("Artgents",),
                  forbidden=("Никадент", "Рябикова", "Елизово", "+7 (900)"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_a02_nika_clinic",
          "nikadent",
          [
              _turn(
                  "Расскажите о клинике кратко",
                  1,
                  fake_envelope=_envelope(clinic_nika),
                  required_all=("Никадент", "16", "Камчатк"),
                  forbidden=("Artgents", "Тверская", "+7 (495) 128"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_a03_demo_aprf",
          "demo",
          [
              _turn(
                  "Используете APRF?",
                  1,
                  fake_envelope=_envelope(aprf_demo_text),
                  required_all=("APRF",),
                  forbidden=("+7 (900)", "Рябикова"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_a04_nika_branches",
          "nikadent",
          [
              _turn(
                  "Какие филиалы?",
                  1,
                  fake_envelope=_envelope(branches_nika),
                  required_all=("два филиала", "Рябикова", "Пограничная"),
                  forbidden=("Тверская", "Artgents"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_a05_demo_allon4_price",
          "demo",
          [
              _turn(
                  "Сколько стоит All-on-4?",
                  1,
                  fake_envelope=_envelope(
                      demo_allon4_price_text,
                      service_id="all_on_4",
                      commercial_intent="price",
                      extent="full_arch",
                  ),
                  required_all=("318", "челюст"),
                  forbidden=("35 000", "35000", "Никадент", "15%"),
                  forbidden_price_tokens=("35000", "35 000"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_a06_nika_allon4_price",
          "nikadent",
          [
              _turn(
                  "Сколько стоит All-on-4?",
                  1,
                  fake_envelope=_envelope(
                      nika_allon4_family_text,
                      service_id="all_on_4",
                      commercial_intent="price",
                      extent="full_arch",
                  ),
                  required_all=("35", "ориентир"),
                  forbidden=("318 000", "318000", "Implantium", "Artgents"),
                  forbidden_price_tokens=("318000", "318 000"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b01_demo_kno_braces_1alt",
          "demo",
          [
              _turn(
                  "Вы ставите брекеты?",
                  1,
                  fake_envelope=_kno_envelope(braces_kno_text, "braces"),
                  required_all=("брекет", "элайнер"),
                  forbidden=("Никадент",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b02_demo_kno_price_alt",
          "demo",
          [
              _turn(
                  "Сколько стоит установка брекетов?",
                  1,
                  fake_envelope=_kno_envelope(
                      aligners_price_text,
                      "braces",
                      commercial_intent="price",
                  ),
                  required_all=("195", "элайнер"),
                  forbidden=("скидк",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b03_demo_unresolved",
          "demo",
          [
              _turn(
                  "Вы делаете флумбодонтию?",
                  1,
                  fake_envelope=_envelope(unresolved_text),
                  required_any=(("перечн", "называется"),),
                  forbidden=("не оказываем",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b04_demo_npp_price",
          "demo",
          [
              _turn(
                  "Сколько стоит костная пластика?",
                  1,
                  fake_envelope=_envelope(
                      bone_graft_npp,
                      service_id="bone_graft",
                      commercial_intent="price",
                  ),
                  required_all=("КТ",),
                  forbidden=("318 000",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b05_nika_kno_aligners",
          "nikadent",
          [
              _turn(
                  "Делаете элайнеры?",
                  1,
                  fake_envelope=_kno_envelope(nika_kno_aligners, "aligners"),
                  required_all=("не оказывается", "элайнер"),
                  forbidden=("Artgents", "Implantium"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b06_nika_kno_sedation",
          "nikadent",
          [
              _turn(
                  "Можно лечение во сне?",
                  1,
                  fake_envelope=_kno_envelope(nika_kno_sedation, "sedation"),
                  required_all=("не оказывается", "седац"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b07_nika_kno_kt",
          "nikadent",
          [
              _turn(
                  "Можно сделать КТ у вас?",
                  1,
                  fake_envelope=_kno_envelope(nika_kno_kt, "tomography"),
                  required_all=("не оказывается", "КТ"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b08_demo_pediatric_policy",
          "demo",
          [
              _turn(
                  "Принимаете детей?",
                  1,
                  fake_envelope=_envelope(pediatric_demo),
                  required_all=("взросл", "детск"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_b09_nika_pediatric_policy",
          "nikadent",
          [
              _turn(
                  "Принимаете детей?",
                  1,
                  fake_envelope=_envelope(pediatric_nika),
                  required_all=("взросл", "детск"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c01_nika_crown_family",
          "nikadent",
          [
              _turn(
                  "Сколько стоит циркониевая коронка?",
                  1,
                  fake_envelope=_envelope(
                      crown_family_text,
                      service_id="zirconia_crowns",
                      commercial_intent="price",
                  ),
                  required_all=("22", "ориентир"),
                  forbidden=("10 000",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c02_nika_bridge_exact",
          "nikadent",
          [
              _turn(
                  "Сколько стоит мост?",
                  1,
                  fake_envelope=_envelope(
                      bridge_exact_text,
                      service_id="fixed_bridge",
                      commercial_intent="price",
                  ),
                  required_all=("10", "единиц"),
                  forbidden=("22 000",),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c03_nika_inlay_exact",
          "nikadent",
          [
              _turn(
                  "Сколько стоит культевая вкладка?",
                  1,
                  fake_envelope=_envelope(
                      inlay_exact_text,
                      service_id="core_inlay",
                      commercial_intent="price",
                  ),
                  required_all=("7", "зуб"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c04_nika_sinus_not_implant_family",
          "nikadent",
          [
              _turn(
                  "Сколько синус-лифтинг?",
                  1,
                  fake_envelope=_envelope(
                      sinus_exact_text,
                      service_id="sinus_lift",
                      commercial_intent="price",
                  ),
                  required_all=("25",),
                  forbidden_price_tokens=("35000", "35 000"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c05_nika_tax_deduction",
          "nikadent",
          [
              _turn(
                  "Можно ли получить налоговый вычет за лечение?",
                  1,
                  fake_envelope=_envelope(
                      tax_text,
                      commercial_intent="none",
                  ),
                  required_all=("13", "налогов"),
                  forbidden=("рассроч", "скидк"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_c06_nika_neutral_info",
          "nikadent",
          [
              _turn(
                  "Что такое All-on-4?",
                  1,
                  fake_envelope=_envelope(
                      neutral_allon4,
                      service_id="all_on_4",
                  ),
                  forbidden=("₽", "000"),
                  forbidden_price_tokens=("35000", "318000"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_d01_demo_osse",
          "demo",
          [
              _turn(
                  "Какая приживаемость?",
                  1,
                  fake_envelope=_envelope(osse_demo_text),
                  required_all=("99,8", "26"),
                  forbidden=("16 лет",),
                  diagnostic=diag_common,
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_d02_nika_osse",
          "nikadent",
          [
              _turn(
                  "Какая приживаемость?",
                  1,
                  fake_envelope=_envelope(osse_nika_text),
                  required_all=("99,8", "16"),
                  forbidden=("26 лет", "APRF использ"),
                  diagnostic=diag_common,
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_d03_demo_parking",
          "demo",
          [
              _turn(
                  "Есть парковка?",
                  0,
                  fake_envelope=None,
                  required_all=("парков", "2", "бесплат"),
                  forbidden=("+7 (900)",),
                  service_route_contains="sales_fast_contacts",
              ),
          ],
      ),
      _case(
          "s53_d04_nika_no_aprf",
          "nikadent",
          [
              _turn(
                  "Используете APRF?",
                  1,
                  fake_envelope=_envelope(nika_no_aprf_text),
                  forbidden=(
                      "APRF использ",
                      "биоматериал из собственной крови",
                      "ускоряет заживление",
                  ),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_d05_nika_no_demo_parking",
          "nikadent",
          [
              _turn(
                  "Есть парковка?",
                  0,
                  fake_envelope=None,
                  forbidden=("2 часа бесплатно", "пропуск на ресепшене", "Тверская"),
                  service_route_contains="sales_fast_admin",
              ),
          ],
      ),
      _case(
          "s53_e01_demo_doctors",
          "demo",
          [
              _turn(
                  "Кто у вас делает имплантацию?",
                  1,
                  fake_envelope=_envelope(demo_doctors_text, service_id="classic"),
                  required_all=("Орлов", "Волков"),
                  forbidden=("Кадиев", "Лавренов"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_e02_nika_doctors",
          "nikadent",
          [
              _turn(
                  "Кто у вас делает имплантацию?",
                  1,
                  fake_envelope=_envelope(nika_doctors_text, service_id="classic"),
                  required_all=("Кадиев", "Лавренов"),
                  forbidden=("Орлов", "Волков"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_e03_nika_no_demo_doctor",
          "nikadent",
          [
              _turn(
                  "Кто такой Орлов?",
                  1,
                  fake_envelope=_envelope(nika_no_orlov),
                  forbidden=("Орлов Никита", "имплантолог"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_f01_demo_promo_overview",
          "demo",
          [
              _turn(
                  "Какие акции у вас есть?",
                  1,
                  fake_envelope=_envelope(
                      "В клинике действуют сезонные акции и спецпредложения.",
                      commercial_intent="promotion",
                      promotion_scope="general",
                      service_id=None,
                  ),
                  required_all=("скидк", "консультац"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_f02_nika_promo_overview",
          "nikadent",
          [
              _turn(
                  "Какие акции у вас есть?",
                  1,
                  fake_envelope=_envelope(
                      nika_promo_overview,
                      commercial_intent="promotion",
                      promotion_scope="general",
                  ),
                  required_all=("бесплатн", "консультац"),
                  forbidden=("гарантия 1 год", "work_warranty"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_f03_nika_service_promo_none",
          "nikadent",
          [
              _turn(
                  "Расскажите про All-on-4",
                  1,
                  fake_envelope=_envelope(
                      nika_free_ortho,
                      service_id="all_on_4",
                      scenario="none",
                  ),
                  required_all=("бесплатн", "консультац"),
                  forbidden=("скидк", "15%", "implant_same_day"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_f04_mt_promo_cadence",
          "demo",
          [
              _turn(
                  "Расскажите про All-on-4",
                  1,
                  fake_envelope=_envelope(
                      neutral_allon4,
                      service_id="all_on_4",
                      scenario="none",
                  ),
                  required_all=("четыр", "имплант"),
                  service_route_contains="sales_fast_materialized",
              ),
              _turn(
                  "Расскажите про All-on-6",
                  1,
                  fake_envelope=_envelope(
                      "All-on-6 — протокол на шести имплантах.",
                      service_id="all_on_6",
                  ),
                  forbidden=("15%", "скидк"),
                  service_route_contains="sales_fast_materialized",
              ),
              _turn(
                  "Повторите акцию, которую только что показывали",
                  1,
                  fake_envelope=_envelope(
                      demo_promo_15,
                      commercial_intent="promotion",
                      promotion_scope="shown",
                      service_id="all_on_4",
                  ),
                  required_all=("15%", "скидк"),
                  service_route_contains="sales_fast_materialized",
              ),
          ],
          session_sid="s53_f04_mt_promo_cadence",
      ),
      _case(
          "s53_g01_demo_contacts",
          "demo",
          [
              _turn(
                  "Контакты",
                  0,
                  fake_envelope=None,
                  required_all=("+7 (495) 128", "Тверская"),
                  forbidden=("Рябикова", "Никадент"),
                  service_route_contains="sales_fast_contacts",
              ),
          ],
      ),
      _case(
          "s53_g02_nika_contacts",
          "nikadent",
          [
              _turn(
                  "Контакты",
                  0,
                  fake_envelope=None,
                  required_all=("Рябикова", "Пограничная"),
                  forbidden=("Тверская", "Artgents"),
                  service_route_contains="sales_fast_contacts",
              ),
          ],
      ),
      _case(
          "s53_g03_nika_branch_ryabikova",
          "nikadent",
          [
              _turn(
                  "Адрес на Рябикова",
                  0,
                  fake_envelope=None,
                  required_all=("Рябикова", "49"),
                  forbidden=("Пограничная", "Тверская"),
                  service_route_contains="sales_fast_contacts",
              ),
          ],
      ),
      _case(
          "s53_g04_nika_branch_pogranichnaya",
          "nikadent",
          [
              _turn(
                  "Телефон филиала на Пограничной",
                  0,
                  fake_envelope=None,
                  required_all=("+7 (914) 995-78-82",),
                  forbidden=("Рябикова", "495"),
                  service_route_contains="sales_fast_contacts",
              ),
          ],
      ),
      _case(
          "s53_g05_nika_urgent_admin_branch",
          "nikadent",
          [
              _turn(
                  "Срочно, филиал Пограничная, после операции воспаление",
                  0,
                  fake_envelope=None,
                  route="ADMIN",
                  required_any=(("+7 (900)", "+7 (984)", "позвоните"),),
                  forbidden=("Рябикова", "495"),
                  service_route_contains="sales_fast_admin",
              ),
          ],
      ),
      _case(
          "s53_g06_demo_urgent_admin",
          "demo",
          [
              _turn(
                  "После операции появилось воспаление, что делать?",
                  0,
                  fake_envelope=None,
                  route="ADMIN",
                  required_all=("+7 (495)",),
                  forbidden=("Рябикова",),
                  service_route_contains="sales_fast_admin",
              ),
          ],
      ),
      _case(
          "s53_g07_mt_booking",
          "demo",
          [
              _turn(
                  "Хочу записаться",
                  0,
                  fake_envelope=None,
                  required_any=(("запис", "администратор", "контакт"),),
                  forbidden=("15:00", "пятниц"),
                  service_route_contains="lead_flow",
              ),
              _turn(
                  "Можно в пятницу в 15:00?",
                  0,
                  fake_envelope=None,
                  required_any=(("администратор", "контакт", "уточн"),),
                  forbidden=("15:00", "15.00", "пятницу в"),
                  service_route_contains="lead_booking_date_defer",
              ),
          ],
          session_sid="s53_g07_mt_booking",
      ),
      _case(
          "s53_h01_demo_admin_symptom",
          "demo",
          [
              _turn(
                  "После операции появилось воспаление, подскажите порядок действий",
                  0,
                  fake_envelope=None,
                  route="ADMIN",
                  service_route_contains="sales_fast_admin",
              ),
          ],
      ),
      _case(
          "s53_h02_demo_fear_pain",
          "demo",
          [
              _turn(
                  "Боюсь боли при имплантации",
                  1,
                  fake_envelope=_envelope(
                      fear_pain_text,
                      service_id="classic",
                      scenario="pain_fear",
                  ),
                  required_any=(("боль", "анестез"),),
                  route="ANSWER",
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_h03_nika_admin_symptom",
          "nikadent",
          [
              _turn(
                  "Болит зуб после имплантации",
                  0,
                  fake_envelope=None,
                  route="ADMIN",
                  service_route_contains="sales_fast_admin",
              ),
          ],
      ),
      _case(
          "s53_h04_nika_fear_osse",
          "nikadent",
          [
              _turn(
                  "Боюсь, что имплант не приживётся",
                  1,
                  fake_envelope=_envelope(
                      fear_osse_nika,
                      service_id="classic",
                  ),
                  required_all=("99",),
                  route="ANSWER",
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_h05_demo_fear_osse",
          "demo",
          [
              _turn(
                  "Боюсь, что имплант не приживётся",
                  1,
                  fake_envelope=_envelope(
                      fear_osse_demo,
                      service_id="classic",
                      scenario="result_reliability",
                  ),
                  required_all=("99,8",),
                  route="ANSWER",
                  diagnostic=diag_common,
                  service_route_contains="sales_fast_materialized",
              ),
          ],
      ),
      _case(
          "s53_j01_mt_cache_isolation",
          "demo",
          [
              _turn(
                  "Сколько стоит All-on-4?",
                  1,
                  sid="sid_stage53_demo",
                  fake_envelope=_envelope(
                      demo_allon4_price_text,
                      service_id="all_on_4",
                      commercial_intent="price",
                  ),
                  required_all=("318",),
                  forbidden_price_tokens=("35000", "35 000"),
              ),
              _turn(
                  "Сколько стоит All-on-4?",
                  1,
                  sid="sid_stage53_nika",
                  client_id="nikadent",
                  fake_envelope=_envelope(
                      nika_allon4_family_text,
                      service_id="all_on_4",
                      commercial_intent="price",
                      extent="full_arch",
                  ),
                  required_all=("35",),
                  forbidden_price_tokens=("318000", "318 000"),
              ),
              _turn(
                  "Сколько стоит All-on-4?",
                  1,
                  sid="sid_stage53_demo",
                  fake_envelope=_envelope(
                      demo_allon4_price_text,
                      service_id="all_on_4",
                      commercial_intent="price",
                  ),
                  required_all=("318",),
                  forbidden_price_tokens=("35000", "35 000"),
              ),
          ],
      ),
  ]

  case_ids = [str(row["case_id"]) for row in cases]
  if tuple(case_ids) != EXPECTED_CASE_IDS:
      raise RuntimeError(
          f"build_matrix_document case_id mismatch expected={EXPECTED_CASE_IDS} actual={tuple(case_ids)}"
      )

  return {
      "schema": MATRIX_SCHEMA,
      "cases": cases,
  }


def write_frozen_matrix_json() -> Path:
    """Write matrix JSON from build_matrix_document() to the frozen path."""

    doc = build_matrix_document()
    path = matrix_json_path()
    path.write_bytes(
        json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    )
    return path
