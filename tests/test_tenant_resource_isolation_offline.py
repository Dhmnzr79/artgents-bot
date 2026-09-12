"""Active One Call resource boundaries — strict tenant + cache isolation (offline)."""

from __future__ import annotations

import concurrent.futures
import re
import uuid

import pytest

from core.client_config_loader import ExplicitPackClientIdError, require_explicit_pack_client_id
from core.one_call_client_pack_identity import build_client_pack_identity
from core.target_client_data import (
    clear_target_client_data_cache,
    evict_target_client_data_cache_for_client,
    load_target_client_data,
)
from core.target_runtime_client_context import (
    TargetRuntimeClientContextError,
    clear_target_runtime_client_context_cache,
    load_target_runtime_client_context,
)

_DEMO_PRICE_DIGITS = "318000"
_NIKADENT_PRICE_DIGITS = "10000"


def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def test_warm_demo_then_nikadent_isolated_pack_data() -> None:
    load_target_runtime_client_context("demo")
    nika_data = load_target_client_data("nikadent")
    demo_data = load_target_client_data("demo")
    assert nika_data.client_id == "nikadent"
    assert demo_data.client_id == "demo"
    assert nika_data.bundle is not demo_data.bundle
    nika_amounts = _digits(str(nika_data.bundle.model_dump()))
    demo_amounts = _digits(str(demo_data.bundle.model_dump()))
    assert _NIKADENT_PRICE_DIGITS in nika_amounts
    assert _DEMO_PRICE_DIGITS in demo_amounts
    assert _DEMO_PRICE_DIGITS not in nika_amounts


def test_warm_nikadent_then_demo_isolated_pack_data() -> None:
    load_target_runtime_client_context("nikadent")
    demo_ctx = load_target_runtime_client_context("demo")
    assert demo_ctx.client_id == "demo"
    demo_amounts = _digits(str(demo_ctx.bundle.model_dump()))
    assert _DEMO_PRICE_DIGITS in demo_amounts
    assert _NIKADENT_PRICE_DIGITS not in demo_amounts


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()
    yield
    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()


@pytest.mark.parametrize(
    "bad_id",
    [
        None,
        "",
        "   ",
        " demo",
        "demo ",
        "default",
        "../demo",
        "demo/..",
        "/demo",
        "C:\\demo",
        "..",
    ],
)
def test_require_explicit_pack_client_id_rejects_unsafe_values(bad_id) -> None:
    with pytest.raises(ExplicitPackClientIdError):
        require_explicit_pack_client_id(bad_id)


def test_require_explicit_pack_client_id_accepts_demo_and_nikadent() -> None:
    assert require_explicit_pack_client_id("demo") == "demo"
    assert require_explicit_pack_client_id("nikadent") == "nikadent"


def test_load_target_client_data_none_fails_closed() -> None:
    with pytest.raises(ExplicitPackClientIdError):
        load_target_client_data(None)


def test_load_target_runtime_context_none_fails_closed() -> None:
    with pytest.raises(ExplicitPackClientIdError):
        load_target_runtime_client_context(None)


def test_unknown_safe_segment_pack_missing_fails_closed() -> None:
    missing = f"no_such_clinic_{uuid.uuid4().hex[:8]}"
    require_explicit_pack_client_id(missing)
    with pytest.raises(FileNotFoundError):
        load_target_client_data(missing)


def test_demo_context_data_client_id_matches() -> None:
    data = load_target_client_data("demo")
    ctx = load_target_runtime_client_context("demo")
    assert data.client_id == "demo"
    assert ctx.client_id == "demo"
    assert data.pack_root.name == "demo"


def test_nikadent_context_data_client_id_matches() -> None:
    data = load_target_client_data("nikadent")
    ctx = load_target_runtime_client_context("nikadent")
    assert data.client_id == "nikadent"
    assert ctx.client_id == "nikadent"


def _find_tooth_extraction_offer(bundle):
    return next(
        o
        for o in bundle.offers
        if o.offer_id == "tooth_extraction.default"
        and o.service_id == "tooth_extraction"
        and o.active
    )


def _assert_tooth_extraction_isolation(*, demo_data, nika_data) -> None:
    assert demo_data.client_id == "demo"
    assert nika_data.client_id == "nikadent"
    assert "tooth_extraction" in demo_data.bundle.services
    assert "tooth_extraction" in nika_data.bundle.services
    demo_offer = _find_tooth_extraction_offer(demo_data.bundle)
    nika_offer = _find_tooth_extraction_offer(nika_data.bundle)
    assert demo_offer.offer_id == "tooth_extraction.default"
    assert nika_offer.offer_id == "tooth_extraction.default"
    assert int(demo_offer.price.min_amount) == 4500
    assert int(nika_offer.price.min_amount) == 5000


@pytest.mark.parametrize(
    ("warm_first", "warm_second"),
    [("demo", "nikadent"), ("nikadent", "demo")],
)
def test_same_service_id_price_isolation_between_packs(
    warm_first: str,
    warm_second: str,
) -> None:
    load_target_client_data(warm_first)
    load_target_client_data(warm_second)
    demo_data = load_target_client_data("demo")
    nika_data = load_target_client_data("nikadent")
    _assert_tooth_extraction_isolation(demo_data=demo_data, nika_data=nika_data)


def test_pack_identity_hash_differs_between_demo_and_nikadent() -> None:
    demo_id = build_client_pack_identity("demo")
    nika_id = build_client_pack_identity("nikadent")
    assert demo_id.client_id == "demo"
    assert nika_id.client_id == "nikadent"
    assert demo_id.client_pack_hash != nika_id.client_pack_hash
    assert demo_id.cache_key() != nika_id.cache_key()


def test_evict_demo_does_not_drop_nikadent_runtime_cache() -> None:
    demo_ctx = load_target_runtime_client_context("demo")
    nika_ctx = load_target_runtime_client_context("nikadent")
    evict_target_client_data_cache_for_client("demo", keep_pack_hash=demo_ctx.pack_identity.client_pack_hash)
    nika_again = load_target_runtime_client_context("nikadent")
    assert nika_again.client_id == "nikadent"
    assert nika_again.pack_identity.cache_key() == nika_ctx.pack_identity.cache_key()


def test_concurrent_demo_nikadent_loads_do_not_cross_contaminate() -> None:
    results: dict[str, str] = {}

    def _load(tenant: str) -> None:
        ctx = load_target_runtime_client_context(tenant)
        if ctx.client_id != tenant:
            results[tenant] = "wrong_client"
            return
        amounts = _digits(str(ctx.bundle.model_dump()))
        if tenant == "demo":
            results[tenant] = "ok" if _DEMO_PRICE_DIGITS in amounts else "bad"
            if _NIKADENT_PRICE_DIGITS in amounts:
                results[tenant] = "leak"
        else:
            results[tenant] = "ok" if _NIKADENT_PRICE_DIGITS in amounts else "bad"
            if _DEMO_PRICE_DIGITS in amounts:
                results[tenant] = "leak"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_load, t) for t in ("demo", "nikadent")]
        for f in futs:
            f.result()
    assert results == {"demo": "ok", "nikadent": "ok"}


def test_runtime_context_error_on_invalid_tenant_not_demo_fallback() -> None:
    with pytest.raises((ExplicitPackClientIdError, TargetRuntimeClientContextError, FileNotFoundError)):
        load_target_runtime_client_context("default")
