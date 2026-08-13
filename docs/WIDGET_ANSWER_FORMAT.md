# Формат текста ответа в виджете

Канонический контракт между **Generator** (LLM) и **виджетом** (`static/widget/`).

## Разрешённый поднабор Markdown

| Элемент | Синтаксис | Примечание |
|---------|-----------|------------|
| Абзац | Текст, абзацы через пустую строку | 0–1 короткая вводная фраза, затем суть |
| Маркированный список | `- пункт` | Рендер с круглым маркером в CSS, не символом в тексте |
| Нумерованный список | `1. пункт` | Обычная нумерация |
| Выделение | `**текст**` | Только ₽, %, сроки, **Этап N**, **пожизненная** — не бренды |

## Запрещено в ответе

- Заголовки `#`, `##`
- Ссылки `[текст](url)`, сырой HTML
- Вложенные списки
- Таблицы, кодовые блоки
- Символы «галочки» / `•` вручную (оформление — на фронте)
- Служебные комментарии из md (`<!-- aliases: ... -->`)

## Когда список, когда абзац

- **Список** — если в ответе **3+** однотипных пункта (цены, шаги, варианты систем).
- **Абзац** — если мысль укладывается в 1–2 предложения.
- Не перечисляй факты списком «для красоты», если достаточно связного текста.
- **Нельзя начинать ответ со списка** — сначала одна короткая вводная фраза, связанная со списком.
- Первый символ ответа не должен быть `-`, `•`, `1.`.

Если LLM всё же начал со списка, бэкенд добавляет вводную детерминированно (`core/answer_lead.py`).

## Источник md vs ответ

В файлах `md/` допустимы `<!-- aliases: ... -->` и сложная вёрстка для индекса.  
В контекст LLM комментарии aliases **не попадают** (см. `chunk_context_md_for_llm`).  
Модель не обязана копировать `**` из источника — виджет их отрисует, если они есть в ответе.

## Маркетинг и промо (composer path)

На `price_lookup` и в композер-пакете промо/платёжные факты приходят из **карточек пакета** (`fact_refs` → `facts.json`), не из frontmatter md.

Порядок в `answer`: суть (LLM) → детерминированные карточки price/promo/payment → policy/CTA не переписывают уже записанный текст.

**Удалено с runtime:** answer slots из frontmatter (`clinic_note`, `consult_value`, `promo_note`) — не применяются на composer-пути. Маркетинговый смысл → `facts.json` + `marketing.yaml` (`MARKETING_EDITING_GUIDE.md`).

## Price tail (детерминированный хвост)

На `price_lookup` бэкенд дописывает или отдаёт **целиком** детерминированный price-блок. Суммы **не** из LLM.

| Путь | Когда | Источник |
|------|-------|----------|
| **PriceBook v2** | есть `pricebook/services/{service_id}.json` (demo — всегда) | `core/price_answer_assembler.py` — полный ответ + quick replies |
| **Legacy append** | нет pricebook entry (другие client packs) | `core/price_offers.py` → `generator_append_text` |

Может содержать маркированный список с `**суммами**` — разрешённый поднабор markdown.

Telemetry в `meta`: `price_offers_applied`, `price_offer_ids`, `price_offer_unit` (см. `CURRENT_ARCHITECTURE.md` §6).

---

- Промпт: `RESPONSE_FORMAT` в `llm.py` (все ветки Generator, включая стрим).
- Рендер: `static/widget/answer_format.js` + стили `.clinic-msg__body--rich` в `widget.css`.

## Стриминг и terminal lifecycle (current widget/SSE contract)

**Статус:** синхронизировано с принятым Stage 5.2 (`490bdbb`; test EOL cleanup `984ab65`). Server SSE schema/order **не менялись** в Stage 5.2.

### Terminal protocol (инварианты важнее единого event order)

- На один user turn server path эмитит **не более одного** `event: ui` и **не более одного** `event: done`.
- **`ui` принимается до `done`.** `done` завершает уже принятый turn, а не предшествует final UI.
- Конкретный порядок control events (`status`, `typing`, `text_delta`) может отличаться по path (direct/0-call vs normal stream); инварианты `ui≤1`, `done≤1`, `done` terminal сохраняются.

### Источник final text

- **Final `ui.answer` — authoritative final text** для state-backed bot bubble.
- `text_delta` — live presentation only; виджет может показать временный live bubble во время stream.
- При совпадении streamed и final текста виджет может использовать streamed форму без визуальной подмены.
- При расхождении authoritative final UI **заменяет** speculative/partial live text; live и final **не складываются** в два сообщения.
- Direct/0-call path может не иметь `text_delta`; normal stream — 0..N `text_delta`.
- `status` / `typing` — control/lifecycle events, не patient answer.

### Parser (`static/widget/api.js`)

- State принадлежит одному `streamAsk()`.
- Valid UI payload: plain object с `answer` или `meta`; `{}`/массив/примитив не занимают authoritative slot.
- Первый valid `ui` принимается; duplicate/late `ui` игнорируется; `onUi` максимум один раз.
- `onDone` максимум один раз; duplicate `done` игнорируется.
- EOF после accepted UI без `done` → безопасная синтетическая финализация.
- Reader/network error после accepted UI → `finalizeOnce()` без `onError` и без второго lifecycle.
- Transport error до valid UI → обычный error path (`onError`, pending cleared, без final bot message).
- JSON fallback проходит тот же exactly-once lifecycle.

### Widget (`static/widget/widget.js`)

- Один user turn → максимум один `state.messages.push`, один terminal `renderFeed`, один `endPendingRequest`.
- `finalizeTurn()` идемпотентен: duplicate terminal callbacks не создают второй bubble.
- Control metadata (`meta.service_route`, `provider_calls` и т.п.) пациенту **не показывается**.

### Historical / server-side prebuffer

Серверный **prebuffer** (`core/stream_answer_text.py`) может применяться на server stream path для lead-before-list и display-текста **до** `text_delta`. Это **не** заменяет authoritative `ui.answer` в виджете и **не** является stream owner final bubble. Если path не использует prebuffer (direct/0-call), виджет всё равно финализируется по `ui` / streamed fallback rules Stage 5.2.
