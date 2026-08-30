"""Frozen architecture comparison matrix (16 demo scenarios / 19 turns)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from evals.v5.arch_compare.arch_compare_contract import (
    EXPECTED_SCENARIO_COUNT,
    EXPECTED_TURN_COUNT,
    FROZEN_MATRIX_DIGEST,
    MATRIX_JSON_REL_PATH,
    MATRIX_SCHEMA,
    matrix_digest_sha256,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MATRIX_PATH = _REPO_ROOT / MATRIX_JSON_REL_PATH.replace("/", "\\").replace("\\", "/")

RouteClass = Literal["ANSWER", "ADMIN", "CLARIFY", "LOCAL"]
EvaluationKind = Literal["model_text", "code_facts", "both"]


@dataclass(frozen=True, slots=True)
class ArchCompareTurnSpec:
    turn_id: str
    user_message: str
    provider_turn: bool
    expected_route_class: RouteClass
    expected_service_id: str | None = None
    expected_brand: str | None = None
    commercial_intent: str = "none"
    promotion_scope: str = "none"
    dialog_history_turn_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArchCompareScenarioSpec:
    scenario_id: str
    relevant_source_refs: tuple[str, ...]
    evaluation_kind: EvaluationKind
    required_exact_facts: tuple[str, ...]
    forbidden_facts: tuple[str, ...]
    turns: tuple[ArchCompareTurnSpec, ...]
    session_reset: bool = True
    notes: str = ""


def matrix_json_path() -> Path:
    return _MATRIX_PATH


def load_matrix_document() -> dict[str, Any]:
    raw = matrix_json_path().read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise RuntimeError("arch_compare_matrix_not_object")
    return doc


def frozen_matrix_digest() -> str:
    return matrix_digest_sha256(matrix_json_path().read_bytes())


def assert_frozen_matrix_unchanged() -> None:
    doc = load_matrix_document()
    if doc.get("schema") != MATRIX_SCHEMA:
        raise RuntimeError(f"schema mismatch expected={MATRIX_SCHEMA} actual={doc.get('schema')}")
    scenarios = doc.get("scenarios")
    if not isinstance(scenarios, list):
        raise RuntimeError("arch_compare_scenarios_missing")
    if len(scenarios) != EXPECTED_SCENARIO_COUNT:
        raise RuntimeError(
            f"scenario count mismatch expected={EXPECTED_SCENARIO_COUNT} actual={len(scenarios)}"
        )
    turn_count = sum(len(row["turns"]) for row in scenarios)
    if turn_count != EXPECTED_TURN_COUNT:
        raise RuntimeError(f"turn count mismatch expected={EXPECTED_TURN_COUNT} actual={turn_count}")
    if FROZEN_MATRIX_DIGEST:
        actual = frozen_matrix_digest()
        if actual != FROZEN_MATRIX_DIGEST:
            raise RuntimeError(f"matrix digest mismatch expected={FROZEN_MATRIX_DIGEST} actual={actual}")


def _turn(
    turn_id: str,
    user_message: str,
    *,
    provider_turn: bool,
    expected_route_class: RouteClass,
    expected_service_id: str | None = None,
    expected_brand: str | None = None,
    commercial_intent: str = "none",
    promotion_scope: str = "none",
    dialog_history_turn_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    row: dict[str, object] = {
        "turn_id": turn_id,
        "user_message": user_message,
        "provider_turn": provider_turn,
        "expected_route_class": expected_route_class,
        "commercial_intent": commercial_intent,
        "promotion_scope": promotion_scope,
        "dialog_history_turn_ids": list(dialog_history_turn_ids),
    }
    if expected_service_id is not None:
        row["expected_service_id"] = expected_service_id
    if expected_brand is not None:
        row["expected_brand"] = expected_brand
    return row


def _scenario(
    scenario_id: str,
    *,
    relevant_source_refs: list[str],
    evaluation_kind: EvaluationKind,
    required_exact_facts: list[str],
    forbidden_facts: list[str],
    turns: list[dict[str, object]],
    session_reset: bool = True,
    notes: str = "",
) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "relevant_source_refs": relevant_source_refs,
        "evaluation_kind": evaluation_kind,
        "required_exact_facts": required_exact_facts,
        "forbidden_facts": forbidden_facts,
        "session_reset": session_reset,
        "notes": notes,
        "turns": turns,
    }


def build_matrix_document() -> dict[str, object]:
    scenarios: list[dict[str, object]] = [
        _scenario(
            "SVC-01",
            relevant_source_refs=["prosthetics__service__removable_dentures.md"],
            evaluation_kind="model_text",
            required_exact_facts=[],
            forbidden_facts=[],
            turns=[
                _turn(
                    "SVC-01_t1",
                    "Расскажите про съёмные протезы",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="removable_dentures",
                ),
            ],
        ),
        _scenario(
            "PRC-01",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "implantation__info__implant_systems.md",
                "implantation__faq__cost.md",
            ],
            evaluation_kind="both",
            required_exact_facts=[
                "318000:Implantium:all_on_4",
                "368000:Impro:all_on_4",
                "428000:Nobel Biocare:all_on_4",
                "billing_unit:jaw",
            ],
            forbidden_facts=["35000"],
            turns=[
                _turn(
                    "PRC-01_t1",
                    "Сколько стоит All-on-4?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    commercial_intent="price",
                ),
            ],
        ),
        _scenario(
            "PRC-02",
            relevant_source_refs=[
                "implantation__service__all_on_6.md",
                "implantation__service__all_on_4.md",
                "comparison__all_on_4_vs_all_on_6.md",
            ],
            evaluation_kind="both",
            required_exact_facts=[
                "398000:Implantium:all_on_6",
                "458000:Impro:all_on_6",
                "528000:Nobel Biocare:all_on_6",
                "billing_unit:jaw",
            ],
            forbidden_facts=[],
            turns=[
                _turn(
                    "PRC-02_t1",
                    "Сколько стоит All-on-6?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_6",
                    commercial_intent="price",
                ),
            ],
        ),
        _scenario(
            "BRD-01",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "implantation__info__implant_systems.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["428000:Nobel Biocare:all_on_4"],
            forbidden_facts=["318000", "368000"],
            turns=[
                _turn(
                    "BRD-01_t1",
                    "Сколько стоит All-on-4 на Nobel Biocare?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    expected_brand="Nobel Biocare",
                    commercial_intent="price",
                ),
            ],
        ),
        _scenario(
            "MT-01",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "implantation__info__implant_systems.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["428000:Nobel Biocare:all_on_4"],
            forbidden_facts=[],
            turns=[
                _turn(
                    "MT-01_t1",
                    "Сколько стоит All-on-4?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    commercial_intent="price",
                ),
                _turn(
                    "MT-01_t2",
                    "А Nobel?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    expected_brand="Nobel Biocare",
                    commercial_intent="price",
                    dialog_history_turn_ids=["MT-01_t1"],
                ),
            ],
            session_reset=True,
        ),
        _scenario(
            "PRC-03",
            relevant_source_refs=[
                "implantation__faq__cost.md",
                "implantation__service__classic.md",
                "implantation__info__methods_overview.md",
            ],
            evaluation_kind="model_text",
            required_exact_facts=["no_random_single_offer"],
            forbidden_facts=["318000", "428000"],
            turns=[
                _turn(
                    "PRC-03_t1",
                    "Сколько стоит имплантация?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    commercial_intent="price",
                ),
            ],
        ),
        _scenario(
            "OBJ-01",
            relevant_source_refs=[
                "implantation__faq__cost.md",
                "implantation__faq__pain.md",
                "clinic__info__consultation.md",
            ],
            evaluation_kind="model_text",
            required_exact_facts=[],
            forbidden_facts=["15%", "скидка"],
            turns=[
                _turn(
                    "OBJ-01_t1",
                    "Я боюсь, что имплантация — это дорого",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="classic",
                ),
            ],
        ),
        _scenario(
            "PRM-01",
            relevant_source_refs=[
                "clinic__info__consultation.md",
                "clinic__info__advantages.md",
                "implantation__service__benefits.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["promo_allowed:max_2"],
            forbidden_facts=["выдуманная_акция"],
            turns=[
                _turn(
                    "PRM-01_t1",
                    "Какие у вас акции?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    commercial_intent="promotion",
                    promotion_scope="general",
                ),
            ],
        ),
        _scenario(
            "PAY-01",
            relevant_source_refs=[
                "clinic__info__consultation.md",
                "implantation__faq__cost.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["installment_fact:exact_catalog"],
            forbidden_facts=[],
            turns=[
                _turn(
                    "PAY-01_t1",
                    "Есть ли рассрочка?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                ),
            ],
        ),
        _scenario(
            "DOC-01",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "doctors__doctor__orlov.md",
                "doctors__doctor__volkov.md",
                "doctors__doctor__overview.md",
            ],
            evaluation_kind="model_text",
            required_exact_facts=["Орлов", "Волков"],
            forbidden_facts=["Кадиев"],
            turns=[
                _turn(
                    "DOC-01_t1",
                    "Расскажите про All-on-4",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                ),
                _turn(
                    "DOC-01_t2",
                    "Кто проводит такую имплантацию?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    dialog_history_turn_ids=["DOC-01_t1"],
                ),
            ],
        ),
        _scenario(
            "MED-01",
            relevant_source_refs=[
                "implantation__info__aftercare.md",
                "implantation__faq__pain.md",
            ],
            evaluation_kind="model_text",
            required_exact_facts=[],
            forbidden_facts=["ADMIN"],
            turns=[
                _turn(
                    "MED-01_t1",
                    "Боюсь, что после имплантации будет отёк",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="classic",
                ),
            ],
        ),
        _scenario(
            "ADM-01",
            relevant_source_refs=["clinic__info__contacts.md"],
            evaluation_kind="code_facts",
            required_exact_facts=["admin_stub", "demo_phone"],
            forbidden_facts=["318000", "скидка"],
            turns=[
                _turn(
                    "ADM-01_t1",
                    "После имплантации появился отёк и становится хуже",
                    provider_turn=False,
                    expected_route_class="ADMIN",
                ),
            ],
        ),
        _scenario(
            "BRD-02",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "implantation__info__implant_systems.md",
            ],
            evaluation_kind="model_text",
            required_exact_facts=["no_invented_offer"],
            forbidden_facts=["MegaImplant", "428000"],
            turns=[
                _turn(
                    "BRD-02_t1",
                    "Сколько стоит All-on-4 на MegaImplant X?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                    expected_brand="MegaImplant X",
                    commercial_intent="price",
                ),
            ],
        ),
        _scenario(
            "SW-01",
            relevant_source_refs=[
                "implantation__service__all_on_4.md",
                "orthodontics__service__aligners.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["195000:aligners"],
            forbidden_facts=[],
            turns=[
                _turn(
                    "SW-01_t1",
                    "Расскажите про All-on-4",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="all_on_4",
                ),
                _turn(
                    "SW-01_t2",
                    "А сколько стоят элайнеры?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="aligners",
                    commercial_intent="price",
                    dialog_history_turn_ids=["SW-01_t1"],
                ),
            ],
        ),
        _scenario(
            "CNT-01",
            relevant_source_refs=["clinic__info__contacts.md"],
            evaluation_kind="code_facts",
            required_exact_facts=["+7 (495) 128", "Тверская"],
            forbidden_facts=["Рябикова"],
            turns=[
                _turn(
                    "CNT-01_t1",
                    "Как с вами связаться?",
                    provider_turn=False,
                    expected_route_class="LOCAL",
                ),
            ],
        ),
        _scenario(
            "NPP-01",
            relevant_source_refs=[
                "implantation__service__bone_graft.md",
                "diagnostics__service__tomography.md",
            ],
            evaluation_kind="both",
            required_exact_facts=["no_fixed_price_without_diagnostics"],
            forbidden_facts=["318000"],
            turns=[
                _turn(
                    "NPP-01_t1",
                    "Сколько стоит костная пластика?",
                    provider_turn=True,
                    expected_route_class="ANSWER",
                    expected_service_id="bone_graft",
                    commercial_intent="price",
                ),
            ],
        ),
    ]
    if len(scenarios) != EXPECTED_SCENARIO_COUNT:
        raise RuntimeError("build_matrix_document scenario count mismatch")
    return {"schema": MATRIX_SCHEMA, "scenarios": scenarios}


def write_frozen_matrix_json() -> Path:
    doc = build_matrix_document()
    path = matrix_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8"))
    return path


def parse_scenario_specs() -> tuple[ArchCompareScenarioSpec, ...]:
    doc = load_matrix_document()
    specs: list[ArchCompareScenarioSpec] = []
    for row in doc["scenarios"]:
        turns = tuple(
            ArchCompareTurnSpec(
                turn_id=str(turn["turn_id"]),
                user_message=str(turn["user_message"]),
                provider_turn=bool(turn["provider_turn"]),
                expected_route_class=str(turn["expected_route_class"]),  # type: ignore[arg-type]
                expected_service_id=(
                    str(turn["expected_service_id"])
                    if turn.get("expected_service_id")
                    else None
                ),
                expected_brand=(
                    str(turn["expected_brand"]) if turn.get("expected_brand") else None
                ),
                commercial_intent=str(turn.get("commercial_intent") or "none"),
                promotion_scope=str(turn.get("promotion_scope") or "none"),
                dialog_history_turn_ids=tuple(
                    str(x) for x in (turn.get("dialog_history_turn_ids") or ())
                ),
            )
            for turn in row["turns"]
        )
        specs.append(
            ArchCompareScenarioSpec(
                scenario_id=str(row["scenario_id"]),
                relevant_source_refs=tuple(str(x) for x in row["relevant_source_refs"]),
                evaluation_kind=str(row["evaluation_kind"]),  # type: ignore[arg-type]
                required_exact_facts=tuple(str(x) for x in row["required_exact_facts"]),
                forbidden_facts=tuple(str(x) for x in row["forbidden_facts"]),
                turns=turns,
                session_reset=bool(row.get("session_reset", True)),
                notes=str(row.get("notes") or ""),
            )
        )
    return tuple(specs)
