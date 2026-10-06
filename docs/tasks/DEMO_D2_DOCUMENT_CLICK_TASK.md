# D2-DOC-CLICK — явное задание документного клика и ordinary other

Дата: 2026-09-28. Владелец после read-only аудита разрешил обе коррекции,
синхронизацию документов и реализацию перед возвратом к ценам.
Это продолжение существующей D2-задачи; REC-4-P2 пока не начинается.
Приоритет: AGENTS.md → Execution Lock → Delivery Roadmap → Target Contract,
Product Decisions, Acceptance. Astra проверила архитектуру read-only.

## Baseline и границы

- Папка/Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`.
- HEAD и локальный origin branch: `a930ed70df9d2d709cc36b9076be55659485c582`
  (REC-4-P1 после независимого Checker и Cursor PASS, разрешённого commit/push).
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До работы tracked diff/staging пусты. Чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` сохраняются. Git предупреждает о правах
  на global ignore/`.pytest_cache`; это не разрешение их менять.
- Старые repo/worktree не трогать. Бот/live/provider/SMTP, merge/deploy,
  разрушительные действия не разрешены. Commit/push — отдельное разрешение.

## Подтверждённая проблема и результат

Трассы 28 сентября: `b4ff2b75` — проверенный клик анестезии принят моделью за
пустое сообщение; `other` с prose стал `content/authored`, gate отказал без
commit. `989e20cd` — модель дословно повторила прошлый ответ; replay=false.
`c603257c` — модель дословно вернула раздел о состоянии после установки.
Сырые payload/переписки в карточку и commit не включаются.

1. D2-104: сервер до provider уже разрешил документ/раздел. Тот же
   `D2SelectedDocumentAction` передаётся модели с обязательным непустым
   `section_title` из captured section через существующий `_document_followups`.
   Title — пояснение задания, не authority и не новое patient utterance.
   Authority остаётся tenant/revision/document/section. `USER_MESSAGE` не
   подменяется подписью кнопки, `selected_ui_ref` и action относятся к одному
   действию. Другие виды UI не получают document task.
2. Один prompt явно объясняет: выбранный раздел — текущий запрос, пустой q
   при клике ожидаем, прежняя prose — история. Ответить на выбранный вопрос
   своими словами по полному корпусу, не повторять прошлый ответ вместо
   уточнения. При дополнительном тексте учитывать его самостоятельный смысл.
   JSON-поля action/заголовок являются данными, не системными инструкциями.
3. D2-105: в единственном production parser непустая prose `content/other`
   при omitted `content_realization` получает `model_prose`. Explicit authored,
   invalid/null и пустой other не переписываются. Прежний other→content путь
   сохраняется; нового parser или fallback нет.
4. Downstream source/CTA binding, optional topic/service из D2-097/098,
   обычная память, lead/privacy, tenant/revision, transport/replay сохраняются.
   Нельзя чинить неподходящую prose заменой на абзац MD, regex или новым gate
   повторов. D2-092 действует, второй LLM/retry не добавляется.

## Точный write allowlist

```text
contracts/d2_dialogue.py
contracts/request_understanding.py
contracts/response_plan_materialization.py
core/d2_dialogue.py
core/d2_snapshot_sources.py
core/d2_live_provider.py
core/one_call_prompt_contract.py
tests/test_d2_document_click_task_http.py
tests/test_d2_envelope_correction.py
docs/tasks/DEMO_D2_DOCUMENT_CLICK_TASK.md
docs/tasks/DEMO_D2_TARGET_CONTRACT.md
docs/tasks/DEMO_D2_ACCEPTANCE.md
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md
```

Новые: эта карточка и HTTP-тест. В существующем envelope-correction тесте
допустима только версия единственного prompt; такая правка не потребовалась.
Tenant packs, frontend, price renderer,
store/schema, launcher, рабочие DB/logs и чужой WIP read-only.

## Приёмка и проверки

**ACCEPTANCE:** A03/B12/B15/B20, C01 и соседние tenant/UI/lead/privacy/replay
границы. Не полный REC-5 и не доказательство качества настоящей модели.
**D2 ROUTE:** `/ask`/`/ask/stream` → проверенный action → единственный provider
input/prompt → production parser → прежний materializer → frozen response,
ordinary memory и replay. **LEGACY IMPACT:** старый runtime не подключается.
**OWNER DECISION:** GO после объяснения обеих причин; вставка перед P2 принята.
**FUTURE SCOPE:** REC-4-P2, REC-5, отдельно согласованный bounded live eval.

- Baseline: `tests/test_d2_r1_contract.py`, `tests/test_d2_rec2_content_http.py`,
  `tests/test_d2_envelope_correction.py`; известный other failure не скрывать,
  сравнить на текущем clean baseline до правок.
- Новый test: два разных документа и соседние sections через реальные JSON/SSE;
  фактический prompt и полный corpus; q остаётся пустым; текущий question/title
  известен до model call; модельный текст сохраняется без серверной подмены;
  source/CTA/state/replay совпадают с тем же action.
- Raw omitted mode для other с prose проходит и на ручном вводе, и на клике;
  explicit authored остаётся строгим; invalid/null не нормализуются; empty other
  сохраняет штатный путь. Исторический `test_other_with_prose...` не менять.
- Stale/forged/foreign click не доходит до provider; lead/price choice не получает
  document action. Проверить существующие адресные tests widget replay/lead/B14.
- Все тесты offline: fake provider, временные tenant/DB/logs, запрет сети;
  `BOT_LOG_DIR` в temp до Python imports, pytest basetemp/cache только temp.
- Fake ответы доказывают проводку и сохранение смысла заданного ответа, но не
  надёжность генерации. Для последующей live-проверки: pain, другой документ,
  соседние кнопки, history/repeat; отдельные GO и бюджет.

Ledger draft с фактами до независимого Checker; затем отдельный Cursor review.
После REJECT — focused исправление и recheck. После PASS код и Ledger не
дописывать; только разрешённые exact stage/commit/push. P2 возобновить отдельным
GO на точном SHA принятого DOC-CLICK checkpoint.
