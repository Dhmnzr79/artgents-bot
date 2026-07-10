# Аудит документации `docs/` vs код

**Дата снимка:** 2026-07-10  
**Статус:** правки по P0–P2 **внесены** в том же коммите/сессии (см. ниже).  
**Метод:** сверка с runtime, `config.py`, `clients/demo/`, тестами и CI.

При расхождении docs и кода — **код + `FLAGS_AND_STATUS.md`** для флагов, **`clients/demo/pricebook/`** для demo-денег и акций.

---

## Резюме (после правок)

| Категория | Было | Стало |
|---|---|---|
| Архитектура / routing | устарели даты, нет `brand_money` | `CURRENT_ARCHITECTURE`, `ROUTING_MAP` обновлены |
| PriceBook / маркетинг | примеры 15 июля, 15k, `promo` в service | `PRICEBOOK_V2`, `MARKETING_EDITING_GUIDE` = канон demo |
| Виджет | answer slots как runtime | слоты сняты; промо через карточки пакета |
| DASHBOARD | оба retrieval-события «мертвы» | только `retrieval_fallback` снят; `retrieval_selected` оставлен |
| FULLCONTEXT | шапка «symptom OFF» | журнал помечен; текущие дефолты в FLAGS |

---

## Что поправили (чеклист)

- [x] `PRICEBOOK_V2.md` — facts, whitening 18k / 15 авг., без `promo` в service JSON на demo
- [x] `MARKETING_EDITING_GUIDE.md` — канон 6 фактов, pytest без `test_answer_slots.py`
- [x] `WIDGET_ANSWER_FORMAT.md` — убраны frontmatter slots
- [x] `CURRENT_ARCHITECTURE.md`, `ROUTING_MAP.md` — `brand_money`, `ui.yaml`, даты, composer gate
- [x] `FULLCONTEXT_ROADMAP.md` — дефолты ON; журнал 2026-07-08 с пометками «на тот момент»
- [x] `DASHBOARD.md` — убран только `retrieval_fallback`
- [x] `TECH_DEBT.md` — закрыто whitening / marketing cleanup demo
- [x] `MULTICLIENT.md` — `ui.yaml`, дата
- [x] `README.md` — ссылка на этот файл

---

## Заметки ревью (исправления первой версии аудита)

1. **`retrieval_selected`** жив (`orchestration/helpers.py`); снесён только **`retrieval_fallback`**.
2. Пример **`veneers` без `implant_warranty`** в роадмапе Этапа 7 — **верен** (`fact_refs` без warranty).
3. Working agreement «флаги OFF» — **процесс для новых этапов**, не текущие дефолты ядра.

---

## Остаётся открытым (код / backlog, не только docs)

- `marketing.yaml` → `limits:` — грузится, не применяется (см. `FLAGS_AND_STATUS`, Этап 7).
- `free_implant_consult` `kind: promo` vs медзона — план `promo` → `benefit`.
- `test_patient_playbook.py` не в CI.
- `core/claim_gate.py` — хвост в коде.
- Marketing-тесты в `MARKETING_EDITING_GUIDE` — локально; в `ci.yml` пока нет.

---

## Где опираться

| Вопрос | Документ |
|---|---|
| Runtime / `/ask` | `CURRENT_ARCHITECTURE.md`, `ROUTING_MAP.md` |
| Флаги | `FLAGS_AND_STATUS.md` |
| Demo-акции и facts | `MARKETING_EDITING_GUIDE.md`, `clients/demo/pricebook/facts.json` |
| Demo-цены | `clients/demo/pricebook/README.md` |
| Roadmap / история решений | `FULLCONTEXT_ROADMAP.md` |
| Долг | `TECH_DEBT.md` |

---

*Обновлять после крупных правок runtime или demo-пака.*
