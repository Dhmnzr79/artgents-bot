from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from pydantic import ValidationError

from evals.v5.response_plan_replay import (
    ReplayFatalHarnessError,
    ReplayHarnessError,
    _build_replay_composer_result,
    audit_materialized_provenance_key,
    build_service_value_candidate,
    classify_unexplained_visible_delta,
    detect_expected_contract_change_reasons,
    extract_angle_tagged_json,
    extract_section_json,
    map_config_to_context_strategy,
    normalize_fact_id,
    parse_raw_model_envelope,
    provider_network_calls,
    resolve_captured_composer_route,
    run_replay,
    serialize_artifact_bytes,
    serialize_result_bytes,
    serialize_result_json,
    validate_captured_patient_text_for_route_mode,
    validate_provenance_matrix,
    validate_source_bundle,
    write_replay_outputs,
    render_markdown_report,
    REPLAY_ID,
)
from evals.v5.response_plan_replay_contract import (
    LegacySourceMetadata,
    ReplayComparison,
    ReplayRecordResult,
    SourceHashes,
    SourceKey,
    TargetInputSummary,
    TargetOutputSummary,
    EXPECTED_FACTS_SHA256,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_RAW_TURNS_SHA256,
    EXPECTED_STRUCTURED_TURNS_SHA256,
    sha256_file,
)

FROZEN_ROOT = Path(
    r"C:\Cursor Projects\demo-bot-one-call-baseline-verify-report-parity-1cf8bbd\evals\v5\artifacts\arch_compare\arch_compare_live_v1_2026-08-31-01"
)
FROZEN_FACTS = Path(
    r"C:\Cursor Projects\demo-bot-one-call-baseline-verify-report-parity-1cf8bbd\clients\demo\target_response\pricebook\facts.json"
)
CHECKED_IN_REPLAY_DIR = Path(
    r"C:\Cursor Projects\demo-bot-one-call-baseline\evals\v5\artifacts\response_plan_replay_1cf8bbd_2026-08-31-01"
)
CHECKED_IN_REPORT = Path(
    r"C:\Cursor Projects\demo-bot-one-call-baseline\evals\v5\reports\response_plan_replay_1cf8bbd_2026-08-31-01.md"
)


@pytest.fixture(scope="module")
def frozen_source() -> tuple[Path, Path]:
    if not FROZEN_ROOT.is_file() and not (FROZEN_ROOT / "structured_turns.json").is_file():
        pytest.skip("frozen replay source unavailable")
    if not FROZEN_FACTS.is_file():
        pytest.skip("frozen facts unavailable")
    return FROZEN_ROOT, FROZEN_FACTS


def test_source_hash_mismatch_rejected(tmp_path: Path, frozen_source: tuple[Path, Path]) -> None:
    source_root, facts_path = frozen_source
    broken = tmp_path / "broken"
    broken.mkdir()
    for name in ("structured_turns.json", "raw_turns.json", "manifest.json"):
        (broken / name).write_text((source_root / name).read_text(encoding="utf-8"), encoding="utf-8")
    (broken / "structured_turns.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ReplayHarnessError) as exc:
        validate_source_bundle(broken, facts_path)
    assert exc.value.code == "source_hash_mismatch"


def test_source_count_contract(frozen_source: tuple[Path, Path]) -> None:
    source_root, facts_path = frozen_source
    structured, raw_rows, _manifest, _facts, _hashes = validate_source_bundle(source_root, facts_path)
    assert len(structured) == 76
    assert len(raw_rows) == 76


def test_source_join_missing_duplicate(frozen_source: tuple[Path, Path]) -> None:
    source_root, facts_path = frozen_source
    structured, raw_rows, _, _, _ = validate_source_bundle(source_root, facts_path)
    keys = {
        (row["scenario_id"], row["turn_id"], row["config_id"], row["session_id"]) for row in structured
    }
    raw_keys = {
        (row["scenario_id"], row["turn_id"], row["config_id"], row["session_id"]) for row in raw_rows
    }
    assert len(keys) == 76
    assert keys == raw_keys


def test_config_to_context_strategy_closed_mapping() -> None:
    assert map_config_to_context_strategy("flash_full") == "full_context"
    assert map_config_to_context_strategy("plus_curated") == "hybrid"
    with pytest.raises(ReplayHarnessError):
        map_config_to_context_strategy("unknown_config")


def test_invalid_raw_envelope_json_rejected() -> None:
    with pytest.raises(ReplayHarnessError) as exc:
        parse_raw_model_envelope("{not-json")
    assert exc.value.code == "adapter_error"


def test_strict_tagged_json_extraction() -> None:
    payload = extract_angle_tagged_json(
        '<CLINIC_CONTACT_AUTHORITY>\n{"client_id":"demo","contact":{"phone":"+7"}}\n</CLINIC_CONTACT_AUTHORITY>',
        "CLINIC_CONTACT_AUTHORITY",
    )
    assert payload is not None
    assert payload["client_id"] == "demo"


def test_section_json_extraction() -> None:
    content = '=== SELECTED_EXACT_OFFER ===\n{"availability":"none","offers":[]}\n\n<PRE_MODEL_HINTS>\n{}'
    payload = extract_section_json(content, "SELECTED_EXACT_OFFER")
    assert payload["availability"] == "none"


def test_no_phone_extraction_from_visible_text() -> None:
    visible = "Позвоните: +7 (495) 128-47-60"
    assert extract_angle_tagged_json(visible, "CLINIC_CONTACT_AUTHORITY") is None


def test_no_amount_extraction_from_visible_text() -> None:
    visible = "Стоимость 318 000 ₽"
    assert extract_section_json(visible, "SELECTED_EXACT_OFFER") is None


def test_legacy_direct_ids_not_promoted_to_requested(frozen_source: tuple[Path, Path]) -> None:
    source_root, facts_path = frozen_source
    result = run_replay(source_root, facts_path)
    for record in result.records:
        if record.legacy_source.direct_fact_ids:
            assert record.target_input_summary.requested_fact_ids == ()
            if "commercial_intent_conflict" not in record.capture_gaps:
                assert "legacy_direct_fact_explicitness_not_captured" in record.capture_gaps


def test_automatic_warranty_forbidden(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.target_automatic_warranty_count == 0


def test_fact_prefix_normalization_only_for_existing_frozen_id(frozen_source: tuple[Path, Path]) -> None:
    _source_root, facts_path = frozen_source
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    known = set(facts.keys())
    assert normalize_fact_id("fact:installment_12", known) == "installment_12"
    assert normalize_fact_id("fact:missing", known) is None


def test_missing_unknown_fact_becomes_capture_gap_or_omit(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if record.target_output.resolved:
            assert "implant_warranty" not in record.target_output.finalized_commercial_ids.get(
                "amplifier_fact_ids", ()
            )


def test_missing_scope_not_replayable(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    scope_records = [record for record in result.records if "typed_scope_absent" in record.capture_gaps]
    assert scope_records
    assert all(record.capture_fidelity == "not_replayable" for record in scope_records)


def test_missing_terminal_mode_not_replayable(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    terminal_records = [record for record in result.records if "terminal_mode_not_captured" in record.capture_gaps]
    assert len(terminal_records) == 8
    assert all(record.capture_fidelity == "not_replayable" for record in terminal_records)


def test_no_public_price_not_shoehorned(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if "no_public_price_not_representable" in record.capture_gaps:
            assert record.target_output.price_block_count == 0


def test_missing_required_condition_ids_only_on_price_plans(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        has_condition_gap = "required_offer_condition_ids_not_captured" in record.capture_gaps
        if has_condition_gap and record.target_output.resolved:
            assert record.target_output.price_block_count > 0
            assert record.captured_commercial_intent == "price"
        elif record.target_output.resolved and record.captured_commercial_intent != "price":
            assert "required_offer_condition_ids_not_captured" not in record.capture_gaps


NON_PRICE_SELECTED_OFFER_SCENARIOS = ("SVC-01", "DOC-01")


@pytest.mark.parametrize("scenario_id", NON_PRICE_SELECTED_OFFER_SCENARIOS)
def test_non_price_selected_offers_not_replayable_without_mode_capture(
    frozen_source: tuple[Path, Path], scenario_id: str
) -> None:
    result = run_replay(*frozen_source)
    records = [
        record
        for record in result.records
        if record.source_key.scenario_id == scenario_id
        and record.legacy_source.selected_offer_ids
        and record.captured_commercial_intent != "price"
        and not record.legacy_source.canonical_price_block
        and record.provider_turn
    ]
    assert records, f"expected provider records for {scenario_id}"
    for record in records:
        assert record.capture_fidelity == "not_replayable"
        assert "composer_mode_not_captured" in record.capture_gaps
        assert not record.target_output.resolved
        assert record.target_output.price_block_count == 0


def test_sw01_non_price_records_not_replayable_without_mode_capture(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    records = [
        record
        for record in result.records
        if record.source_key.scenario_id == "SW-01"
        and record.captured_commercial_intent != "price"
        and record.legacy_source.selected_offer_ids
        and not record.legacy_source.canonical_price_block
        and record.provider_turn
    ]
    assert records
    for record in records:
        assert record.capture_fidelity == "not_replayable"
        assert "composer_mode_not_captured" in record.capture_gaps
        assert not record.target_output.resolved
        assert record.target_output.price_block_count == 0


def test_selected_offers_without_price_intent_global_invariant(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if (
            record.captured_commercial_intent == "none"
            and record.legacy_source.selected_offer_ids
            and record.target_output.resolved
        ):
            assert record.target_output.price_block_count == 0
            assert not record.false_price_insertion


def test_legacy_price_block_present_ignores_selected_offer_ids(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if not record.target_output.resolved:
            continue
        if record.legacy_source.selected_offer_ids and not record.legacy_source.canonical_price_block:
            assert record.delta.legacy_price_block_present is False


def test_frozen_service_value_provenance(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if record.field_provenance.get("service_value_text") == "frozen_baseline_lookup":
            assert record.field_provenance.get("service_value_candidate") == "frozen_baseline_lookup"
        if record.field_provenance.get("service_value_text") == "captured_exact":
            assert record.field_provenance.get("service_value_candidate") == "captured_exact"


def test_no_fabricated_defaults_in_replay(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.fabricated_field_count == 0
    for record in result.records:
        assert "fabricated_currency_default" not in record.fabricated_findings
        assert "fabricated_billing_unit_default" not in record.fabricated_findings
        assert "fabricated_quick_reply_id" not in record.fabricated_findings


def test_metrics_match_per_record_aggregates(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    metrics = result.metrics
    assert metrics.false_price_insertion_count == sum(1 for record in result.records if record.false_price_insertion)
    assert metrics.fabricated_field_count == sum(len(record.fabricated_findings) for record in result.records)
    assert metrics.client_isolation_violations == sum(
        1
        for record in result.records
        if any(item.startswith("client_isolation") for item in record.contract_violations)
    )
    assert metrics.missing_required_conditions_count == sum(
        1 for record in result.records if "required_offer_condition_ids_not_captured" in record.capture_gaps
    )
    assert metrics.unexplained_visible_delta_count == sum(
        1 for record in result.records if record.unexplained_visible_delta
    )
    assert metrics.provenance_finding_count == sum(len(record.provenance_findings) for record in result.records)
    assert metrics.unresolved_count == sum(1 for record in result.records if not record.target_output.resolved)
    gap_counter = {}
    for record in result.records:
        for gap in record.capture_gaps:
            gap_counter[gap] = gap_counter.get(gap, 0) + 1
    assert metrics.capture_gap_counts == dict(sorted(gap_counter.items()))


def test_false_price_insertion_count_zero(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.false_price_insertion_count == 0


def test_patient_text_preserved_on_replayed_records(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.patient_text_preserved_count == result.metrics.resolved_count


def test_finalized_session_parity_on_replayed_records(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if not record.target_output.resolved:
            continue
        finalized = record.target_output.finalized_commercial_ids
        assert "price_offer_ids" in finalized
        assert "required_offer_condition_ids" in finalized


def test_all_records_classified(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.unclassified_count == 0
    assert (
        result.metrics.full_count
        + result.metrics.partial_count
        + result.metrics.not_replayable_count
        == 76
    )


def test_deterministic_byte_identical_output(frozen_source: tuple[Path, Path], tmp_path: Path) -> None:
    source_root, facts_path = frozen_source
    first = serialize_result_json(run_replay(source_root, facts_path))
    second = serialize_result_json(run_replay(source_root, facts_path))
    assert first == second
    out = tmp_path / "result.json"
    out.write_text(first, encoding="utf-8")
    assert out.read_text(encoding="utf-8") == second


def test_source_files_unchanged_after_replay(frozen_source: tuple[Path, Path]) -> None:
    source_root, facts_path = frozen_source
    before = {
        "structured": sha256_file(source_root / "structured_turns.json"),
        "raw": sha256_file(source_root / "raw_turns.json"),
        "manifest": sha256_file(source_root / "manifest.json"),
        "facts": sha256_file(facts_path),
    }
    run_replay(source_root, facts_path)
    after = {
        "structured": sha256_file(source_root / "structured_turns.json"),
        "raw": sha256_file(source_root / "raw_turns.json"),
        "manifest": sha256_file(source_root / "manifest.json"),
        "facts": sha256_file(facts_path),
    }
    assert before == after
    assert before["structured"] == EXPECTED_STRUCTURED_TURNS_SHA256
    assert before["raw"] == EXPECTED_RAW_TURNS_SHA256
    assert before["manifest"] == EXPECTED_MANIFEST_SHA256
    assert before["facts"] == EXPECTED_FACTS_SHA256


def test_network_provider_tripwire() -> None:
    original_connect = socket.socket.connect

    def blocked_connect(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("network forbidden in replay tests")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    try:
        before = provider_network_calls()
        result = run_replay(FROZEN_ROOT, FROZEN_FACTS)
        assert result.metrics.provider_network_calls == 0
        assert provider_network_calls() == before
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]


def test_exact_text_mismatch_alone_not_expected_contract_change(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if record.delta.exact_text_match is False and not record.expected_contract_change_reasons:
            assert "expected_contract_change" not in record.delta_classes


def test_expected_contract_change_requires_concrete_reason(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if "expected_contract_change" in record.delta_classes:
            assert record.expected_contract_change_reasons
        if record.expected_contract_change_reasons:
            assert "expected_contract_change" in record.delta_classes


def test_unexplained_visible_delta_tracked_separately(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.unexplained_visible_delta_count == sum(
        1 for record in result.records if record.unexplained_visible_delta
    )
    for record in result.records:
        if record.unexplained_visible_delta:
            assert "unexplained_visible_delta" in record.delta_classes
            assert record.delta.exact_text_match is False


def test_price_intent_missing_metadata_not_replayable(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    missing = [
        record
        for record in result.records
        if record.captured_commercial_intent == "price" and record.price_intent_unresolved
    ]
    assert missing
    for record in missing:
        assert record.capture_fidelity == "not_replayable"
        assert not record.target_output.resolved
        assert record.target_output.price_block_count == 0


def test_resolved_price_intent_has_exactly_one_price_block(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        if record.target_output.resolved and record.captured_commercial_intent == "price":
            assert record.target_output.price_block_count == 1


def test_service_value_missing_everywhere_creates_capture_gap() -> None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    candidate = build_service_value_candidate(
        {"service_value_id": "missing_service_value_id"},
        {},
        "demo",
        capture_gaps=gaps,
        field_provenance=provenance,
    )
    assert candidate is None
    assert "service_value_text_not_captured" in gaps
    assert provenance["service_value_text"] == "not_captured"


def test_service_value_structured_text_is_captured_exact() -> None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    candidate = build_service_value_candidate(
        {"service_value_id": "svc_value", "service_value_text": "Captured text"},
        {},
        "demo",
        capture_gaps=gaps,
        field_provenance=provenance,
    )
    assert candidate is not None
    assert provenance["service_value_text"] == "captured_exact"


def test_service_value_frozen_lookup_provenance() -> None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    candidate = build_service_value_candidate(
        {"service_value_id": "installment_12"},
        {"installment_12": {"text_fact": "Frozen text"}},
        "demo",
        capture_gaps=gaps,
        field_provenance=provenance,
    )
    assert candidate is not None
    assert provenance["service_value_text"] == "frozen_baseline_lookup"


def test_resolved_records_have_required_provenance_keys(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    required = {
        "client_id",
        "session_key.sid",
        "context_strategy",
        "route_authority_kind",
        "route",
        "mode",
        "response_scope",
        "selected_service_id",
        "commercial_intent",
        "transport_kind",
    }
    for record in result.records:
        if not record.target_output.resolved:
            continue
        for key in required:
            assert key in record.field_provenance


def test_provenance_findings_zero_on_successful_replay(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert result.metrics.provenance_finding_count == sum(len(record.provenance_findings) for record in result.records)
    for record in result.records:
        if record.target_output.resolved:
            assert not any("materialized_with_not_captured" in item for item in record.provenance_findings)


def test_unexpected_resolver_error_is_fatal_not_response_plan_violation(
    frozen_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import evals.v5.response_plan_replay as replay_module

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unexpected replay bug")

    monkeypatch.setattr(replay_module, "resolve_captured_composer_route", lambda *a, **k: ("ANSWER", "standard"))
    monkeypatch.setattr(replay_module, "resolve_response_plan", boom)
    with pytest.raises(ReplayHarnessError) as exc:
        run_replay(*frozen_source)
    assert exc.value.code == "fatal_replay_error"


def test_detect_expected_change_reason_unit() -> None:
    reasons = detect_expected_contract_change_reasons(
        resolved=True,
        legacy=LegacySourceMetadata(direct_fact_ids=("implant_warranty",)),
        structured={},
        target_output=TargetOutputSummary(
            resolved=True,
            price_block_count=1,
            finalized_commercial_ids={"price_offer_ids": ("a", "b"), "requested_fact_ids": ()},
        ),
        capture_gaps=["automatic_warranty_suppressed"],
        false_price_insertion=False,
    )
    assert "legacy_direct_facts_not_promoted" in reasons
    assert "combined_multi_price_block" not in reasons


def test_classify_unexplained_visible_delta_unit() -> None:
    assert classify_unexplained_visible_delta(
        resolved=True,
        exact_text_match=False,
        false_price_insertion=False,
        delta_classes=[],
    )
    assert not classify_unexplained_visible_delta(
        resolved=True,
        exact_text_match=True,
        false_price_insertion=False,
        delta_classes=[],
    )


def test_extended_metrics_match_per_record_aggregates(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    metrics = result.metrics
    assert metrics.expected_contract_change_count == sum(
        1 for record in result.records if record.expected_contract_change_reasons
    )
    assert metrics.unresolved_count == sum(1 for record in result.records if not record.target_output.resolved)
    assert metrics.price_intent_without_price_count == sum(
        1 for record in result.records if record.price_intent_unresolved
    )
    reason_counter = {}
    for record in result.records:
        for reason in record.expected_contract_change_reasons:
            reason_counter[reason] = reason_counter.get(reason, 0) + 1
    assert metrics.expected_change_reason_counts == dict(sorted(reason_counter.items()))


def test_unknown_expected_reason_rejected_by_contract() -> None:
    with pytest.raises(ValidationError):
        ReplayRecordResult(
            source_key=SourceKey(
                scenario_id="X",
                turn_id="X_t1",
                config_id="flash_full",
                session_id="s1",
            ),
            source_hashes=SourceHashes(
                structured_turns=EXPECTED_STRUCTURED_TURNS_SHA256,
                raw_turns=EXPECTED_RAW_TURNS_SHA256,
                manifest=EXPECTED_MANIFEST_SHA256,
                facts=EXPECTED_FACTS_SHA256,
            ),
            provider_turn=True,
            capture_fidelity="partial",
            legacy_source=LegacySourceMetadata(),
            target_input_summary=TargetInputSummary(),
            target_output=TargetOutputSummary(),
            delta=ReplayComparison(),
            expected_contract_change_reasons=("not_a_real_reason_code",),  # type: ignore[arg-type]
        )


def test_single_price_alone_not_expected_change(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert "single_price_from_captured_offer" not in result.metrics.expected_change_reason_counts


def test_target_multi_alone_not_legacy_multi_block_change(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    assert "combined_multi_price_block" not in result.metrics.expected_change_reason_counts


def test_expected_reason_does_not_suppress_unexplained_delta(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    both = [
        record
        for record in result.records
        if record.expected_contract_change_reasons and record.unexplained_visible_delta
    ]
    if result.metrics.resolved_count == 0:
        assert not both
    else:
        assert both


def test_missing_price_provenance_detected() -> None:
    from contracts.response_plan import (
        CanonicalSinglePriceCandidate,
        PreComposerPlan,
        PricePlan,
        SessionKey,
        UiPlanCandidates,
    )
    from tests.test_response_plan_contract import composer_route_authority

    field_provenance = {
        "client_id": "captured_exact",
        "price_plan": "derived_from_captured_structure",
        "price_offer_id": "captured_exact",
        "price_amount": "captured_exact",
        "price_currency": "captured_exact",
        "price_billing_unit": "captured_exact",
        "price_display_text": "captured_exact",
    }
    precomposer = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="service",
        selected_service_id="svc",
        price_plan=PricePlan(
            kind="single",
            single=CanonicalSinglePriceCandidate(
                source_client_id="demo",
                offer_id="offer.a",
                display_text="100 ₽",
                amount=100,
                currency="RUB",
                billing_unit="tooth",
            ),
        ),
        ui_candidates=UiPlanCandidates(),
    )
    findings = validate_provenance_matrix(
        field_provenance=field_provenance,
        precomposer=precomposer,
        structured={},
        envelope={},
        resolved_output=None,
        client_id="demo",
    )
    assert "missing_provenance:price.source_client_id" in findings


def test_missing_fact_provenance_detected() -> None:
    from contracts.response_plan import (
        CommercialFactCandidate,
        PreComposerPlan,
        PricePlan,
        SessionKey,
        UiPlanCandidates,
    )
    from tests.test_response_plan_contract import composer_route_authority

    fact = CommercialFactCandidate(
        fact_id="installment_12",
        display_text="Frozen text",
        explicit_only=False,
        allowed_roles=("promo",),
        applicability="clinic_wide",
        allowed_service_ids=(),
        source_client_id="demo",
    )
    field_provenance = {
        "client_id": "captured_exact",
        f"fact:{fact.fact_id}:fact_id": "captured_exact",
        f"fact:{fact.fact_id}:display_text": "frozen_baseline_lookup",
        f"fact:{fact.fact_id}:explicit_only": "frozen_baseline_lookup",
        f"fact:{fact.fact_id}:applicability": "frozen_baseline_lookup",
        f"fact:{fact.fact_id}:allowed_service_ids": "frozen_baseline_lookup",
        f"fact:{fact.fact_id}:requires_implant_scope": "frozen_baseline_lookup",
        f"fact:{fact.fact_id}:source_client_id": "captured_exact",
    }
    precomposer = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="service",
        selected_service_id="svc",
        price_plan=PricePlan(kind="none"),
        commercial_facts=(fact,),
        ui_candidates=UiPlanCandidates(),
    )
    findings = validate_provenance_matrix(
        field_provenance=field_provenance,
        precomposer=precomposer,
        structured={},
        envelope={},
        resolved_output=None,
        client_id="demo",
    )
    assert "missing_provenance:fact:installment_12:allowed_roles" in findings


def test_missing_ui_label_provenance_detected() -> None:
    from contracts.response_plan import PreComposerPlan, PricePlan, SessionKey, UiPlanCandidates, UiQuickReplyCandidate
    from tests.test_response_plan_contract import composer_route_authority

    reply = UiQuickReplyCandidate(source_client_id="demo", reply_id="qr1", label="Label")
    field_provenance = {
        "client_id": "captured_exact",
        "ui_quick_reply:qr1:reply_id": "captured_exact",
        "ui_quick_reply:qr1:source_client_id": "captured_exact",
    }
    precomposer = PreComposerPlan(
        session_key=SessionKey(client_id="demo", sid="s1"),
        context_strategy="full_context",
        route_authority=composer_route_authority(),
        response_scope="service",
        selected_service_id="svc",
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(quick_replies=(reply,)),
    )
    findings = validate_provenance_matrix(
        field_provenance=field_provenance,
        precomposer=precomposer,
        structured={},
        envelope={},
        resolved_output=None,
        client_id="demo",
    )
    assert "missing_provenance:ui_quick_reply:qr1:label" in findings


def test_frozen_fact_roles_provenance_not_captured_exact(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        for key, provenance in record.field_provenance.items():
            if key.endswith(":allowed_roles") or key.endswith(":applicability"):
                assert provenance == "frozen_baseline_lookup"


def test_legacy_block_order_alone_not_expected_change() -> None:
    reasons = detect_expected_contract_change_reasons(
        resolved=True,
        legacy=LegacySourceMetadata(),
        structured={"legacy_block_order": ["patient_text", "price_block", "promo"]},
        target_output=TargetOutputSummary(resolved=True, price_block_count=1),
        capture_gaps=[],
        false_price_insertion=False,
    )
    assert reasons == ()
    assert "contractual_block_order_change" not in reasons


def test_removed_block_order_reason_rejected_by_contract() -> None:
    with pytest.raises(ValidationError):
        ReplayRecordResult(
            source_key=SourceKey(
                scenario_id="X",
                turn_id="X_t1",
                config_id="flash_full",
                session_id="s1",
            ),
            source_hashes=SourceHashes(
                structured_turns=EXPECTED_STRUCTURED_TURNS_SHA256,
                raw_turns=EXPECTED_RAW_TURNS_SHA256,
                manifest=EXPECTED_MANIFEST_SHA256,
                facts=EXPECTED_FACTS_SHA256,
            ),
            provider_turn=True,
            capture_fidelity="partial",
            legacy_source=LegacySourceMetadata(),
            target_input_summary=TargetInputSummary(),
            target_output=TargetOutputSummary(),
            delta=ReplayComparison(),
            expected_contract_change_reasons=("contractual_block_order_change",),  # type: ignore[arg-type]
        )


def test_response_plan_contract_error_not_adapter_error(
    frozen_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import evals.v5.response_plan_replay as replay_module
    from contracts.response_plan import ResponsePlanContractError

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ResponsePlanContractError("model_price_text_missing")

    monkeypatch.setattr(replay_module, "resolve_captured_composer_route", lambda *a, **k: ("ANSWER", "standard"))
    monkeypatch.setattr(replay_module, "resolve_response_plan", boom)
    result = run_replay(*frozen_source)
    assert result.metrics.adapter_error_count == 0
    violating = [record for record in result.records if record.target_output.response_plan_error]
    assert violating
    assert all(record.target_output.adapter_error is None for record in violating)
    assert result.metrics.response_plan_violation_count >= len(violating)
    assert all("response_plan_violation" in record.delta_classes for record in violating)


def test_adapter_error_branch_excludes_contract_violations(
    frozen_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import evals.v5.response_plan_replay as replay_module

    baseline = run_replay(*frozen_source)
    baseline_adapter_count = baseline.metrics.adapter_error_count
    baseline_violation_count = baseline.metrics.response_plan_violation_count

    def forced_adapter_failure(raw_envelope: str | None) -> dict:
        raise replay_module.ReplayHarnessError("synthetic_adapter_failure")

    monkeypatch.setattr(replay_module, "parse_raw_model_envelope", forced_adapter_failure)
    result = run_replay(*frozen_source)

    adapter_records = [record for record in result.records if record.target_output.adapter_error]
    assert adapter_records
    record = adapter_records[0]
    assert record.target_output.adapter_error == "synthetic_adapter_failure"
    assert record.target_output.response_plan_error is None
    assert record.contract_violations == ()
    assert record.delta_classes == ("adapter_error",)
    assert result.metrics.adapter_error_count > baseline_adapter_count
    assert result.metrics.response_plan_violation_count == baseline_violation_count


def _route_capture(envelope: dict[str, object]) -> tuple[str, str] | None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    return resolve_captured_composer_route(envelope, capture_gaps=gaps, field_provenance=provenance)


def test_missing_route_not_defaulted_to_answer() -> None:
    result = _route_capture({"mode": "standard"})
    assert result is None


def test_missing_mode_not_defaulted_to_standard() -> None:
    result = _route_capture({"route": "ANSWER"})
    assert result is None


def test_invalid_route_not_defaulted_to_answer() -> None:
    result = _route_capture({"route": "FOO", "mode": "standard"})
    assert result is None


def test_invalid_pair_not_defaulted_to_answer() -> None:
    result = _route_capture({"route": "CLARIFY", "mode": "contacts"})
    assert result is None


def test_whitespace_padded_route_rejected_without_strip() -> None:
    result = _route_capture({"route": " ANSWER", "mode": "standard"})
    assert result is None


def test_whitespace_padded_mode_rejected_without_strip() -> None:
    result = _route_capture({"route": "ANSWER", "mode": "standard "})
    assert result is None


def test_missing_answer_patient_text_not_replaced_with_empty_string() -> None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    assert not validate_captured_patient_text_for_route_mode(
        route="ANSWER",
        mode="standard",
        patient_text=None,
        capture_gaps=gaps,
        field_provenance=provenance,
    )
    assert "composer_patient_text_not_captured" in gaps


def test_missing_clarify_patient_text_not_replaced_with_default() -> None:
    gaps: list[str] = []
    provenance: dict[str, str] = {}
    assert not validate_captured_patient_text_for_route_mode(
        route="CLARIFY",
        mode="standard",
        patient_text=None,
        capture_gaps=gaps,
        field_provenance=provenance,
    )
    assert "composer_patient_text_not_captured" in gaps


def test_unknown_pair_in_build_replay_composer_result_has_no_fallback() -> None:
    with pytest.raises(ReplayFatalHarnessError):
        _build_replay_composer_result(
            route="CLARIFY",
            mode="contacts",
            patient_text="text",
            price_text=None,
            requested_fact_ids=(),
        )


def test_capture_gap_does_not_increment_adapter_or_violation_counts(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    gap_records = [
        record
        for record in result.records
        if "composer_mode_not_captured" in record.capture_gaps
    ]
    assert gap_records
    assert result.metrics.adapter_error_count == 0
    assert all("adapter_error" not in record.delta_classes for record in gap_records)
    assert all("response_plan_violation" not in record.delta_classes for record in gap_records)
    assert result.metrics.response_plan_violation_count == 0


def test_only_exact_captured_route_mode_get_captured_exact_provenance(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        route_prov = record.field_provenance.get("route")
        mode_prov = record.field_provenance.get("mode")
        if route_prov == "captured_exact" and mode_prov == "captured_exact":
            assert record.target_input_summary.route is not None
            assert record.target_input_summary.mode is not None
        if route_prov == "not_captured" or mode_prov == "not_captured":
            assert not record.target_output.resolved


def test_route_authority_kind_not_masked_as_captured_model_data(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    for record in result.records:
        kind = record.field_provenance.get("route_authority_kind")
        if kind == "target_contract_constant":
            assert kind != "captured_exact"
            assert kind != "derived_from_captured_structure"
        if record.target_output.resolved:
            assert record.field_provenance.get("route_authority_kind") == "target_contract_constant"


def test_record_without_route_mode_does_not_reach_resolver(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    unresolved = [
        record
        for record in result.records
        if "composer_mode_not_captured" in record.capture_gaps
    ]
    assert unresolved
    assert all(not record.target_output.resolved for record in unresolved)
    assert all(record.target_output.response_plan_error is None for record in unresolved)
    assert all(record.target_output.rendered_text is None for record in unresolved)


def test_capture_gap_adapter_contract_fatal_branches_remain_separate(
    frozen_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import evals.v5.response_plan_replay as replay_module
    from contracts.response_plan import ResponsePlanContractError

    baseline = run_replay(*frozen_source)
    gap_only = [
        record
        for record in baseline.records
        if record.capture_fidelity == "not_replayable" and "composer_mode_not_captured" in record.capture_gaps
    ]
    assert gap_only
    assert all(record.delta_classes == ("capture_gap",) for record in gap_only)

    def adapter_boom(raw_envelope: str | None) -> dict:
        raise replay_module.ReplayHarnessError("synthetic_adapter_failure")

    monkeypatch.setattr(replay_module, "parse_raw_model_envelope", adapter_boom)
    adapter_result = run_replay(*frozen_source)
    assert adapter_result.metrics.adapter_error_count > 0
    assert all("adapter_error" in record.delta_classes for record in adapter_result.records if record.target_output.adapter_error)

    def contract_boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ResponsePlanContractError("model_price_text_missing")

    monkeypatch.setattr(replay_module, "parse_raw_model_envelope", parse_raw_model_envelope)
    monkeypatch.setattr(replay_module, "resolve_captured_composer_route", lambda *a, **k: ("ANSWER", "standard"))
    monkeypatch.setattr(replay_module, "resolve_response_plan", contract_boom)
    contract_result = run_replay(*frozen_source)
    assert contract_result.metrics.response_plan_violation_count > 0


def test_target_contract_constant_allowed_only_for_harness_constants() -> None:
    findings: list[str] = []
    audit_materialized_provenance_key(
        {"route_authority_kind": "target_contract_constant"},
        "route_authority_kind",
        findings,
    )
    assert findings == []
    audit_materialized_provenance_key({"route": "target_contract_constant"}, "route", findings)
    assert "materialized_with_not_captured:route" in findings or "invalid_provenance:route" in findings


def test_frozen_snapshot_lacks_exact_route_mode_capture(frozen_source: tuple[Path, Path]) -> None:
    result = run_replay(*frozen_source)
    exact = [
        record
        for record in result.records
        if record.field_provenance.get("route") == "captured_exact"
        and record.field_provenance.get("mode") == "captured_exact"
    ]
    mode_missing = [record for record in result.records if "composer_mode_not_captured" in record.capture_gaps]
    assert not exact
    assert len(mode_missing) == 40
    assert result.metrics.resolved_count == 0


def test_replay_artifact_bytes_use_canonical_crlf() -> None:
    from evals.v5.response_plan_replay_contract import REPLAY_ARTIFACT_NEWLINE

    encoded = serialize_artifact_bytes('{"a": 1}\n')
    assert encoded == b'{"a": 1}\r\n'
    assert REPLAY_ARTIFACT_NEWLINE.encode("utf-8") in encoded
    assert not encoded.startswith(b"\xef\xbb\xbf")


def test_checked_in_artifact_parity(frozen_source: tuple[Path, Path], tmp_path: Path) -> None:
    if not CHECKED_IN_REPLAY_DIR.is_dir():
        pytest.skip("checked-in replay artifacts unavailable")
    source_root, facts_path = frozen_source
    result = run_replay(source_root, facts_path)
    fresh_bytes = serialize_result_bytes(result)
    checked_in_bytes = (CHECKED_IN_REPLAY_DIR / "result.json").read_bytes()
    assert fresh_bytes == checked_in_bytes
    second_bytes = serialize_result_bytes(run_replay(source_root, facts_path))
    assert fresh_bytes == second_bytes

    write_replay_outputs(
        result,
        output_dir=tmp_path / "replay_out",
        source_root=source_root,
        head_sha="1cf8bbd200bddf5732b5723d25dc34fcc1545ac0",
        fail_if_exists=False,
    )
    written_result_bytes = (tmp_path / "replay_out" / "result.json").read_bytes()
    assert written_result_bytes == checked_in_bytes

    manifest_bytes = (CHECKED_IN_REPLAY_DIR / "manifest.json").read_bytes()
    assert (tmp_path / "replay_out" / "manifest.json").read_bytes() == manifest_bytes

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    assert manifest["replay_id"] == REPLAY_ID
    assert manifest["source_hashes"]["structured_turns"] == EXPECTED_STRUCTURED_TURNS_SHA256
    assert manifest["source_hashes"]["raw_turns"] == EXPECTED_RAW_TURNS_SHA256
    assert manifest["source_hashes"]["manifest"] == EXPECTED_MANIFEST_SHA256
    assert manifest["source_hashes"]["facts"] == EXPECTED_FACTS_SHA256

    payload = json.loads(fresh_bytes.decode("utf-8"))
    assert payload["metrics"]["resolved_count"] == 0
    assert payload["metrics"]["not_replayable_count"] == 76
    for record in payload["records"]:
        assert "execution_kind" not in record.get("field_provenance", {})

    if CHECKED_IN_REPORT.is_file():
        report_bytes = CHECKED_IN_REPORT.read_bytes()
        render_markdown_report(result, tmp_path / "report.md")
        assert (tmp_path / "report.md").read_bytes() == report_bytes
        report = report_bytes.decode("utf-8")
        assert f"resolved: {payload['metrics']['resolved_count']}" in report
        assert f"not replayable: {payload['metrics']['not_replayable_count']}" in report
