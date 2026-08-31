"""Offline replay harness for frozen arch_compare captures (RESPONSE-REPLAY-1)."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from collections import Counter
from contextlib import contextmanager
from json import JSONDecodeError, JSONDecoder
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts.response_plan import (
    CanonicalContactCandidate,
    CodeOwnedTerminalCandidate,
    CommercialFactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    FinalizedCommercialIds,
    PreComposerPlan,
    PricePlan,
    ResponsePlanContractError,
    RouteModePair,
    ServiceValueCandidate,
    SessionKey,
    TextualCtaCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
    UiVideoCandidate,
    UiWidgetCandidate,
    all_allowed_route_mode_pairs,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from evals.v5.response_plan_replay_contract import (
    CONFIG_TO_CONTEXT_STRATEGY,
    EXPECTED_CODE_ONLY_TURN_COUNT,
    EXPECTED_FACTS_SHA256,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_PROVIDER_TURN_COUNT,
    EXPECTED_RAW_TURNS_SHA256,
    EXPECTED_RECORD_COUNT,
    EXPECTED_STRUCTURED_TURNS_SHA256,
    ExpectedContractChangeReason,
    LegacySourceMetadata,
    ReplayComparison,
    REPLAY_ARTIFACT_NEWLINE,
    ReplayManifest,
    ReplayMetrics,
    ReplayRecordResult,
    ReplayResult,
    SourceHashes,
    SourceKey,
    TargetInputSummary,
    TargetOutputSummary,
    sha256_file,
)

REPLAY_ID = "response_plan_replay_1cf8bbd_2026-08-31-01"
SOURCE_ATTEMPT_ID = "arch_compare_live_v1_2026-08-31-01"
DEFAULT_SOURCE_SUBPATH = Path("evals/v5/artifacts/arch_compare/arch_compare_live_v1_2026-08-31-01")
DEFAULT_FACTS_SUBPATH = Path("clients/demo/target_response/pricebook/facts.json")

FACT_PREFIX = "fact:"
PRICE_INTENT_VALUE = "price"
VALID_MATERIALIZED_PROVENANCE = frozenset(
    {
        "captured_exact",
        "derived_from_captured_structure",
        "frozen_baseline_lookup",
        "target_contract_constant",
    }
)
TARGET_CONTRACT_CONSTANT_KEYS = frozenset({"route_authority_kind"})
_PROVIDER_NETWORK_CALLS = 0


class ReplayHarnessError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}: {detail}")


class ReplayFatalHarnessError(ReplayHarnessError):
    """Unexpected programming error during replay; must not be masked as architecture violation."""


def extract_angle_tagged_json(content: str, tag: str) -> dict[str, Any] | None:
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    start = content.find(open_tag)
    if start < 0:
        return None
    start += len(open_tag)
    end = content.find(close_tag, start)
    if end < 0:
        return None
    payload = content[start:end].strip()
    return json.loads(payload)


def extract_section_json(content: str, section: str) -> dict[str, Any] | None:
    marker = f"=== {section} ==="
    if marker not in content:
        return None
    rest = content.split(marker, 1)[1].lstrip("\n")
    decoder = JSONDecoder()
    payload, _ = decoder.raw_decode(rest)
    if not isinstance(payload, dict):
        raise ReplayHarnessError("adapter_error", "section_json_not_object")
    return payload


@contextmanager
def offline_replay_guard() -> Any:
    global _PROVIDER_NETWORK_CALLS
    prior = _PROVIDER_NETWORK_CALLS
    original_connect = socket.socket.connect

    def blocked_connect(self, *args: Any, **kwargs: Any) -> None:
        global _PROVIDER_NETWORK_CALLS
        _PROVIDER_NETWORK_CALLS += 1
        raise OSError("network_forbidden_in_offline_replay")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        _PROVIDER_NETWORK_CALLS = prior


def provider_network_calls() -> int:
    return _PROVIDER_NETWORK_CALLS


def map_config_to_context_strategy(config_id: str) -> str:
    try:
        return CONFIG_TO_CONTEXT_STRATEGY[config_id]
    except KeyError as exc:
        raise ReplayHarnessError("adapter_error", "unknown_config_id") from exc


def normalize_fact_id(raw_id: str, known_ids: set[str]) -> str | None:
    candidate = raw_id.strip()
    if not candidate:
        return None
    if candidate.startswith(FACT_PREFIX):
        normalized = candidate[len(FACT_PREFIX) :]
        if normalized in known_ids:
            return normalized
        return None
    if candidate in known_ids:
        return candidate
    return None


def parse_raw_model_envelope(raw_envelope: str | None) -> dict[str, Any]:
    if raw_envelope is None:
        raise ReplayHarnessError("adapter_error", "missing_raw_model_envelope")
    try:
        payload = json.loads(raw_envelope)
    except JSONDecodeError as exc:
        raise ReplayHarnessError("adapter_error", "invalid_raw_model_envelope_json") from exc
    if not isinstance(payload, dict):
        raise ReplayHarnessError("adapter_error", "raw_model_envelope_not_object")
    return payload


def load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ReplayHarnessError("source_invalid", f"{path.name}_not_list")
    return payload


def record_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (row["scenario_id"], row["turn_id"], row["config_id"], row["session_id"])


def validate_source_bundle(
    source_root: Path,
    facts_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], SourceHashes]:
    structured_path = source_root / "structured_turns.json"
    raw_path = source_root / "raw_turns.json"
    manifest_path = source_root / "manifest.json"
    for path in (structured_path, raw_path, manifest_path, facts_path):
        if not path.is_file():
            raise ReplayHarnessError("source_missing", str(path))

    hashes = SourceHashes(
        structured_turns=sha256_file(structured_path),
        raw_turns=sha256_file(raw_path),
        manifest=sha256_file(manifest_path),
        facts=sha256_file(facts_path),
    )
    if hashes.structured_turns != EXPECTED_STRUCTURED_TURNS_SHA256:
        raise ReplayHarnessError("source_hash_mismatch", "structured_turns")
    if hashes.raw_turns != EXPECTED_RAW_TURNS_SHA256:
        raise ReplayHarnessError("source_hash_mismatch", "raw_turns")
    if hashes.manifest != EXPECTED_MANIFEST_SHA256:
        raise ReplayHarnessError("source_hash_mismatch", "manifest")
    if hashes.facts != EXPECTED_FACTS_SHA256:
        raise ReplayHarnessError("source_hash_mismatch", "facts")

    structured = load_json_list(structured_path)
    raw_rows = load_json_list(raw_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    facts = json.loads(facts_path.read_text(encoding="utf-8"))

    if len(structured) != EXPECTED_RECORD_COUNT:
        raise ReplayHarnessError("source_count_mismatch", "structured")
    if len(raw_rows) != EXPECTED_RECORD_COUNT:
        raise ReplayHarnessError("source_count_mismatch", "raw")

    structured_keys = [record_key(row) for row in structured]
    raw_keys = [record_key(row) for row in raw_rows]
    if len(set(structured_keys)) != EXPECTED_RECORD_COUNT:
        raise ReplayHarnessError("source_duplicate_keys", "structured")
    if len(set(raw_keys)) != EXPECTED_RECORD_COUNT:
        raise ReplayHarnessError("source_duplicate_keys", "raw")
    if set(structured_keys) != set(raw_keys):
        raise ReplayHarnessError("source_join_mismatch")

    provider_count = sum(1 for row in structured if row.get("provider_turn"))
    code_only_count = EXPECTED_RECORD_COUNT - provider_count
    if provider_count != EXPECTED_PROVIDER_TURN_COUNT:
        raise ReplayHarnessError("source_count_mismatch", "provider_turn")
    if code_only_count != EXPECTED_CODE_ONLY_TURN_COUNT:
        raise ReplayHarnessError("source_count_mismatch", "code_only_turn")

    return structured, raw_rows, manifest, facts, hashes


def user_message_content(raw_row: dict[str, Any]) -> str:
    outbound = raw_row.get("outbound_payload") or {}
    for message in outbound.get("messages", []):
        if message.get("role") == "user":
            return message.get("content") or ""
    return ""


def build_fact_catalog(
    facts: dict[str, Any],
    client_id: str,
    fact_ids: set[str],
    *,
    field_provenance: dict[str, str],
) -> dict[str, CommercialFactCandidate]:
    catalog: dict[str, CommercialFactCandidate] = {}
    for fact_id in fact_ids:
        entry = facts.get(fact_id)
        if entry is None:
            continue
        kind = entry.get("kind")
        allowed_roles: list[str] = []
        explicit_only = fact_id in {"implant_warranty", "clinic_warranty"}
        if explicit_only:
            allowed_roles.append("requested_fact")
        if kind == "promo":
            allowed_roles.append("promo")
        if kind in {"benefit", "payment"}:
            allowed_roles.append("automatic_amplifier")
        if fact_id == "implant_warranty":
            allowed_roles = ["requested_fact"]
            explicit_only = True
        if not allowed_roles:
            continue
        service_ids = tuple(entry.get("allowed_service_ids") or ())
        applicability = "service_scoped" if service_ids else "clinic_wide"
        field_provenance[f"fact:{fact_id}:fact_id"] = "captured_exact"
        field_provenance[f"fact:{fact_id}:display_text"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:allowed_roles"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:applicability"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:allowed_service_ids"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:explicit_only"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:requires_implant_scope"] = "frozen_baseline_lookup"
        field_provenance[f"fact:{fact_id}:source_client_id"] = "captured_exact"
        catalog[fact_id] = CommercialFactCandidate(
            fact_id=fact_id,
            display_text=entry["text_fact"],
            explicit_only=explicit_only,
            allowed_roles=tuple(dict.fromkeys(allowed_roles)),
            applicability=applicability,
            allowed_service_ids=service_ids,
            source_client_id=client_id,
            requires_implant_scope=fact_id == "implant_warranty",
        )
    return catalog


def build_service_value_candidate(
    structured: dict[str, Any],
    facts: dict[str, Any],
    client_id: str,
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> ServiceValueCandidate | None:
    service_value_id = structured.get("service_value_id")
    if not service_value_id:
        return None
    field_provenance["service_value_id"] = "captured_exact"
    text = structured.get("service_value_text")
    if text:
        field_provenance["service_value_text"] = "captured_exact"
    elif service_value_id in facts:
        text = facts[service_value_id]["text_fact"]
        field_provenance["service_value_text"] = "frozen_baseline_lookup"
    else:
        capture_gaps.append("service_value_text_not_captured")
        field_provenance["service_value_text"] = "not_captured"
        return None
    field_provenance["service_value.source_client_id"] = "captured_exact"
    return ServiceValueCandidate(
        fact_id=service_value_id,
        display_text=text,
        source_client_id=client_id,
    )


def build_ui_candidates(
    structured: dict[str, Any],
    client_id: str,
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> UiPlanCandidates:
    metadata = structured.get("cta_ui_metadata") or {}
    quick_replies: list[UiQuickReplyCandidate] = []
    for item in metadata.get("quick_replies") or []:
        label = item.get("label")
        if not label:
            continue
        reply_id = item.get("ref")
        if not reply_id:
            capture_gaps.append("quick_reply_id_not_captured")
            field_provenance["ui_quick_replies"] = "not_captured"
            continue
        field_provenance[f"ui_quick_reply:{reply_id}:reply_id"] = "captured_exact"
        field_provenance[f"ui_quick_reply:{reply_id}:label"] = "captured_exact"
        field_provenance[f"ui_quick_reply:{reply_id}:source_client_id"] = "captured_exact"
        quick_replies.append(
            UiQuickReplyCandidate(
                source_client_id=client_id,
                reply_id=reply_id,
                label=label,
            )
        )
    if quick_replies:
        field_provenance["ui_quick_replies"] = "captured_exact"
    return UiPlanCandidates(quick_replies=tuple(quick_replies), widget=None, video=None)


def format_amount(amount: int, currency: str) -> str:
    if currency == "RUB":
        formatted = f"{amount:,}".replace(",", "\u00a0").replace("\u00a0", " ")
        return f"{formatted} ₽"
    return f"{amount} {currency}"


def resolve_captured_commercial_intent(
    pre_model_hints: dict[str, Any] | None,
    envelope: dict[str, Any],
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> str | None:
    hints_intent = pre_model_hints.get("commercial_intent") if pre_model_hints else None
    envelope_intent = envelope.get("commercial_intent")
    if hints_intent is not None:
        field_provenance["commercial_intent_hints"] = "captured_exact"
    if envelope_intent is not None:
        field_provenance["commercial_intent_envelope"] = "captured_exact"
    if hints_intent is None and envelope_intent is None:
        capture_gaps.append("commercial_intent_not_captured")
        field_provenance["commercial_intent"] = "not_captured"
        return None
    if hints_intent is not None and envelope_intent is not None and hints_intent != envelope_intent:
        capture_gaps.append("commercial_intent_conflict")
        field_provenance["commercial_intent"] = "not_captured"
        return None
    intent = hints_intent if hints_intent is not None else envelope_intent
    field_provenance["commercial_intent"] = (
        "captured_exact" if hints_intent == intent else "derived_from_captured_structure"
    )
    return str(intent)


def normalize_offer_entries(offer_payload: dict[str, Any]) -> list[dict[str, Any]]:
    offers = offer_payload.get("offers")
    if isinstance(offers, list) and offers:
        return [offer for offer in offers if isinstance(offer, dict)]
    if offer_payload.get("offer_id"):
        return [offer_payload]
    return []


def require_offer_field(
    offer: dict[str, Any],
    field: str,
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
    provenance_key: str,
) -> Any:
    value = offer.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        capture_gaps.append("exact_offer_metadata_not_captured")
        field_provenance[provenance_key] = "not_captured"
        return None
    field_provenance[provenance_key] = "captured_exact"
    return value


def build_price_plan(
    structured: dict[str, Any],
    offer_payload: dict[str, Any] | None,
    client_id: str,
    *,
    captured_commercial_intent: str | None,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> PricePlan:
    from contracts.response_plan import CanonicalMultiPriceCandidate, CanonicalSinglePriceCandidate

    if captured_commercial_intent != PRICE_INTENT_VALUE:
        field_provenance["price_plan"] = "captured_exact"
        return PricePlan(kind="none")

    if offer_payload is None:
        capture_gaps.append("exact_offer_metadata_not_captured")
        field_provenance["price_plan"] = "not_captured"
        return PricePlan(kind="none")

    availability = offer_payload.get("availability")
    field_provenance["price_availability"] = "captured_exact"
    if availability == "no_public_price":
        capture_gaps.append("no_public_price_not_representable")
        field_provenance["price_plan"] = "not_captured"
        return PricePlan(kind="none")

    offers = normalize_offer_entries(offer_payload)
    if availability in {"none", None} or not offers:
        if captured_commercial_intent == PRICE_INTENT_VALUE:
            capture_gaps.append("exact_offer_metadata_not_captured")
        field_provenance["price_plan"] = "not_captured"
        return PricePlan(kind="none")

    canonical_price_block = structured.get("canonical_price_block")
    if isinstance(canonical_price_block, str) and canonical_price_block.strip():
        field_provenance["price_display_text"] = "captured_exact"
        display_text = canonical_price_block.strip()
    else:
        display_text = None

    if availability == "selected" and len(offers) == 1:
        offer = offers[0]
        offer_id = require_offer_field(
            offer, "offer_id", capture_gaps=capture_gaps, field_provenance=field_provenance, provenance_key="price_offer_id"
        )
        amount_raw = require_offer_field(
            offer, "amount", capture_gaps=capture_gaps, field_provenance=field_provenance, provenance_key="price_amount"
        )
        currency = require_offer_field(
            offer, "currency", capture_gaps=capture_gaps, field_provenance=field_provenance, provenance_key="price_currency"
        )
        billing_unit = require_offer_field(
            offer,
            "billing_unit",
            capture_gaps=capture_gaps,
            field_provenance=field_provenance,
            provenance_key="price_billing_unit",
        )
        if None in {offer_id, amount_raw, currency, billing_unit}:
            field_provenance["price_plan"] = "not_captured"
            return PricePlan(kind="none")
        if display_text is None:
            package_label = offer.get("package_label")
            if isinstance(package_label, str) and package_label.strip():
                display_text = f"{format_amount(int(amount_raw), str(currency))} {package_label.strip()}"
                field_provenance["price_display_text"] = "derived_from_captured_structure"
            else:
                capture_gaps.append("exact_offer_metadata_not_captured")
                field_provenance["price_plan"] = "not_captured"
                return PricePlan(kind="none")
        field_provenance["price_plan"] = "derived_from_captured_structure"
        field_provenance["price.source_client_id"] = "captured_exact"
        return PricePlan(
            kind="single",
            single=CanonicalSinglePriceCandidate(
                source_client_id=client_id,
                offer_id=str(offer_id),
                display_text=display_text,
                amount=int(amount_raw),
                currency=str(currency),
                billing_unit=str(billing_unit),
            ),
        )

    if availability == "multiple" and 2 <= len(offers) <= 3:
        offer_ids: list[str] = []
        for index, offer in enumerate(offers[:3]):
            offer_id = require_offer_field(
                offer,
                "offer_id",
                capture_gaps=capture_gaps,
                field_provenance=field_provenance,
                provenance_key=f"price_offer_id:{index}",
            )
            amount_raw = require_offer_field(
                offer,
                "amount",
                capture_gaps=capture_gaps,
                field_provenance=field_provenance,
                provenance_key=f"price_amount:{index}",
            )
            currency = require_offer_field(
                offer,
                "currency",
                capture_gaps=capture_gaps,
                field_provenance=field_provenance,
                provenance_key=f"price_currency:{index}",
            )
            if None in {offer_id, amount_raw, currency}:
                field_provenance["price_plan"] = "not_captured"
                return PricePlan(kind="none")
            offer_ids.append(str(offer_id))
        if display_text is None:
            lines: list[str] = []
            for offer in offers[:3]:
                label = offer.get("option_label") or offer.get("offer_id")
                if label is None or not str(label).strip():
                    capture_gaps.append("exact_offer_metadata_not_captured")
                    field_provenance["price_plan"] = "not_captured"
                    return PricePlan(kind="none")
                currency = offer.get("currency")
                amount = offer.get("amount")
                if currency is None or amount is None:
                    capture_gaps.append("exact_offer_metadata_not_captured")
                    field_provenance["price_plan"] = "not_captured"
                    return PricePlan(kind="none")
                lines.append(f"- {label} — {format_amount(int(amount), str(currency))}")
            display_text = "\n".join(lines)
            field_provenance["price_display_text"] = "derived_from_captured_structure"
        field_provenance["price_plan"] = "derived_from_captured_structure"
        field_provenance["price.source_client_id"] = "captured_exact"
        return PricePlan(
            kind="multi",
            multi=CanonicalMultiPriceCandidate(
                source_client_id=client_id,
                offer_ids=tuple(offer_ids),
                display_text=display_text,
            ),
        )

    capture_gaps.append("exact_offer_metadata_not_captured")
    field_provenance["price_plan"] = "not_captured"
    return PricePlan(kind="none")


def legacy_price_block_present(legacy: LegacySourceMetadata) -> bool:
    return bool(legacy.canonical_price_block and legacy.canonical_price_block.strip())


def legacy_separate_price_blocks_captured(structured: dict[str, Any]) -> bool:
    """True only when structured capture explicitly records multiple legacy price blocks."""
    legacy_blocks = structured.get("legacy_separate_price_blocks")
    if isinstance(legacy_blocks, list) and len(legacy_blocks) >= 2:
        return True
    return False


def detect_expected_contract_change_reasons(
    *,
    resolved: bool,
    legacy: LegacySourceMetadata,
    structured: dict[str, Any],
    target_output: TargetOutputSummary,
    capture_gaps: list[str],
    false_price_insertion: bool,
) -> tuple[ExpectedContractChangeReason, ...]:
    if not resolved or false_price_insertion:
        return ()
    reasons: list[ExpectedContractChangeReason] = []
    finalized = target_output.finalized_commercial_ids
    requested_ids = finalized.get("requested_fact_ids", ())
    promo_ids = set(finalized.get("promo_fact_ids", ()))
    amplifier_ids = set(finalized.get("amplifier_fact_ids", ()))
    if legacy.direct_fact_ids and not requested_ids:
        unpromoted = [
            fact_id
            for fact_id in legacy.direct_fact_ids
            if fact_id not in promo_ids and fact_id not in amplifier_ids
        ]
        if unpromoted:
            reasons.append("legacy_direct_facts_not_promoted")
    if (
        "automatic_warranty_suppressed" in capture_gaps
        and "implant_warranty" in legacy.amplifier_fact_ids
    ):
        reasons.append("automatic_warranty_suppressed")
    price_offer_ids = finalized.get("price_offer_ids", ())
    if (
        len(price_offer_ids) > 1
        and legacy_separate_price_blocks_captured(structured)
        and target_output.price_block_count == 1
    ):
        reasons.append("combined_multi_price_block")
    return tuple(dict.fromkeys(reasons))


def classify_unexplained_visible_delta(
    *,
    resolved: bool,
    exact_text_match: bool | None,
    false_price_insertion: bool,
    delta_classes: list[str],
) -> bool:
    if not resolved or false_price_insertion:
        return False
    if "response_plan_violation" in delta_classes or "fatal_replay_error" in delta_classes:
        return False
    if exact_text_match is True:
        return False
    return exact_text_match is False


def audit_materialized_provenance_key(
    field_provenance: dict[str, str],
    key: str,
    findings: list[str],
) -> None:
    value = field_provenance.get(key)
    if value is None:
        findings.append(f"missing_provenance:{key}")
        return
    if value == "not_captured":
        findings.append(f"materialized_with_not_captured:{key}")
        return
    if value not in VALID_MATERIALIZED_PROVENANCE:
        findings.append(f"invalid_provenance:{key}")
        return
    if value == "target_contract_constant" and key not in TARGET_CONTRACT_CONSTANT_KEYS:
        findings.append(f"invalid_provenance:{key}")
        return
    if value == "captured_exact" and key.endswith(":display_text") and key.startswith("fact:"):
        findings.append(f"frozen_lookup_marked_captured:{key}")


RESOLVED_REQUIRED_PROVENANCE_KEYS: tuple[str, ...] = (
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
)


def validate_provenance_matrix(
    *,
    field_provenance: dict[str, str],
    precomposer: PreComposerPlan,
    structured: dict[str, Any],
    envelope: dict[str, Any],
    resolved_output: Any | None,
    client_id: str,
) -> tuple[str, ...]:
    findings: list[str] = []
    for key in RESOLVED_REQUIRED_PROVENANCE_KEYS:
        audit_materialized_provenance_key(field_provenance, key, findings)

    if precomposer.price_plan.kind == "single" and precomposer.price_plan.single is not None:
        for key in (
            "price_plan",
            "price_offer_id",
            "price_amount",
            "price_currency",
            "price_billing_unit",
            "price_display_text",
            "price.source_client_id",
        ):
            audit_materialized_provenance_key(field_provenance, key, findings)
        if precomposer.price_plan.single.source_client_id != client_id:
            findings.append("client_isolation_price_single")

    if precomposer.price_plan.kind == "multi" and precomposer.price_plan.multi is not None:
        for key in ("price_plan", "price_display_text", "price.source_client_id"):
            audit_materialized_provenance_key(field_provenance, key, findings)
        for index in range(len(precomposer.price_plan.multi.offer_ids)):
            for key in (f"price_offer_id:{index}", f"price_amount:{index}", f"price_currency:{index}"):
                audit_materialized_provenance_key(field_provenance, key, findings)
        if precomposer.price_plan.multi.source_client_id != client_id:
            findings.append("client_isolation_price_multi")

    for fact in precomposer.commercial_facts:
        prefix = f"fact:{fact.fact_id}"
        for suffix in (
            "fact_id",
            "display_text",
            "explicit_only",
            "allowed_roles",
            "applicability",
            "allowed_service_ids",
            "requires_implant_scope",
            "source_client_id",
        ):
            audit_materialized_provenance_key(field_provenance, f"{prefix}:{suffix}", findings)
        if fact.source_client_id != client_id:
            findings.append("client_isolation_fact")

    if precomposer.service_value_candidate is not None:
        for key in ("service_value_id", "service_value_text", "service_value.source_client_id"):
            audit_materialized_provenance_key(field_provenance, key, findings)
        if precomposer.service_value_candidate.source_client_id != client_id:
            findings.append("client_isolation_service_value")

    for reply in precomposer.ui_candidates.quick_replies:
        prefix = f"ui_quick_reply:{reply.reply_id}"
        for suffix in ("reply_id", "label", "source_client_id"):
            audit_materialized_provenance_key(field_provenance, f"{prefix}:{suffix}", findings)
        if reply.source_client_id != client_id:
            findings.append("client_isolation_quick_reply")

    if structured.get("patient_text"):
        audit_materialized_provenance_key(field_provenance, "patient_text", findings)
    if envelope.get("price_text"):
        audit_materialized_provenance_key(field_provenance, "composer.price_text", findings)

    if resolved_output is not None and resolved_output.price_block is not None:
        audit_materialized_provenance_key(field_provenance, "price_plan", findings)

    return tuple(dict.fromkeys(findings))


def audit_fabricated_findings(
    *,
    field_provenance: dict[str, str],
    precomposer: PreComposerPlan,
    client_id: str,
) -> list[str]:
    findings: list[str] = []
    if precomposer.price_plan.kind == "single" and precomposer.price_plan.single is not None:
        single = precomposer.price_plan.single
        if single.currency == "RUB" and field_provenance.get("price_currency") != "captured_exact":
            findings.append("fabricated_currency_default")
        if single.billing_unit == "unknown" and field_provenance.get("price_billing_unit") != "captured_exact":
            findings.append("fabricated_billing_unit_default")
    for reply in precomposer.ui_candidates.quick_replies:
        if reply.reply_id == "quick_reply":
            findings.append("fabricated_quick_reply_id")
    for key, provenance in field_provenance.items():
        if key == "service_value_candidate" and provenance == "captured_exact":
            if field_provenance.get("service_value_text") == "frozen_baseline_lookup":
                findings.append("service_value_provenance_mismatch")
    return findings


def collect_legacy_direct_fact_ids(envelope: dict[str, Any] | None) -> tuple[str, ...]:
    if envelope is None:
        return ()
    references = envelope.get("references") or {}
    direct = references.get("direct_fact_ids") or []
    return tuple(str(item) for item in direct if str(item).strip())


def build_replay_route_authority(client_id: str) -> ComposerSelectedRouteAuthority:
    contact = CanonicalContactCandidate(source_client_id=client_id, phone="+7 (000) 000-00-00")
    return ComposerSelectedRouteAuthority(
        allowed_route_modes=all_allowed_route_mode_pairs(),
        terminal_candidates=(
            CodeOwnedTerminalCandidate(
                source_client_id=client_id,
                route="ANSWER",
                mode="contacts",
                authority="contacts",
                display_text="Контакты",
                canonical_contact=contact,
            ),
            CodeOwnedTerminalCandidate(
                source_client_id=client_id,
                route="ADMIN",
                mode="standard",
                authority="governed_ui",
                display_text="ADMIN",
                canonical_contact=contact,
            ),
            CodeOwnedTerminalCandidate(
                source_client_id=client_id,
                route="ADMIN",
                mode="medical_terminal",
                authority="deterministic_policy_terminal",
                display_text="MEDICAL",
                canonical_contact=contact,
            ),
        ),
    )


def resolve_captured_composer_route(
    envelope: dict[str, Any],
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> tuple[str, str] | None:
    route = envelope.get("route")
    mode = envelope.get("mode")
    route_valid = False
    mode_valid = False

    if route is None:
        capture_gaps.append("composer_route_not_captured")
        field_provenance["route"] = "not_captured"
    elif not isinstance(route, str) or route != route.strip() or not route:
        capture_gaps.append("composer_route_mode_invalid")
        field_provenance["route"] = "not_captured"
    else:
        route_valid = True
        field_provenance["route"] = "captured_exact"

    if mode is None:
        capture_gaps.append("composer_mode_not_captured")
        field_provenance["mode"] = "not_captured"
    elif not isinstance(mode, str) or mode != mode.strip() or not mode:
        capture_gaps.append("composer_route_mode_invalid")
        field_provenance["mode"] = "not_captured"
    else:
        mode_valid = True
        field_provenance["mode"] = "captured_exact"

    if not route_valid or not mode_valid:
        return None

    try:
        RouteModePair(route=route, mode=mode)
    except ValidationError:
        capture_gaps.append("composer_route_mode_invalid")
        field_provenance["route"] = "not_captured"
        field_provenance["mode"] = "not_captured"
        return None

    return route, mode


def validate_captured_patient_text_for_route_mode(
    *,
    route: str,
    mode: str,
    patient_text: object,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> bool:
    if (route, mode) not in {("ANSWER", "standard"), ("CLARIFY", "standard")}:
        return True
    if not isinstance(patient_text, str) or not patient_text:
        capture_gaps.append("composer_patient_text_not_captured")
        field_provenance["patient_text"] = "not_captured"
        return False
    field_provenance["patient_text"] = "captured_exact"
    return True


def _build_replay_composer_result(
    *,
    route: str,
    mode: str,
    patient_text: str | None,
    price_text: str | None,
    requested_fact_ids: tuple[str, ...],
) -> ComposerResult:
    pair = (route, mode)
    if pair == ("ANSWER", "standard"):
        return ComposerResult(
            route=route,
            mode=mode,
            patient_text=patient_text,
            price_text=price_text,
            requested_fact_ids=requested_fact_ids,
        )
    if pair == ("ANSWER", "contacts"):
        return ComposerResult(route=route, mode=mode, patient_text=None)
    if pair == ("ADMIN", "standard"):
        return ComposerResult(route=route, mode=mode, patient_text=None)
    if pair == ("ADMIN", "medical_terminal"):
        return ComposerResult(route=route, mode=mode, patient_text=None)
    if pair == ("CLARIFY", "standard"):
        return ComposerResult(route=route, mode=mode, patient_text=patient_text)
    raise ReplayFatalHarnessError("fatal_replay_error", f"unknown_route_mode_pair:{route}+{mode}")


def classify_not_replayable(
    structured: dict[str, Any],
    *,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
) -> str | None:
    route = structured.get("route")
    if route in {"ADMIN", "LOCAL"} or not structured.get("provider_turn"):
        capture_gaps.append("terminal_mode_not_captured")
        field_provenance["terminal_mode"] = "not_captured"
        field_provenance["route_authority_kind"] = "not_captured"
        return "terminal_mode_not_captured"
    return None


def build_replay_record(
    structured: dict[str, Any],
    raw_row: dict[str, Any],
    facts: dict[str, Any],
    source_hashes: SourceHashes,
) -> ReplayRecordResult:
    key = SourceKey(
        scenario_id=structured["scenario_id"],
        turn_id=structured["turn_id"],
        config_id=structured["config_id"],
        session_id=structured["session_id"],
    )
    capture_gaps: list[str] = []
    field_provenance: dict[str, str] = {}
    contract_violations: list[str] = []
    delta_classes: list[str] = []

    legacy_envelope = None
    legacy_direct_ids: tuple[str, ...] = ()
    if structured.get("raw_model_envelope"):
        try:
            legacy_envelope = parse_raw_model_envelope(structured.get("raw_model_envelope"))
            legacy_direct_ids = collect_legacy_direct_fact_ids(legacy_envelope)
        except ReplayHarnessError:
            legacy_envelope = None

    legacy = LegacySourceMetadata(
        route=structured.get("route"),
        patient_text=structured.get("patient_text"),
        visible_answer=structured.get("visible_answer"),
        direct_fact_ids=legacy_direct_ids,
        promo_fact_ids=tuple(structured.get("promo_fact_ids") or []),
        amplifier_fact_ids=tuple(structured.get("amplifier_fact_ids") or []),
        service_value_id=structured.get("service_value_id"),
        selected_offer_ids=tuple(structured.get("selected_offer_ids") or []),
        canonical_price_block=structured.get("canonical_price_block")
        if isinstance(structured.get("canonical_price_block"), str)
        else None,
        provider_turn=bool(structured.get("provider_turn")),
        turn_error=raw_row.get("turn_error"),
        error_code=structured.get("error_code"),
    )

    not_replayable_reason = classify_not_replayable(structured, capture_gaps=capture_gaps, field_provenance=field_provenance)
    if not_replayable_reason:
        if legacy_direct_ids:
            capture_gaps.append("legacy_direct_fact_explicitness_not_captured")
        return ReplayRecordResult(
            source_key=key,
            source_hashes=source_hashes,
            provider_turn=bool(structured.get("provider_turn")),
            context_strategy=None,
            capture_fidelity="not_replayable",
            capture_gaps=tuple(dict.fromkeys(capture_gaps)),
            field_provenance=field_provenance,
            legacy_source=legacy,
            target_input_summary=TargetInputSummary(),
            target_output=TargetOutputSummary(),
            delta=ReplayComparison(legacy_visible_answer=legacy.visible_answer),
            delta_classes=("capture_gap",),
            contract_violations=tuple(contract_violations),
        )

    try:
        context_strategy = map_config_to_context_strategy(structured["config_id"])
        field_provenance["context_strategy"] = "captured_exact"
    except ReplayHarnessError as exc:
        capture_gaps.append("unknown_config_id")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer, exc.code
        )

    user_content = user_message_content(raw_row)
    try:
        clinic_authority = extract_angle_tagged_json(user_content, "CLINIC_CONTACT_AUTHORITY")
    except JSONDecodeError as exc:
        raise ReplayHarnessError("adapter_error", "invalid_clinic_contact_authority_json") from exc
    if clinic_authority is None:
        capture_gaps.append("client_authority_not_captured")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )
    client_id = clinic_authority.get("client_id")
    if not client_id:
        capture_gaps.append("client_authority_not_captured")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )
    field_provenance["client_id"] = "captured_exact"

    try:
        envelope = parse_raw_model_envelope(structured.get("raw_model_envelope"))
    except ReplayHarnessError as exc:
        return _adapter_error_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer, exc.code
        )

    try:
        pre_model_hints = extract_angle_tagged_json(user_content, "PRE_MODEL_HINTS")
    except JSONDecodeError as exc:
        raise ReplayHarnessError("adapter_error", "invalid_pre_model_hints_json") from exc
    if pre_model_hints is not None:
        field_provenance["pre_model_hints"] = "captured_exact"

    captured_commercial_intent = resolve_captured_commercial_intent(
        pre_model_hints,
        envelope,
        capture_gaps=capture_gaps,
        field_provenance=field_provenance,
    )
    if "commercial_intent_conflict" in capture_gaps:
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )

    selected_service_id = envelope.get("requested_service_id") or envelope.get("service_id")
    if not selected_service_id:
        capture_gaps.append("typed_scope_absent")
        if legacy_direct_ids:
            capture_gaps.append("legacy_direct_fact_explicitness_not_captured")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )
    field_provenance["selected_service_id"] = "captured_exact"
    field_provenance["session_key.sid"] = "captured_exact"

    if legacy_direct_ids:
        capture_gaps.append("legacy_direct_fact_explicitness_not_captured")
    requested_fact_ids: tuple[str, ...] = ()
    field_provenance["requested_fact_ids"] = "not_captured"

    patient_text = structured.get("patient_text")
    price_text = envelope.get("price_text")
    field_provenance["composer.price_text"] = "captured_exact" if price_text else "not_captured"

    known_fact_ids = set(facts.keys())
    promo_ids: list[str] = []
    for raw_id in structured.get("promo_fact_ids") or []:
        normalized = normalize_fact_id(str(raw_id), known_fact_ids)
        if normalized is None:
            capture_gaps.append("unknown_promo_fact_id")
            continue
        promo_ids.append(normalized)
        field_provenance[f"promo:{normalized}"] = "captured_exact"

    amplifier_ids: list[str] = []
    for raw_id in structured.get("amplifier_fact_ids") or []:
        normalized = normalize_fact_id(str(raw_id), known_fact_ids)
        if normalized is None:
            capture_gaps.append("unknown_amplifier_fact_id")
            continue
        if normalized == "implant_warranty":
            capture_gaps.append("automatic_warranty_suppressed")
            continue
        amplifier_ids.append(normalized)
        field_provenance[f"amplifier:{normalized}"] = "captured_exact"

    offer_payload = None
    try:
        offer_payload = extract_section_json(user_content, "SELECTED_EXACT_OFFER")
        if offer_payload is not None:
            field_provenance["selected_exact_offer"] = "captured_exact"
    except JSONDecodeError as exc:
        raise ReplayHarnessError("adapter_error", "invalid_selected_exact_offer_json") from exc

    if offer_payload and offer_payload.get("availability") == "no_public_price":
        capture_gaps.append("no_public_price_not_representable")

    try:
        price_plan = build_price_plan(
            structured,
            offer_payload,
            client_id,
            captured_commercial_intent=captured_commercial_intent,
            capture_gaps=capture_gaps,
            field_provenance=field_provenance,
        )
    except ReplayHarnessError as exc:
        return _adapter_error_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer, exc.code
        )

    if price_plan.kind in {"single", "multi"}:
        capture_gaps.append("required_offer_condition_ids_not_captured")
        field_provenance["required_offer_conditions"] = "not_captured"
    else:
        field_provenance["required_offer_conditions"] = "not_captured"

    if captured_commercial_intent == PRICE_INTENT_VALUE and price_plan.kind == "none":
        return _price_intent_not_replayable_result(
            key,
            source_hashes,
            structured,
            legacy,
            capture_gaps,
            field_provenance,
            legacy.visible_answer,
            captured_commercial_intent=captured_commercial_intent,
            target_input=TargetInputSummary(
                context_strategy=context_strategy,
                response_scope="service",
                selected_service_id=selected_service_id,
                route_authority_kind="composer_selected",
            ),
        )

    referenced_ids = set(promo_ids) | set(amplifier_ids)

    fact_catalog = build_fact_catalog(facts, client_id, referenced_ids, field_provenance=field_provenance)
    commercial_facts = tuple(fact_catalog[fact_id] for fact_id in sorted(referenced_ids) if fact_id in fact_catalog)

    service_value_candidate = build_service_value_candidate(
        structured,
        facts,
        client_id,
        capture_gaps=capture_gaps,
        field_provenance=field_provenance,
    )
    if service_value_candidate is not None:
        field_provenance["service_value_candidate"] = field_provenance["service_value_text"]

    textual_cta_candidate = None
    if (structured.get("cta_ui_metadata") or {}).get("selected_cta_key"):
        capture_gaps.append("textual_cta_text_not_captured")
        field_provenance["textual_cta_candidate"] = "not_captured"

    transport_kind = "streaming" if (raw_row.get("outbound_payload") or {}).get("stream") else "blocking"
    field_provenance["transport_kind"] = "captured_exact"
    captured_route_mode = resolve_captured_composer_route(
        envelope,
        capture_gaps=capture_gaps,
        field_provenance=field_provenance,
    )
    if captured_route_mode is None:
        if legacy_direct_ids and "legacy_direct_fact_explicitness_not_captured" not in capture_gaps:
            capture_gaps.append("legacy_direct_fact_explicitness_not_captured")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )

    composer_route, composer_mode = captured_route_mode
    if not validate_captured_patient_text_for_route_mode(
        route=composer_route,
        mode=composer_mode,
        patient_text=patient_text,
        capture_gaps=capture_gaps,
        field_provenance=field_provenance,
    ):
        if legacy_direct_ids and "legacy_direct_fact_explicitness_not_captured" not in capture_gaps:
            capture_gaps.append("legacy_direct_fact_explicitness_not_captured")
        return _not_replayable_result(
            key, source_hashes, structured, legacy, capture_gaps, field_provenance, legacy.visible_answer
        )

    field_provenance["route_authority_kind"] = "target_contract_constant"
    field_provenance["response_scope"] = "derived_from_captured_structure"

    target_input = TargetInputSummary(
        context_strategy=context_strategy,
        response_scope="service",
        selected_service_id=selected_service_id,
        route_authority_kind="composer_selected",
        route=composer_route,
        mode=composer_mode,
        requested_fact_ids=requested_fact_ids,
        promo_candidate_ids=tuple(promo_ids),
        amplifier_candidate_ids=tuple(amplifier_ids),
    )

    precomposer = PreComposerPlan(
        session_key=SessionKey(client_id=client_id, sid=structured["session_id"]),
        context_strategy=context_strategy,
        route_authority=build_replay_route_authority(client_id),
        response_scope="service",
        selected_service_id=selected_service_id,
        price_plan=price_plan,
        commercial_facts=commercial_facts,
        promo_candidate_ids=tuple(promo_ids),
        automatic_amplifier_candidate_ids=tuple(amplifier_ids),
        service_value_candidate=service_value_candidate,
        textual_cta_candidate=textual_cta_candidate,
        ui_candidates=build_ui_candidates(
            structured, client_id, capture_gaps=capture_gaps, field_provenance=field_provenance
        ),
        transport_kind=transport_kind,
    )

    fabricated_findings = audit_fabricated_findings(
        field_provenance=field_provenance,
        precomposer=precomposer,
        client_id=client_id,
    )
    provenance_findings = validate_provenance_matrix(
        field_provenance=field_provenance,
        precomposer=precomposer,
        structured=structured,
        envelope=envelope,
        resolved_output=None,
        client_id=client_id,
    )
    all_audit_findings = tuple(dict.fromkeys([*fabricated_findings, *provenance_findings]))
    if all_audit_findings:
        for finding in all_audit_findings:
            if finding.startswith("client_isolation"):
                contract_violations.append(finding)

    composer = _build_replay_composer_result(
        route=composer_route,
        mode=composer_mode,
        patient_text=structured.get("patient_text"),
        price_text=envelope.get("price_text"),
        requested_fact_ids=requested_fact_ids,
    )

    target_output = TargetOutputSummary()

    if "no_public_price_not_representable" in capture_gaps and price_plan.kind == "none":
        fidelity: str = "partial"
        delta_classes.append("capture_gap")
    else:
        fidelity = "partial" if capture_gaps else "full"

    if all_audit_findings:
        fidelity = "partial"

    try:
        resolved = resolve_response_plan(precomposer, composer)
        rendered = render_response_text(resolved)
        project_response_ui(resolved)
    except ResponsePlanContractError as exc:
        code = getattr(exc, "code", None) or "response_plan_contract_error"
        contract_violations.append(str(code))
        delta_classes.append("response_plan_violation")
        target_output = TargetOutputSummary(
            response_plan_error=str(code),
            contract_violations=tuple(dict.fromkeys(contract_violations)),
        )
        return ReplayRecordResult(
            source_key=key,
            source_hashes=source_hashes,
            provider_turn=True,
            context_strategy=context_strategy,
            capture_fidelity="partial",
            capture_gaps=tuple(dict.fromkeys(capture_gaps)),
            field_provenance=field_provenance,
            legacy_source=legacy,
            target_input_summary=target_input,
            target_output=target_output,
            delta=ReplayComparison(legacy_visible_answer=legacy.visible_answer),
            delta_classes=tuple(dict.fromkeys(delta_classes)),
            contract_violations=tuple(dict.fromkeys(contract_violations)),
            captured_commercial_intent=captured_commercial_intent,
            fabricated_findings=fabricated_findings,
            provenance_findings=provenance_findings,
        )
    except ValidationError as exc:
        return _adapter_error_result(
            key,
            source_hashes,
            structured,
            legacy,
            capture_gaps,
            field_provenance,
            legacy.visible_answer,
            "response_plan_validation_error",
        )
    except ReplayHarnessError:
        raise
    except Exception as exc:
        raise ReplayFatalHarnessError("fatal_replay_error", str(exc)) from exc

    post_resolve_provenance = validate_provenance_matrix(
        field_provenance=field_provenance,
        precomposer=precomposer,
        structured=structured,
        envelope=envelope,
        resolved_output=resolved,
        client_id=client_id,
    )
    provenance_findings = tuple(dict.fromkeys([*provenance_findings, *post_resolve_provenance]))
    fabricated_findings = audit_fabricated_findings(
        field_provenance=field_provenance,
        precomposer=precomposer,
        client_id=client_id,
    )
    all_audit_findings = tuple(dict.fromkeys([*fabricated_findings, *provenance_findings]))

    safety_violations = collect_safety_violations(structured, resolved, rendered)
    contract_violations.extend(safety_violations)
    if safety_violations:
        delta_classes.append("response_plan_violation")

    captured_patient = structured.get("patient_text")
    patient_text_preserved = True
    if captured_patient and captured_patient.strip():
        patient_text_preserved = resolved.patient_text == captured_patient
        if not patient_text_preserved:
            contract_violations.append("patient_text_not_preserved")
            delta_classes.append("response_plan_violation")

    comparison = ReplayComparison(
        legacy_visible_answer=legacy.visible_answer,
        target_visible_answer=rendered,
        exact_text_match=rendered == (legacy.visible_answer or ""),
        patient_text_preserved=patient_text_preserved,
        legacy_price_block_present=legacy_price_block_present(legacy),
        target_price_block_present=resolved.price_block is not None,
    )

    false_price_insertion = (
        captured_commercial_intent != PRICE_INTENT_VALUE and resolved.price_block is not None
    )
    if false_price_insertion:
        contract_violations.append("false_price_insertion")
        delta_classes.append("response_plan_violation")

    finalized = resolved.finalized_commercial_ids
    target_output = TargetOutputSummary(
        resolved=True,
        rendered_text=rendered,
        patient_text=resolved.patient_text,
        terminal_text=resolved.terminal_text,
        price_block_count=1 if resolved.price_block is not None else 0,
        finalized_commercial_ids={
            "requested_fact_ids": finalized.requested_fact_ids,
            "promo_fact_ids": finalized.promo_fact_ids,
            "amplifier_fact_ids": finalized.amplifier_fact_ids,
            "service_value_ids": finalized.service_value_ids,
            "price_offer_ids": finalized.price_offer_ids,
            "required_offer_condition_ids": finalized.required_offer_condition_ids,
        },
        diagnostics=tuple(item.code for item in resolved.diagnostics),
        contract_violations=tuple(dict.fromkeys(contract_violations)),
    )

    if captured_commercial_intent == PRICE_INTENT_VALUE and target_output.price_block_count != 1:
        contract_violations.append("price_intent_without_price_block")
        delta_classes.append("response_plan_violation")

    expected_reasons = detect_expected_contract_change_reasons(
        resolved=True,
        legacy=legacy,
        structured=structured,
        target_output=target_output,
        capture_gaps=capture_gaps,
        false_price_insertion=false_price_insertion,
    )
    if expected_reasons:
        delta_classes.append("expected_contract_change")

    unexplained_delta = classify_unexplained_visible_delta(
        resolved=True,
        exact_text_match=comparison.exact_text_match,
        false_price_insertion=false_price_insertion,
        delta_classes=delta_classes,
    )
    if unexplained_delta:
        delta_classes.append("unexplained_visible_delta")

    if capture_gaps:
        delta_classes.append("capture_gap")
    if comparison.exact_text_match and not capture_gaps and not contract_violations and not all_audit_findings:
        delta_classes.append("no_material_change")

    if contract_violations or all_audit_findings:
        fidelity = "partial"

    return ReplayRecordResult(
        source_key=key,
        source_hashes=source_hashes,
        provider_turn=True,
        context_strategy=context_strategy,
        capture_fidelity=fidelity,
        capture_gaps=tuple(dict.fromkeys(capture_gaps)),
        field_provenance=field_provenance,
        legacy_source=legacy,
        target_input_summary=target_input,
        target_output=target_output,
        delta=comparison,
        delta_classes=tuple(dict.fromkeys(delta_classes)) or ("capture_gap",),
        contract_violations=tuple(dict.fromkeys(contract_violations)),
        captured_commercial_intent=captured_commercial_intent,
        false_price_insertion=false_price_insertion,
        fabricated_findings=fabricated_findings,
        provenance_findings=provenance_findings,
        expected_contract_change_reasons=expected_reasons,
        unexplained_visible_delta=unexplained_delta,
        price_intent_unresolved=False,
    )


def collect_safety_violations(
    structured: dict[str, Any],
    resolved: Any,
    rendered: str,
) -> list[str]:
    violations: list[str] = []
    if resolved.price_block is not None and len(resolved.price_block.offer_ids) == 0:
        violations.append("empty_price_block")
    visible_roles: list[str] = []
    visible_roles.extend(block.fact_id for block in resolved.requested_fact_blocks)
    if resolved.service_value_block is not None:
        visible_roles.append(resolved.service_value_block.fact_id)
    visible_roles.extend(block.fact_id for block in resolved.promo_blocks)
    visible_roles.extend(block.fact_id for block in resolved.automatic_amplifier_blocks)
    if len(visible_roles) != len(set(visible_roles)):
        violations.append("duplicate_visible_fact_id")
    if "implant_warranty" in resolved.finalized_commercial_ids.amplifier_fact_ids:
        violations.append("automatic_implant_warranty")
    if resolved.required_offer_conditions and resolved.price_block is None:
        violations.append("conditions_without_price")
    return violations


def _price_intent_not_replayable_result(
    key: SourceKey,
    source_hashes: SourceHashes,
    structured: dict[str, Any],
    legacy: LegacySourceMetadata,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
    visible_answer: str | None,
    *,
    captured_commercial_intent: str | None,
    target_input: TargetInputSummary,
) -> ReplayRecordResult:
    return ReplayRecordResult(
        source_key=key,
        source_hashes=source_hashes,
        provider_turn=True,
        context_strategy=target_input.context_strategy,
        capture_fidelity="not_replayable",
        capture_gaps=tuple(dict.fromkeys(capture_gaps)),
        field_provenance=field_provenance,
        legacy_source=legacy,
        target_input_summary=target_input,
        target_output=TargetOutputSummary(resolved=False),
        delta=ReplayComparison(legacy_visible_answer=visible_answer),
        delta_classes=("capture_gap",),
        contract_violations=(),
        captured_commercial_intent=captured_commercial_intent,
        price_intent_unresolved=True,
    )


def _not_replayable_result(
    key: SourceKey,
    source_hashes: SourceHashes,
    structured: dict[str, Any],
    legacy: LegacySourceMetadata,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
    visible_answer: str | None,
    adapter_error: str | None = None,
) -> ReplayRecordResult:
    target_output = TargetOutputSummary(adapter_error=adapter_error) if adapter_error else TargetOutputSummary()
    return ReplayRecordResult(
        source_key=key,
        source_hashes=source_hashes,
        provider_turn=bool(structured.get("provider_turn")),
        context_strategy=None,
        capture_fidelity="not_replayable",
        capture_gaps=tuple(dict.fromkeys(capture_gaps)),
        field_provenance=field_provenance,
        legacy_source=legacy,
        target_input_summary=TargetInputSummary(),
        target_output=target_output,
        delta=ReplayComparison(legacy_visible_answer=visible_answer),
        delta_classes=("capture_gap",),
        contract_violations=(),
    )


def _adapter_error_result(
    key: SourceKey,
    source_hashes: SourceHashes,
    structured: dict[str, Any],
    legacy: LegacySourceMetadata,
    capture_gaps: list[str],
    field_provenance: dict[str, str],
    visible_answer: str | None,
    adapter_error: str,
) -> ReplayRecordResult:
    return ReplayRecordResult(
        source_key=key,
        source_hashes=source_hashes,
        provider_turn=bool(structured.get("provider_turn")),
        context_strategy=None,
        capture_fidelity="not_replayable",
        capture_gaps=tuple(dict.fromkeys(capture_gaps)),
        field_provenance=field_provenance,
        legacy_source=legacy,
        target_input_summary=TargetInputSummary(),
        target_output=TargetOutputSummary(adapter_error=adapter_error),
        delta=ReplayComparison(legacy_visible_answer=visible_answer),
        delta_classes=("adapter_error",),
        contract_violations=(),
    )


def stable_sort_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (row["scenario_id"], row["turn_id"], row["config_id"], row["session_id"]),
    )


def compute_metrics(records: list[ReplayRecordResult]) -> ReplayMetrics:
    capture_gap_counts: Counter[str] = Counter()
    for record in records:
        capture_gap_counts.update(record.capture_gaps)

    full = sum(1 for record in records if record.capture_fidelity == "full")
    partial = sum(1 for record in records if record.capture_fidelity == "partial")
    not_replayable = sum(1 for record in records if record.capture_fidelity == "not_replayable")
    resolved = sum(1 for record in records if record.target_output.resolved)
    rendered = sum(1 for record in records if record.target_output.rendered_text is not None)
    adapter_errors = sum(1 for record in records if "adapter_error" in record.delta_classes)
    response_plan_violations = sum(
        1 for record in records if "response_plan_violation" in record.delta_classes
    )
    preserved = sum(1 for record in records if record.delta.patient_text_preserved is True)
    exact = sum(1 for record in records if record.delta.exact_text_match is True)
    expected_changes = sum(1 for record in records if record.expected_contract_change_reasons)
    legacy_direct = sum(1 for record in records if record.legacy_source.direct_fact_ids)
    warranty_legacy = sum(
        1
        for record in records
        if "implant_warranty" in record.legacy_source.direct_fact_ids
        or "implant_warranty" in record.legacy_source.promo_fact_ids
        or "implant_warranty" in record.legacy_source.amplifier_fact_ids
    )
    requested_warranty = sum(
        1
        for record in records
        if record.target_output.resolved
        and "implant_warranty" in record.target_output.finalized_commercial_ids.get("requested_fact_ids", ())
    )
    automatic_warranty = sum(
        1
        for record in records
        if record.target_output.resolved
        and "implant_warranty" in record.target_output.finalized_commercial_ids.get("amplifier_fact_ids", ())
    )
    single_price = sum(
        1
        for record in records
        if record.target_output.resolved and record.target_output.price_block_count == 1
        and len(record.target_output.finalized_commercial_ids.get("price_offer_ids", ())) == 1
    )
    multi_price = sum(
        1
        for record in records
        if record.target_output.resolved
        and len(record.target_output.finalized_commercial_ids.get("price_offer_ids", ())) > 1
    )
    no_price = sum(
        1
        for record in records
        if record.target_output.resolved and not record.target_output.finalized_commercial_ids.get("price_offer_ids")
    )
    missing_conditions = sum(1 for record in records if "required_offer_condition_ids_not_captured" in record.capture_gaps)
    terminal_not_replayable = sum(1 for record in records if "terminal_mode_not_captured" in record.capture_gaps)
    scope_not_replayable = sum(1 for record in records if "typed_scope_absent" in record.capture_gaps)
    safety = sum(
        1
        for record in records
        if "response_plan_violation" in record.delta_classes
        or any(
            code
            in {
                "patient_text_not_preserved",
                "duplicate_visible_fact_id",
                "automatic_implant_warranty",
                "conditions_without_price",
            }
            for code in record.contract_violations
        )
    )
    unclassified = sum(1 for record in records if record.capture_fidelity not in {"full", "partial", "not_replayable"})
    client_isolation = sum(
        1
        for record in records
        if any(item.startswith("client_isolation") for item in record.contract_violations)
    )
    fabricated = sum(len(record.fabricated_findings) for record in records)
    false_price_insertions = sum(1 for record in records if record.false_price_insertion)
    expected_reason_counts: Counter[str] = Counter()
    for record in records:
        expected_reason_counts.update(record.expected_contract_change_reasons)
    unexplained = sum(1 for record in records if record.unexplained_visible_delta)
    provenance_findings_total = sum(len(record.provenance_findings) for record in records)
    price_intent_without_price = sum(1 for record in records if record.price_intent_unresolved)
    fatal_errors = sum(1 for record in records if "fatal_replay_error" in record.delta_classes)
    unresolved = sum(1 for record in records if not record.target_output.resolved)

    return ReplayMetrics(
        source_count=len(records),
        provider_turn_count=sum(1 for record in records if record.provider_turn),
        code_only_turn_count=sum(1 for record in records if not record.provider_turn),
        full_count=full,
        partial_count=partial,
        not_replayable_count=not_replayable,
        resolved_count=resolved,
        rendered_count=rendered,
        adapter_error_count=adapter_errors,
        response_plan_violation_count=response_plan_violations,
        patient_text_preserved_count=preserved,
        exact_text_match_count=exact,
        expected_contract_change_count=expected_changes,
        capture_gap_counts=dict(sorted(capture_gap_counts.items())),
        legacy_direct_ids_not_promoted_count=legacy_direct,
        legacy_warranty_appearances=warranty_legacy,
        target_requested_warranty_count=requested_warranty,
        target_automatic_warranty_count=automatic_warranty,
        single_price_count=single_price,
        multi_price_count=multi_price,
        no_price_count=no_price,
        missing_required_conditions_count=missing_conditions,
        terminal_not_replayable_count=terminal_not_replayable,
        scope_not_replayable_count=scope_not_replayable,
        client_isolation_violations=client_isolation,
        provider_network_calls=provider_network_calls(),
        safety_violation_count=safety,
        unclassified_count=unclassified,
        fabricated_field_count=fabricated,
        false_price_insertion_count=false_price_insertions,
        expected_change_reason_counts=dict(sorted(expected_reason_counts.items())),
        unexplained_visible_delta_count=unexplained,
        provenance_finding_count=provenance_findings_total,
        price_intent_without_price_count=price_intent_without_price,
        fatal_replay_error_count=fatal_errors,
        unresolved_count=unresolved,
    )


def compute_overall_verdict(metrics: ReplayMetrics) -> str:
    if metrics.fatal_replay_error_count:
        return "FAIL"
    if metrics.unclassified_count or metrics.provider_network_calls:
        return "FAIL"
    if metrics.false_price_insertion_count:
        return "FAIL"
    if metrics.provenance_finding_count and metrics.resolved_count:
        return "FAIL"
    if metrics.fabricated_field_count:
        return "FAIL"
    if metrics.safety_violation_count:
        return "FAIL"
    if metrics.full_count == EXPECTED_RECORD_COUNT:
        return "PASS"
    if metrics.not_replayable_count or metrics.partial_count:
        return "PARTIAL_CAPTURE"
    return "FAIL"


def run_replay(
    source_root: Path,
    facts_path: Path,
) -> ReplayResult:
    with offline_replay_guard():
        structured_rows, raw_rows, _manifest, facts, source_hashes = validate_source_bundle(source_root, facts_path)
        raw_by_key = {record_key(row): row for row in raw_rows}
        records: list[ReplayRecordResult] = []
        for structured in stable_sort_records(structured_rows):
            raw_row = raw_by_key[record_key(structured)]
            try:
                records.append(build_replay_record(structured, raw_row, facts, source_hashes))
            except ReplayFatalHarnessError as exc:
                raise ReplayHarnessError("fatal_replay_error", exc.detail) from exc
        metrics = compute_metrics(records)
        return ReplayResult(
            replay_id=REPLAY_ID,
            overall_verdict=compute_overall_verdict(metrics),
            metrics=metrics,
            records=tuple(records),
        )


def serialize_result_json(result: ReplayResult) -> str:
    payload = json.loads(result.model_dump_json())
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def serialize_artifact_bytes(text: str) -> bytes:
    logical = text.replace("\r\n", "\n").replace("\r", "\n")
    return logical.replace("\n", REPLAY_ARTIFACT_NEWLINE).encode("utf-8")


def serialize_result_bytes(result: ReplayResult) -> bytes:
    return serialize_artifact_bytes(serialize_result_json(result))


def write_artifact_bytes(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialize_artifact_bytes(text))


def write_replay_outputs(
    result: ReplayResult,
    *,
    output_dir: Path,
    source_root: Path,
    head_sha: str,
    fail_if_exists: bool = True,
) -> None:
    if output_dir.exists():
        if fail_if_exists and any(output_dir.iterdir()):
            raise ReplayHarnessError("output_exists", str(output_dir))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    manifest = ReplayManifest(
        replay_id=REPLAY_ID,
        source_attempt_id=SOURCE_ATTEMPT_ID,
        source_root=str(source_root),
        source_hashes=result.records[0].source_hashes if result.records else SourceHashes(
            structured_turns=EXPECTED_STRUCTURED_TURNS_SHA256,
            raw_turns=EXPECTED_RAW_TURNS_SHA256,
            manifest=EXPECTED_MANIFEST_SHA256,
            facts=EXPECTED_FACTS_SHA256,
        ),
        head_sha=head_sha,
    )
    write_artifact_bytes(
        output_dir / "manifest.json",
        json.dumps(json.loads(manifest.model_dump_json()), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_artifact_bytes(output_dir / "result.json", serialize_result_json(result))


def render_markdown_report(result: ReplayResult, report_path: Path) -> None:
    lines = [
        f"# {result.replay_id}",
        "",
        f"Overall verdict: **{result.overall_verdict}**",
        "",
        "## Metrics",
        "",
        f"- source count: {result.metrics.source_count}",
        f"- full: {result.metrics.full_count}",
        f"- partial: {result.metrics.partial_count}",
        f"- not replayable: {result.metrics.not_replayable_count}",
        f"- resolved: {result.metrics.resolved_count}",
        f"- rendered: {result.metrics.rendered_count}",
        f"- provider/network calls: {result.metrics.provider_network_calls}",
        f"- false price insertions: {result.metrics.false_price_insertion_count}",
        f"- fabricated fields: {result.metrics.fabricated_field_count}",
        f"- expected contract changes: {result.metrics.expected_contract_change_count}",
        f"- unexplained visible deltas: {result.metrics.unexplained_visible_delta_count}",
        f"- provenance findings: {result.metrics.provenance_finding_count}",
        f"- price intent unresolved: {result.metrics.price_intent_without_price_count}",
        f"- fatal replay errors: {result.metrics.fatal_replay_error_count}",
        "",
        "## Expected change reasons",
        "",
    ]
    for reason, count in sorted(result.metrics.expected_change_reason_counts.items()):
        lines.append(f"- {reason}: {count}")
    lines.extend(
        [
        "",
        "## Capture gap taxonomy",
        "",
        ]
    )
    for gap, count in sorted(result.metrics.capture_gap_counts.items()):
        lines.append(f"- {gap}: {count}")
    lines.extend(["", "## Records", "", "| scenario | turn | config | fidelity | delta classes | capture gaps | target |", "|---|---|---|---|---|---|---|"])
    for record in result.records:
        gaps = ", ".join(record.capture_gaps) if record.capture_gaps else "-"
        deltas = ", ".join(record.delta_classes)
        target = "resolved" if record.target_output.resolved else record.capture_fidelity
        lines.append(
            f"| {record.source_key.scenario_id} | {record.source_key.turn_id} | {record.source_key.config_id} | "
            f"{record.capture_fidelity} | {deltas} | {gaps} | {target} |"
        )
    write_artifact_bytes(report_path, "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RESPONSE-REPLAY-1 offline replay")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--facts-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--head-sha", default="1cf8bbd200bddf5732b5723d25dc34fcc1545ac0")
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args(argv)

    result = run_replay(args.source_root, args.facts_path)
    write_replay_outputs(
        result,
        output_dir=args.output_dir,
        source_root=args.source_root,
        head_sha=args.head_sha,
        fail_if_exists=not args.allow_existing_output,
    )
    render_markdown_report(result, args.report_path)
    print(json.dumps({"overall_verdict": result.overall_verdict, "metrics": json.loads(result.metrics.model_dump_json())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
