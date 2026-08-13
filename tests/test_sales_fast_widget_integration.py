from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import app as app_module
import config
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.sales_one_plus import SalesOnePlusStrictFact
from core import turn_timing
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.sales_one_plus_turn import run_sales_one_plus_candidate_stream
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_client_pack_identity import build_client_pack_identity
from core.target_cached_full_context import build_target_cached_full_context
from core.target_client_data import load_target_client_data
from tests.one_call_stage2_fixture import Stage2Case, case_by_id, load_stage2_cases
from tests.test_sales_one_plus_turn import answer_envelope, admin_envelope
from orchestration.sales_fast_widget_turn import orchestrate_sales_fast_widget_turn
from session import mem_reset

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "one_call_stage2_cases.json"
_PACK_IDENTITY = build_client_pack_identity("demo")
_DEMO_CATALOG = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
_DEMO_REF_CATALOG = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0
        self.invocation = None
        self.factory_invoked = True

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        text = str(self.output)
        on_raw_delta(text)
        return None


def _authority() -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(authority="exact_turn", provenance="salesfast_test")


def _resolution(case: Stage2Case) -> ExactSalesResolution:
    axes = case.exact_sales
    authority = _authority()
    return ExactSalesResolution(
        service_id=axes.service_id,
        aspect=axes.aspect,
        extent=axes.extent,
        jaw=axes.jaw,
        stage=axes.stage,
        service_id_authority=authority,
        aspect_authority=authority,
        extent_authority=authority,
        jaw_authority=authority,
        stage_authority=authority,
    )


def _strict_facts(case: Stage2Case) -> tuple[SalesOnePlusStrictFact, ...]:
    return tuple(
        SalesOnePlusStrictFact(
            id=fact.id,
            kind=fact.kind,
            text=fact.text,
            must_preserve_exact=fact.must_preserve_exact,
        )
        for fact in case.strict_facts
    )


def _load_cases() -> tuple[Stage2Case, ...]:
    return load_stage2_cases(_FIXTURE_PATH)


def _case(case_id: str) -> Stage2Case:
    return case_by_id(case_id, _FIXTURE_PATH)


def test_flag_off_preserves_planner_target_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", False)
    pre = SimpleNamespace(
        q="ordinary",
        sid="s-off",
        client_id="demo",
        st={},
        data={},
        planner_speculation=None,
    )
    order: list[str] = []

    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *_a, **_k: pre)
    monkeypatch.setattr(app_module, "try_run_typed_ui_planner_turn", lambda **_k: None)
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **_k: order.append("planner"))
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        lambda **_k: order.append("target") or type(
            "AskOrchestrationResult",
            (),
            {"kind": "service_reply", "q": pre.q, "sid": pre.sid, "client_id": pre.client_id},
        )(),
    )
    monkeypatch.setattr(
        "orchestration.sales_one_plus_ask_turn.orchestrate_sales_one_plus_ask_turn",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("sales_one_plus must not run when flag OFF")),
    )

    with app_module.app.test_request_context(
        "/ask",
        method="POST",
        json={"q": pre.q, "sid": pre.sid, "client_id": pre.client_id},
    ):
        app_module.request.ctx = app_module.make_request_context()
        app_module._orchestrate_ask_turn(
            {"q": pre.q, "sid": pre.sid, "client_id": pre.client_id}
        )
    assert order == ["planner", "target"]


@pytest.mark.parametrize("case_id", ("a01", "a02", "a03"))
def test_flag_on_local_admin_cases_make_zero_provider_calls(case_id: str) -> None:
    # Normative ADMIN boundary: docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md
    # § «Нормативная граница ANSWER / ADMIN» — current symptom / personal medical
    # question categories. Future sales fears (f01–f03) must remain ANSWER, not ADMIN.
    case = _case(case_id)
    backend = _CountingBackend("@ADMIN\nignored")
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    result = run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context=case.sales_context,
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert result.decision == "admin"
    assert backend.call_count == 0


@pytest.mark.parametrize("case_id", ("f01", "f02", "f03"))
def test_sales_fears_use_model_route_with_exactly_one_call(case_id: str) -> None:
    case = _case(case_id)
    backend = _CountingBackend(
        answer_envelope(case.required_all[0] if case.required_all else "ответ")
    )
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    result = run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context=case.sales_context,
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert result.decision == "answer"
    assert backend.call_count == 1


def test_parking_and_sterility_answer_from_md_without_verifier() -> None:
    for case_id in ("m01", "m02"):
        case = _case(case_id)
        backend = _CountingBackend(answer_envelope("Есть парковка и стерильность по материалам клиники."))
        context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
        result = run_sales_one_plus_candidate_stream(
            user_message=case.user_message,
            cached_full_context=context,
            exact_sales_resolution=_resolution(case),
            current_strict_facts=_strict_facts(case),
            sales_context=case.sales_context,
            static_admin_handoff_text="Позвоните администратору.",
            backend=backend,
            on_delta=lambda _delta: None,
            pack_identity=_PACK_IDENTITY,
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        )
        assert result.decision == "answer"
        assert backend.call_count == 1


def test_exact_price_case_uses_one_call_without_verifier() -> None:
    case = _case("p03")
    backend = _CountingBackend(answer_envelope("Стоимость классической имплантации — 76 200 ₽ за один зуб."))
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    result = run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context=case.sales_context,
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert result.decision == "answer" and backend.call_count == 1


def test_both_jaws_without_offer_sets_needs_admin_quote_context() -> None:
    case = _case("p04")
    assert case.sales_context.get("needs_admin_quote") is True
    backend = _CountingBackend(answer_envelope("Точную сумму на обе челюсти уточним на консультации."))
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    result = run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context=case.sales_context,
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert result.decision == "answer"
    assert "636000" not in (result.patient_text or "")
    assert backend.call_count == 1


def test_marketing_fact_is_not_passed_to_pre_flash_invocation() -> None:
    case = _case("p01")
    backend = _CountingBackend(answer_envelope("All-on-4 стоит 318 000 ₽.", commercial_intent="price"))
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context={},
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    prompt = backend.invocation.user_prompt
    assert "PRE_MODEL_HINTS" in prompt
    assert "CURRENT_STRICT_FACTS" not in prompt
    assert "318" not in prompt


def test_streaming_parser_emits_only_validated_patient_text() -> None:
    emitted: list[str] = []

    def emit(delta: str) -> None:
        emitted.append(delta)

    parser = SalesOnePlusStreamParser(
        emit,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    payload = answer_envelope("Видимый текст")
    parser.ingest(payload)
    envelope = parser.finalize()
    joined = "".join(emitted)
    assert envelope.route == "ANSWER"
    assert '"route"' not in joined
    assert "service_id" not in joined
    assert joined == "Видимый текст"


def test_provider_error_falls_back_without_second_call() -> None:
    case = _case("m01")
    backend = _CountingBackend(RuntimeError("timeout"))
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    result = run_sales_one_plus_candidate_stream(
        user_message=case.user_message,
        cached_full_context=context,
        exact_sales_resolution=_resolution(case),
        current_strict_facts=_strict_facts(case),
        sales_context=case.sales_context,
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert result.decision == "admin"
    assert result.handoff_text == "Позвоните администратору."
    assert backend.call_count == 1


def test_orchestrator_uses_pinned_flash_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    factory_called = {"value": False}

    class _Backend:
        call_count = 0

        def __init__(self, *, model: str) -> None:
            captured["model"] = model

        def generate(self, _invocation, /):
            self.call_count += 1
            return answer_envelope("Есть парковка у здания.")

    def _factory() -> _Backend:
        factory_called["value"] = True
        return _Backend(model=config.SALES_ONE_PLUS_FLASH_MODEL)

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _factory,
    )
    result = orchestrate_sales_fast_widget_turn(q="Есть парковка?", sid="s-pin", client_id="demo")
    assert result.service_route == "sales_fast_materialized"
    assert captured["model"] == config.SALES_ONE_PLUS_FLASH_MODEL
    assert factory_called["value"] is True


def test_widget_runtime_preserves_followup_cta_shape(monkeypatch: pytest.MonkeyPatch, flask_app) -> None:
    backend = _CountingBackend(answer_envelope("Есть парковка у здания."))
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Есть ли парковка?", "sid": "s1", "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="s1",
            user_message="Есть ли парковка?",
            backend=backend,
        )
    payload = outcome.widget.payload
    assert "quick_replies" in payload
    assert "cta" in payload
    assert "video" in payload
    assert payload.get("meta", {}).get("answer_path") == "sales_fast"


@pytest.fixture
def flask_app():
    return app_module.app


def _install_sales_fast_transport(
    monkeypatch: pytest.MonkeyPatch,
    backend: _CountingBackend,
    *,
    factory: object | None = None,
) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        factory or (lambda: backend),
    )


def _orchestrate_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend: _CountingBackend,
    q: str,
    sid: str,
    factory: object | None = None,
) -> dict:
    _install_sales_fast_transport(monkeypatch, backend, factory=factory)
    mem_reset(sid)
    planner_called = {"value": False}
    target_called = {"value": False}
    pre_resolver_called = {"value": False}

    def _planner(**_kwargs):
        planner_called["value"] = True

    def _target(**_kwargs):
        target_called["value"] = True
        raise AssertionError("target_fullcontext must not run when sales-fast flag is ON")

    def _pre_resolver(*_a, **_k):
        pre_resolver_called["value"] = True
        raise AssertionError("pre_resolver must not run when sales-fast flag is ON")

    monkeypatch.setattr(app_module, "run_pre_resolver_turn", _pre_resolver)
    monkeypatch.setattr(app_module, "run_planner_turn", _planner)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", _target)
    with app_module.app.test_request_context(
        "/ask",
        method="POST",
        json={"q": q, "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        orch = app_module._orchestrate_ask_turn({"q": q, "sid": sid, "client_id": "demo"})
        assert planner_called["value"] is False
        assert target_called["value"] is False
        assert pre_resolver_called["value"] is False
        assert orch.kind == "service_reply"
        return dict(orch.service_payload or {})


@pytest.mark.parametrize(
    "question",
    (
        "Как тяжёлые хронические заболевания влияют на возможность имплантации?",
        "После операции появилось воспаление, подскажите порядок действий",
        "Как подбирают лечение при сложных противопоказаниях к имплантации?",
    ),
)
def test_widget_path_local_admin_cases_skip_provider_factory(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
) -> None:
    backend = _CountingBackend("@ADMIN\nignored")
    factory_invoked = {"value": False}

    def _factory() -> _CountingBackend:
        factory_invoked["value"] = True
        return backend

    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _factory,
    )
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q=question,
        sid=f"admin-{hash(question)}",
        factory=_factory,
    )
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert factory_invoked["value"] is False
    assert backend.call_count == 0


def test_widget_path_parking_answer_uses_deterministic_contacts_after_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Да, у клиники есть городская парковка у здания; для пациентов — 2 часа бесплатно по пропуску на ресепшене."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Есть ли парковка?",
        sid="widget-parking",
    )
    answer = payload["answer"].lower()
    assert "парков" in answer
    assert backend.call_count == 0


def test_widget_path_sterility_answer_uses_one_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность обеспечивается одноразовыми материалами и обработкой по протоколу клиники."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Как обеспечивается стерильность?",
        sid="widget-sterility",
    )
    answer = payload["answer"].lower()
    assert "стериль" in answer or "безопас" in answer
    assert backend.call_count == 1


def test_widget_path_exact_one_tooth_price_from_clinic_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "Классическая имплантация Implantium — 85 200 ₽ за один зуб под ключ.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
        )
    )
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Сколько стоит классический имплант за один зуб?",
        sid="widget-one-tooth",
    )
    answer = payload["answer"]
    assert "от" in answer.lower() and "76" in answer and "200" in answer
    assert "Implantium" in answer and "Impro" in answer and "Nobel" in answer
    assert "85" in answer and "200" in answer
    assert backend.call_count == 1
    offer = payload.get("offer") or {}
    assert offer.get("mode") == "overview"
    assert offer.get("entry_amount") == 76200
    assert offer.get("featured_offer_id") == "classic.one_tooth.impro"


def test_widget_path_few_teeth_does_not_invent_total(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Точную стоимость на несколько зубов администратор уточнит на консультации."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Сколько стоит имплантация нескольких зубов?",
        sid="widget-few-teeth",
    )
    answer = payload["answer"]
    assert "152400" not in answer.replace(" ", "")
    assert backend.call_count == 1


def test_widget_path_both_jaws_does_not_invent_total(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("На обе челюсти точную сумму уточним на консультации с администратором."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Сколько будет All-on-4 на обе челюсти?",
        sid="widget-both-jaws",
    )
    answer = payload["answer"]
    assert "636000" not in answer.replace(" ", "")
    assert backend.call_count == 1


def test_widget_path_marketing_fact_is_in_answer_not_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "All-on-4 на нижнюю челюсть — 368 000 ₽.",
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
        )
    )
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Сколько стоит All-on-4 на нижнюю челюсть?",
        sid="widget-marketing",
    )
    answer = payload["answer"].lower()
    fact_refs = list((payload.get("offer") or {}).get("fact_refs") or [])
    assert fact_refs
    for ref in fact_refs:
        assert ref.startswith("fact:")
    assert "рассроч" in answer
    assert answer.count("рассроч") == 1
    assert backend.call_count == 1
    assert payload.get("cta") is not None or payload.get("quick_replies")


def test_widget_path_direct_repeat_marketing_fact_bypasses_suppression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Да, рассрочка до 12 месяцев доступна."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Можно ли в рассрочку?",
        sid="widget-repeat-fact",
    )
    assert "12" in payload["answer"]
    assert backend.call_count == 1


def test_widget_path_fear_pain_uses_single_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Имплантация проходит под анестезией, лечение обычно безболезненное."))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Боюсь боли при имплантации",
        sid="widget-fear-pain",
    )
    answer = payload["answer"].lower()
    assert "боль" in answer or "анестез" in answer
    assert backend.call_count == 1


def test_widget_path_provider_failure_falls_back_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(RuntimeError("timeout"))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Как обеспечивается стерильность?",
        sid="widget-provider-fail",
    )
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert backend.call_count == 1
    assert "администратор" in payload["answer"].lower() or "клиник" in payload["answer"].lower()


def test_widget_path_observability_timings_without_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    captured_obs: dict[str, object] = {}

    def _capture_obs(**kwargs: object) -> None:
        captured_obs.clear()
        captured_obs.update(kwargs)
        from core.sales_fast_observability import record_sales_fast_observability

        record_sales_fast_observability(**kwargs)

    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.record_sales_fast_observability",
        _capture_obs,
    )
    _install_sales_fast_transport(monkeypatch, backend)
    mem_reset("widget-obs")
    client = app_module.app.test_client()
    client.post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "widget-obs", "client_id": "demo"},
    )
    obs = captured_obs
    timings = obs.get("timings") or {}
    assert obs.get("provider_calls") == 0
    assert obs.get("backend_invocations") == 1
    assert "local_gate" in timings
    assert "resolver" in timings
    assert "provider" in timings
    assert "presentation" in timings
    blob = json.dumps(obs, ensure_ascii=False)
    assert "Как обеспечивается стерильность" not in blob
    assert "Стерильность по протоколу" not in blob


def test_governed_ui_envelope_conflict_is_admin_without_model_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from contracts.local_problem_gate import LocalProblemGateResult
    from core.target_presentation_decision import TargetPresentationCadenceState
    from core.target_runtime_session import read_target_runtime_session

    model_text = "MODEL CONFLICT TEXT MUST NOT APPEAR"
    backend = _CountingBackend(
        answer_envelope(
            model_text,
            service_id=None,
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            commercial_intent="price",
        )
    )
    ui = _authority()
    ui_governed = ExactSalesFieldAuthority(authority="governed_ui", provenance="ui")
    governed_resolution = ExactSalesResolution(
        "classic",
        "price",
        "one_tooth",
        None,
        None,
        ui_governed,
        ui,
        ui_governed,
        ui,
        ui,
    )
    cadence = TargetPresentationCadenceState()

    def _resolve(**kwargs: object):
        sid = str(kwargs.get("sid") or "ui-conflict")
        session_state = read_target_runtime_session(sid)
        return governed_resolution, session_state, cadence

    monkeypatch.setattr("core.sales_fast_widget_runtime._resolve_sales_context", _resolve)
    governed_gate = LocalProblemGateResult(
        decision="pass",
        reason_code="governed_typed_ui",
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Сколько стоит?", "sid": "ui-conflict", "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="ui-conflict",
            user_message="Сколько стоит?",
            backend=backend,
            local_gate_result=governed_gate,
        )
    assert outcome.model_route == "model_admin"
    assert outcome.failure_kind == "semantic_ui_envelope_conflict_service_id"
    assert model_text not in str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
