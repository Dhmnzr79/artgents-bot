# Документация

Документы в `docs/` описывают текущий runtime и живые рабочие контракты. Исторические roadmaps, которые уже отработали или были поглощены `FULLCONTEXT_ROADMAP.md`, удаляются из папки; при необходимости их можно поднять из git history.

---

## Канон runtime

| Документ | Для чего |
|---|---|
| `CURRENT_ARCHITECTURE.md` | текущая архитектура `/ask`, composer, price, Stage 5.5 |
| `ROUTING_MAP.md` | порядок маршрутов и route labels |
| `MULTICLIENT.md` | client packs, sessions, domains, provider model |
| `TECH_DEBT.md` | открытый долг и закрытые решения |
| `FULLCONTEXT_ROADMAP.md` | живой roadmap full-context ядра |

---

## Подсистемы

| Документ | Для чего |
|---|---|
| `PRICEBOOK_V2.md` | модель и сценарии PriceBook |
| `WIDGET_ANSWER_FORMAT.md` | формат ответа для виджета |
| `DASHBOARD.md` | admin dashboard, events, Postgres |
| `MARKETING_EDITING_GUIDE.md` | как править marketing copy/config |
| `DOCS_AUDIT.md` | снимок сверки docs vs код (2026-07-10) |

---

## Правила

- Если код и docs расходятся, сверяться с кодом и править docs в том же PR.
- Не описывать RAG/search как runtime: content-путь после Stage 3.4 — full-context composer.
- `core/md_chunks.py` и `get_chunk_by_ref` — это прямой ref resolver, не RAG.
- Цены, бренды, порядок и кнопки — deterministic; LLM пишет только текстовое обрамление там, где это явно включено.
- Активная продуктовая работа по умолчанию идёт по `clients/demo/`; другие packs трогать только по задаче владельца.
