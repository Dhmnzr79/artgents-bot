"""Unit contract for A0 preservation eval harness (no live suite)."""

from __future__ import annotations

import json
import os

import pytest

from evals.v5.smoke_case_runner import (
    _PROTECTED_UI_CONTRACT_KEYS,
    _build_source_catalog_from_doc,
    extract_evidence_source_doc_id,
    load_json,
    parse_sse_ui_payload,
    validate_preservation_contract,
    validate_price_followup_contract,
    validate_smoke_case,
)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PRESERVATION_PATH = os.path.join(_REPO_ROOT, "evals", "v5", "demo", "preservation.json")
_FROZEN_HASH = "c2072ca74c2da73bf657d793195d2eb6c8ba7bd5"


def _preservation_spec() -> dict:
    return load_json(_PRESERVATION_PATH)


def _case(case_id: str) -> dict:
    for row in _preservation_spec()["cases"]:
        if row.get("id") == case_id:
            return dict(row)
    raise KeyError(case_id)


def _base_resp(**overrides) -> dict:
    resp = {
        "answer": "Тестовый ответ с фактами 99,8% и 26 лет.",
        "quick_replies": [],
        "video": None,
        "meta": {
            "doc_id": "implantation__faq__osseointegration",
            "answer_path": "composer",
            "followups": [],
            "metadata_first": {"selected_doc_id": "implantation__faq__osseointegration"},
            "generator_input": {"doc_id": "implantation__faq__osseointegration"},
        },
    }
    resp.update(overrides)
    if "meta" in overrides:
        resp["meta"] = {**_base_resp()["meta"], **overrides["meta"]}
    return resp


def test_preservation_json_hash_frozen() -> None:
    import subprocess

    digest = subprocess.check_output(
        ["git", "hash-object", _PRESERVATION_PATH],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()
    assert digest == _FROZEN_HASH


def test_preservation_spec_pipeline_contract() -> None:
    spec = _preservation_spec()
    pc = spec.get("pipeline_contract") or {}
    assert pc.get("endpoint") == "/ask/stream"
    assert pc.get("sse_event") == "ui"


def test_all_protected_ui_fields_known_in_spec() -> None:
    for row in _preservation_spec()["cases"]:
        ui = row.get("protected_ui_contract")
        if not isinstance(ui, dict):
            continue
        for key in ui:
            assert key in _PROTECTED_UI_CONTRACT_KEYS, f"{row['id']}: unknown protected_ui key {key!r}"


@pytest.mark.parametrize(
    "case_id",
    [
        "preservation_02_osseointegration",
        "preservation_03_all_on_4_vs_all_on_6",
    ],
)
def test_source_catalog_preflight_matches_spec(case_id: str) -> None:
    row = _case(case_id)
    ui = row["protected_ui_contract"]
    catalog, err = _build_source_catalog_from_doc(
        client_id=row["client_id"],
        source_doc_id=str(ui["source_doc_id"]),
        followup_source=str(ui["followup_source"]),
    )
    assert err is None, err
    assert catalog is not None
    refs, labels = catalog
    assert refs == ui["source_catalog_refs_ordered"]
    assert labels == ui["source_catalog_labels_ordered"]


def test_osseointegration_positive_payload() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(
        meta={
            "followups": [
                {
                    "label": "А если имплант не приживётся",
                    "ref": "implantation__faq__osseointegration.md#a-esli-implant-ne-prizhivetsya",
                }
            ],
        },
        video={"key": "pain-doctor-explains", "src": "/api/media/pain-doctor-explains", "title": "x"},
    )
    assert validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content") is None


def test_fail_wrong_evidence_source() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(
        meta={
            "doc_id": "implantation__faq__osseointegration",
            "metadata_first": {"selected_doc_id": "implantation__faq__osseointegration"},
            "generator_input": {"doc_id": "implantation__faq__osseointegration"},
            "answer_packet": {
                "cards": [{"kind": "content", "source_ref": "implantation__faq__pain.md#korotko"}]
            },
        }
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "evidence_source" in reason


def test_fail_selected_doc_id_cannot_mask_wrong_content_card() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(
        meta={
            "metadata_first": {"selected_doc_id": "implantation__faq__osseointegration"},
            "answer_packet": {
                "cards": [{"kind": "content", "source_ref": "implantation__faq__pain.md#korotko"}]
            },
        }
    )
    doc_id, prov = extract_evidence_source_doc_id(resp)
    assert doc_id == "implantation__faq__pain"
    assert prov == "answer_packet.cards.source_ref"
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "evidence_source" in reason


def test_fail_missing_followup() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(meta={"followups": []})
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "visible_followup_refs" in reason


def test_fail_wrong_followup_order() -> None:
    row = _case("preservation_03_all_on_4_vs_all_on_6")
    resp = _base_resp(
        meta={
            "doc_id": "comparison__all_on_4_vs_all_on_6",
            "metadata_first": {"selected_doc_id": "comparison__all_on_4_vs_all_on_6"},
            "generator_input": {"doc_id": "comparison__all_on_4_vs_all_on_6"},
            "followups": [
                {
                    "label": "Когда выбирают шесть имплантов",
                    "ref": "comparison__all_on_4_vs_all_on_6.md#kogda-vybirayut-shest",
                },
                {
                    "label": "Когда достаточно четырёх имплантов",
                    "ref": "comparison__all_on_4_vs_all_on_6.md#kogda-dostatochno-chetyreh",
                },
            ],
        }
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "visible_followup_refs" in reason


def test_fail_wrong_followup_label() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(
        meta={
            "followups": [
                {
                    "label": "Неверная подпись",
                    "ref": "implantation__faq__osseointegration.md#a-esli-implant-ne-prizhivetsya",
                }
            ],
        }
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "visible_followup_labels" in reason


def test_fail_wrong_video_key() -> None:
    row = _case("preservation_02_osseointegration")
    resp = _base_resp(
        meta={"followups": [{"label": "А если имплант не приживётся", "ref": "implantation__faq__osseointegration.md#a-esli-implant-ne-prizhivetsya"}]},
        video={"key": "wrong-key", "src": "/x", "title": "x"},
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="content")
    assert reason and "video_key" in reason


def test_classic_price_optional_amount_present_passes() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    resp = {
        "answer": "Implantium 76 200 ₽, Impro 85 200 ₽, Nobel 101 200 ₽",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    assert validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup") is None


def test_classic_price_optional_amount_absent_passes() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    resp = {
        "answer": "Implantium 76 200 ₽, Impro 85 200 ₽",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    assert validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup") is None


def test_fail_allowed_optional_not_in_pricebook() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    row = dict(row)
    row["protected_ui_contract"] = {
        **row["protected_ui_contract"],
        "allowed_optional_amounts": [999999],
    }
    resp = {
        "answer": "Implantium 76 200 ₽, Impro 85 200 ₽",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "amount_not_in_pricebook" in reason


def test_fail_undeclared_pricebook_total_in_answer() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    row = dict(row)
    row["protected_ui_contract"] = {
        **row["protected_ui_contract"],
        "allowed_optional_amounts": [],
    }
    resp = {
        "answer": "Implantium 76 200 ₽, Impro 85 200 ₽, Nobel 101 200 ₽",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "undeclared_pricebook_total" in reason


def test_fail_wrong_price_unit() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    resp = {
        "answer": "Стоимость зависит от выбранной системы.",
        "quick_replies": [],
        "meta": {"price_offer_unit": "jaw", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "expected_unit" in reason


def test_fail_missing_required_amount() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    resp = {
        "answer": "Implantium от 76 200 ₽.",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "required_amount" in reason


def test_fail_forbidden_amount_present() -> None:
    row = _case("preservation_04_classic_one_tooth_price")
    resp = {
        "answer": "Implantium 76 200 ₽, Impro 85 200 ₽, All-on-4 318 000 ₽",
        "quick_replies": [],
        "meta": {"price_offer_unit": "one_tooth", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "forbidden_amount" in reason


def test_fail_extra_third_price_quick_reply() -> None:
    row = _case("preservation_05_all_on_4_jaw_price")
    resp = {
        "answer": "All-on-4 от 318 000 и 368 000 ₽ за челюсть.",
        "quick_replies": [
            {"label": "Оплата по этапам", "ref": "price:all_on_4/stages"},
            {"label": "Что входит", "ref": "price:all_on_4/includes"},
            {"label": "Лишняя", "ref": "price:all_on_4/extra"},
        ],
        "meta": {"price_offer_unit": "jaw", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "price_quick_reply_count" in reason


def test_fail_swapped_price_quick_replies() -> None:
    row = _case("preservation_05_all_on_4_jaw_price")
    resp = {
        "answer": "All-on-4 от 318 000 и 368 000 ₽ за челюсть.",
        "quick_replies": [
            {"label": "Что входит", "ref": "price:all_on_4/includes"},
            {"label": "Оплата по этапам", "ref": "price:all_on_4/stages"},
        ],
        "meta": {"price_offer_unit": "jaw", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "price_quick_reply" in reason


def test_fail_swapped_pricebook_followup_source_order() -> None:
    expected = [
        {"label": "Оплата по этапам", "ref": "price:all_on_4/stages", "action": "price_aspect", "aspect": "stages"},
        {"label": "Что входит", "ref": "price:all_on_4/includes", "action": "price_aspect", "aspect": "includes"},
    ]
    quick = [
        {"label": "Оплата по этапам", "ref": "price:all_on_4/stages"},
        {"label": "Что входит", "ref": "price:all_on_4/includes"},
    ]
    pb_followups = [
        {"label": "Что входит", "action": "price_aspect", "aspect": "includes"},
        {"label": "Оплата по этапам", "action": "price_aspect", "aspect": "stages"},
    ]
    reason = validate_price_followup_contract(
        expected_actions=expected,
        pb_followups=pb_followups,
        quick_replies=quick,
    )
    assert reason and "price_followup_source" in reason


def test_fail_wrong_price_quick_reply() -> None:
    row = _case("preservation_05_all_on_4_jaw_price")
    resp = {
        "answer": "All-on-4 от 318 000 и 368 000 ₽ за челюсть.",
        "quick_replies": [
            {"label": "Оплата по этапам", "ref": "price:all_on_4/wrong"},
            {"label": "Что входит", "ref": "price:all_on_4/includes"},
        ],
        "meta": {"price_offer_unit": "jaw", "answer_path": "composer"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup")
    assert reason and "price_quick_reply" in reason


def test_all_on_4_price_positive_payload() -> None:
    row = _case("preservation_05_all_on_4_jaw_price")
    resp = {
        "answer": "All-on-4 от 318 000 и 368 000 ₽ за челюсть.",
        "quick_replies": [
            {"label": "Оплата по этапам", "ref": "price:all_on_4/stages"},
            {"label": "Что входит", "ref": "price:all_on_4/includes"},
        ],
        "meta": {"price_offer_unit": "jaw", "answer_path": "composer"},
    }
    assert validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="price_lookup") is None


def test_fail_promo_present_when_expected_absent() -> None:
    row = _case("preservation_06_marketing_optional_overlay")
    resp = _base_resp(
        meta={
            "doc_id": "implantation__faq__pain",
            "metadata_first": {"selected_doc_id": "implantation__faq__pain"},
            "generator_input": {"doc_id": "implantation__faq__pain"},
            "answer_packet": {
                "cards": [{"kind": "promo", "aspect": "pain", "fact_id": "free_implant_consult"}],
                "promo_decisions": [{"allowed": True, "reason": "allowed", "fact_id": "x"}],
            },
        }
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer="Анестезия делает процедуру небольной.", route="content")
    assert reason and "expected_promo_absent" in reason


def test_fail_empty_core_answer() -> None:
    row = _case("preservation_06_marketing_optional_overlay")
    resp = _base_resp(
        meta={
            "doc_id": "implantation__faq__pain",
            "metadata_first": {"selected_doc_id": "implantation__faq__pain"},
            "generator_input": {"doc_id": "implantation__faq__pain"},
            "low_score": True,
            "fallback_reason": "retrieval_no_candidates",
        }
    )
    reason = validate_preservation_contract(row=row, resp=resp, answer="", route="content")
    assert reason and "core_answer_required" in reason


def test_fail_unknown_protected_ui_field() -> None:
    row = _case("preservation_02_osseointegration")
    row = dict(row)
    row["protected_ui_contract"] = {
        **row["protected_ui_contract"],
        "unexpected_harness_field": True,
    }
    reason = validate_preservation_contract(row=row, resp=_base_resp(), answer="x", route="content")
    assert reason and "unknown fields" in reason


def test_extract_evidence_source_from_packet_card() -> None:
    resp = {
        "meta": {
            "answer_packet": {
                "cards": [{"kind": "content", "source_ref": "comparison__all_on_4_vs_all_on_6.md#korotko"}]
            }
        }
    }
    doc_id, prov = extract_evidence_source_doc_id(resp)
    assert doc_id == "comparison__all_on_4_vs_all_on_6"
    assert prov == "answer_packet.cards.source_ref"


def test_contacts_boundary_fails_on_composer_path() -> None:
    row = _case("preservation_01_contacts_address")
    resp = {
        "answer": "Москва, Тверская, Пушкинская",
        "meta": {"answer_path": "composer", "doc_id": "clinic__info__contacts"},
    }
    reason = validate_preservation_contract(row=row, resp=resp, answer=resp["answer"], route="contacts_chunk")
    assert reason and "contacts_boundary" in reason


def test_validate_smoke_case_delegates_preservation_contract() -> None:
    row = _case("preservation_02_osseointegration")
    answer = "Приживаемость имплантов 99,8% за 26 лет работы клиники."
    resp = _base_resp(
        meta={
            "followups": [],
            "numeric_fact_gate": {"action": "pass"},
            "forbidden_claim_hits": [],
        }
    )
    fail = validate_smoke_case(row=row, resp=resp, answer=answer, route="retrieval_chunk")
    assert fail is not None
    assert fail.status == "FAIL"
    assert "visible_followup" in fail.reason


def test_parse_sse_ui_payload_returns_last_ui_event() -> None:
    body = (
        "event: ui\n"
        'data: {"answer": "first", "meta": {"seq": 1}}\n'
        "\n"
        "event: ui\n"
        'data: {"answer": "second", "meta": {"seq": 2}}\n'
        "\n"
    )
    payload = parse_sse_ui_payload(body)
    assert payload["answer"] == "second"
    assert payload["meta"]["seq"] == 2


def test_parse_sse_ui_payload_rejects_non_object() -> None:
    body = "event: ui\ndata: []\n\n"
    with pytest.raises(ValueError, match="ui payload is not a JSON object"):
        parse_sse_ui_payload(body)


def test_smoke_case_fails_za_zub_without_amount_hints() -> None:
    row = {
        "id": "price_unit_contract",
        "expected_price_unit": "one_tooth",
    }
    answer = "Цена за зуб зависит от выбранной системы имплантов."
    resp = {
        "answer": answer,
        "quick_replies": [],
        "meta": {"answer_path": "composer"},
    }
    fail = validate_smoke_case(row=row, resp=resp, answer=answer, route="price_lookup")
    assert fail is not None
    assert fail.status == "FAIL"
    assert "price_offer_unit" in fail.reason


def test_smoke_case_fails_za_chelyust_without_amount_hints() -> None:
    row = {
        "id": "price_unit_contract",
        "expected_price_unit": "jaw",
    }
    answer = "Стоимость за челюсть обсуждается на консультации."
    resp = {
        "answer": answer,
        "quick_replies": [],
        "meta": {"answer_path": "composer"},
    }
    fail = validate_smoke_case(row=row, resp=resp, answer=answer, route="price_lookup")
    assert fail is not None
    assert fail.status == "FAIL"
    assert "price_offer_unit" in fail.reason


def test_smoke_case_fails_price_unit_without_meta_or_amount_hint() -> None:
    row = {
        "id": "price_unit_contract",
        "expected_price_unit": "one_tooth",
    }
    answer = "Стоимость Implantium 76200 и Impro 85200 рублей."
    resp = {
        "answer": answer,
        "quick_replies": [],
        "meta": {"answer_path": "composer"},
    }
    fail = validate_smoke_case(row=row, resp=resp, answer=answer, route="price_lookup")
    assert fail is not None
    assert fail.status == "FAIL"
    assert "price_offer_unit" in fail.reason


def test_marketing_positive_without_promo() -> None:
    row = _case("preservation_06_marketing_optional_overlay")
    resp = _base_resp(
        meta={
            "doc_id": "implantation__faq__pain",
            "metadata_first": {"selected_doc_id": "implantation__faq__pain"},
            "generator_input": {"doc_id": "implantation__faq__pain"},
            "answer_packet": {
                "cards": [{"kind": "content", "source_ref": "implantation__faq__pain.md#korotko"}],
                "promo_decisions": [],
            },
        }
    )
    assert (
        validate_preservation_contract(
            row=row,
            resp=resp,
            answer="Анестезия делает установку импланта небольной.",
            route="content",
        )
        is None
    )
