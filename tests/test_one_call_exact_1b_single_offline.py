"""CP-EXACT-1B-SINGLE offline wiring tests."""

from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import ENVELOPE_NORMALIZED_MISSING_PRICE_TEXT
from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult
from core.one_call_envelope_protocol import (
    dumps_production_envelope,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.one_call_price_text import (
    assemble_price_turn_visible_text,
    patient_text_contains_monetary_amount,
    resolve_price_text_for_turn,
    validate_model_price_text,
)
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.one_call_selected_exact_offer_block import (
    SELECTED_EXACT_OFFER_HEADER,
    build_selected_exact_offer_block,
)
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_presentation_pass import build_one_call_presentation_result
from core.resolve_precomposer_selected_offer import (
    resolve_precomposer_selected_offer,
    resolve_precomposer_selected_offer_for_turn,
)
from core.target_brand_mention_extraction import extract_brand_mentions_from_message
from core.target_brand_resolver import TargetBrandResolutionError
from core.target_runtime_session import read_target_runtime_session
from core.sales_fast_authoritative_commerce import build_canonical_exact_offer_price_line
from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.sales_one_plus_turn import run_sales_one_plus_candidate, run_sales_one_plus_candidate_stream
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_client_data import load_target_client_data
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_runtime_client_context import load_target_runtime_client_context
from core.target_strategy_context import strategy_match_from_effective_scope
from contracts.effective_scope import EffectiveScope
from session import bind_session_client, mem_reset
import app as app_module
import config
from tests.test_sales_one_plus_turn import (
    _context,
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_EXACT_CATALOG,
    _DEMO_REF_CATALOG,
    _PACK_IDENTITY,
    _resolution,
    admin_envelope,
    answer_envelope,
)

_DEMO_DATA = load_target_client_data("demo")
_DEMO_BUNDLE = _DEMO_DATA.bundle
_DEMO_CONTEXT = load_target_runtime_client_context("demo")
_IMPLANTIUM_PRICE_TEXT = (
    "Стоимость All-on-4 на Implantium — 318 000 ₽ за одну челюсть; "
    "КТ и костная пластика по показаниям — отдельно."
)
_IMPLANTIUM_PACKAGE_SCOPE = "КТ и костная пластика по показаниям — отдельно"
_FREE_IMPLANT_CONSULT_SNIPPET = "бесплатная консультация по имплантации"


def _enable_sales_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)


def _reset_demo_session(sid: str) -> None:
    bind_session_client("demo")
    mem_reset(sid)


def _normalize_visible_text(text: str) -> str:
    return text.replace("\u00a0", " ").replace(" ", "").casefold()


def _count_amount_token(text: str, amount: str) -> int:
    return _normalize_visible_text(text).count(amount)


def _authority(source: str) -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(authority=source, provenance=source)  # type: ignore[arg-type]


def _governed_resolution(
    service_id: str,
    *,
    extent: str | None = None,
    jaw: str | None = None,
) -> ExactSalesResolution:
    gov = _authority("governed_ui")
    unk = _authority("unknown")
    return ExactSalesResolution(
        service_id=service_id,
        aspect="price",
        extent=extent,  # type: ignore[arg-type]
        jaw=jaw,  # type: ignore[arg-type]
        stage=None,
        service_id_authority=gov,
        aspect_authority=gov,
        extent_authority=gov if extent else unk,
        jaw_authority=gov if jaw else unk,
        stage_authority=unk,
    )


def _tomography_selection() -> PrecomposerSelectedOfferResult:
    return resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("tomography"),
    )


class _Backend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.calls += 1
        self.invocation = invocation
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.calls += 1
        self.invocation = invocation
        on_raw_delta(str(self.output))
        return None


@pytest.fixture
def flask_app():
    return app_module.app


def test_precomposer_selects_demo_tomography_fixed_offer() -> None:
    selection = _tomography_selection()
    assert selection.availability == "selected"
    assert selection.offer is not None
    assert selection.offer.offer_id == "tomography.default"
    assert selection.offer.price.mode == "fixed"
    assert selection.offer.price.amount == 3000


def test_precomposer_returns_none_for_inactive_service() -> None:
    inactive = _DEMO_BUNDLE.model_copy(deep=True)
    service = inactive.services["tomography"].model_copy(update={"active": False})
    inactive.services["tomography"] = service
    selection = resolve_precomposer_selected_offer(
        bundle=inactive,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("tomography"),
    )
    assert selection.availability == "none"


def test_precomposer_returns_none_for_jaw_both() -> None:
    selection = resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=_governed_resolution("tomography", jaw="both"),
    )
    assert selection.availability == "none"


def test_precomposer_returns_none_without_authoritative_service() -> None:
    unk = _authority("unknown")
    resolution = ExactSalesResolution(
        "tomography",
        "price",
        None,
        None,
        None,
        unk,
        unk,
        unk,
        unk,
        unk,
    )
    selection = resolve_precomposer_selected_offer(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=resolution,
    )
    assert selection.availability == "none"


def test_selected_exact_offer_block_only_in_dynamic_suffix() -> None:
    selection = _tomography_selection()
    suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=_governed_resolution("tomography"),
        current_strict_facts=(),
        sales_context={},
        user_message="Сколько стоит КТ?",
        exact_commercial_catalog=_DEMO_EXACT_CATALOG,
        precomposer_selected_offer=selection,
        response_schema_bundle=_DEMO_BUNDLE,
    )
    assert SELECTED_EXACT_OFFER_HEADER in suffix
    assert "=== EXACT_COMMERCIAL_CATALOG ===" not in suffix
    assert '"availability": "selected"' in suffix
    assert '"price_text_allowed": true' in suffix


def test_selected_exact_offer_none_block() -> None:
    block = build_selected_exact_offer_block(
        bundle=_DEMO_BUNDLE,
        selection=PrecomposerSelectedOfferResult(availability="none"),
    )
    assert '"availability": "none"' in block
    assert '"price_text_allowed": false' in block


def test_envelope_parses_price_text_and_missing_normalizes() -> None:
    catalog = _DEMO_CATALOG
    ref = _DEMO_REF_CATALOG
    commercial = _DEMO_COMMERCIAL_CATALOG
    payload = production_envelope_template()
    payload.pop("price_text")
    raw = json.dumps(payload, ensure_ascii=False)
    envelope = parse_production_envelope_json(
        raw,
        active_service_catalog=catalog,
        service_reference_catalog=ref,
        commercial_fact_catalog=commercial,
    )
    assert envelope.price_text is None


def test_admin_and_clarify_ignore_price_text() -> None:
    catalog = _DEMO_CATALOG
    ref = _DEMO_REF_CATALOG
    commercial = _DEMO_COMMERCIAL_CATALOG
    admin = parse_production_envelope_json(
        admin_envelope(price_text="999 ₽"),
        active_service_catalog=catalog,
        service_reference_catalog=ref,
        commercial_fact_catalog=commercial,
    )
    assert admin.price_text is None
    clarify = parse_production_envelope_json(
        dumps_production_envelope(
            route="CLARIFY",
            patient_text="Уточните, пожалуйста.",
            clarify_axis="service",
            clarify_service_options=["tomography", "all_on_4"],
            price_text="999 ₽",
        ),
        active_service_catalog=catalog,
        service_reference_catalog=ref,
        commercial_fact_catalog=commercial,
    )
    assert clarify.price_text is None


def test_resolve_price_text_accepts_valid_model_price_text() -> None:
    selection = _tomography_selection()
    assert selection.offer is not None
    canonical = build_canonical_exact_offer_price_line(offer=selection.offer, bundle=_DEMO_BUNDLE)
    model_price = "Стоимость КТ — 3 000 ₽ за одно исследование."
    resolved = resolve_price_text_for_turn(
        price_text=model_price,
        commercial_intent="price",
        selection=selection,
        bundle=_DEMO_BUNDLE,
    )
    assert resolved.owner == "model_price_text"
    assert resolved.line == model_price
    assert canonical.count("3") >= 1


def test_missing_price_text_uses_canonical_fallback_patient_preserved() -> None:
    selection = _tomography_selection()
    patient = "КТ помогает увидеть кость до лечения."
    resolved = resolve_price_text_for_turn(
        price_text=None,
        commercial_intent="price",
        selection=selection,
        bundle=_DEMO_BUNDLE,
    )
    assert resolved.owner == "canonical_fallback"
    assert resolved.diagnostic == "missing"
    assert "3" in resolved.line and "000" in resolved.line
    assert patient == "КТ помогает увидеть кость до лечения."


def test_wrong_amount_triggers_canonical_fallback() -> None:
    selection = _tomography_selection()
    assert selection.offer is not None
    resolved = resolve_price_text_for_turn(
        price_text="Стоимость — 9 999 ₽ за исследование.",
        commercial_intent="price",
        selection=selection,
        bundle=_DEMO_BUNDLE,
    )
    assert resolved.owner == "canonical_fallback"
    assert resolved.diagnostic == "wrong_amount"


def test_extra_amount_triggers_fallback() -> None:
    selection = _tomography_selection()
    failure = validate_model_price_text(
        "3 000 ₽ и 5 000 ₽ за исследование",
        offer=selection.offer,  # type: ignore[arg-type]
        bundle=_DEMO_BUNDLE,
    )
    assert failure == "extra_amount"


def test_prompt_contract_version_nine_documents_price_text() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 9
    from core.one_call_prompt_contract import ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS

    assert "price_text" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    assert "Do not return used_offer_id" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS


def test_streaming_buffers_until_validation_no_price_in_delta(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    selection = _tomography_selection()
    envelope = answer_envelope(
        "КТ нужна для планирования.",
        commercial_intent="price",
        scenario="cost",
        service_id="tomography",
        service_reference_status="resolved",
        requested_service_id="tomography",
        price_text="Стоимость КТ — 3 000 ₽ за одно исследование.",
    )
    backend = _Backend(envelope)
    _reset_demo_session("cp-exact-1b-stream")
    deltas: list[str] = []

    def on_delta(text: str) -> None:
        deltas.append(text)

    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Сколько стоит КТ?", "sid": "cp-exact-1b-stream", "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-cp-exact-1b-stream"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="cp-exact-1b-stream",
            user_message="Сколько стоит КТ?",
            backend=backend,
            on_delta=on_delta,
        )
    assert outcome.widget.kind == "materialized"
    answer = str(outcome.widget.payload.get("answer") or "")
    assert "3" in answer and "000" in answer
    assert "КТ нужна" in answer
    assert all("price_text" not in delta for delta in deltas)


def test_widget_turn_precomposer_block_present(monkeypatch: pytest.MonkeyPatch) -> None:
    selection = _tomography_selection()
    backend = _Backend(
        answer_envelope(
            "Перед имплантацией обычно делают КТ.",
            commercial_intent="price",
            service_id="tomography",
            service_reference_status="resolved",
            requested_service_id="tomography",
            price_text=None,
        )
    )
    run_sales_one_plus_candidate(
        user_message="Сколько стоит КТ?",
        cached_full_context=_context(),
        exact_sales_resolution=_governed_resolution("tomography"),
        static_admin_handoff_text="ADMIN",
        backend=backend,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        exact_commercial_catalog=_DEMO_EXACT_CATALOG,
        precomposer_selected_offer=selection,
        response_schema_bundle=_DEMO_BUNDLE,
    )
    assert backend.invocation is not None
    assert SELECTED_EXACT_OFFER_HEADER in backend.invocation.user_prompt
    assert "tomography.default" in backend.invocation.user_prompt


_PRECOMPOSER_SINGLETON_SERVICES = frozenset({"tomography"})


def _fresh_empty_session():
    sid = "cp-exact-1b-empty-session"
    bind_session_client("demo")
    mem_reset(sid)
    return read_target_runtime_session(sid)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Сколько стоит All-on-4 Implantium?", ("implantium",)),
        ("имплантиум", ("implantium",)),
        ("IMPLANTIUM", ("implantium",)),
        ("Nobel Biocare", ("nobel_biocare",)),
        ("Nobel, Biocare?", ("nobel_biocare",)),
        ("Nobel Biocare и Nobel", ("nobel_biocare",)),
        ("Nobel или Impro", ("nobel_biocare", "impro")),
        ("Straumann", ()),
        ("имплантиумный", ()),
        ("Nobe", ()),
    ],
)
def test_brand_mention_extraction_from_message(message: str, expected: tuple[str, ...]) -> None:
    mentions = extract_brand_mentions_from_message(_DEMO_BUNDLE.brands, message)
    assert mentions == expected


def test_brand_mention_alias_collision_is_fail_closed() -> None:
    broken = _DEMO_BUNDLE.model_copy(deep=True)
    broken.brands.brands["impro"] = broken.brands.brands["impro"].model_copy(
        update={"aliases": ("импро", "имплантиум")}
    )
    with pytest.raises(TargetBrandResolutionError) as exc:
        extract_brand_mentions_from_message(broken.brands, "имплантиум")
    assert exc.value.code == "brand_resolution_ambiguous"


@pytest.mark.parametrize(
    ("message", "brand_id", "offer_id"),
    [
        ("Сколько стоит All-on-4 Implantium?", "implantium", "all_on_4.jaw.implantium"),
        ("Сколько стоит All-on-4 Nobel?", "nobel_biocare", "all_on_4.jaw.nobel"),
    ],
)
def test_precomposer_selects_demo_all_on_4_brand_offer(
    message: str,
    brand_id: str,
    offer_id: str,
) -> None:
    from core.sales_fast_service_identity import resolve_catalog_service_identity

    identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
    resolution = resolve_exact_sales_resolution_for_test(message, identity)
    selection = resolve_precomposer_selected_offer_for_turn(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=resolution,
        user_message=message,
        service_identity=identity,
        session_state=_fresh_empty_session(),
    )
    assert selection.availability == "selected"
    assert selection.offer is not None
    assert selection.offer.offer_id == offer_id
    assert selection.offer.brand_id == brand_id


def resolve_exact_sales_resolution_for_test(message: str, identity) -> ExactSalesResolution:
    from contracts.answer_plan import AspectKind
    from core.answer_planner import detect_aspects_regex
    from core.exact_sales_resolver import ExactSalesResolverInputs, resolve_exact_sales_inputs

    aspects = detect_aspects_regex(message)
    exact_aspect: AspectKind | None = aspects[0] if aspects else None
    return resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_DEMO_BUNDLE.services,
            current_topic=None,
            session_turn_count=0,
            exact_service_term=identity.explicit_service_term,
            exact_aspect=exact_aspect,
        )
    )


def test_precomposer_known_brand_without_service_offer_not_substituted() -> None:
    message = "Сколько стоит КТ Implantium?"
    from core.sales_fast_service_identity import resolve_catalog_service_identity

    identity = resolve_catalog_service_identity(message, _DEMO_BUNDLE)
    resolution = resolve_exact_sales_resolution_for_test(message, identity)
    selection = resolve_precomposer_selected_offer_for_turn(
        bundle=_DEMO_BUNDLE,
        doctor_catalog=_DEMO_CONTEXT.doctor_catalog,
        resolution=resolution,
        user_message=message,
        service_identity=identity,
        session_state=_fresh_empty_session(),
    )
    assert selection.availability == "none"


def test_precomposer_patient_text_hostile_amount_preserved_in_assembly() -> None:
    selection = _tomography_selection()
    patient = "Неправильная цена 999999 ₽, но КТ важна."
    line = "Стоимость КТ — 3 000 ₽ за одно исследование."
    assembled = assemble_price_turn_visible_text(
        price_line=line,
        patient_text=patient,
        marketing_suffix="",
    )
    assert "999999" in assembled
    assert "3 000" in assembled
    assert patient_text_contains_monetary_amount(patient)


def test_widget_precomposer_hostile_patient_text_preserved_with_canonical_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    hostile = "999999"
    backend = _Backend(
        answer_envelope(
            f"Неправильная цена {hostile} ₽.",
            commercial_intent="price",
            service_id="tomography",
            service_reference_status="resolved",
            requested_service_id="tomography",
            price_text=None,
        )
    )
    _reset_demo_session("cp-exact-1b-hostile")
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Сколько стоит КТ?", "sid": "cp-exact-1b-hostile", "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-hostile"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="cp-exact-1b-hostile",
            user_message="Сколько стоит КТ?",
            backend=backend,
        )
        answer = str(outcome.widget.payload.get("answer") or "")
        flags = request.ctx.get("turn_timing", {}).get("flags", {})
    assert hostile in answer.replace(" ", "")
    assert "3000" in answer.replace("\u00a0", "").replace(" ", "")
    assert flags.get("price_text_patient_monetary_amount") is True


def test_widget_non_price_all_on_4_implantium_has_no_auto_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    patient = "Да, делаем All-on-4 на Implantium."
    backend = _Backend(
        answer_envelope(
            patient,
            commercial_intent="none",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        )
    )
    _reset_demo_session("cp-exact-1b-nonprice-brand")
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Делаете All-on-4 Implantium?",
            "sid": "cp-exact-1b-nonprice-brand",
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"request_id": "rid-nonprice-brand"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="cp-exact-1b-nonprice-brand",
            user_message="Делаете All-on-4 Implantium?",
            backend=backend,
        )
    assert outcome.widget.kind == "materialized"
    assert outcome.model_route == "model"
    answer = str(outcome.widget.payload.get("answer") or "")
    normalized = _normalize_visible_text(answer)
    assert "318000" not in normalized
    assert _normalize_visible_text(_IMPLANTIUM_PRICE_TEXT) not in normalized
    assert patient in answer
    assert "администратор" not in normalized


def test_widget_two_turn_all_on_4_then_nobel_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    sid = "cp-exact-1b-two-turn"
    _reset_demo_session(sid)
    first_backend = _Backend(
        answer_envelope(
            "All-on-4 — это полное восстановление челюсти.",
            commercial_intent="none",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-two-turn-1"}
        run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Сколько стоит All-on-4?",
            backend=first_backend,
        )
    second_backend = _Backend(
        answer_envelope(
            "Nobel Biocare — премиальный вариант.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text="Стоимость All-on-4 на Nobel Biocare — 428 000 ₽ за одну челюсть.",
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "А Nobel?", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-two-turn-2"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="А Nobel?",
            backend=second_backend,
        )
        answer = str(outcome.widget.payload.get("answer") or "")
    assert second_backend.invocation is not None
    assert "all_on_4.jaw.nobel" in second_backend.invocation.user_prompt
    assert "428000" in answer.replace("\u00a0", "").replace(" ", "")


def test_widget_all_on_4_implantium_price_turn_full_path(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    user_message = "Сколько стоит All-on-4 Implantium?"
    patient = "All-on-4 на Implantium — популярный вариант полного восстановления челюсти."
    backend = _Backend(
        answer_envelope(
            patient,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=_IMPLANTIUM_PRICE_TEXT,
        )
    )
    sid = "cp-exact-1b-implantium-full"
    _reset_demo_session(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-implantium-full"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            backend=backend,
        )
        answer = str(outcome.widget.payload.get("answer") or "")
        flags = request.ctx.get("turn_timing", {}).get("flags", {})
    assert outcome.widget.kind == "materialized"
    assert outcome.model_route == "model"
    assert backend.invocation is not None
    assert SELECTED_EXACT_OFFER_HEADER in backend.invocation.user_prompt
    assert "all_on_4.jaw.implantium" in backend.invocation.user_prompt
    assert '"brand_label": "Implantium"' in backend.invocation.user_prompt
    assert flags.get("price_text_owner") == "model_price_text"
    assert flags.get("price_text_diagnostic") is None
    assert patient in answer
    assert _IMPLANTIUM_PACKAGE_SCOPE in answer
    assert _count_amount_token(answer, "318000") == 1
    assert _IMPLANTIUM_PRICE_TEXT in answer
    price_idx = answer.index(_IMPLANTIUM_PRICE_TEXT)
    promo_idx = answer.casefold().index(_FREE_IMPLANT_CONSULT_SNIPPET)
    assert price_idx < promo_idx
    offer = outcome.widget.payload.get("offer")
    assert isinstance(offer, dict)
    assert offer.get("mode") == "exact_offer"
    assert offer.get("offer_id") == "all_on_4.jaw.implantium"
    assert offer.get("amount") == 318000
    assert "администратор" not in _normalize_visible_text(answer)


def test_demo_nikadent_session_isolation_same_sid(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _enable_sales_fast(monkeypatch)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    sid = "cp-exact-1b-client-isolation"

    bind_session_client("demo")
    mem_reset(sid)
    demo_backend = _Backend(
        answer_envelope(
            "All-on-4 — полное восстановление челюсти.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=_IMPLANTIUM_PRICE_TEXT,
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-iso-demo"}
        run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Сколько стоит All-on-4?",
            backend=demo_backend,
        )
    demo_session = read_target_runtime_session(sid)
    assert demo_session.last_service_id == "all_on_4"

    bind_session_client("nikadent")
    mem_reset(sid)
    nika_session = read_target_runtime_session(sid)
    assert nika_session.last_service_id is None

    nika_backend = _Backend(
        answer_envelope(
            "Удаление зуба стоит 5 000 ₽.",
            commercial_intent="price",
            service_id="tooth_extraction",
            service_reference_status="resolved",
            requested_service_id="tooth_extraction",
            price_text="Стоимость удаления зуба — 5 000 ₽ за процедуру.",
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Сколько стоит удаление зуба?",
            "sid": sid,
            "client_id": "nikadent",
        },
    ):
        from flask import request

        request.ctx = {"request_id": "rid-iso-nika"}
        run_sales_fast_widget_turn(
            client_id="nikadent",
            sid=sid,
            user_message="Сколько стоит удаление зуба?",
            backend=nika_backend,
        )
    nika_session_after = read_target_runtime_session(sid)
    assert nika_session_after.last_service_id == "tooth_extraction"

    bind_session_client("nikadent")
    followup_backend = _Backend(
        answer_envelope(
            "Nobel Biocare — премиальный вариант.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="unresolved",
            price_text="Стоимость All-on-4 на Nobel Biocare — 428 000 ₽ за одну челюсть.",
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "А Nobel?", "sid": sid, "client_id": "nikadent"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-iso-nika-followup"}
        run_sales_fast_widget_turn(
            client_id="nikadent",
            sid=sid,
            user_message="А Nobel?",
            backend=followup_backend,
        )
    assert followup_backend.invocation is not None
    assert '"availability": "none"' in followup_backend.invocation.user_prompt

    bind_session_client("demo")
    demo_session_after = read_target_runtime_session(sid)
    assert demo_session_after.last_service_id == "all_on_4"
    assert demo_session_after.last_service_id != "tooth_extraction"
    bind_session_client("demo")

