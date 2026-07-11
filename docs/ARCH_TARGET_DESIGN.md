# ARCH_TARGET_DESIGN — целевая архитектура понимания (demo)

**Статус:** утверждено Денисом 2026-07-11. Опора strangler-миграции.
**Основано на:** `docs/ARCH_RECON_REPORT.md`.

---

## Принцип

Уходим от RAG-наследного «стрелочника» (сейчас 6–10 LLM-вызовов + 5+ regex-слоёв, часть дублирует и спорит на одном ходе) к одной цельной форме. **НЕ рерайт с нуля — strangler:** сценарии переносим по одному на общий позвоночник, старые гейты удаляем по мере переноса, рабочую систему и детерминированную политику сохраняем.

## Форма: Понять → Политика → Ответить

1. **Понять** — один структурный LLM-вызов (эволюция `turn_planner`) → карточка хода по **ортогональным осям**.
2. **Политика** — тонкий **детерминированный** слой, срабатывает на карточке. Только там, где контроль обязателен.
3. **Ответить** — один composer (full context): тема + тон + пришпиленные факты.

## Схема «понять» (оси ортогональны, один вызов)

| Ось | Значения | Владелец |
|-----|----------|----------|
| **topic** | implantation, whitening, doctors, clinic, prosthetics… | тема ответа |
| **intent** | info, price_lookup, price_concern, booking, contacts | маршрут/политика (**цена живёт здесь**) |
| **aspect** | pain, duration, warranty, stages, comparison | под-аспект темы (чистый; `price` убран как дубль intent) |
| **emotion** | none, fear, doubt | **НОВАЯ ось** → политика; отдельно от клиники |
| **specificity** | overview, specific, comparison | форма ответа (бывш. query_mode) |
| **patient_scope** | one_tooth, full_arch, …, unknown | клинический объём (бывш. patient_situation, без эмоции) |
| service_id / followup_of / brand_filter / needs_clarify | — | policy inputs |

Цель — **один** вызов со всеми осями. Надёжность заполнения многих полей замерить в P0, не переусложнять двумя вызовами заранее.

## Политика (детерминированная)

**Сохранить как есть (несущее):** price regex scope, `numeric_fact_gate`, medzone-personal → hand-off, booking date-defer, contacts, ingress hard_stop/policies, price-card из pricebook, protocol/focus guards, `routing.yaml`.

**Новое правило (пилот emotion):**
- `emotion ∈ {fear, doubt}` И **нет** medzone-personal → **reassurance по ТЕМЕ**: контент самой темы + тёплый тон + успокаивающие факты этой темы. Trust-бандл (репутация/стаж) — только для темы «доверие/опыт», не для всех страхов.
- medzone-personal → hand-off (как сейчас).
- Явный ценовой сигнал (price regex) → цена. Эмоция **НЕ** даунгрейдит в `price_concern` без ценового сигнала.

## Сквозной закон: нет молчаливых fail-open, меняющих смысл

Причина бага T8 — тихий fallback планировщик→resolver с другой семантикой (угадал «цену»). Убираем как класс:

> Плохой/неизвестный вывод «понять» → **нейтральный безопасный дефолт** (content/composer), громкий лог. **Никогда не угадывать цену.** Валидация не крашится (unknown → null + log).

## Eval-net — ПРЕДУСЛОВИЕ, не поздний шаг

Живая routing-матрица (полный pipeline, **не стабы**) строится ДО любого переноса поведения. Юнит-стаб не единственный guard (он дал ложное зелёное на T8). Каждый перенос гейтится этой матрицей.

## Strangler-порядок

**Круг 1 (сейчас): пилот emotion.**
`eval-net` → `P0` (ось emotion + безопасный сбой + убить price-fail-open) → `P1` (политика reassurance по теме) → доказать fear-матрицу живьём → **ПАУЗА и разбор**.

**Позже (после паузы):** P3 trust→политика · P4 aspect_planner→planner.aspects · P5 resolver→тень · P6 patient_situation→planner.

## Trust-линия

Недоделанный fear→trust хак **не коммитить**. Репутацию (T1–T6) пересобрать как **policy-выход** оси `emotion=none, aspect=experience/reviews` в P3. Код trust (lookup/flow) переиспользовать как policy-модуль; приоритетный A3-гейт удалить после переноса.
