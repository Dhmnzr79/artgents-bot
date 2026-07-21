# TASK — S25 Deterministic Target Brand Term Resolution

**Ветка:** `codex/stage-a`

**Baseline:** `95e967b feat: project exact brand offers S24`

**Серия / checkpoint:** `S25` — pure offline-разрешение одного уже выделенного brand
term в exact target `brand_id` по ID, canonical name или authored alias.

**Режим:** governance + один новый unwired resolver + synthetic/real-data unit tests +
price architecture status. Никаких client-data changes, извлечения бренда из полного
сообщения, service selection, session/runtime, ответов, routes/UI, authority или live/LLM.

## Owner direction

После завершённого S24 владелец разрешил идти дальше. S24 принимает только exact
`brand_id`; следующий минимальный пробел — безопасно превратить уже выделенный upstream
термин вроде `Nobel Biocare`, `Nobel` или `нобель` в `nobel_biocare` по target brand
catalog.

S25 не получает целое сообщение пациента и не ищет в нём подстроки. Это dictionary
boundary, а не новый classifier. Demo не имеет live-клиентов; compatibility path для
current/legacy не создаётся.

## Минимальная граница S25

Создать `core/target_brand_resolver.py` с pure function:

```python
@dataclass(frozen=True, slots=True)
class TargetBrandResolution:
    brand_id: str
    brand: TargetBrand


def resolve_target_brand_term(
    brand_catalog: TargetBrandCatalog,
    brand_term: str,
) -> TargetBrandResolution | None:
    ...
```

`brand_term` — один exact brand token/name, уже выделенный upstream. Result содержит
exact authored ID и deep copy canonical brand record. Неизвестный корректный term
возвращает `None`; это нормальный no-match, а не повод подставить похожий бренд.

## Exact normalization and matching

### 1. Input validation

`brand_term` обязан быть nonblank `str`. Иначе:

```text
TargetBrandResolutionError.code == "brand_resolution_term_invalid"
TargetBrandResolutionError.value == original input
TargetBrandResolutionError.candidate_brand_ids == ()
```

Error наследует `ValueError`; message exact `f"{code}: {value!r}"`.

### 2. Единственная допустимая normalization

Для input и authored lookup values применяется только:

```python
value.strip().casefold()
```

Никакой punctuation removal, word splitting, stemming, fuzzy matching, transliteration,
keyboard-layout repair, substring/regex search или LLM inference.

Lookup values каждого catalog record:

1. dictionary `brand_id`;
2. `brand.canonical_name`;
3. каждый authored `brand.aliases` в authored order.

Совпадение после `strip().casefold()` разрешает только разницу регистра и внешних
пробелов. Например:

- `nobel_biocare`, `Nobel Biocare`, `nobel`, ` НОБЕЛЬ ` → `nobel_biocare`;
- `сколько стоит Nobel?`, `Nobe`, `Нобелем`, `Straumann` → `None`, если таких exact
  authored labels нет.

### 3. Collision law

- Несколько lookup values одного и того же brand, совпавшие с term, остаются одним
  кандидатом.
- Если normalized term указывает на два или более разных brand IDs, resolver fail-closed:

```text
code == "brand_resolution_ambiguous"
value == original brand_term
candidate_brand_ids == tuple of distinct matching IDs in catalog authored order
```

- Никакой приоритет ID над canonical/alias и никакой первый случайный бренд не выбирается
  при cross-brand collision.

### 4. Result law

- Один distinct candidate → frozen/slots `TargetBrandResolution`.
- `brand_id` остаётся exact dictionary key без normalization.
- `brand` — deep copy source record; country/aliases не вычисляются и не меняются.
- Ноль candidates → `None` без fallback.
- Вызов stateless и не мутирует catalog/records/alias lists.

S25 output напрямую совместим с S24: caller может передать
`resolution.brand_id` как `selected_brand_id`. S25 сам S24 не вызывает и не выбирает
service/offer.

## Что S25 сознательно не делает

- не принимает/не анализирует полное сообщение пациента, TurnFrame или A9 scope;
- не извлекает несколько брендов и не обрабатывает brand groups/countries как запрос;
- не выбирает service/family/option/offer, не проверяет наличие offer у service;
- не меняет S24 и не применяет active/strategy/price rules;
- не создаёт prompt, FullContext packet, ResponseSpec или текст ответа;
- не читает файлы/Markdown/client/session/clock и не пишет state;
- не подключается к legacy resolver, composer/routes/API/app/UI/config;
- не меняет contracts, target/current client data или product authority;
- не меняет/не перезапускает A9 artifacts и не запускает live/LLM.

Извлечение brand term из сообщения, multi-brand/group semantics, service shortlist,
session/runtime и response composition остаются отдельными future checkpoints.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_brand_resolver.py` — new pure offline resolver;
- `tests/test_target_brand_resolver.py` — new synthetic unit contract;
- `tests/test_demo_target_brand_resolver.py` — new read-only demo acceptance/composition;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S25 resolver/status boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая target/current brand aliases, price/service/strategy/MD;
- весь `contracts/**`, включая frozen S1 brand schema/validators;
- existing S10/S15/S21/S22/S23/S24 core modules, loaders и current runtime paths;
- legacy `core/price_offers.py`, `core/price_brand_money.py`, planner brand filter и их tests;
- full-message/substring recognition, service selection, dialog/session state;
- ResponseSpec/composer/prompt/FullContext/routes/API/app/UI/config;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и product authority.

## Acceptance tests

### Synthetic resolver contract

`tests/test_target_brand_resolver.py` обязан доказать:

1. exact API/result fields, frozen+slots shell и detached `TargetBrand`;
2. invalid/non-string/blank term даёт stable invalid error;
3. exact ID, canonical name и каждый alias resolve в exact brand ID;
4. outer whitespace + Unicode `casefold()` разрешены;
5. punctuation, substring/full phrase, typo, morphology, transliteration и unknown term
   возвращают `None`, не fuzzy fallback;
6. совпадение ID/canonical/alias одного brand не создаёт ambiguity;
7. cross-brand collision ID/canonical/alias fail-closed со stable ordered candidates;
8. catalog authored order определяет только diagnostic candidate order, не выбор;
9. country/canonical/aliases возвращаются exact без изменения;
10. repeated calls stateless, catalog и nested lists не мутируются;
11. imports только stdlib + target brand contracts; нет IO/client/session/runtime/S24.

### Real demo acceptance

`tests/test_demo_target_brand_resolver.py` обязан read-only доказать:

1. real S2 brand catalog грузится через frozen loader/bundle boundary;
2. `implantium`/`Implantium`/`имплантиум` → `implantium`;
3. `impro`/`Impro`/`импро` → `impro`;
4. `nobel_biocare`/`Nobel Biocare`/`nobel`/`нобель`/`нобел` и case/outer spaces →
   `nobel_biocare`;
5. unknown, typo и full phrase не match;
6. `нобель` resolution можно явно передать в S24 для `all_on_4` и получить только
   `all_on_4.jaw.nobel` с exact 428000 RUB/jaw и payment stages;
7. target/current files не меняются; нет product imports/writes/skip/xfail/live/LLM.

### Минимальные соседние regression tests

После target tests запустить только:

- `tests/test_target_brand_offer_projection.py`;
- `tests/test_demo_target_brand_offer_projection.py`;
- `tests/test_response_schema_contract.py`;
- `tests/test_response_schema_loader.py`;
- `tests/test_demo_target_price_offers.py`.

Не запускать full suite, legacy brand tests, live/LLM или A9 harness/re-audit.

## Checker gates

### Gate 1 — governance, до кода

Read-only checker обязан подтвердить:

- scope — один already-extracted term, а не full-message brand recognition;
- normalization/collision/no-match laws однозначны и fail-closed;
- output минимален и напрямую совместим с S24 без product wiring;
- allowlist/protected boundary и tests достаточны;
- нет runtime/authority/A9/live расширения.

До `✅` код/data S25 не писать.

### Gate 2 — completion, до completion commit

Checker обязан подтвердить exact diff/allowlist, честные tests, no fuzzy/substring/fallback,
deep-copy/stateless behavior и отсутствие product wiring/authority/A9/live.

## Git protocol

1. Записать TASK + pending roadmap; `git diff --check`.
2. Получить governance checker `✅` до code/data.
3. Commit `docs: govern target brand resolution S25` и push только
   `origin/codex/stage-a`.
4. Реализовать allowlist и запустить target + listed neighbor tests.
5. Получить completion checker `✅`, затем roadmap `[x]`.
6. Commit `feat: resolve target brand terms S25` и push только
   `origin/codex/stage-a`.
7. Финал: clean tree, HEAD == `origin/codex/stage-a`.

## Definition of Done

- governance checker `✅` получен до code/data;
- deterministic exact brand term resolver реализован и независимо проверен;
- target/neighbor tests green без skip/xfail;
- client data/contracts/current paths/runtime/authority/A9/live не затронуты;
- два checkpoint commits pushed only `codex/stage-a`;
- рабочее дерево чистое и синхронизировано.
