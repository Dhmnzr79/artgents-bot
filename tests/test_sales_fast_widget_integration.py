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
from tests.test_sales_one_plus_turn import answer_envelope, admin_envelope, _DEMO_COMMERCIAL_CATALOG
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


def test_widget_future_fear_faq_reaches_fake_backend(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    model_text = "После имплантации возможен умеренный отёк — это нормальная реакция."
    backend = _CountingBackend(
        answer_envelope(model_text, commercial_intent="none", service_id=None)
    )
    _install_sales_fast_transport(monkeypatch, backend)
    mem_reset("widget-future-fear")
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Будет ли отёк после имплантации?",
            "sid": "widget-future-fear",
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="widget-future-fear",
            user_message="Будет ли отёк после имплантации?",
            backend=backend,
        )
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert model_text in str(outcome.widget.payload.get("answer") or "")


@pytest.mark.parametrize("case_id", ("a02",))
def test_symptom_case_reaches_composer_with_one_provider_call(case_id: str) -> None:
    case = _case(case_id)
    backend = _CountingBackend(admin_envelope())
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert result.decision == "admin"
    assert result.reason == "model_admin"
    assert backend.call_count == 1


@pytest.mark.parametrize("case_id", ("a01", "a03"))
def test_general_medical_faq_cases_use_model_route_with_exactly_one_call(case_id: str) -> None:
    case = _case(case_id)
    backend = _CountingBackend(answer_envelope("Ответ по материалам клиники о безопасности имплантации."))
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert result.decision == "answer"
    assert backend.call_count == 1
    assert result.patient_text


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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
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
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
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
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    payload = answer_envelope("Видимый текст")
    parser.ingest(payload)
    envelope = parser.finalize()
    joined = "".join(emitted)
    assert envelope.route == "ANSWER"
    assert '"route"' not in joined
    assert "service_id" not in joined
    assert joined == "Видимый текст"


def test_provider_error_raises_backend_failure_without_second_call() -> None:
    from core.sales_one_plus_turn import SalesOnePlusBackendFailure

    case = _case("m01")
    backend = _CountingBackend(RuntimeError("timeout"))
    context = build_target_cached_full_context(_REPO_ROOT / "clients" / "demo" / "md")
    with pytest.raises(SalesOnePlusBackendFailure, match="backend_failed"):
        run_sales_one_plus_candidate_stream(
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
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )
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


def _install_rotating_backend_factory(
    monkeypatch: pytest.MonkeyPatch,
    backends: list[_CountingBackend],
) -> None:
    index = {"value": 0}

    def factory() -> _CountingBackend:
        backend = backends[index["value"]]
        index["value"] += 1
        return backend

    _install_sales_fast_transport(monkeypatch, backends[0], factory=factory)


def _parse_sse_events(resp) -> list[tuple[str, dict]]:
    buffer = ""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    for chunk in resp.response:
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.startswith("event: "):
                current_event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                raw = line[len("data: ") :]
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    data = {}
                if current_event:
                    events.append((current_event, data))
                current_event = None
    return events


_ADMIN_HANDOFF_BASE_LITERAL = (
    "Спасибо, что написали. С этим вопросом лучше обратиться "
    "к администратору клиники — он поможет дальше."
)


def _orchestrate_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend: _CountingBackend,
    q: str,
    sid: str,
    factory: object | None = None,
) -> dict:
    from session import bind_session_client, mem_reset

    _install_sales_fast_transport(monkeypatch, backend, factory=factory)
    bind_session_client("demo")
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


def test_widget_path_model_admin_uses_one_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    question: str = "После операции появилось воспаление, подскажите порядок действий",
) -> None:
    backend = _CountingBackend(admin_envelope())
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
    assert factory_invoked["value"] is True
    assert backend.call_count == 1


@pytest.mark.parametrize(
    "question",
    (
        "Как тяжёлые хронические заболевания влияют на возможность имплантации?",
        "Как подбирают лечение при сложных противопоказаниях к имплантации?",
    ),
)
def test_widget_path_general_medical_faq_uses_one_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
) -> None:
    backend = _CountingBackend(
        answer_envelope("Ответ по материалам клиники о безопасности имплантации.")
    )
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
        sid=f"faq-{hash(question)}",
        factory=_factory,
    )
    assert payload["meta"]["service_route"] != "sales_fast_admin"
    assert factory_invoked["value"] is True
    assert backend.call_count == 1
    assert str(payload.get("answer") or "").strip()


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
    flask_app,
) -> None:
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache
    from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
    from session import bind_session_client, mem_reset

    clear_target_runtime_client_context_cache()
    sid = "widget-marketing-service-two-promos"
    bind_session_client("demo")
    mem_reset(sid)
    backend = _CountingBackend(
        answer_envelope(
            "All-on-4 — это полное восстановление зубного ряда на четырёх имплантах.",
            commercial_intent="none",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Расскажите про All-on-4 на нижнюю челюсть", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Расскажите про All-on-4 на нижнюю челюсть",
            backend=backend,
        )
    answer = str(outcome.widget.payload.get("answer") or "").lower()
    assert "15%" in answer or "консультац" in answer
    assert "также мы предлагаем" in answer
    assert "рассроч" in answer
    assert backend.call_count == 1


def test_widget_path_price_all_on_4_includes_two_promos_not_installment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 7, 21),
    )
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.runtime_today",
        lambda: date(2026, 7, 21),
    )
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
        sid="widget-price-marketing",
    )
    answer = payload["answer"]
    answer_lower = answer.lower()
    assert "368" in answer or "318" in answer
    assert "скидк" in answer_lower
    assert "консультац" in answer_lower
    assert "При оплате в день обращения — скидка до 15% на имплантацию." in answer
    assert "бесплатная консультация по имплантации и протезированию" in answer_lower
    assert "кт при необходимости оплачивается отдельно" in answer_lower
    assert "также мы предлагаем" in answer_lower
    assert "рассроч" in answer_lower
    assert "по этапам" in answer_lower
    assert "договор" in answer_lower
    offer = payload.get("offer") or {}
    fact_refs = list(offer.get("fact_refs") or [])
    if fact_refs:
        assert "fact:implant_same_day_discount" in fact_refs
        assert "fact:free_implant_consult" in fact_refs
    assert backend.call_count == 1


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


def test_widget_path_provider_failure_returns_technical_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(RuntimeError("timeout"))
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Как обеспечивается стерильность?",
        sid="widget-provider-fail",
    )
    assert payload["meta"]["service_route"] == "sales_fast_error"
    assert backend.call_count == 1
    assert "не удалось подготовить ответ" in payload["answer"].lower()
    assert "позвоните" not in payload["answer"].lower()


def test_widget_two_turn_history_reaches_composer_prompt(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from session import bind_session_client, mem_add_bot, mem_add_user, mem_reset

    sid = "widget-history-cycle"
    bind_session_client("demo")
    mem_reset(sid)
    first_q = "Делаете all-on-4?"
    first_answer = "Да, выполняем All-on-4."
    backend1 = _CountingBackend(answer_envelope(first_answer))
    _install_sales_fast_transport(monkeypatch, backend1)
    with flask_app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=first_q,
            backend=backend1,
        )
    mem_add_user(sid, first_q)
    mem_add_bot(sid, first_answer)

    second_q = "а сколько стоит?"
    backend2 = _CountingBackend(answer_envelope("Стоимость зависит от случая."))
    _install_sales_fast_transport(monkeypatch, backend2)
    with flask_app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=second_q,
            backend=backend2,
        )
    prompt = str(backend2.invocation.user_prompt)
    assert "не источник фактов" in prompt
    assert first_q.lower() in prompt.lower()
    assert first_answer.lower() in prompt.lower()
    assert prompt.count(second_q) == 1


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


def test_governed_ui_envelope_conflict_is_scope_clarify_without_model_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from contracts.local_problem_gate import LocalProblemGateResult
    from core.sales_fast_service_identity import SalesFastServiceIdentity
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
        identity = SalesFastServiceIdentity(
            explicit_service_id=None,
            explicit_service_term=None,
            session_service_id=None,
            catalog_ambiguous=False,
        )
        return governed_resolution, session_state, cadence, identity

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
    assert outcome.model_route == "clarify"
    assert outcome.failure_kind == "semantic_ui_envelope_conflict_service_id"
    assert model_text not in str(outcome.widget.payload.get("answer") or "")
    assert outcome.widget.payload.get("offer") is None
    assert backend.call_count == 1


def _run_widget_turn_with_envelope(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client_id: str,
    sid: str,
    user_message: str,
    envelope_json: str,
    flask_app,
) -> tuple[dict, _CountingBackend]:
    from session import bind_session_client

    backend = _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    if client_id != "demo":
        monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    bind_session_client(client_id)
    mem_reset(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id=client_id,
            sid=sid,
            user_message=user_message,
            backend=backend,
        )
    assert outcome.widget.kind == "materialized"
    return dict(outcome.widget.payload or {}), backend


def _run_widget_turn_keep_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client_id: str,
    sid: str,
    user_message: str,
    envelope_json: str,
    flask_app,
    backend: _CountingBackend | None = None,
    on_delta: object | None = None,
    allow_terminal: bool = False,
) -> tuple[dict, _CountingBackend]:
    from session import bind_session_client

    active_backend = backend or _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, active_backend)
    if client_id != "demo":
        monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    bind_session_client(client_id)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id=client_id,
            sid=sid,
            user_message=user_message,
            backend=active_backend,
            on_delta=on_delta,
        )
    if not allow_terminal:
        assert outcome.widget.kind == "materialized"
    return dict(outcome.widget.payload or {}), active_backend


def test_widget_path_nikadent_all_on_4_family_price_materializes_and_persists_session(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
    from core.target_runtime_session import read_target_runtime_session

    sid = "widget-nika-allon4-family"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid,
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "Короткий ответ о стоимости All-on-4.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
        ),
        flask_app=flask_app,
    )
    answer = payload["answer"]
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_materialized"
    assert "35" in answer and "000" in answer
    assert FAMILY_CONTEXT_DISCLAIMER in answer
    assert payload.get("offer") is None
    session = read_target_runtime_session(sid)
    assert session.last_service_id == "all_on_4"


def test_widget_path_nikadent_crown_family_price_materializes_without_exact_offer_card(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
    from core.target_runtime_session import read_target_runtime_session

    sid = "widget-nika-crown-family"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid,
        user_message="Сколько стоит циркониевая коронка?",
        envelope_json=answer_envelope(
            "Короткий ответ о стоимости коронки.",
            commercial_intent="price",
            service_id="zirconia_crowns",
        ),
        flask_app=flask_app,
    )
    answer = payload["answer"]
    assert backend.call_count == 1
    assert "22" in answer and "000" in answer
    assert FAMILY_CONTEXT_DISCLAIMER in answer
    assert payload.get("offer") is None
    session = read_target_runtime_session(sid)
    assert session.last_service_id == "zirconia_crowns"


def test_widget_path_demo_general_promotion_overview_materializes_and_persists_session(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from datetime import date

    from core.target_client_data import load_target_client_data
    from core.target_runtime_session import read_target_runtime_session

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.runtime_today",
        lambda: date(2026, 8, 10),
    )
    data = load_target_client_data("demo")
    expected_ids = (
        "implant_same_day_discount",
        "professional_whitening_discount",
        "free_implant_consult",
    )
    expected_texts = tuple(str(data.bundle.facts[fact_id].text_fact) for fact_id in expected_ids)
    sid = "widget-demo-promo-general"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Какие акции у вас есть?",
        envelope_json=answer_envelope(
            "Расскажу об актуальных акциях клиники.",
            commercial_intent="promotion",
            promotion_scope="general",
            service_id=None,
        ),
        flask_app=flask_app,
    )
    answer = payload["answer"]
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_materialized"
    for text in expected_texts:
        assert text in answer
    session = read_target_runtime_session(sid)
    assert set(session.shown_fact_ids) == set(expected_ids)


def test_widget_path_exact_price_offer_card_preserved(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "widget-nika-bridge-exact"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid,
        user_message="Сколько стоит мост?",
        envelope_json=answer_envelope(
            "Мостовидный протез — от 10 000 ₽ за единицу.",
            commercial_intent="price",
            service_id="fixed_bridge",
        ),
        flask_app=flask_app,
    )
    assert backend.call_count == 1
    offer = payload.get("offer")
    assert isinstance(offer, dict)
    assert offer.get("mode") == "exact_offer"
    assert "10" in payload["answer"]


def test_widget_path_informational_turn_has_no_price_surface(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "widget-nika-neutral"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid,
        user_message="Что такое All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 — протокол имплантации на четырёх имплантах.",
            service_id="all_on_4",
            commercial_intent="none",
        ),
        flask_app=flask_app,
    )
    assert backend.call_count == 1
    assert "₽" not in payload["answer"]
    assert payload.get("offer") is None


def test_widget_path_fail_closed_promotion_does_not_persist_session_promo_state(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session

    sid = "widget-fail-closed-promo"
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Какие акции на лечение кариеса?",
        envelope_json=answer_envelope(
            "Какие акции на лечение кариеса?",
            commercial_intent="promotion",
            promotion_scope="service",
            service_id="caries",
        ),
        flask_app=flask_app,
    )
    assert backend.call_count == 1
    assert payload["meta"].get("presentation_fail_closed") == "promotion_no_eligible_facts"
    session = read_target_runtime_session(sid)
    assert session.last_rendered_promo_fact_id is None
    assert session.shown_fact_ids == ()


def test_widget_path_promo_cadence_suppresses_repeat_and_shown_scope_repeats_last(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session
    from session import bind_session_client

    sid = "widget-promo-cadence"
    bind_session_client("demo")
    mem_reset(sid)
    backend = _CountingBackend(
        answer_envelope(
            "Расскажу про All-on-4.",
            service_id="all_on_4",
            commercial_intent="none",
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Расскажите про All-on-4", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome1 = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Расскажите про All-on-4",
            backend=backend,
        )
    answer1 = str(outcome1.widget.payload.get("answer") or "")
    assert "15" in answer1 or "скидк" in answer1.lower()
    assert "консультац" in answer1.lower()
    session1 = read_target_runtime_session(sid)
    assert session1.last_rendered_promo_fact_id is None
    assert session1.last_turn_rendered_promo_fact_ids == (
        "implant_same_day_discount",
        "free_implant_consult",
    )

    backend3 = _CountingBackend(
        answer_envelope(
            "Повторю акцию.",
            service_id="all_on_4",
            commercial_intent="promotion",
            promotion_scope="shown",
        )
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Повторите акцию, которую только что показывали",
            "sid": sid,
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome3 = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Повторите акцию, которую только что показывали",
            backend=backend3,
        )
    answer3 = str(outcome3.widget.payload.get("answer") or "").lower()
    assert outcome3.widget.payload.get("meta", {}).get("presentation_fail_closed") == (
        "promotion_shown_ambiguous"
    )


def test_widget_path_multiclient_cache_isolation_without_mid_sequence_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache
    from session import bind_session_client

    clear_target_runtime_client_context_cache()
    sid_demo = "widget-mt-demo"
    sid_nika = "widget-mt-nika"

    payload_demo_1, _ = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid_demo,
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4 на Implantium — 318 000 ₽ за одну челюсть.",
            commercial_intent="price",
            service_id="all_on_4",
        ),
        flask_app=flask_app,
    )
    assert "318" in payload_demo_1["answer"]
    assert "35 000" not in payload_demo_1["answer"].replace("\u00a0", " ")

    payload_nika, _ = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid_nika,
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "Короткий ответ о стоимости All-on-4.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
        ),
        flask_app=flask_app,
    )
    assert "35" in payload_nika["answer"]
    assert "318" not in payload_nika["answer"]

    bind_session_client("demo")
    mem_reset(sid_demo)
    payload_demo_2, _ = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid_demo,
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4 на Implantium — 318 000 ₽ за одну челюсть.",
            commercial_intent="price",
            service_id="all_on_4",
        ),
        flask_app=flask_app,
    )
    assert "318" in payload_demo_2["answer"]
    clear_target_runtime_client_context_cache()


def test_widget_runtime_injects_contact_authority_into_provider_prompt(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid="contact-prompt-demo",
        user_message="Есть ли парковка?",
        envelope_json=answer_envelope("Есть парковка у здания."),
        flask_app=flask_app,
    )
    assert backend.invocation is not None
    user_prompt = backend.invocation.user_prompt
    assert "<CLINIC_CONTACT_AUTHORITY>" in user_prompt
    assert "+7 (495) 128-47-60" in user_prompt
    assert "<PRE_MODEL_HINTS>" in user_prompt
    assert "__authority_client_id" not in user_prompt
    assert '"amount"' not in user_prompt
    assert payload["meta"].get("answer_path") == "sales_fast"


def test_widget_runtime_nikadent_prompt_has_branch_contacts_not_demo(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    _, backend = _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid="contact-prompt-nika",
        user_message="Расскажите о клинике",
        envelope_json=answer_envelope("Ответ по клинике."),
        flask_app=flask_app,
    )
    user_prompt = backend.invocation.user_prompt
    assert "<CLINIC_CONTACT_AUTHORITY>" in user_prompt
    assert "ryabikova" in user_prompt
    assert "pogranichnaya" in user_prompt
    assert demo_phone not in user_prompt


def test_http_ask_internal_error_uses_resolved_client_not_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    nika_phone = canonical_contact_phone("nikadent")
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    monkeypatch.setattr(
        app_module,
        "_orchestrate_ask_turn",
        lambda _data: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Какие акции?", "sid": "err-nika", "client_id": "nikadent"},
    )
    payload = resp.get_json()
    assert payload["meta"]["error"] == "internal"
    assert demo_phone not in payload["answer"]
    assert nika_phone in payload["answer"]


def test_http_ask_error_before_client_resolution_is_neutral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    monkeypatch.setattr(
        app_module,
        "resolve_request_client_id",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("resolve failed")),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "вопрос", "sid": "err-no-client", "client_id": "nikadent"},
    )
    payload = resp.get_json()
    assert payload["meta"]["error"] == "internal"
    assert demo_phone not in payload["answer"]
    assert "Что-то пошло не так" in payload["answer"]


def test_http_ask_stream_worker_error_uses_explicit_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    nika_phone = canonical_contact_phone("nikadent")
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))

    def _boom(*_a, **_k):
        raise RuntimeError("sse worker failure")

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn", _boom)
    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "Какие акции?", "sid": "err-stream-nika", "client_id": "nikadent"},
    )
    body = resp.get_data(as_text=True)
    assert "event: ui" in body
    assert demo_phone not in body
    assert nika_phone in body
    assert body.count("event: ui\n") == 1


def test_contact_isolation_demo_nikadent_demo_with_preserved_session(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_contact_authority import canonical_contact_phone
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache
    from session import bind_session_client, mem_reset

    demo_phone = canonical_contact_phone("demo")
    nika_branch_phone = "+7 (900) 444-69-97"
    sid = "contact-isolation-preserved-session"
    bind_session_client("demo")
    mem_reset(sid)
    _install_sales_fast_transport(monkeypatch, _CountingBackend(answer_envelope("placeholder")))

    payload_demo, backend_demo = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Какой телефон клиники?",
        envelope_json=answer_envelope(
            f"Позвоните нам: {demo_phone}.",
        ),
        flask_app=flask_app,
    )
    assert demo_phone in backend_demo.invocation.user_prompt
    assert demo_phone in payload_demo["answer"]
    assert nika_branch_phone not in backend_demo.invocation.user_prompt

    payload_nika, backend_nika = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="nikadent",
        sid=sid,
        user_message="Какой телефон филиала на Рябикова?",
        envelope_json=answer_envelope(
            f"Филиал на Рябикова: {nika_branch_phone}.",
        ),
        flask_app=flask_app,
    )
    assert nika_branch_phone in backend_nika.invocation.user_prompt
    assert demo_phone not in backend_nika.invocation.user_prompt
    assert nika_branch_phone in payload_nika["answer"]
    assert demo_phone not in payload_nika["answer"]

    payload_demo_2, backend_demo_2 = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Повторите телефон клиники",
        envelope_json=answer_envelope(
            f"Телефон клиники: {demo_phone}.",
        ),
        flask_app=flask_app,
    )
    assert demo_phone in backend_demo_2.invocation.user_prompt
    assert nika_branch_phone not in backend_demo_2.invocation.user_prompt
    assert demo_phone in payload_demo_2["answer"]
    assert nika_branch_phone not in payload_demo_2["answer"]
    clear_target_runtime_client_context_cache()


def test_widget_prompt_contact_block_in_generate_and_generate_stream(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    generate_backend = _CountingBackend(answer_envelope("Ответ по парковке."))
    _, generate_hit = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid="contact-generate",
        user_message="Есть парковка?",
        envelope_json=answer_envelope("Ответ по парковке."),
        flask_app=flask_app,
        backend=generate_backend,
        on_delta=None,
    )
    assert generate_hit.invocation is not None
    assert "<CLINIC_CONTACT_AUTHORITY>" in generate_hit.invocation.user_prompt

    stream_backend = _CountingBackend(answer_envelope("Ответ по графику."))
    _, stream_hit = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid="contact-stream",
        user_message="Какой график работы?",
        envelope_json=answer_envelope("Ответ по графику."),
        flask_app=flask_app,
        backend=stream_backend,
        on_delta=lambda _delta: None,
    )
    assert stream_hit.invocation is not None
    assert "<CLINIC_CONTACT_AUTHORITY>" in stream_hit.invocation.user_prompt
    assert "+7 (495) 128-47-60" in stream_hit.invocation.user_prompt


def test_partial_contacts_appear_in_provider_prompt_without_phone(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.clinic_contact_policies import ClinicContactFacts

    facts = ClinicContactFacts(
        phone_display="",
        whatsapp_display=None,
        address_display="г. Елизово, ул. Рябикова, д. 49",
        hours_display="Пн–Пт 9:00–18:00",
        parking_display=None,
    )
    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts",
        lambda _client_id: facts,
    )
    _, backend = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="nikadent",
        sid="partial-contact-prompt",
        user_message="Где вы находитесь?",
        envelope_json=answer_envelope("Адрес указан в контактах."),
        flask_app=flask_app,
    )
    prompt = backend.invocation.user_prompt
    assert "<CLINIC_CONTACT_AUTHORITY>" in prompt
    assert "Рябикова" in prompt
    assert "9:00" in prompt
    assert '"contacts_available":true' in prompt.replace(" ", "")


def test_http_ask_error_with_corrupt_contact_source_returns_neutral_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import yaml

    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")

    def _yaml_fail(_path: object) -> object:
        raise yaml.YAMLError("corrupt policies")

    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts_from_policies_path",
        _yaml_fail,
    )
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    monkeypatch.setattr(
        app_module,
        "_orchestrate_ask_turn",
        lambda _data: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Какие акции?", "sid": "err-corrupt-contacts", "client_id": "nikadent"},
    )
    payload = resp.get_json()
    assert payload["meta"]["error"] == "internal"
    assert "Что-то пошло не так" in payload["answer"]
    assert demo_phone not in payload["answer"]


def test_http_ask_stream_corrupt_contacts_single_ui_and_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import yaml

    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")

    def _yaml_fail(_path: object) -> object:
        raise yaml.YAMLError("corrupt policies")

    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts_from_policies_path",
        _yaml_fail,
    )
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    monkeypatch.setattr(
        app_module,
        "_orchestrate_ask_turn",
        lambda _data: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "Какие акции?", "sid": "err-stream-corrupt", "client_id": "nikadent"},
    )
    body = resp.get_data(as_text=True)
    assert body.count("event: ui\n") == 1
    assert "event: done\n" in body
    assert demo_phone not in body
    assert "Что-то пошло не так" in body


def test_nikadent_model_admin_without_contacts_has_no_demo_phone_or_extra_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.clinic_contact_policies import ClinicContactFacts
    from core.target_contact_authority import canonical_contact_phone
    from core.one_call_envelope_protocol import dumps_production_envelope

    demo_phone = canonical_contact_phone("demo")
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts",
        lambda _client_id: ClinicContactFacts(
            phone_display="",
            whatsapp_display=None,
            address_display=None,
            hours_display=None,
            parking_display=None,
        ),
    )
    backend = _CountingBackend(
        dumps_production_envelope(
            route="ADMIN",
            patient_text=None,
            clarify_axis=None,
            clarify_service_options=None,
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "После операции появилось воспаление, подскажите порядок действий",
            "sid": "admin-nika-no-contacts",
            "client_id": "nikadent",
        },
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="nikadent",
            sid="admin-nika-no-contacts",
            user_message="После операции появилось воспаление, подскажите порядок действий",
            backend=backend,
        )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert outcome.model_route == "model_admin"
    assert backend.call_count == 1
    assert demo_phone not in answer
    assert answer == _ADMIN_HANDOFF_BASE_LITERAL


def test_widget_price_profile_full_path_two_turns_with_service_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    flask_app,
) -> None:
    from core.sales_fast_presentation import AUTOMATIC_AMPLIFIER_LIST_HEADER
    from core.target_runtime_session import read_target_runtime_session
    from session import bind_session_client, mem_reset
    from tests.marketing_price_profile_pack import (
        AMP_IDS,
        AMP_TEXTS,
        CLIENT_ID,
        PRICE_MAIN_TEXT,
        PROMO_A_ID,
        PROMO_A_TEXT,
        PROMO_B_ID,
        PROMO_B_TEXT,
        SERVICE_ID,
        SV_FACT_ID,
        SV_TEXT,
        build_marketing_price_profile_pack,
        patch_isolated_marketing_price_repo,
    )

    build_marketing_price_profile_pack(tmp_path)
    patch_isolated_marketing_price_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(
        config,
        "ALLOWED_CLIENTS",
        frozenset({CLIENT_ID, "demo", "nikadent"}),
    )
    sid = "widget-price-profile-full"
    bind_session_client(CLIENT_ID)
    mem_reset(sid)
    payload1, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        envelope_json=answer_envelope(
            PRICE_MAIN_TEXT,
            commercial_intent="price",
            service_id=SERVICE_ID,
            extent="full_arch",
            jaw="lower",
        ),
        flask_app=flask_app,
    )
    answer1 = str(payload1.get("answer") or "")
    assert "368" in answer1
    assert PROMO_A_TEXT in answer1
    assert PROMO_B_TEXT in answer1
    assert answer1.count(AUTOMATIC_AMPLIFIER_LIST_HEADER) == 1
    for amp_text in AMP_TEXTS:
        assert f"- {amp_text}" in answer1
    assert SV_TEXT not in answer1
    for amp_text in AMP_TEXTS:
        assert answer1.count(amp_text) == 1
    session1 = read_target_runtime_session(sid)
    assert session1.shown_service_value_ids == ()
    assert PROMO_A_ID in session1.shown_fact_ids
    assert PROMO_B_ID in session1.shown_fact_ids
    assert all(f"fact:{amp_id}" in session1.shown_amplifier_refs for amp_id in AMP_IDS)

    payload2, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Расскажите про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол восстановления.",
            commercial_intent="none",
            service_id=SERVICE_ID,
            extent="full_arch",
            jaw="lower",
        ),
        flask_app=flask_app,
    )
    answer2 = str(payload2.get("answer") or "")
    assert PROMO_A_TEXT not in answer2
    assert PROMO_B_TEXT not in answer2
    for amp_text in AMP_TEXTS:
        assert amp_text not in answer2
    assert SV_TEXT in answer2
    session2 = read_target_runtime_session(sid)
    assert SV_FACT_ID in session2.shown_service_value_ids


def test_widget_service_value_full_session_cycle_without_manual_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session
    from session import bind_session_client, mem_reset
    from tests.marketing_sv_cycle_pack import (
        CLIENT_ID,
        SV_FACT_ID,
        SV_TEXT,
        build_marketing_sv_cycle_pack,
        patch_isolated_marketing_sv_repo,
    )

    build_marketing_sv_cycle_pack(tmp_path)
    patch_isolated_marketing_sv_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(
        config,
        "ALLOWED_CLIENTS",
        frozenset({CLIENT_ID, "demo", "nikadent"}),
    )
    sid = "widget-sv-cycle"
    bind_session_client(CLIENT_ID)
    mem_reset(sid)
    turn1_envelope = answer_envelope(
        "All-on-4 на нижнюю челюсть — протокол.",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        commercial_intent="none",
    )
    payload1, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Расскажите про All-on-4 на нижнюю челюсть",
        envelope_json=turn1_envelope,
        flask_app=flask_app,
    )
    answer1 = str(payload1.get("answer") or "")
    assert SV_TEXT in answer1
    assert answer1.index(SV_TEXT) < answer1.index("15%")
    session1 = read_target_runtime_session(sid)
    assert session1.shown_service_value_ids == (SV_FACT_ID,)
    assert len(session1.last_turn_rendered_promo_fact_ids) == 2

    payload2, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Ещё раз про All-on-4",
        envelope_json=answer_envelope(
            "Повтор про All-on-4.",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            commercial_intent="none",
        ),
        flask_app=flask_app,
    )
    assert SV_TEXT not in str(payload2.get("answer") or "")

    payload3, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Расскажите про All-on-6",
        envelope_json=answer_envelope(
            "All-on-6 — другой протокол.",
            service_id="all_on_6",
            extent="full_arch",
            jaw="lower",
            commercial_intent="none",
        ),
        flask_app=flask_app,
    )
    assert SV_TEXT not in str(payload3.get("answer") or "")

    payload4, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Что это за преимущество?",
        envelope_json=answer_envelope(
            "Про преимущество.",
            service_id="all_on_6",
            extent="full_arch",
            jaw="lower",
            references={"direct_fact_ids": [SV_FACT_ID]},
        ),
        flask_app=flask_app,
    )
    assert SV_TEXT in str(payload4.get("answer") or "")


class _StreamTrackingBackend(_CountingBackend):
    def __init__(self, output: object) -> None:
        super().__init__(output)
        self.stream_path_used = False
        self.stream_raw_chunks: list[str] = []

    def generate_stream(self, invocation, on_raw_delta, /):
        self.stream_path_used = True
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        text = str(self.output)
        for index in range(0, len(text), 24):
            chunk = text[index : index + 24]
            self.stream_raw_chunks.append(chunk)
            on_raw_delta(chunk)
        return None


def test_widget_streaming_marketing_path_persists_session_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session
    from session import bind_session_client, mem_reset
    from tests.marketing_sv_cycle_pack import (
        CLIENT_ID,
        SV_FACT_ID,
        SV_TEXT,
        build_marketing_sv_cycle_pack,
        patch_isolated_marketing_sv_repo,
    )

    build_marketing_sv_cycle_pack(tmp_path)
    patch_isolated_marketing_sv_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(
        config,
        "ALLOWED_CLIENTS",
        frozenset({CLIENT_ID, "demo", "nikadent"}),
    )
    sid = "widget-stream-marketing"
    bind_session_client(CLIENT_ID)
    mem_reset(sid)
    turn_envelope = answer_envelope(
        "All-on-4 на нижнюю челюсть — протокол.",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        commercial_intent="none",
    )
    backend = _StreamTrackingBackend(turn_envelope)
    streamed: list[str] = []
    payload1, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Расскажите про All-on-4 на нижнюю челюсть",
        envelope_json=turn_envelope,
        flask_app=flask_app,
        backend=backend,
        on_delta=lambda delta: streamed.append(delta),
    )
    final_answer = str(payload1.get("answer") or "")
    assert backend.stream_path_used is True
    assert backend.call_count == 1
    assert streamed == [final_answer]
    assert SV_TEXT in final_answer
    assert final_answer.count(SV_TEXT) == 1
    assert final_answer.count("15%") == 1
    session1 = read_target_runtime_session(sid)
    assert session1.shown_service_value_ids == (SV_FACT_ID,)
    assert len(session1.last_turn_rendered_promo_fact_ids) == 2

    payload2, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id=CLIENT_ID,
        sid=sid,
        user_message="Ещё раз",
        envelope_json=answer_envelope(
            "Повтор.",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            commercial_intent="none",
        ),
        flask_app=flask_app,
        on_delta=lambda _delta: None,
    )
    assert SV_TEXT not in str(payload2.get("answer") or "")


def test_materialized_widget_ok_skips_extract_session_selection_fallback(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core import sales_fast_presentation as presentation_module

    fallback_calls = {"count": 0}
    original = presentation_module.sales_fast_session_selection

    def _spy(**kwargs):
        fallback_calls["count"] += 1
        return original(**kwargs)

    monkeypatch.setattr(presentation_module, "sales_fast_session_selection", _spy)
    _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid="widget-no-fallback-selection",
        user_message="Расскажите про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол.",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            commercial_intent="none",
        ),
        flask_app=flask_app,
    )
    assert fallback_calls["count"] == 0


def test_http_ask_two_turn_history_reaches_composer_without_manual_mem_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from session import bind_session_client, mem_reset

    sid = "http-ask-history-cycle"
    first_q = "Делаете all-on-4?"
    second_q = "а сколько стоит?"
    backends = [
        _CountingBackend(answer_envelope("Да, выполняем All-on-4.")),
        _CountingBackend(answer_envelope("Стоимость зависит от случая.")),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    bind_session_client("demo")
    mem_reset(sid)
    client = app_module.app.test_client()
    resp1 = client.post(
        "/ask",
        json={"q": first_q, "sid": sid, "client_id": "demo"},
    )
    assert resp1.status_code == 200
    visible_first = str(resp1.get_json().get("answer") or "")
    assert visible_first.strip()
    resp2 = client.post(
        "/ask",
        json={"q": second_q, "sid": sid, "client_id": "demo"},
    )
    assert resp2.status_code == 200
    assert backends[1].invocation is not None
    prompt = str(backends[1].invocation.user_prompt)
    corpus = str(backends[1].invocation.model_corpus_text)
    assert first_q.lower() in prompt.lower()
    assert visible_first.lower() in prompt.lower()
    assert prompt.count(second_q) == 1
    assert first_q.lower() not in corpus.lower()
    assert visible_first.lower() not in corpus.lower()


def test_http_ask_stream_two_turn_history_reaches_composer_without_manual_mem_seed(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from session import bind_session_client, mem_reset

    sid = "http-stream-history-cycle"
    first_q = "Делаете all-on-4?"
    second_q = "а сколько стоит?"
    backends = [
        _CountingBackend(answer_envelope("Да, выполняем All-on-4.")),
        _CountingBackend(answer_envelope("Стоимость зависит от случая.")),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    bind_session_client("demo")
    mem_reset(sid)
    client = flask_app.test_client()
    resp1 = client.post(
        "/ask/stream",
        json={"q": first_q, "sid": sid, "client_id": "demo"},
    )
    assert resp1.status_code == 200
    events1 = _parse_sse_events(resp1)
    ui1 = [data for name, data in events1 if name == "ui"]
    assert ui1
    visible_first = str(ui1[-1].get("answer") or "")
    assert visible_first.strip()
    resp2 = client.post(
        "/ask/stream",
        json={"q": second_q, "sid": sid, "client_id": "demo"},
    )
    assert resp2.status_code == 200
    _parse_sse_events(resp2)
    assert backends[1].invocation is not None
    prompt = str(backends[1].invocation.user_prompt)
    corpus = str(backends[1].invocation.model_corpus_text)
    assert first_q.lower() in prompt.lower()
    assert visible_first.lower() in prompt.lower()
    assert prompt.count(second_q) == 1
    assert first_q.lower() not in corpus.lower()
    assert visible_first.lower() not in corpus.lower()


def test_http_ask_history_does_not_cross_clients_with_same_sid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from session import bind_session_client, mem_reset

    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    sid = "shared-sid-history"
    demo_q = "Сколько стоит All-on-4 в demo?"
    nika_q = "Сколько стоит All-on-4 в nikadent?"
    demo_answer = "Demo All-on-4 ответ."
    nika_answer = "Nikadent All-on-4 ответ."
    demo_followup_q = "а рассрочка?"
    backends = [
        _CountingBackend(answer_envelope(demo_answer, service_id="all_on_4")),
        _CountingBackend(answer_envelope(nika_answer, service_id="all_on_4")),
        _CountingBackend(answer_envelope("Продолжение demo.")),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    bind_session_client("demo")
    mem_reset(sid)
    bind_session_client("nikadent")
    mem_reset(sid)
    bind_session_client("demo")
    client = app_module.app.test_client()
    resp_demo = client.post("/ask", json={"q": demo_q, "sid": sid, "client_id": "demo"})
    assert resp_demo.status_code == 200
    visible_demo = str(resp_demo.get_json().get("answer") or "")
    assert visible_demo.strip()
    client.post("/ask", json={"q": nika_q, "sid": sid, "client_id": "nikadent"})
    assert backends[1].invocation is not None
    nika_prompt = str(backends[1].invocation.user_prompt)
    assert nika_q.lower() in nika_prompt.lower()
    assert demo_q.lower() not in nika_prompt.lower()
    assert visible_demo.lower() not in nika_prompt.lower()
    client.post("/ask", json={"q": demo_followup_q, "sid": sid, "client_id": "demo"})
    assert backends[2].invocation is not None
    demo_prompt = str(backends[2].invocation.user_prompt)
    assert demo_followup_q.lower() in demo_prompt.lower()
    assert demo_q.lower() in demo_prompt.lower()
    assert visible_demo.lower() in demo_prompt.lower()
    assert nika_q.lower() not in demo_prompt.lower()
    assert nika_answer.lower() not in demo_prompt.lower()
    bind_session_client("demo")


def test_scope_clarify_preserves_service_and_marketing_session_state(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session

    sid = "scope-clarify-state"
    _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Расскажите про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол имплантации на четырёх имплантах.",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            commercial_intent="none",
        ),
        flask_app=flask_app,
    )
    before = read_target_runtime_session(sid)
    assert before.last_service_id == "all_on_4"
    assert before.shown_fact_ids or before.shown_amplifier_refs

    payload, backend = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ стоит 5000 ₽.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
        flask_app=flask_app,
        allow_terminal=True,
    )
    after = read_target_runtime_session(sid)
    assert after == before
    answer = str(payload.get("answer") or "").lower()
    assert payload["meta"]["service_route"] == "sales_fast_scope_clarify"
    assert "позвоните" not in answer
    assert "администратор" not in answer
    assert "5000" not in answer
    assert payload.get("offer") is None
    assert payload.get("cta") is None
    assert payload.get("video") is None
    assert payload.get("situation", {}).get("show") is False
    assert backend.call_count == 1


def test_http_ask_model_admin_exact_literal_text_and_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.one_call_envelope_protocol import dumps_production_envelope
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    expected = (
        f"{_ADMIN_HANDOFF_BASE_LITERAL} Если ситуация срочная, пожалуйста, позвоните: {demo_phone}."
    )
    backend = _CountingBackend(
        dumps_production_envelope(
            route="ADMIN",
            patient_text=None,
            clarify_axis=None,
            clarify_service_options=None,
        )
    )
    payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="После операции появилось воспаление, подскажите порядок действий",
        sid="admin-demo-literal",
    )
    assert payload["answer"] == expected
    assert payload["quick_replies"] == []
    assert payload.get("cta") is None
    assert payload.get("video") is None
    assert payload.get("offer") is None
    assert payload.get("situation", {}).get("show") is False
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert backend.call_count == 1


def test_http_ask_model_admin_without_phone_exact_literal_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.clinic_contact_policies import ClinicContactFacts
    from core.one_call_envelope_protocol import dumps_production_envelope
    from core.target_contact_authority import canonical_contact_phone

    demo_phone = canonical_contact_phone("demo")
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts",
        lambda _client_id: ClinicContactFacts(
            phone_display="",
            whatsapp_display=None,
            address_display=None,
            hours_display=None,
            parking_display=None,
        ),
    )
    backend = _CountingBackend(
        dumps_production_envelope(
            route="ADMIN",
            patient_text=None,
            clarify_axis=None,
            clarify_service_options=None,
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "После операции появилось воспаление",
            "sid": "admin-no-phone-literal",
            "client_id": "nikadent",
        },
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="nikadent",
            sid="admin-no-phone-literal",
            user_message="После операции появилось воспаление",
            backend=backend,
        )
    payload = dict(outcome.widget.payload or {})
    answer = str(payload.get("answer") or "")
    assert answer == _ADMIN_HANDOFF_BASE_LITERAL
    assert demo_phone not in answer
    assert payload["quick_replies"] == []
    assert payload.get("cta") is None
    assert payload.get("video") is None
    assert payload.get("offer") is None
    assert payload.get("situation", {}).get("show") is False
    assert backend.call_count == 1
