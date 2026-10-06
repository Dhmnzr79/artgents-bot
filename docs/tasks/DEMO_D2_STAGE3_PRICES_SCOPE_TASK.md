# D2 — этап 3: цены и объём

Статус: реализация разрешена. База: `63d980f`
(`feat(d2): persist typed dialogue memory`). Работа выполняется в этой папке
и на текущей ветке по согласованию владельца.

## Проверенная исходная позиция

- Repository/Git top level: `C:\Users\denis\.codex\worktrees\27e1\artgents-bot`.
- Ветка: `codex/d2-stage1-contract`; HEAD: `63d980f`.
- `origin/main` и merge-base: `141ce91`.
- Никаких staged изменений нет. Внешний WIP: `data/` и
  `.pytest_tmp_stage2_debug.sqlite`, `.pytest_tmp_stage2_debug2.sqlite`.
  Их нельзя менять, удалять или добавлять в Git в этом этапе.

## Цель и точная граница

Реализовать только этап 3 действующей roadmap: общий D2 turn показывает
короткий overview утверждённого направления, до трёх упорядоченных
предложений одной известной услуги, проверенные price mode/сумму/единицу и
существенные условия; typed situation управляет выбором объёма без
умножения цены. При неизвестном объёме остаётся обзор без повторного меню;
точная услуга без публичной цены остаётся `no_public_price`.

Для нескольких ценовых частей materialize только первая в порядке D1R;
остальные остаются явно deferred. Этап не расширяет сборку mixed
price+content ответа — это этап 4.

Отбор нескольких offer известной услуги разрешён только по существующему
tenant-authored `D2DirectionAuthority.ordered_offer_ids`, с проверкой exact
service, typed extent и лимитом три. Нельзя выбирать по label, free text,
regex, semantic inference или legacy strategy selector.

Если услуга относится к нескольким direction либо у неё отсутствует
однозначный tenant-authored порядок, остановиться и запросить решение
владельца: не выбирать порядок молча и не возвращаться к legacy selector.

Подтверждённое исключение владельца для demo tenant: в
`clients/demo/target_response/d2_direction_prices.json` дополнить
существующий authored порядок All-on-4 только двумя уже существующими ID, так
чтобы полный порядок был `all_on_4.jaw.impro` →
`all_on_4.jaw.implantium` → `all_on_4.jaw.nobel`. Не менять сумму, валюту,
условия, текст, другие услуги или направления. Это не создаёт новую цену и
не даёт runtime права сортировать предложения самостоятельно.

## Точный write allowlist

```text
core/d2_dialogue.py
core/response_plan_materialization.py
clients/demo/target_response/d2_direction_prices.json
tests/test_d2_stage3_prices_scope.py
tests/test_d2_price_scope_selection.py
tests/test_d2_r1_contract.py
docs/tasks/DEMO_D2_STAGE3_PRICES_SCOPE_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Новые тесты допускаются только по названным путям. Не менять contracts,
production D1R prompt/parser, tenant data кроме явно названного
`d2_direction_prices.json` и только подтверждённых двух ID, HTTP/SSE/widget,
store/session context, lead/privacy owner или legacy runtime. Не добавлять
fallback, второй prompt/parser/state, новый strict gate,
семантические regex или ветки под фразы/услуги.

## Обязательное offline доказательство

Через `run_d2_dialogue_turn` с fake provider, temporary DB/log/tenant copy и
заблокированной сетью доказать:

- overview implantation/prosthetics и четыре typed volume actions;
- exact All-on-4 и другая известная услуга с несколькими предложениями:
  максимум три в tenant order, с price mode, единицей и обязательными
  условиями;
- `one_tooth`, `few_teeth`, `full_arch`, `unknown` и correction: known extent
  фильтруется до отбора; сумма не умножается;
- `no_public_price`, отсутствие подходящей опубликованной цены и отсутствие
  price данных не подменяются чужой/общей ценой;
- follow-up после этапа 2 сохраняет typed service/extent и ordered offer refs;
  tenant/lead/privacy и replay не регрессируют;
- несколько price requests: первая часть отвечает, следующие явно deferred;
  provider/live calls = 0.

Полный pytest запускается только доступным project runtime; нельзя ослаблять
проверки из-за окружения. До закрытия этапа обязательны `git diff --check`,
независимый Checker PASS, отдельный Cursor review и Ledger draft. Commit,
push, merge, deploy, live-вызовы и destructive cleanup — только по
отдельному разрешению владельца.

## Форма checkpoint по Execution Lock §5

- **ACCEPTANCE:** roadmap stage 3 и контрольные A01/A02/A07/A09/A10, B06;
  только applicable price/scope части, без объявления этапа 4 выполненным.
- **D2 ROUTE:** `run_d2_dialogue_turn` → production D1R parser → tenant
  snapshot → `resolve_d2_envelope_response` → один frozen response/UI plan →
  один `D2DialogueStore`.
- **LEGACY IMPACT:** legacy selector не вызывается для exact-service multi-offer;
  Composer/sales_fast, старая ordinary memory, fallback и второй owner не
  подключаются.
- **OWNER DECISION:** не требуется для tenant-authored exact-order selection;
  требуется при неоднозначной direction membership или отсутствии authored
  order у услуги.
- **FUTURE SCOPE:** mixed price+content assembly, HTTP/SSE/widget delivery,
  live provider, tenant-data redesign, merge/deploy — вне этапа 3.
- **Test isolation:** только temporary DB/log/tenant copy и fake provider;
  сеть заблокирована, `data/` и debug SQLite не затрагиваются.
- **Ledger draft / Checker / Cursor:** до review обновляется только после
  реализации в разрешённом allowlist; checkpoint не закрывается без обоих PASS.

Архитектурный вывод Astra учтён как read-only консультация; он не заменяет
согласование владельца.
