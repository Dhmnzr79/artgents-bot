"""Pure token accounting and versioned estimate; never a billing/quota decision."""
from datetime import timezone
from decimal import Decimal, InvalidOperation
import os
from urllib.parse import urlsplit


DEEPSEEK_RATE_VERSION = 'deepseek-flash-2026-10-19'
DEEPSEEK_MODELS = {'deepseek-flash', 'deepseek-v4-flash', 'deepseek-v4-flash-vision-exp'}
# https://api-docs.deepseek.com/quick_start/pricing/
# UTC weekday schedule; Chinese public-holiday exceptions are not automated.
DEEPSEEK_RATES = {
    'peak': (Decimal('.006'), Decimal('.30'), Decimal('1.20')),
    'off_peak': (Decimal('.003'), Decimal('.15'), Decimal('.60')),
}


def field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def token_count(value, name):
    count = field(value, name)
    return count if type(count) is int and 0 <= count <= 2**63 - 1 else None


def cache_split(usage, prompt):
    """Never turn missing/contradictory cache usage into a zero-cache claim."""
    if prompt is None:
        return None, None
    hit_raw, miss_raw = field(usage, 'prompt_cache_hit_tokens'), field(usage, 'prompt_cache_miss_tokens')
    if hit_raw is not None or miss_raw is not None:
        hit, miss = token_count(usage, 'prompt_cache_hit_tokens'), token_count(usage, 'prompt_cache_miss_tokens')
        if (hit_raw is not None and hit is None) or (miss_raw is not None and miss is None):
            return None, None
        if hit is None:
            hit = prompt - miss
        if miss is None:
            miss = prompt - hit
    else:
        hit = token_count(field(usage, 'prompt_tokens_details'), 'cached_tokens')
        if hit is None:
            return None, None
        miss = prompt - hit
    if hit < 0 or miss < 0 or hit + miss != prompt:
        return None, None
    details = field(usage, 'prompt_tokens_details')
    standard_hit = token_count(details, 'cached_tokens')
    if field(details, 'cached_tokens') is not None and (standard_hit is None or standard_hit != hit):
        return None, None
    return hit, miss


def _configured_rate(key):
    try:
        value = Decimal(os.getenv(key, ''))
        return value if value.is_finite() and 0 <= value <= Decimal('1e308') else None
    except InvalidOperation:
        return None


def tariff(model, started_at):
    endpoint = urlsplit(os.getenv('CHAT_BASE_URL', ''))
    if endpoint.scheme == 'https' and endpoint.hostname == 'api.deepseek.com' and model in DEEPSEEK_MODELS:
        utc = started_at.astimezone(timezone.utc)
        peak = utc.weekday() < 5 and (1 <= utc.hour < 4 or 6 <= utc.hour < 10)
        band = 'peak' if peak else 'off_peak'
        return DEEPSEEK_RATES[band], f'{DEEPSEEK_RATE_VERSION}/{band}'
    rates = tuple(_configured_rate(key) for key in (
        'BOT_LLM_USD_PER_1M_CACHED_PROMPT', 'BOT_LLM_USD_PER_1M_PROMPT', 'BOT_LLM_USD_PER_1M_COMPLETION'))
    return rates, 'configured'


def cost_snapshot(model, started_at, cached, uncached, completion):
    rates, basis = tariff(model, started_at)
    estimate = None
    counts = (cached, uncached, completion)
    if all(count is not None for count in counts) and all(
            rate is not None or count == 0 for count, rate in zip(counts, rates)):
        amount = sum(Decimal(count) * (rate or Decimal(0)) for count, rate in zip(counts, rates)) / 1_000_000
        # SQLite REAL is for estimates; reject values outside its finite range.
        if amount.is_finite() and amount <= Decimal('1e308'):
            estimate = float(amount)
    return dict(estimated_usd=estimate, pricing_basis=basis,
        rate_cached_usd_per_1m=float(rates[0]) if rates[0] is not None else None,
        rate_uncached_usd_per_1m=float(rates[1]) if rates[1] is not None else None,
        rate_completion_usd_per_1m=float(rates[2]) if rates[2] is not None else None)
