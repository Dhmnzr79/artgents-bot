# Документация

Документы в `docs/` описывают текущий runtime, архитектурное направление и рабочие продуктовые контракты. Исторические audit/evidence сохранены отдельно от канона текущего checkpoint.

---

## Главные точки входа

| Документ | Для чего |
|---|---|
| `CURRENT_ARCHITECTURE.md` | текущий runtime |
| `STRANGLER_ROADMAP.md` | текущий статус A1–A9 |
| `ARCH_TARGET_DESIGN.md` | архитектурное направление |
| `FULLCONTEXT_ROADMAP.md` | широкий историко-продуктовый roadmap; **не** канон текущего checkpoint |

---

## Активные продуктовые документы

| Документ | Для чего |
|---|---|
| `MARKETING_QUESTION_FOUNDATION.md` | продуктовый фундамент маркетинговых вопросов |
| `MARKETING_QUESTION_TECH.md` | техническая модель маркетинговых вопросов |
| `SERVICE_SELECTION_CONTEXTS.md` | контексты выбора услуги |
| `PRICEBOOK_V2.md` | модель и сценарии PriceBook |
| [`../drafts/PRICE_RESPONSE_RULES_DRAFT.md`](../drafts/PRICE_RESPONSE_RULES_DRAFT.md) | активный продуктовый черновик правил ценовых ответов |

---

## Исторические audit/evidence

| Документ | Для чего |
|---|---|
| `TURN_FRAME_SHADOW_AUDIT_A3.md` | A3 — первый аудит TurnFrame |
| `TOPIC_SHADOW_AUDIT_A6.md` | A6 — измерение качества topic |
| `TOPIC_SHADOW_REAUDIT_A7.md` | A7 — повторный topic-аудит |
| `FIELD_LEVEL_PLANNER_OUTCOME_A7.md` | A7 — field-level planner outcome |
| `A7_REGRESSION_LIVE_PROOF.md` | A7 — live regression proof |
| `PATIENT_SCOPE_DESIGN_A9.md` | A9 — original patient-scope design |
| `PATIENT_SCOPE_SHADOW_AUDIT_A9.md` | A9 — shadow audit |
| `PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` | A9 — native extraction design |
| `PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md` | A9 — frozen raw/projection/parser/prompt spec |
| `ARCH_RECON_REPORT.md` | архитектурная разведка (baseline для target design) |
| `DOCS_AUDIT.md` | снимок сверки docs vs код |
| `TRUST_INTENT_PHASE1_REPORT.md` | отчёт phase 1 trust/intent |

---

## Эксплуатационные документы

| Документ | Для чего |
|---|---|
| `FLAGS_AND_STATUS.md` | флаги, дефолты, канонный набор для прогонов |
| `ROUTING_MAP.md` | порядок маршрутов и route labels |
| `MULTICLIENT.md` | client packs, sessions, domains, provider model |
| `WIDGET_ANSWER_FORMAT.md` | формат ответа для виджета |
| `DASHBOARD.md` | admin dashboard, events, Postgres |
| `TECH_DEBT.md` | открытый долг и закрытые решения |
| `MARKETING_EDITING_GUIDE.md` | как править marketing copy/config |

---

## Правила

- Если код и docs расходятся, сверяться с кодом и править docs в том же PR.
- Текущий A-series checkpoint — только в `STRANGLER_ROADMAP.md`; `ARCH_TARGET_DESIGN.md` и `FULLCONTEXT_ROADMAP.md` на него не дублируют.
- Не описывать RAG/search как runtime: content-путь после Stage 3.4 — full-context composer.
- `core/md_chunks.py` и `get_chunk_by_ref` — это прямой ref resolver, не RAG.
- Цены, бренды, порядок и кнопки — deterministic; LLM пишет только текстовое обрамление там, где это явно включено.
- Активная продуктовая работа по умолчанию идёт по `clients/demo/`; другие packs трогать только по задаче владельца.
