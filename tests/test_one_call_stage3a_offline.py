"""Stage 3A offline acceptance: prefix integrity, TOCTOU, bounded cache, capability harness."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from pathlib import Path

import pytest

import config
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.sales_one_plus import SalesOnePlusStrictFact
from contracts.target_cached_full_context import TargetCachedFullContext
from core.one_call_client_pack_identity import (
    authoritative_pack_relative_paths,
    build_client_pack_identity,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_sales_one_plus_turn import answer_envelope, admin_envelope
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_closed_envelope_validation import (
    ClosedEnvelopeValidationError,
    closed_envelope_template,
    sample_valid_json_mode_envelope,
    validate_closed_envelope_object,
)
from core.one_call_prefix_cache import clear_one_call_prefix_cache
from core.one_call_prefix_cache import get_or_build_stable_prefix
from core.one_call_prefix_input_fingerprint import prefix_cache_lookup_key
from core.sales_fast_widget_runtime import _exact_service_term
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.sales_one_plus_live_backend import sales_one_plus_model
from core.sales_one_plus_turn import run_sales_one_plus_candidate
from core.target_cached_full_context import build_target_cached_full_context
from core.target_runtime_client_context import (
    clear_target_runtime_client_context_cache,
    load_target_runtime_client_context,
    TargetRuntimeClientContextError,
    _CONTEXT_CACHE,
    _MAX_CONTEXT_ENTRIES,
)
from evals.v5.one_call_flash_capability_contract import (
    FROZEN_CAPABILITY_CASES,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_CALLS,
    PROPOSED_LIVE_ATTEMPT_ID,
    frozen_case_ids,
)
from evals.v5.one_call_flash_capability_harness import (
    CapabilityBudgetExceededError,
    FakeProviderResponse,
    FakeProviderTransport,
    ResponseFormatUnsupportedError,
    assert_live_gate_closed,
    execute_capability_case,
    run_offline_capability_plan,
    sample_offline_fake_responses,
)

from core.target_client_data import load_target_client_data, match_service_from_bundle

_REPO = Path(__file__).resolve().parents[1]
_DEMO = _REPO / "clients" / "demo"
_TEMPLATE = _REPO / "clients" / "_template"
_EMPTY_CATALOG = ActiveServiceCatalogSnapshot(canonical_json="[]")
_EMPTY_REF_CATALOG = ServiceReferenceCatalogSnapshot(canonical_json='{"services":[]}')
_DEMO_REF_CATALOG = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)


def _demo_catalog() -> ActiveServiceCatalogSnapshot:
    return ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)


def _resolution() -> ExactSalesResolution:
    authority = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    return ExactSalesResolution(None, None, None, None, None, authority, authority, authority, authority, authority)


def _context(text: str) -> TargetCachedFullContext:
    return TargetCachedFullContext(
        corpus_text=text,
        prompt_corpus_text=text,
        document_count=1,
        document_paths=("x.md",),
        sha256="x",
    )


def _identity(client_id: str = "demo") -> ClientPackIdentityKey:
    return build_client_pack_identity(client_id)


def _valid_pack_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _shared_test_identity() -> ClientPackIdentityKey:
    """Fixed identity for corpus collision tests — valid 64-hex pack hash."""
    return ClientPackIdentityKey(
        client_id="collision-test",
        client_pack_hash=_valid_pack_hash("collision-test-pack"),
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        model_snapshot=config.SALES_ONE_PLUS_FLASH_MODEL,
    )


def _patch_isolated_repo(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    monkeypatch.setattr("core.target_runtime_client_context._REPO_ROOT", repo)
    monkeypatch.setattr("core.one_call_client_pack_identity._REPO_ROOT", repo)
    monkeypatch.setattr("core.target_client_data._REPO_ROOT", repo)
    monkeypatch.setattr("core.client_runtime._REPO_ROOT", str(repo))


class _Backend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.calls += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def test_model_pin_is_flash_snapshot_only() -> None:
    assert config.SALES_ONE_PLUS_FLASH_MODEL == "qwen3.7-flash-2026-07-15"
    assert sales_one_plus_model() == config.SALES_ONE_PLUS_FLASH_MODEL


def test_production_stack_has_no_plus_fallback_in_sales_fast_path() -> None:
    text = (_REPO / "core" / "sales_one_plus_live_backend.py").read_text(encoding="utf-8")
    orchestration = (_REPO / "orchestration" / "sales_fast_widget_turn.py").read_text(encoding="utf-8")
    assert "qwen3.7-plus" not in text
    assert "SALES_ONE_PLUS_FLASH_MODEL" in text
    assert "qwen3.7-plus" not in orchestration


def test_same_identity_different_corpus_is_prefix_cache_miss() -> None:
    identity = _shared_test_identity()
    corpus_a = _context("UNIQUE-CORPUS-MARKER-ALPHA-12345")
    corpus_b = _context("UNIQUE-CORPUS-MARKER-BRAVO-67890")

    bundle_a, hit_a = get_or_build_stable_prefix(
        identity=identity,
        cached_full_context=corpus_a,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert hit_a is False
    assert "UNIQUE-CORPUS-MARKER-ALPHA-12345" in bundle_a.stable_prefix
    assert "UNIQUE-CORPUS-MARKER-BRAVO-67890" not in bundle_a.stable_prefix

    bundle_b, hit_b = get_or_build_stable_prefix(
        identity=identity,
        cached_full_context=corpus_b,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert hit_b is False
    assert "UNIQUE-CORPUS-MARKER-BRAVO-67890" in bundle_b.stable_prefix
    assert "UNIQUE-CORPUS-MARKER-ALPHA-12345" not in bundle_b.stable_prefix


def test_prefix_cache_lookup_key_includes_corpus_fingerprint() -> None:
    identity = _shared_test_identity()
    corpus_a = _context("alpha")
    corpus_b = _context("beta")
    assert prefix_cache_lookup_key(identity, corpus_a, _EMPTY_CATALOG, _EMPTY_REF_CATALOG) != prefix_cache_lookup_key(
        identity, corpus_b, _EMPTY_CATALOG, _EMPTY_REF_CATALOG
    )


def test_stable_pack_hash_for_unchanged_pack() -> None:
    from core.one_call_client_pack_identity import compute_client_pack_hash

    first = compute_client_pack_hash(_DEMO)
    second = compute_client_pack_hash(_DEMO)
    assert first == second
    assert len(first) == 64


def test_pack_hash_changes_when_ui_yaml_changes(tmp_path: Path) -> None:
    from core.one_call_client_pack_identity import compute_client_pack_hash

    pack = tmp_path / "pack"
    shutil.copytree(_DEMO, pack)
    before = compute_client_pack_hash(pack)
    ui = pack / "ui.yaml"
    ui.write_text(ui.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    after = compute_client_pack_hash(pack)
    assert before != after


def test_pack_hash_changes_when_video_catalog_changes(tmp_path: Path) -> None:
    from core.one_call_client_pack_identity import compute_client_pack_hash

    pack = tmp_path / "pack"
    shutil.copytree(_DEMO, pack)
    before = compute_client_pack_hash(pack)
    video = pack / "video_catalog.yaml"
    video.write_text(video.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    after = compute_client_pack_hash(pack)
    assert before != after


def test_pack_hash_changes_when_md_changes(tmp_path: Path) -> None:
    from core.one_call_client_pack_identity import compute_client_pack_hash

    pack = tmp_path / "pack"
    shutil.copytree(_DEMO, pack)
    before = compute_client_pack_hash(pack)
    md_file = next(pack.glob("md/**/*.md"))
    md_file.write_text(md_file.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8")
    after = compute_client_pack_hash(pack)
    assert before != after


def test_no_cross_client_cache_leakage() -> None:
    demo = build_client_pack_identity("demo")
    template = build_client_pack_identity("_template")
    assert demo.cache_key() != template.cache_key()


def test_client_pack_identity_rejects_invalid_hash() -> None:
    with pytest.raises(ValueError, match="client_pack_identity_hash_invalid"):
        ClientPackIdentityKey(
            client_id="demo",
            client_pack_hash="not-a-valid-hash",
            prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
            model_snapshot=config.SALES_ONE_PLUS_FLASH_MODEL,
        )


def test_bounded_prefix_cache_evicts_oldest_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.one_call_prefix_cache._MAX_ENTRIES", 1)
    clear_one_call_prefix_cache()
    corpus = _context("bounded-eviction-corpus")
    identity_a = ClientPackIdentityKey(
        "client-a",
        _valid_pack_hash("prefix-cache-a"),
        ONE_CALL_PROMPT_CONTRACT_VERSION,
        config.SALES_ONE_PLUS_FLASH_MODEL,
    )
    identity_b = ClientPackIdentityKey(
        "client-b",
        _valid_pack_hash("prefix-cache-b"),
        ONE_CALL_PROMPT_CONTRACT_VERSION,
        config.SALES_ONE_PLUS_FLASH_MODEL,
    )
    get_or_build_stable_prefix(identity=identity_a, cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
    get_or_build_stable_prefix(identity=identity_b, cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
    _, hit_a = get_or_build_stable_prefix(identity=identity_a, cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
    assert hit_a is False


def test_bounded_prefix_cache_respects_max_entries() -> None:
    corpus = _context("bounded-test-corpus")
    identities = [
        ClientPackIdentityKey(
            f"client{i}",
            f"{i:064x}",
            ONE_CALL_PROMPT_CONTRACT_VERSION,
            config.SALES_ONE_PLUS_FLASH_MODEL,
        )
        for i in range(10)
    ]
    for identity in identities:
        get_or_build_stable_prefix(identity=identity, cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
    _, hit = get_or_build_stable_prefix(identity=identities[0], cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
    assert hit is False


def test_prefix_cache_parallel_safety() -> None:
    identity = _identity()
    corpus = build_target_cached_full_context(_DEMO / "md")
    errors: list[Exception] = []

    def worker() -> None:
        try:
            bundle, _ = get_or_build_stable_prefix(identity=identity, cached_full_context=corpus, active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG)
            assert bundle.stable_prefix
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors


def test_capability_json_mode_unsupported_transport_error() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [
            FakeProviderResponse(
                model=config.SALES_ONE_PLUS_FLASH_MODEL,
                content=sample_valid_json_mode_envelope(),
                raise_error=ResponseFormatUnsupportedError("response_format unsupported"),
            )
        ]
    )
    result = execute_capability_case(transport, case_by_id("json_mode_blocking"))
    assert result.outcome == "unsupported"
    assert transport.attempts_per_case["json_mode_blocking"] == 1


def test_capability_json_mode_supported_with_valid_envelope() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    envelope = sample_valid_json_mode_envelope()
    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=envelope)]
    )
    result = execute_capability_case(transport, case_by_id("json_mode_blocking"))
    assert result.outcome == "supported"


def test_capability_json_mode_malformed_non_json_text() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content="not json")]
    )
    result = execute_capability_case(transport, case_by_id("json_mode_blocking"))
    assert result.outcome == "malformed"


def test_capability_legacy_transport_error_no_retry() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=answer_envelope("ok"), raise_error=RuntimeError("net"))]
    )
    result = execute_capability_case(transport, case_by_id("legacy_blocking"))
    assert result.outcome == "transport_error"
    assert transport.attempts_per_case["legacy_blocking"] == 1


def test_prefix_identical_for_different_questions_same_pack() -> None:
    identity = _identity()
    corpus = build_target_cached_full_context(_DEMO / "md")
    catalog = _demo_catalog()
    prefix_a = build_one_call_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=catalog,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    prefix_b = build_one_call_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=catalog,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert prefix_a == prefix_b
    assert "<USER_MESSAGE_DATA>" not in prefix_a
    assert "=== ACTIVE_SERVICE_CATALOG ===" in prefix_a


def test_active_service_catalog_contains_demo_active_services() -> None:
    catalog = _demo_catalog()
    prefix = build_one_call_stable_prefix(
        identity=_identity(),
        cached_full_context=build_target_cached_full_context(_DEMO / "md"),
        active_service_catalog=catalog,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    bundle = load_target_client_data("demo").bundle
    for service_id, service in sorted(bundle.services.items()):
        if not service.active:
            continue
        title = str(service.name or service_id).strip()
        assert service_id in prefix
        assert title in prefix
    block = prefix.split("=== ACTIVE_SERVICE_CATALOG ===\n", 1)[1].split("\n\n", 1)[0]
    for service_id in sorted(bundle.services):
        if bundle.services[service_id].active:
            assert block.count(f'"service_id":"{service_id}"') == 1


def test_active_service_catalog_excludes_inactive_services(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(_DEMO, pack)
    catalog_path = pack / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    inactive_id = sorted(catalog.keys())[0]
    catalog[inactive_id]["active"] = False
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(pack / "target_response")
    snapshot = ActiveServiceCatalogSnapshot.from_bundle(bundle)
    assert inactive_id not in snapshot.canonical_json


def test_same_identity_corpus_different_catalog_is_prefix_cache_miss() -> None:
    identity = _shared_test_identity()
    corpus = _context("catalog-cache-miss-corpus")
    catalog_a = ActiveServiceCatalogSnapshot(
        canonical_json='[{"service_id":"svc_a","title":"Service A"}]'
    )
    catalog_b = ActiveServiceCatalogSnapshot(
        canonical_json='[{"service_id":"svc_b","title":"Service B"}]'
    )
    bundle_a, hit_a = get_or_build_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=catalog_a,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert hit_a is False
    assert "svc_a" in bundle_a.stable_prefix
    bundle_b, hit_b = get_or_build_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=catalog_b,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert hit_b is False
    assert "svc_b" in bundle_b.stable_prefix
    assert "svc_a" not in bundle_b.stable_prefix


def test_catalog_change_updates_pack_identity_and_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = tmp_path / "clients" / "catalog_identity"
    shutil.copytree(_DEMO, pack)
    _patch_isolated_repo(monkeypatch, tmp_path)
    clear_target_runtime_client_context_cache()

    ctx_before = load_target_runtime_client_context("catalog_identity")
    prefix_before = build_one_call_stable_prefix(
        identity=ctx_before.pack_identity,
        cached_full_context=ctx_before.cached_full_context,
        active_service_catalog=ActiveServiceCatalogSnapshot.from_bundle(ctx_before.bundle),
        service_reference_catalog=ServiceReferenceCatalogSnapshot.from_bundle(ctx_before.bundle),
    )
    catalog_path = pack / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["stage3a_catalog_only_service"] = {
        "name": "Catalog Only Probe",
        "aliases": ["catalog only probe unique"],
        "family": "diagnostics",
        "roles": [],
        "active": True,
        "content_ref": "diagnostics__service__tomography.md",
        "selection": {"mode": "direct"},
        "options": [],
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    ctx_after = load_target_runtime_client_context("catalog_identity")
    prefix_after = build_one_call_stable_prefix(
        identity=ctx_after.pack_identity,
        cached_full_context=ctx_after.cached_full_context,
        active_service_catalog=ActiveServiceCatalogSnapshot.from_bundle(ctx_after.bundle),
        service_reference_catalog=ServiceReferenceCatalogSnapshot.from_bundle(ctx_after.bundle),
    )
    assert ctx_before.pack_identity.cache_key() != ctx_after.pack_identity.cache_key()
    assert prefix_before != prefix_after
    assert "stage3a_catalog_only_service" in prefix_after


def test_active_service_catalog_not_in_dynamic_suffix() -> None:
    backend = _Backend(answer_envelope("ok"))
    catalog = _demo_catalog()
    run_sales_one_plus_candidate(
        user_message="вопрос",
        cached_full_context=build_target_cached_full_context(_DEMO / "md"),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните.",
        backend=backend,
        pack_identity=_identity(),
        active_service_catalog=catalog,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert "=== ACTIVE_SERVICE_CATALOG ===" in backend.invocation.system_prompt
    assert "=== ACTIVE_SERVICE_CATALOG ===" not in backend.invocation.user_prompt
    assert catalog.canonical_json not in backend.invocation.user_prompt


def test_one_call_production_has_no_clinic_specific_service_ids() -> None:
    clinic_tokens = (
        "all_on_4",
        "all_on_6",
        "classic",
        "implant_alpha",
        "stage3a_probe_service",
    )
    paths = [
        _REPO / "core" / "one_call_active_service_catalog.py",
        _REPO / "core" / "one_call_fullcontext_messages.py",
        _REPO / "core" / "one_call_prefix_cache.py",
        _REPO / "core" / "one_call_prefix_input_fingerprint.py",
        _REPO / "core" / "sales_one_plus_turn.py",
        _REPO / "core" / "sales_fast_widget_runtime.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in clinic_tokens:
            assert token not in text


def test_capability_legacy_arbitrary_text_malformed() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content="arbitrary text")]
    )
    result = execute_capability_case(transport, case_by_id("legacy_blocking"))
    assert result.outcome == "malformed"


def test_runtime_context_cache_uses_pack_identity_not_client_id_only() -> None:
    clear_target_runtime_client_context_cache()
    ctx = load_target_runtime_client_context("demo")
    assert ctx.pack_identity.client_id == "demo"
    assert ctx.cache_key == ctx.pack_identity.cache_key()


def test_runtime_context_bounded_cache_evicts_old_pack_same_client(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_target_runtime_client_context_cache()
    call = 0

    def _sequential_hash(pack_root: Path) -> str:
        nonlocal call
        call += 1
        if call <= 2:
            return "a" + "0" * 63
        return "b" + "0" * 63

    monkeypatch.setattr("core.one_call_client_pack_identity.compute_client_pack_hash", _sequential_hash)
    ctx_old = load_target_runtime_client_context("demo")
    old_key = ctx_old.cache_key
    assert old_key in _CONTEXT_CACHE

    ctx_new = load_target_runtime_client_context("demo")
    new_key = ctx_new.cache_key
    assert new_key != old_key
    assert old_key not in _CONTEXT_CACHE
    assert new_key in _CONTEXT_CACHE


def test_runtime_context_lru_evicts_across_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_target_runtime_client_context_cache()
    monkeypatch.setattr("core.target_runtime_client_context._MAX_CONTEXT_ENTRIES", 1)
    demo_ctx = load_target_runtime_client_context("demo")
    demo_key = demo_ctx.cache_key
    template_ctx = load_target_runtime_client_context("_template")
    assert len(_CONTEXT_CACHE) == 1
    assert demo_key not in _CONTEXT_CACHE
    assert template_ctx.cache_key in _CONTEXT_CACHE


def test_runtime_context_bounded_max_entries() -> None:
    clear_target_runtime_client_context_cache()
    clients = ["demo", "_template"]
    for client_id in clients:
        load_target_runtime_client_context(client_id)
    assert len(_CONTEXT_CACHE) <= _MAX_CONTEXT_ENTRIES


def test_runtime_context_sees_service_catalog_change_without_manual_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = tmp_path / "clients" / "stale_catalog"
    shutil.copytree(_DEMO, pack)
    _patch_isolated_repo(monkeypatch, tmp_path)
    clear_target_runtime_client_context_cache()

    ctx_before = load_target_runtime_client_context("stale_catalog")
    new_service_id = "stage3a_probe_service_unique"
    catalog_path = pack / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog[new_service_id] = {
        "name": "Stage3A Probe Service",
        "aliases": ["stage3a probe alias unique"],
        "family": "diagnostics",
        "roles": [],
        "active": True,
        "content_ref": "diagnostics__service__tomography.md",
        "selection": {"mode": "direct"},
        "options": [],
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    ctx_after = load_target_runtime_client_context("stale_catalog")
    assert new_service_id in ctx_after.bundle.services
    assert ctx_before.cache_key != ctx_after.cache_key
    match = match_service_from_bundle("stage3a probe alias unique", ctx_after.bundle)
    assert match.get("matched_service_id") == new_service_id


def test_runtime_context_sees_facts_change_without_manual_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = tmp_path / "clients" / "stale_facts"
    shutil.copytree(_DEMO, pack)
    _patch_isolated_repo(monkeypatch, tmp_path)
    clear_target_runtime_client_context_cache()

    ctx_before = load_target_runtime_client_context("stale_facts")
    facts_path = pack / "target_response" / "pricebook" / "facts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    facts["stage3a_probe_fact"] = {
        "id": "stage3a_probe_fact",
        "kind": "benefit",
        "text_fact": "unique-fact-marker-12345",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": ["classic"],
        "incompatible_with": [],
        "detail_ref": "clinic__info__payment_terms.md#korotko",
    }
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")

    ctx_after = load_target_runtime_client_context("stale_facts")
    assert ctx_before.cache_key != ctx_after.cache_key
    assert ctx_after.bundle is not ctx_before.bundle


def test_runtime_context_sees_topic_change_without_manual_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = tmp_path / "clients" / "stale_topic"
    shutil.copytree(_DEMO, pack)
    _patch_isolated_repo(monkeypatch, tmp_path)
    clear_target_runtime_client_context_cache()

    ctx_before = load_target_runtime_client_context("stale_topic")
    md_file = pack / "md" / "clinic__info__advantages.md"
    md_text = md_file.read_text(encoding="utf-8")
    md_file.write_text(md_text.replace("topic: clinic\n", "topic: stage3a_probe_topic\n", 1), encoding="utf-8")

    ctx_after = load_target_runtime_client_context("stale_topic")
    assert ctx_before.cache_key != ctx_after.cache_key
    assert "stage3a_probe_topic" in ctx_after.allowed_topics


def test_service_matching_uses_same_pack_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = tmp_path / "clients" / "match_bundle"
    shutil.copytree(_DEMO, pack)
    _patch_isolated_repo(monkeypatch, tmp_path)
    clear_target_runtime_client_context_cache()

    catalog_path = pack / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    probe_id = "stage3a_match_probe_service"
    catalog[probe_id] = {
        "name": "Match Probe",
        "aliases": ["match probe alias unique"],
        "family": "diagnostics",
        "roles": [],
        "active": True,
        "content_ref": "diagnostics__service__tomography.md",
        "selection": {"mode": "direct"},
        "options": [],
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    ctx = load_target_runtime_client_context("match_bundle")
    term = _exact_service_term("match probe alias unique", ctx)
    assert term in {"Match Probe", "match probe alias unique"}


def test_client_pack_changed_during_load_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_target_runtime_client_context_cache()
    call = 0

    def _flaky_hash(pack_root: Path) -> str:
        nonlocal call
        call += 1
        return _valid_pack_hash(f"flaky-{call}")

    monkeypatch.setattr("core.one_call_client_pack_identity.compute_client_pack_hash", _flaky_hash)
    with pytest.raises(TargetRuntimeClientContextError) as exc:
        load_target_runtime_client_context("demo")
    assert exc.value.code == "client_pack_changed_during_load"


def test_client_pack_changed_during_load_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_target_runtime_client_context_cache()
    sequence = [
        _valid_pack_hash("before-load"),
        _valid_pack_hash("after-load"),
        _valid_pack_hash("after-load"),
    ]
    idx = 0

    def _sequential_hash(pack_root: Path) -> str:
        nonlocal idx
        value = sequence[min(idx, len(sequence) - 1)]
        idx += 1
        return value

    monkeypatch.setattr("core.one_call_client_pack_identity.compute_client_pack_hash", _sequential_hash)
    ctx = load_target_runtime_client_context("demo")
    assert ctx.pack_identity.client_pack_hash == _valid_pack_hash("after-load")


def test_invocation_puts_corpus_in_system_not_user() -> None:
    fact = SalesOnePlusStrictFact(id="f", kind="offer", text="Цена 100 000 ₽.")
    backend = _Backend(answer_envelope("Ответ."))
    identity = _shared_test_identity()
    result = run_sales_one_plus_candidate(
        user_message="Есть парковка?",
        cached_full_context=_context("MD number 73.5 and microfact parking."),
        exact_sales_resolution=_resolution(),
        current_strict_facts=(fact,),
        sales_context={"cta": "lead"},
        static_admin_handoff_text="Позвоните.",
        backend=backend,
        pack_identity=identity,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert result.decision == "answer"
    assert "APPROVED_MD_CORPUS" in backend.invocation.system_prompt
    assert "APPROVED_MD_CORPUS" not in backend.invocation.user_prompt


def test_local_prefix_cache_hit_same_identity_and_corpus() -> None:
    identity = _shared_test_identity()
    corpus = _context("repeat-corpus-marker")
    backend = _Backend(answer_envelope("Да"))
    run_sales_one_plus_candidate(
        user_message="q1",
        cached_full_context=corpus,
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните.",
        backend=backend,
        pack_identity=identity,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert backend.invocation.local_prefix_cache_hit is False
    backend2 = _Backend(answer_envelope("Да"))
    run_sales_one_plus_candidate(
        user_message="q2",
        cached_full_context=corpus,
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните.",
        backend=backend2,
        pack_identity=identity,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
    )
    assert backend2.invocation.local_prefix_cache_hit is True
    assert backend2.invocation.system_prompt == backend.invocation.system_prompt


def test_capability_harness_live_gate_none() -> None:
    assert LIVE_AUTHORIZED_ATTEMPT_ID is None
    assert_live_gate_closed()


def test_capability_frozen_plan_has_six_cases() -> None:
    assert len(FROZEN_CAPABILITY_CASES) == 6
    assert frozen_case_ids() == (
        "json_mode_blocking",
        "json_mode_streaming",
        "legacy_blocking",
        "legacy_streaming",
        "cache_cold",
        "cache_repeat",
    )


def test_capability_plan_respects_max_calls_budget() -> None:
    transport = FakeProviderTransport(sample_offline_fake_responses())
    summary = run_offline_capability_plan(transport)
    assert summary["provider_calls"] <= MAX_CALLS
    assert summary["provider_json_mode_support_asserted"] is False
    assert summary["offline_json_mode_validator_passed"] is True
    assert summary["proposed_attempt_id"] == PROPOSED_LIVE_ATTEMPT_ID
    assert len(summary["case_results"]) == 6


def test_fake_transport_never_asserts_provider_json_mode_support() -> None:
    envelope = sample_valid_json_mode_envelope()
    transport = FakeProviderTransport(
        [
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=envelope),
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=envelope),
        ]
    )
    summary = run_offline_capability_plan(
        transport,
        cases=tuple(FROZEN_CAPABILITY_CASES[:2]),
    )
    assert summary["offline_json_mode_validator_passed"] is True
    assert summary["provider_json_mode_support_asserted"] is False
    assert summary["attempt_marker"]["provider_json_mode_support_asserted"] is False


def test_closed_envelope_rejects_missing_nullable_key() -> None:
    payload = closed_envelope_template()
    del payload["clarify_axis"]
    with pytest.raises(ClosedEnvelopeValidationError, match="missing_fields"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_admin_with_patient_text() -> None:
    payload = closed_envelope_template(
        route="ADMIN",
        patient_text="not allowed",
        clarify_axis=None,
        clarify_service_options=None,
    )
    with pytest.raises(ClosedEnvelopeValidationError, match="patient_text_forbidden_for_admin"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_answer_with_clarify_axis() -> None:
    payload = closed_envelope_template(clarify_axis="service")
    with pytest.raises(ClosedEnvelopeValidationError, match="clarify_axis_forbidden_for_answer"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_clarify_without_axis() -> None:
    payload = closed_envelope_template(route="CLARIFY", clarify_axis=None)
    with pytest.raises(ClosedEnvelopeValidationError, match="clarify_axis_required_for_clarify"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_service_clarify_with_one_option() -> None:
    payload = closed_envelope_template(
        route="CLARIFY",
        clarify_axis="service",
        clarify_service_options=["classic"],
    )
    with pytest.raises(ClosedEnvelopeValidationError, match="clarify_service_options_invalid"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_service_clarify_with_duplicate_options() -> None:
    payload = closed_envelope_template(
        route="CLARIFY",
        clarify_axis="service",
        clarify_service_options=["classic", "classic"],
    )
    with pytest.raises(ClosedEnvelopeValidationError, match="clarify_service_options_invalid"):
        validate_closed_envelope_object(payload)


def test_closed_envelope_rejects_unknown_field() -> None:
    payload = closed_envelope_template(extra_field="x")
    with pytest.raises(ClosedEnvelopeValidationError, match="unknown_fields"):
        validate_closed_envelope_object(payload)


def test_capability_fake_model_mismatch() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model="wrong-model", content=answer_envelope("ok"))]
    )
    result = execute_capability_case(transport, case_by_id("legacy_blocking"))
    assert result.outcome == "model_mismatch"
    assert result.transport_attempts == 1


def test_capability_fake_malformed_and_no_retry() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content="", malformed=True)]
    )
    result = execute_capability_case(transport, case_by_id("legacy_blocking"))
    assert result.outcome == "malformed"
    assert transport.attempts_per_case["legacy_blocking"] == 1


def test_capability_fake_transport_error_no_retry() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=answer_envelope("ok"), raise_error=RuntimeError("net"))]
    )
    result = execute_capability_case(transport, case_by_id("legacy_blocking"))
    assert result.outcome == "transport_error"
    assert transport.attempts_per_case["legacy_blocking"] == 1


def test_capability_cached_tokens_zero_and_positive() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content="@ANSWER\ncold", cached_tokens=0),
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content="@ANSWER\nwarm", cached_tokens=128),
        ]
    )
    cold = execute_capability_case(transport, case_by_id("cache_cold"))
    warm = execute_capability_case(transport, case_by_id("cache_repeat"))
    assert cold.cached_tokens == 0
    assert cold.outcome == "supported"
    assert warm.cached_tokens == 128
    assert warm.outcome == "supported"


def test_capability_cache_repeat_without_cached_tokens_is_cache_miss() -> None:
    from evals.v5.one_call_flash_capability_contract import case_by_id

    transport = FakeProviderTransport(
        [
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=answer_envelope("cold"), cached_tokens=0),
            FakeProviderResponse(model=config.SALES_ONE_PLUS_FLASH_MODEL, content=answer_envelope("repeat"), cached_tokens=0),
        ]
    )
    repeat = execute_capability_case(transport, case_by_id("cache_repeat"))
    assert repeat.outcome == "cache_miss"


def test_authoritative_file_set_includes_ui_and_video() -> None:
    paths = authoritative_pack_relative_paths(_DEMO)
    assert "ui.yaml" in paths
    assert "video_catalog.yaml" in paths


def test_cache_key_format() -> None:
    identity = _identity()
    pattern = re.compile(
        rf"^{identity.client_id}:[a-f0-9]{{64}}:p{ONE_CALL_PROMPT_CONTRACT_VERSION}:m{config.SALES_ONE_PLUS_FLASH_MODEL}$"
    )
    assert pattern.match(identity.cache_key())


def test_production_stack_does_not_import_evals() -> None:
    for rel in (
        "core/sales_one_plus_turn.py",
        "core/sales_fast_widget_runtime.py",
        "orchestration/sales_fast_widget_turn.py",
    ):
        text = (_REPO / rel).read_text(encoding="utf-8")
        assert "evals" not in text
