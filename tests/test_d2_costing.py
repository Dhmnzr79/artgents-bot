"""Actual usage arithmetic and tariff snapshots, without any provider calls."""
from datetime import datetime
from types import SimpleNamespace as NS
import pytest
from core.d2_costing import cache_split, cost_snapshot, token_count


@pytest.mark.parametrize('usage,expected',[
    ({'prompt_cache_hit_tokens':900,'prompt_cache_miss_tokens':100},(900,100)),
    (NS(prompt_cache_hit_tokens=900,prompt_cache_miss_tokens=100),(900,100)),
    ({'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000},(0,1000)),
    ({'prompt_cache_hit_tokens':1000},(1000,0)),
    ({'prompt_cache_miss_tokens':100},(900,100)),
    ({'prompt_tokens_details':{'cached_tokens':900}},(900,100)),
    (NS(prompt_tokens_details=NS(cached_tokens=900)),(900,100)),
    ({},(None,None)),
    ({'prompt_cache_hit_tokens':True,'prompt_cache_miss_tokens':999},(None,None)),
    ({'prompt_cache_hit_tokens':-1,'prompt_cache_miss_tokens':1001},(None,None)),
    ({'prompt_cache_hit_tokens':900,'prompt_cache_miss_tokens':101},(None,None)),
    ({'prompt_tokens_details':{'cached_tokens':1001}},(None,None)),
    ({'prompt_cache_hit_tokens':'900','prompt_tokens_details':{'cached_tokens':900}},(None,None)),
    ({'prompt_cache_hit_tokens':900,'prompt_cache_miss_tokens':100,'prompt_tokens_details':{'cached_tokens':800}},(None,None)),
])
def test_usage_split(usage,expected):
    assert cache_split(usage,1000)==expected


@pytest.mark.parametrize('value',[None,-1,True,1.5,'10',float('nan'),2**63])
def test_malformed_counts_are_unknown(value):
    assert token_count({'count':value},'count')is None


def test_sdk_usage_exposes_native_deepseek_cache_fields():
    from openai.types.completion_usage import CompletionUsage
    usage=CompletionUsage(prompt_tokens=1000,completion_tokens=100,total_tokens=1100,
        prompt_cache_hit_tokens=900,prompt_cache_miss_tokens=100)
    assert cache_split(usage,usage.prompt_tokens)==(900,100)


@pytest.mark.parametrize('instant,band,amount',[
    ('2026-10-19T00:59:59+00:00','off_peak',.000777),
    ('2026-10-19T01:00:00+00:00','peak',.001554),
    ('2026-10-19T03:59:59+00:00','peak',.001554),
    ('2026-10-19T04:00:00+00:00','off_peak',.000777),
    ('2026-10-19T06:00:00+00:00','peak',.001554),
    ('2026-10-19T10:00:00+00:00','off_peak',.000777),
    ('2026-10-24T01:00:00+00:00','off_peak',.000777),
    ('2026-10-19T03:00:00+02:00','peak',.001554),
])
def test_deepseek_schedule_and_three_part_price(monkeypatch,instant,band,amount):
    monkeypatch.setenv('CHAT_BASE_URL','https://api.deepseek.com/v1')
    result=cost_snapshot('deepseek-flash',datetime.fromisoformat(instant),9000,1000,1000)
    assert result['estimated_usd']==pytest.approx(amount)
    assert result['pricing_basis']==f'deepseek-flash-2026-10-19/{band}'
    assert result['rate_cached_usd_per_1m']==(.006 if band=='peak'else .003)
    assert result['rate_uncached_usd_per_1m']==(.30 if band=='peak'else .15)
    assert result['rate_completion_usd_per_1m']==(1.20 if band=='peak'else .60)


@pytest.mark.parametrize('endpoint,model',[
    ('https://provider.invalid/v1','deepseek-flash'),
    ('https://api.deepseek.com.attacker.invalid','deepseek-flash'),
    ('https://api.deepseek.com','other-model'),
])
def test_do_not_apply_deepseek_rates_to_other_endpoint_or_model(monkeypatch,endpoint,model):
    monkeypatch.setenv('CHAT_BASE_URL',endpoint)
    for key in ('BOT_LLM_USD_PER_1M_PROMPT','BOT_LLM_USD_PER_1M_COMPLETION','BOT_LLM_USD_PER_1M_CACHED_PROMPT'):monkeypatch.delenv(key,raising=False)
    result=cost_snapshot(model,datetime.fromisoformat('2026-10-19T01:00:00+00:00'),900,100,100)
    assert result['estimated_usd']is None and result['pricing_basis']=='configured'


def test_configured_rates_need_cache_price_only_when_cache_used(monkeypatch):
    monkeypatch.setenv('CHAT_BASE_URL','https://provider.invalid')
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_PROMPT','1');monkeypatch.setenv('BOT_LLM_USD_PER_1M_COMPLETION','2')
    monkeypatch.delenv('BOT_LLM_USD_PER_1M_CACHED_PROMPT',raising=False)
    now=datetime.fromisoformat('2026-10-19T01:00:00+00:00')
    assert cost_snapshot('model',now,0,1000,100)['estimated_usd']==.0012
    assert cost_snapshot('model',now,900,100,100)['estimated_usd']is None
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_CACHED_PROMPT','.01')
    assert cost_snapshot('model',now,900,100,100)['estimated_usd']==.000309
    assert cost_snapshot('model',now,None,None,100)['estimated_usd']is None


@pytest.mark.parametrize('rate',['nan','Infinity','-1','1e309','not-a-rate'])
def test_invalid_rate_never_becomes_a_zero_estimate(monkeypatch,rate):
    monkeypatch.setenv('CHAT_BASE_URL','https://provider.invalid')
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_PROMPT',rate);monkeypatch.setenv('BOT_LLM_USD_PER_1M_COMPLETION','2')
    result=cost_snapshot('model',datetime.fromisoformat('2026-10-19T01:00:00+00:00'),0,1000,100)
    assert result['estimated_usd']is None
