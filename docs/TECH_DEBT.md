# Tech Debt

**Статус:** открытый долг после post-RAG cleanup.  
**Обновлено:** 2026-07-10.  
**Runtime:** `CURRENT_ARCHITECTURE.md`.

---

## 1. До prod

| Задача | Комментарий |
|---|---|
| Freeze pack `cesi` / `nikadent` | продуктовые правки без явной задачи — только `clients/demo/` |
| VPS + Caddy + wildcard domains | один bot-service, host → client id |
| Smoke 10-20 вопросов на клиента | цена, врачи, контакты, lead |
| `allowed_origins` | реальные домены сайтов клиник, не только bot-subdomains |
| Lead delivery | проверить `features.yaml` + `lead_config.yaml` для prod packs |
| Demo media/content placeholders | заменить перед публичным показом |

---

## 2. Живой runtime-долг

| Долг | Статус |
|---|---|
| PriceBook v2 остатки | S2 detail refs, S6 brand_group, legacy price fallbacks, lint followup refs |
| `price_concern` для протезирования | при пустом `concern_ref` может уходить в общий implant cost FAQ |
| Follow-up compatibility | MVP есть; остаются gray-zone rewrite и better aspect carry |
| Patient situation | есть playbook и situation-price; нужны one-tooth playbook, real clarify, urgent slice |
| Content “что подойдёт” | работает на текущем playbook flow; будущий рендер можно перевести на `SituationView` |
| Lead flow v2 | расширить gray-zone classifier/evals для длинного хвоста отказов и пауз |
| Guide router | отложен; включать только отдельным флагом и отдельным eval |
| `core/claim_gate.py` | pipeline blocklist снят, но файл-хвост ещё существует; удалить отдельной маленькой уборкой после grep |

---

## 3. Закрыто, не возвращать

| Закрыто | Решение |
|---|---|
| RAG search stack | удалён в Stage 3.4; content идёт через full-context composer |
| OpenAI embeddings in runtime | сняты вместе с RAG |
| Superseded composer/dialog/marketing roadmaps | удалены из `docs/`; история остаётся в git |
| Pre-resolver booking LLM | lead gate только по explicit booking regex/ref; policy LLM не перехватывает ход |
| Dialog focus roadmap | реализован, отдельный roadmap удалён |
| Marketing cleanup demo (2026-07) | акции сведены в `facts.json` + `promo_rules`; см. `MARKETING_EDITING_GUIDE.md` |
| Whitening 15k vs 18k | demo: **18 000 ₽** `from` в pricebook |
| Price-scope planner experiment 5.5a-2 | отменён; regex price-routing остаётся для dental bot |

---

## 4. PriceBook v2

Оставшиеся UX/data вопросы:

| # | Проблема |
|---|---|
| 1 | Simple service detail refs: “что входит” должно уметь открывать detail md без новой цены |
| 2 | Brand group routing: “корейские импланты” должен попадать в `brand_group`, если это есть в данных |
| 3 | Legacy price fallbacks — для cesi/nikadent; demo уже на чистом pricebook |
| 4 | Catalog price refs: привести catalog к целевому `pricebook_id`, где нужно |
| 5 | Pricebook lint: проверять resolvable followup/detail refs |
| 6 | Product eval: не ослаблять golden при переходе на компактные deterministic replies |

См. `PRICEBOOK_V2.md`.

---

## 5. Patient situation

Уже есть:

- `core/patient_situation.py`;
- `core/patient_playbook.py`;
- `patient_options_overview`;
- `SituationView`;
- `situation_price_overview` за `SITUATION_PRICE_ON`.

Открыто:

- playbook для `one_tooth_missing`;
- real clarify на неоднозначных ситуациях;
- urgent slice без агрессивного booking;
- content-render через `SituationView`, если это даст пользу без риска.

---

## 6. Price routing

Текущее решение: dental regex-routing остаётся.

Почему:

- вопросы вида “сколько имплантация” — это method/category price scope, а не ситуация пациента;
- planner contract не является надёжным источником `PriceScopeResult`;
- live-проверка 5.5a-2 ухудшила D1: вместо обзора протоколов был выбран конкретный протокол.

Не делать:

- не возвращать `PRICE_ROUTING_FROM_PLANNER`;
- не удалять `core/price_scope.py` и `core/patient_scope_cues.py` без нового владельческого решения;
- не добавлять blocklists вместо позитивных scope rules.

---

## 7. Docs hygiene

При изменении runtime:

1. обновлять `CURRENT_ARCHITECTURE.md`;
2. если меняется порядок маршрутов — обновлять `ROUTING_MAP.md`;
3. если меняется структура client pack — обновлять `MULTICLIENT.md`;
4. если долг закрыт — переносить в “Закрыто” или удалять строку;
5. не держать отработанные roadmaps в `docs/`, если они поглощены живым документом.
