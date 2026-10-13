# D2 — коррекция model envelope и подписи цены после widget-аудита

Дата: 2026-09-26. Статус: владелец дал GO на эту ограниченную коррекцию
после checkpoint REC-3, до REC-4. Это отдельный checkpoint текущего recovery
roadmap; он не закрывает REC-4 или полную приёмку REC-5.

## Preflight и baseline

- Рабочая папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`; HEAD и origin branch:
  `28ff60a4f51228dec1409e7b703cd279ea2dcee7`.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
  Свежий fetch в этом preflight не выполнялся.
- Tracked diff и staging пусты до карточки. Чужой untracked `data/` сохранён,
  не открывать и не stage. Git предупреждает о недоступности `.pytest_cache/`
  и global ignore, поэтому полнота их untracked-обзора не подтверждена.
- Исторические строки Roadmap/Ledger относятся к своим checkpoint, а не к
  текущему Git-status. REC-3 сохранён в `28ff60a`.

## Evidence и ограниченный результат

- Свежая сессия, trace `5ef8618b5a1e42779a623786260d4334`:
  вопрос о цене классической имплантации и виниров дал модельный CLARIFY
  с обеими услугами, но `service_reference_status=resolved` при
  `requested_service_id=null`. Единственный parser правильно отверг
  противоречие; widget показал технический `d2_invalid_turn`, commit не было.
- Контекстный trace `d98693aec12047e5956a5b313d02a39e`: модель потеряла
  явно названные виниры и предложила прежний All-on-4. Одна лишь очистка
  старой памяти не объясняет свежую сессию и не является исправлением.
- Смешанный вопрос о приживаемости имплантов и цене отбеливания, trace
  `5a895f2218744531a68641b2210fe52a`: обе части были сохранены, но
  code-owned цена показана без названия услуги. Цена и текст материала
  относятся к разным услугам, поэтому подпись должна брать имя именно из
  проверенного offer текущего tenant.

**ACCEPTANCE:** B14, D2-080/T2 — явно названные независимые запросы
сохраняются в исходном порядке; при двух ценах первая получает проверенный
ценовой блок, вторая явно deferred; сочетание цены и информации сохраняет
обе части. Простой вопрос, короткое продолжение, смена услуги и настоящая
неоднозначность не регрессируют. C01/R4 — противоречивый model envelope
остаётся неуспешным ходом без цены, UI, commit ordinary/lead и ложного replay;
widget показывает нейтральную человеческую ошибку вместо технического кода.
D2-093 — каждая frozen price row перед суммой называет услугу из
`bundle.services[offer.service_id].name` текущего tenant; режимы fixed/from/
range/no_public_price, порядок offers и существенные условия сохраняются.

**D2 ROUTE:** один действующий prompt и provider call → production parser →
captured tenant snapshot → binding/materializer → frozen plan → JSON/SSE,
widget и store/replay. Ошибка parser остаётся ошибкой транспорта; только
видимый текст widget для `d2_invalid_turn` становится понятным. Никакого
второго semantic parser, повторного model call или восстановления цен из
частичного JSON.

**LEGACY IMPACT:** старый Composer/sales_fast, semantic regex и старая
ordinary memory не становятся fallback. Server-owned цены, tenant/UI/lead/
privacy границы и действующий public wire сохраняются.

**OWNER DECISION:** владелец разрешил эту коррекцию и добавил название услуги
перед ценой. Действующий B14 и D2-080 не смягчать. Astra выполнила
read-only архитектурный разбор; её мнение не подменяет согласования владельца.
Новая schema, автоматическая нормализация конфликтующих обязательных полей,
новые клинические правила и второй вызов модели не разрешены этой карточкой.

**FUTURE SCOPE:** REC-4 сокращает ценовые блоки, убирает повтор единицы
вроде «за одну процедуру — за одну процедуру», чистит подписи кнопок и
реализует нейтральную CTA; REC-5 проводит полную приёмку. Если prompt
неустойчив в отдельно разрешённом live eval, вопрос об упрощении избыточных
полей model envelope — новая архитектурная карточка и решение владельца.

## Точный write allowlist

```text
docs/tasks/DEMO_D2_ENVELOPE_CORRECTION_TASK.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
core/one_call_prompt_contract.py
core/d2_live_provider.py
core/response_plan_materialization.py
static/widget/widget.js
tests/test_d2_envelope_correction.py
tests/test_d2_price_modes.py
tests/test_d2_multipart_scenarios.py
tests/js/d2_widget_harness.mjs
```

Все прочие code, tenant packs, local DB/logs и foreign WIP read-only.
Если понадобится иной файл или изменение schema/wire, остановиться и
предъявить владельцу точную причину и новый allowlist до записи.

## Проверка и ворота

- Исходный офлайн baseline до правок: `test_d2_live_provider_offline.py`,
  `test_d2_multipart_scenarios.py`, `test_d2_price_modes.py` — 15 passed,
  1 failed. Исторический тест ожидает prompt v19 при текущем v20; его
  ожидание не подгонять. Прямой JS harness без подготовленного HTTP payload
  не запускается; использовать его штатный Python fixture.
- Адресные fake-provider/parser/HTTP тесты: простые вопросы, continuation,
  explicit new service, две цены в обоих порядках, цена + информация,
  настоящая неоднозначность, malformed envelope, tenant/price/UI/lead
  boundaries, JSON/SSE/store/replay. Проверить frozen name на двух tenant,
  разных услугах и во всех price modes без изменений сумм и условий.
- Временные БД, логи и tenant copies вне рабочего `data/`; сеть и provider
  запрещены. Live eval — только отдельное GO владельца и бюджет вызовов.
- Перед review подготовить Ledger draft с доказанными фактами. На связный
  checkpoint — независимый Checker и затем Cursor. После PASS Ledger не
  менять. Commit/push только после разрешения владельца; merge/deploy —
  отдельно.
