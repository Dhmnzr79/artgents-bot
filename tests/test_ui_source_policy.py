from policy import (
    apply_response_policy,
    apply_ui_source_policy,
    infer_ui_source_family,
)
from ux_builder import normalize_policy_payload


def test_price_navigation_preserves_price_buttons_and_clears_followups():
    payload = {
        "answer": "Цена зависит от ситуации.",
        "quick_replies": [
            {"label": "Этапы", "ref": "price:implantation/stages"},
            {"label": "Гарантии", "ref": "price:implantation/warranty"},
        ],
        "cta": None,
        "meta": {
            "service_route": "price_lookup",
            "followups": [{"label": "MD follow-up", "ref": "implants.md#more"}],
        },
    }

    apply_ui_source_policy(payload, route="price_lookup")
    normalize_policy_payload(payload)

    assert infer_ui_source_family(payload) == "price_navigation"
    assert [item["ref"] for item in payload["quick_replies"]] == [
        "price:implantation/stages",
        "price:implantation/warranty",
    ]
    assert payload["meta"]["followups"] == []
    assert "followups_non_price_ui" in payload["meta"]["policy_decision"]["ui_source_dropped"]


def test_patient_options_keep_only_option_buttons():
    payload = {
        "answer": "Есть несколько вариантов.",
        "quick_replies": [
            {"label": "All-on-4", "ref": "price:all_on_4"},
            {"label": "Подробнее", "ref": "implants.md#overview"},
            {"label": "All-on-6", "ref": "price:all_on_6"},
        ],
        "cta": {"label": "Записаться", "action": "lead"},
        "meta": {
            "orch_route": "patient_options_overview",
            "followups": [{"label": "MD follow-up", "ref": "implants.md#more"}],
            "ui_source_family": "patient_options",
        },
    }

    out = apply_response_policy(
        payload,
        session_state={},
        q="что выбрать",
        topic_state={},
        doc_meta={},
    )
    normalize_policy_payload(out)

    assert [item["ref"] for item in out["quick_replies"]] == [
        "price:all_on_4",
        "price:all_on_6",
    ]
    assert out["meta"]["followups"] == []
    assert out["cta"] == {"label": "Записаться", "action": "lead"}


def test_md_navigation_still_limits_suggest_refs_to_one():
    payload = {
        "answer": "Ответ по статье.",
        "quick_replies": [
            {"label": "Первое", "ref": "a.md#one"},
            {"label": "Второе", "ref": "a.md#two"},
        ],
        "meta": {"ui_source_family": "md_navigation", "followups": []},
    }

    normalize_policy_payload(payload)

    assert payload["quick_replies"] == [{"label": "Первое", "ref": "a.md#one"}]
    assert payload["meta"]["ui_dropped"] == ["suggest_refs_over_limit"]


def test_doctor_list_drops_non_doctor_navigation():
    payload = {
        "answer": "Наши врачи.",
        "quick_replies": [{"label": "Цена", "ref": "price:implantation"}],
        "meta": {
            "orch_route": "doctors_list",
            "followups": [{"label": "Подробнее", "ref": "doctors.md#one"}],
        },
    }

    apply_ui_source_policy(payload)

    assert infer_ui_source_family(payload) == "doctor_navigation"
    assert payload["quick_replies"] == []
    assert payload["meta"]["followups"] == []
