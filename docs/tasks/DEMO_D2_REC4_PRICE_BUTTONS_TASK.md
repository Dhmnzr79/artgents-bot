# D2-REC-4 — краткие цены и кнопки демо-диалога

Дата: 2026-09-28. Статус: **владелец дал GO на реализацию REC-4**;
Checker и Cursor review реализации ещё не проведены.
Это REC-4 текущего порядка восстановления, не исторический D2-S4 mixed response.
Применяются [Execution Lock](DEMO_D2_EXECUTION_LOCK.md),
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md),
[Target Contract](DEMO_D2_TARGET_CONTRACT.md),
[Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md) и
[Acceptance](DEMO_D2_ACCEPTANCE.md). Исторические Draft/PASS читаются со
своими датами и SHA, а не как текущий Git status.

## Preflight и baseline карточки

- Единственная рабочая папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка `codex/d2-stage1-contract`; HEAD и локальный
  `origin/codex/d2-stage1-contract`: `cebd09bd0deca0dd5c52fd0b3c4b70d6ef8dc654`.
  `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
  Свежий fetch в документальном шаге не выполнялся.
- До создания карточки tracked diff и staging пусты. Чужие untracked `data/`
  и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены; их не открывать для
  записи и не stage. Git предупредил о недоступности `.pytest_cache/` и
  global ignore, поэтому их untracked-состав этим preflight не доказан.
- Единственный write allowlist **подготовки карточки**:
  `docs/tasks/DEMO_D2_REC4_PRICE_BUTTONS_TASK.md`. Код, tenant data, Roadmap,
  Product Decisions, Acceptance, Ledger, тесты и журналы сейчас read-only.
  Перед реализацией повторить preflight и подтвердить новый baseline/allowlist.
- Перед кодовой правкой после GO preflight повторён на том же HEAD `cebd09b`:
  tracked/staged diff пуст, untracked остались `data/`, чужая marketing-заметка
  и эта карточка. Владелец разрешил реализацию по предложенному ниже
  точному allowlist; не перечисленные файлы read-only.
- После начала REC-4 обнаружены три существующих теста общей CTA с прежним
  `button_id=price` вне allowlist. Владелец отдельно разрешил добавить
  `tests/test_d2_continuation_scenarios.py`, `tests/test_d2_demo_snapshot.py`
  и `tests/test_d2_snapshot_sources.py` только для обновления этих проверок
  на нейтральную CTA D2-099; условия тестов не ослаблять.
- Владелец отдельно разрешил обновить в `tests/test_d2_demo_snapshot.py`
  проверку первой цены на краткий REC-4 формат: в ответе обязательны цена,
  объём и существенные условия, а прежние этапы оплаты должны оставаться
  в captured tenant offer. Это единственное расширение назначенного вида
  правок в `test_d2_demo_snapshot.py`.
- После сравнения с чистым HEAD владелец разрешил обновить одну проверку
  `tests/test_d2_snapshot_sources.py`: при цене удаления одного зуба
  опубликованный package scope заменяет общий повтор единицы, а проверки
  отсутствующих и повреждённых данных сохраняются.
- Старый репозиторий `C:\Cursor Projects\artgents-bot`, worktree 27e1,
  checkpoint `b8b28d3` и backup — сохранённая история, не источник
  автоматического переноса или fallback.

## Решение владельца и граница задачи

**OWNER DECISION.** Владелец 2026-09-28 подтвердил простое правило для демо:
если человек назвал одну конкретную услугу, показывать **все подходящие
опубликованные предложения этой услуги** коротким списком. Искусственного
предела в три позиции нет. В демо-каталоге не ожидается много предложений
одной услуги; если это изменится, способ показа большого списка обсуждается
в следующем обновлении, без скрытой пагинации в REC-4. Это сохраняет
Target Contract §7 и текущую строку REC-4 Roadmap. Общий вопрос «Сколько
стоит имплантация/протезирование?» остаётся отдельным утверждённым обзором
**до трёх** основных цен и кнопками объёма. Цены всех услуг/брендов каталога
не становятся «всеми ценами» одного ответа.

Новый untracked `docs/MARKETING_ANSWER_SCENARIOS.md` содержит общее правило
«не больше трёх предложений за раз». Для одного точного ценового запроса
эта строка не заменяет решение выше; у общего authored обзора сохраняется
собственный лимит до трёх. Этот чужой документ не входит в allowlist и не
правится задним числом.

Есть и **противоречие внутри tracked документов**: старое D2-073 в Product
Decisions устанавливает предел три даже для названной услуги, тогда как
позднейшие Target Contract §7 и Roadmap REC-4 задают для exact-service
все подходящие предложения без искусственного лимита. Сегодняшнее решение
владельца подтверждает последнее правило **для одного точного ценового
вопроса** и требует синхронизировать D2-073 до implementation review.
Фраза «до трёх внутри выбранного вопроса» в D2-080 и Target Contract §6
относится к отдельному случаю нескольких самостоятельных ценовых вопросов;
Acceptance B14 сохраняет первую ценовую часть и явное отложение второй.
REC-4 не переделывает multipart-механику. Если реализация обнаружит иной
конфликт этих правил, остановиться и показать владельцу конкретный сценарий
до изменения поведения. Исправление Product Decisions и, если требуется
для однозначности, Target Contract входит только в будущий implementation
allowlist после отдельного GO; сейчас они read-only.

**ACCEPTANCE.** Для точной услуги выбирать только active/published offers
текущего tenant с учётом проверенных service/brand/extent, числовые цены
по возрастанию, затем `no_public_price`, без чужой услуги, бренда,
самовольного лечения и лимита три. Первое ценовое сообщение должно кратко
различать позиции: название услуги/варианта, fixed/from/range либо честное
отсутствие публичной цены, сумма, единица и все существенные оговорки.
Не повторять в каждой позиции полный состав пакета и этапы оплаты, а также
не дублировать единицу внутри одной позиции; не убирать реальные различия вариантов и обязательные
условия. Подробности пакета — по запросу. Не выводить цену из текста модели,
не вычислять стоимость нескольких зубов/челюстей и не подставлять похожую
услугу при пробеле данных. Общий обзор использует только свой tenant-authored
набор, порядок, краткую нейтральную вводную и четыре кнопки объёма.

Показанные подписи быстрых вопросов по материалу должны быть человеческими:
без Markdown-якорей вида `{#section}`, но с прежними проверенными reply/section
refs. CTA материала имеет приоритет. Если её нет, разрешённый содержательный
ответ получает нейтральную CTA текущего tenant «Записаться на консультацию»;
клик входит в существующий lead-flow, сам показ не создаёт заявку. CTA не
обещает бесплатность и запрещена при текущей личной боли/жалобе, спаме,
активной заявке и чистом уточнении по D2-012/D2-023. Максимум две
secondary-кнопки, один navigation channel; прямой ценовой ответ не получает
обычные content follow-up/video. Choice-кнопки объёма остаются отдельными.

Проверяемые семьи: A01/A02/A07/A09/A10/A13/A14/A15, B06/B08/B12/B13/B14/B16/B17,
C04/C05/C07/C09/C10 в затронутых границах. Это не объявляет полную A15 или
REC-5 закрытыми.

**D2 ROUTE:** существующие `/ask` и `/ask/stream` → один production prompt и
parser → captured tenant snapshot → catalog/price/UI authority → один frozen
plan, render и store/replay → widget. Цена, label и CTA определяются только
проверенными данными текущего tenant, не переписыванием прозы модели.

**LEGACY IMPACT:** старые Composer/sales_fast, semantic selectors, второй
parser/LLM и per-request fallback не подключаются. JSON/SSE wire,
request/revision ownership и существующий lead/privacy owner не меняются.
Нет веток под отдельные фразы, услуги или наборы цен.

**FUTURE SCOPE:** REC-5 полная приёмка и ручная widget-проверка, будущий
показ по частям при реально большом каталоге, старые независимые read-only
падения REC-2, live/provider, merge и deploy. REC-4 не чинит двойные
ценовые вопросы путём изменения B14 и не добавляет новый runtime.

## Точный write allowlist будущей реализации

Перечень ниже — **утверждённый allowlist реализации после GO 2026-09-28**.
Наличие пути не требует его менять.

```text
core/response_plan_materialization.py
core/d2_snapshot_sources.py
clients/demo/tone.yaml
clients/nikadent/tone.yaml
clients/demo/target_response/d2_direction_prices.json
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
docs/tasks/DEMO_D2_TARGET_CONTRACT.md
tests/test_d2_rec4_price_ui_http.py
tests/test_d2_price_modes.py
tests/test_d2_price_scope_selection.py
tests/test_d2_content_source_ui.py
tests/test_d2_ui_b12_scenarios.py
tests/test_d2_continuation_scenarios.py
tests/test_d2_demo_snapshot.py
tests/test_d2_snapshot_sources.py
docs/tasks/DEMO_D2_REC4_PRICE_BUTTONS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

`core/d2_dialogue.py`, parser, prompt, store, widget, renderer, lead-flow,
прочие tenant packs и Roadmap остаются read-only. Если изменение окажется
необходимым вне списка, остановиться, объяснить узкую причину и получить
решение владельца до записи. Архитектурный read-only разбор с Astra
подтвердил существующие точки: frozen price row, tenant CTA authority,
document follow-up label и authored direction introduction. Заключение
Astra не заменяет GO владельца и не утверждает реализацию.

## Offline-проверка и ворота

- До кода снять узкий baseline на новом HEAD. Первый прогон четырёх выбранных
  тестовых файлов: 37 passed / 5 errors на setup из-за недоступного старого
  `%TEMP%/pytest-of-denis`; повтор с новым уникальным `--basetemp`: 41 passed /
  1 failed. Провал до правок: `test_free_cta_on_doctors_only_while_fact_window_open`
  (`patient_text_required` в прежнем authored doctor fixture). Отдельный
  старый stage-3 All-on-4 тест на baseline падал раньше проверки краткости:
  `situation_state is None`. Не исправлять их вне границы REC-4.
  Не переносить числа прежних
  PASS на новый diff. Старый `test_other_with_prose_gets_authored_help_not_price_gate`
  (`d2_experiment_content_not_resolved`) и старый history/`spam_closed`
  фиксировать отдельно, если они снова входят в набор; тесты не ослаблять.
- Fake provider и заблокированная сеть; временные tenant copy, DB и logs
  вне рабочего `data/`. Не открывать/изменять чужой SQLite. Порт 9001,
  provider/live и SMTP не запускать, бюджет реальных вызовов = 0.
- Проверить точную услугу с четырьмя различимыми опубликованными offers:
  все четыре коротко, правильный ascending и условия; другой service/brand
  не попал. Отдельно fixed/from/range/no_public, простая цена без optional
  metadata, обязательные оговорки, повреждённая optional UI и источник
  цены текущего tenant. Проверить общий обзор до трёх, нейтральную вводную,
  четыре кнопки и «Не знаю» без повторного scope-вопроса/lead.
- Проверить исходную CTA материала и её приоритет, отсутствие CTA источника,
  нейтральный fallback, запреты D2-012/D2-023, бесплатность только из
  применимого факта, клик → существующий lead owner. Проверить чистую
  подпись follow-up и сохранение того же section ref; stale/forged/foreign
  UI не проходят. При отсутствии цены доступный независимый материал и
  разрешённая CTA сохраняются (B16). У другого tenant свои label/price/CTA,
  без утечки.
- Для затронутых ходов сравнить JSON/SSE, видимый текст и UI, сохранённое
  состояние следующего хода и replay без повторного provider/effect.
  Смешанный price+content и B14 проверить как регрессию, не менять их
  критерии ради REC-4. Проверить, что краткость не удаляет существенные
  условия и не скрывает опубликованное предложение.
- После готового diff внести Ledger draft **до review** с ACCEPTANCE,
  D2 ROUTE, LEGACY IMPACT, OWNER DECISION, FUTURE SCOPE, allowlist,
  isolation и результатами. Получить независимый Checker PASS и отдельный
  Cursor review REC-4 по просьбе владельца. После PASS Ledger не
  дописывать. Commit/push — только после отдельного согласования владельца,
  exact staging и просмотра staged names/stat/diff/check. PASS карточки
  не является PASS реализации или разрешением live/merge/deploy.
