# TASK — S13 Target Payment Stages Contract and Demo Data

**Ветка:** `codex/stage-a`

**Baseline:** `1cc8497 data: materialize demo target price offers S12`

**Серия / checkpoint:** `S13` — минимальное расширение frozen S1 `TargetOffer`
структурированной оплатой по этапам и materialization exact demo stages для 12 top
offers.

**Режим:** offline schema/data extension only. Никаких product consumers, rendering,
routes/UI, live/LLM или product authority.

## Owner decision

21 июля 2026 владелец явно зафиксировал: «оплата по этапам обязательно нужна; на топ
услугах это встречается».

S13 отменяет только S12-решение об удалении полезной stage breakdown. Общая цена,
offers, units/labels и остальные S12 данные не пересматриваются. Target pack остаётся
неподключённым к ответам.

## Цель

Добавить в target price offer optional structured data:

```json
"payment_stages": [
  {
    "label": "Хирургический этап",
    "amount": 45200,
    "currency": "RUB"
  },
  {
    "label": "Ортопедический этап (коронка)",
    "amount": 31000,
    "currency": "RUB"
  }
]
```

И восстановить target followup:

```json
{"id": "stages", "label": "Оплата по этапам", "action": "price_aspect"}
```

только у offers, для которых current clinic source действительно содержит несколько
payment stages и authored `stages` followup.

## Почему это минимальный scope

S12 сохранил totals, packages и includes, но frozen S1 schema не имела stage field.
Без S13 при будущем legacy retirement точные суммы хирургического/ортопедического этапа
и 60/40 breakdown потеряются.

Новый общий contract нужен любому client pack с 2+ этапами. Он не зависит от числа
услуг, бренда, стоматологического протокола или demo IDs. Demo data доказывает contract
на реальных источниках; runtime wiring идёт позже.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/response_schema.py`;
- `tests/test_response_schema_contract.py`;
- `docs/PRICE_SERVICE_ARCHITECTURE.md`;
- 12 existing target offer files:
  - `clients/demo/target_response/pricebook/services/all_on_4.jaw.*.json` (3);
  - `clients/demo/target_response/pricebook/services/all_on_6.jaw.*.json` (3);
  - `clients/demo/target_response/pricebook/services/classic.one_tooth.*.json` (3);
  - `clients/demo/target_response/pricebook/services/one_stage.one_tooth.*.json` (3);
- `tests/test_demo_target_price_offers.py`;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- current `clients/demo/pricebook/**` и остальные current client files;
- остальные 19 target offer files, target services/brands/facts/doctors;
- S2 loader, S4 index, S5/S8 doctor contracts/loaders, S10 context builder;
- изменение price modes, totals, currency, billing units, package labels/includes,
  fact refs, brand/option links или active flags;
- stage percentages как отдельные числа, график дат/сроков, deposit, installment,
  balance calculation, payment status и accounting;
- сумма этапов как универсальный validator или автоматическое вычисление total;
- strategy/marketing/CTA/cadence, stage selection и session state;
- rendering, buttons/UI implementation, composer/verifier, routes/API/app;
- adapters, dual-read, fallback, current runtime wiring и feature flags;
- protected golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Target contract extension

В `contracts/response_schema.py` появляется:

```python
class TargetPaymentStage(TargetSchemaModel):
    label: NonBlankStr
    amount: MoneyAmount
    currency: NonBlankStr
```

`TargetOffer` получает:

```python
payment_stages: list[TargetPaymentStage] | None = None
```

Отсутствующий key и явный JSON `null` оба валидируются как `None`: source не задаёт
поэтапную оплату. `model_dump(exclude_none=True)` удаляет key в обоих случаях.

Если передан list:

- list обязан быть non-empty;
- общий contract допускает **один или больше** stages; `min_length=2` запрещён;
- stage labels exact, non-blank и unique внутри offer;
- amount — strict nonnegative integer; bool/float/string/negative запрещены;
- currency обязательна у каждого stage и не наследуется скрыто;
- authored order сохраняется;
- extras запрещены через `TargetSchemaModel`.

Optional `None`, а не default empty list, сохраняет S12 wire compatibility: у 19 offers
без stages key отсутствует, `model_dump(exclude_none=True)` exact равен raw.

Stable error tokens:

- explicit empty list → `offer_payment_stages_empty`;
- duplicate stage labels → `offer_payment_stage_label_duplicate`.

## Followup integrity law

Если `TargetOffer.followups` содержит `id == "stages"`, `payment_stages` обязан быть
non-empty. Иначе schema отклоняет offer token-ом
`offer_stages_followup_requires_payment_stages`.

Обратное не обязательно: pack может хранить один или несколько stages, но не показывать
отдельную кнопку.
Это отделяет source data от будущей UI/cadence policy.

Другие followup IDs не меняются. S13 не вводит общий enum действий и не рендерит
кнопку.

## Нет скрытой арифметической authority

Общий contract **не** требует `sum(stage.amount) == offer total/min/range`:

- stages могут описывать только часть оплаты;
- будущая клиника может отдельно показывать депозит/остаток;
- `from` total не равен гарантированному финальному итогу;
- schema не рассчитывает проценты и не выводит пропущенные суммы.

Demo acceptance отдельно доказывает, что для 12 current fixed offers exact authored
stage sum совпадает с exact total. Это data fact demo, не универсальный schema law.

## Exact demo materialization

Stages переносятся только для 12 variants четырёх services:

- `all_on_4` — три brand offers, два exact stages 60%/40%;
- `all_on_6` — три brand offers, два exact stages 60%/40%;
- `classic` — три brand offers, хирургический + ортопедический этап;
- `one_stage` — три brand offers, удаление/хирургия + ортопедический этап.

Каждый из этих 12 demo offers имеет exact два stages. Это свойство current demo data,
а не общий schema minimum.

Для каждого target stage:

- `label` = exact current `payment_stages[*].name`;
- `amount` = exact current amount;
- `currency` = exact parent current variant currency (`RUB`);
- order exact current source.

В каждом из 12 offers `followups` exact order соответствует current source:

1. `stages` — exact label/action current stage followup;
2. `includes` — уже materialized S12 followup.

## Почему sinus_lift не входит

Два current sinus variants технически содержат по одному `payment_stage`, равному всей
variant price, но:

- current source не содержит `stages` followup;
- один элемент не является разбивкой оплаты на этапы;
- owner-approved S12 price является `from` из-за зависимости от объёма/доступа;
- перенос fixed single-stage amount рядом с `from` создал бы противоречивую границу.

Поэтому оба target sinus offers и остальные 19 offers сохраняют отсутствие
`payment_stages` key и отсутствие `stages` followup.

## Architecture doc update

`docs/PRICE_SERVICE_ARCHITECTURE.md` фиксирует:

- `pricebook/services/*.json` владеет exact optional payment stages;
- каждый stage явно хранит label/amount/currency;
- stages followup допустим только при non-empty stage data;
- отсутствие stages означает отсутствие утверждённой разбивки, а не право вычислить её;
- percentages из текста label не парсятся;
- суммы этапов/total не пересчитываются и не получают универсальное равенство.
- общий contract допускает 1+ stages; отсутствие sinus materialization является только
  решением по противоречивому demo source, не универсальным запретом одного stage.

Example offer дополняется `payment_stages` и stages followup.

## Contract tests

`tests/test_response_schema_contract.py` минимально расширяется и доказывает:

1. valid two-stage offer exact сохраняет labels/amounts/currency/order;
2. `TargetPaymentStage` входит в `S1_MODEL_TYPES`, extra forbidden;
3. missing key и explicit `null` дают `None`, а exclude-none dump удаляет key;
4. valid single-stage data без followup принимается, доказывая schema minimum 1;
5. empty explicit list отклоняется `offer_payment_stages_empty`, duplicate labels —
   `offer_payment_stage_label_duplicate`;
6. blank label/currency и invalid MoneyAmount отклоняются frozen validators;
7. stages followup без data отклоняется;
8. stages data без followup допустимы;
9. deliberately non-equal stage sum/total допустим, доказывая no arithmetic authority;
10. existing price modes/cross-refs и imports boundary не ослаблены.

## Real-data acceptance update

`tests/test_demo_target_price_offers.py` дополнительно требует:

1. ровно 12 target offers имеют non-empty `payment_stages` и stages followup;
2. exact service/offer set равен четырём current services и 12 variants;
3. stage label/amount/order exact current, currency exact parent variant;
4. sum exact stage amounts равен exact fixed total только для этих 12 demo offers;
5. followup exact stages→includes order/label/action;
6. 19 других offers, включая sinus/pulpitis, не имеют stage key/followup;
7. S1 round-trip, 31 count, source price projection, facts/brands и S10 all-service
   context остаются зелёными;
8. before/after hashes и AST no-product-wiring audit остаются read-only.

## Verification

До schema/data edits:

1. independent checker читает TASK, current stage sources, 12 target offers, frozen S1
   contract/tests, S2/S10, S12 acceptance, architecture docs, checklist и guardrails;
2. checker подтверждает optional wire, followup law, exact 12-offer scope, sinus boundary,
   no arithmetic/runtime/A9 authority;
3. при `❌`/`❓` TASK исправляется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py -q --basetemp=.pytest_tmp_s13_contract`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_price_offers.py -q --basetemp=.pytest_tmp_s13_data`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_loader.py tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s13_neighbors`;
4. `.venv/codex312/Scripts/python.exe -m pytest tests/test_pricebook_contract.py tests/test_pricebook_loader.py -q --basetemp=.pytest_tmp_s13_legacy`;
5. `.venv/codex312/Scripts/python.exe scripts/lint_pricebook.py demo`;
6. `git diff --check`, allowlist status; independent checker повторяет review/runs;
7. live/LLM и полный pytest не запускаются.

## Definition of Done

- target contract универсально хранит exact optional payment stages;
- 12 demo top offers сохраняют exact stage data и safe followup;
- sinus/остальные offers не получают invented breakdown;
- no hidden sum/percentage/payment calculation authority появляется;
- S2/S10 работают с расширенным frozen model без отдельного adapter-а;
- runtime/answers/UI/session/A9/authority не изменены;
- roadmap S13 offline status независимо проверен;
- checker `✅`, governance/completion commits и push только в stage-a, дерево чистое.
