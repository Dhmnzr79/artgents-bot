# Аудит документации vs код (снимок 2026-07-12)

**Контекст:** после пилота emotion P0+P1 (ось `emotion`, fail-open kill, reassurance policy, eval-net).  
**Метод:** сверка `docs/` с runtime, неполным коммитом P0+P1 и артефактами `eval_emotion_matrix_last.txt`.

При расхождении: **код** — для emotion-слоя; **`FLAGS_AND_STATUS.md`** — для флагов; **`clients/demo/`** — для базы.

---

## Резюме

| Зона | Соответствие docs ↔ код |
|------|-------------------------|
| Ядро (composer, pricebook, booking, medzone-price→consult, флаги) | **OK** — снимок `DOCS_AUDIT.md` (2026-07-10) актуален |
| Пилот emotion (P0+P1) | **Разрыв** — в operational-docs почти не отражён |
| ARCH «цель» vs «как было» | TARGET совпадает с кодом; RECON — **исторический** baseline, не текущий runtime |

**Вывод для аудита бота:** критичных противоречий по деньгам/букингу/композеру нет. Главный долг docs — зафиксировать emotion-пилот в `CURRENT_ARCHITECTURE.md` и обновить `DOCS_AUDIT.md`.

---

## Соответствует коду

| Документ | Назначение |
|----------|------------|
| `FLAGS_AND_STATUS.md` | Дефолты, kill-switch, канон eval-флагов |
| `PRICEBOOK_V2.md`, `MARKETING_EDITING_GUIDE.md` | Demo-пак, facts, цены |
| `ROUTING_MAP.md` | Базовая цепочка ingress → planner/resolver → composer/price |
| `ARCH_TARGET_DESIGN.md` | Целевая модель: ось `emotion`, safe default, P3 trust |
| `evals/v5/demo/emotion.json` + `eval_emotion_matrix_last.txt` | Фактический снимок маршрутов страхов (живее текстовых docs) |

---

## Устарело или вводит в заблуждение

| Документ | Расхождение | Связь с P0+P1 |
|----------|-------------|---------------|
| `CURRENT_ARCHITECTURE.md` (2026-07-10) | Нет `emotion`, `emotion_policy`, `medzone_personal`, safe default planner | **Да** |
| `ARCH_RECON_REPORT.md` | Описывает **до-P0**: нет emotion, fail-open T8, `trust_medzone_personal` | **Да** — recon, не runtime |
| `DOCS_AUDIT.md` (2026-07-10) | Не фиксирует emotion-пилот | **Да** |
| Упоминания medzone-personal в ARCH | `trust_medzone_personal` / ingress | В коде: **`core/medzone_personal.py`** |

---

## План vs факт (не ошибка docs, но для аудита)

| Тема | Docs | Код |
|------|------|-----|
| P0+P1 emotion | TARGET: «круг 1 сейчас» | **Реализовано** (eval 8/8) |
| Trust/rep | P3, target = `trust_chunk` | Composer — **ожидаемо** до P3 |
| Topic `whitening` | В RECON в таблице осей | `ServiceTopic` **без whitening** → `unknown` |
| `aspect_planner` | P4, кандидат на снос | Сосуществует с planner — docs честны |
| `marketing.yaml` → `limits:` | Мёртвый конфиг | По-прежнему не применяется |

---

## Где смотреть при аудите

| Вопрос | Источник |
|--------|----------|
| Runtime, флаги, price/booking | `FLAGS_AND_STATUS.md`, `CURRENT_ARCHITECTURE.md` *(+ поправка: emotion в коде)* |
| Страхи, fail-open, тон | `ARCH_TARGET_DESIGN.md`, `eval_emotion_fear_answers_last.txt` |
| «Что было сломано» (T8 и т.д.) | `ARCH_RECON_REPORT.md` — **история**, не «как сейчас» |
| База клиники | `clients/demo/`, `MARKETING_EDITING_GUIDE.md` |

---

## Рекомендуемые правки docs (после коммита P0+P1)

1. `CURRENT_ARCHITECTURE.md` — +5 строк: `emotion` в `TurnPlan`, `core/emotion_policy.py`, `core/medzone_personal.py`, safe default в `resolver_turn`.
2. `DOCS_AUDIT.md` — дополнить секцию «emotion pilot 2026-07-12».
3. `ARCH_RECON_REPORT.md` — шапка: «baseline до P0; актуальный runtime — TARGET + eval-net».

---

*Обновлять после коммита emotion-пилота и при старте P3 (trust).*
