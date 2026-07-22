# ARCH_TARGET_DESIGN — целевая архитектура (v4)

**Статус:** v4, обновлено 2026-07-12 после трёх раундов независимой рецензии. Заменяет v1–v3.
**Честно:** ранние версии выдавали переходную форму за целевую и содержали внутренние противоречия. Исправлено. Помечено **TARGET** vs **СЕЙЧАС**. Историческая опора: [`archive/ARCH_RECON_REPORT.md`](archive/ARCH_RECON_REPORT.md).

---

## Цель №0 — мета-цель (над всем)

> **Меньше сущностей.** **Composer отвечает по умолчанию** (режим evidence — по риску и уверенности TurnFrame). Отдельная механика допустима **только по трём причинам: безопасность · необратимые действия · точные внешние контракты** — и только как **тонкий гард**, не как маршрут.

Примеры по причинам:
- **безопасность:** медзона, hard-stop;
- **необратимые действия:** booking, **создание/отправка лида**;
- **точные внешние контракты:** цена из pricebook, числа/факты из базы, **контакты клиники (адрес/сбор данных)**.

Тон и промо — надстройки по тем же правилам. 🚩 Новый гейт/классификатор/обработчик под **тему** (а не под одну из трёх причин) = скат назад.

## Цели → где живут

| Цель | Где |
|---|---|
| Точные ответы по базе | Composer + дословность |
| Эмпатичные/продающие по конверсии | Политика: флажок `emotion` → тон + фокус (надстройка, НЕ маршрут) |
| Даже если понимание не сработало — хороший ответ по базе | Сквозной закон: сбой → безопасный дефолт, уважающий жёсткие сигналы |
| Цена (бренды/зуб/челюсть) | Boundary: детерминированный ценовой слой (pricebook) |
| Маркетинг (акции) | Политика-надстройка (промо-гейт) |
| Не диагностировать/не выдумывать | Медзона boundary + числовой Verifier + дословность |
| Точные факты и цифры | Verifier (числа) |
| Контекст, уточняющие | TurnFrame: оси specificity/follow-up + история |

---

## Целевая цепочка (TARGET)

```
Boundary detection → TurnFrame → Boundary enforcement + Response policy → Evidence assembly → Composer → Verifier
```

1. **Boundary detection** — дешёвая ранняя детекция. **Полностью коротко замыкают до TurnFrame только** hard-stop, contacts, однозначный booking. **Цена и медзона здесь только детектятся** и ставят **обязательный флаг, который LLM не может отменить** — услугу/объём/форму часто видно лишь после TurnFrame.
2. **TurnFrame** — **один логический контракт**: `topic`, `intent`, **`aspects[]` + `primary_aspect`**, `emotion`, `specificity`, `patient_scope`, **`service_id`**, `follow_up` + **confidence/provenance по каждому полю**. Один контракт ≠ обязательно один физический вызов; для серой зоны допустим узкий доп-resolver. (Составные вопросы — через `aspects[]`, без обходного слоя.)
3. **Boundary enforcement + Response policy** — применяет обязательные флаги (цена→детерминированная price policy, медзона→`response_mode=medical_handoff`) и формирует **декларативный `ResponseSpec`**: тон, `allowed_topics`, `forbidden_topics`, обязательные факты, hand-off?, допустимые deterministic cards. **НЕ таблица тематических промптов.**
4. **Evidence assembly** — **`primary evidence` ВСЕГДА тематически ограничен** (по topic/aspects + `ResponseSpec.allowed/forbidden`). Полная база — только **доп. фон для низкорисковых** ответов, не основа. `allowed/forbidden_topics` применяются **независимо от размера базы**. Композер формулирует по выделенному evidence, а не выбирает факты сам. **Это не возврат старого vector-search/router стека — это детерминированный evidence selection по TurnFrame + ResponseSpec.**
   - **Fail-safe слоя evidence** (иначе он сам станет новым тихим fail-open): низкая уверенность в `topic` → уточнение **или** безопасный multi-topic scope; evidence не найден → **честный defer**; **запрещено молча расширять scope до всей базы**.
5. **Composer** — только формулирует по spec + evidence.
6. **Verifier** — числа, медзона-граница, тема, запрещённые/обязательные факты.
   - **Рантайм:** числа, медзона (дёшево и критично) — каждый ход.
   - **Тематическая протечка:** eval-слой **+ рантайм для high-risk режимов или sampling** (не каждый ход — из-за латентности, но и не только eval, иначе новые формулировки протекут).

## Сквозные законы

- **Нет тихих fail-open, меняющих смысл** (включая слой evidence — см. его fail-safe). Сбой → безопасный дефолт, **уважающий жёсткие сигналы** (цена/contacts/booking/медзона). Лог **`degraded`**, не `ok`.
- **Field-level валидация:** битое необязательное поле → `field_errors`, не крашит весь план.
- **База — истина**, дословность, числовой Verifier.

---

## Что СЕЙЧАС (переходное — честно)

- Понимание **размазано**: planner + resolver + patient_situation + dialog_focus + aspect_planner + regex-гейты.
- `topic` — **не ось**, выводится после planner из `service_id` + regex в адаптере; `ServiceTopic` без `whitening`.
- `emotion_policy` — **таблица** `(topic,aspect)→инструкция` (риск тематических маршрутов).
- Медзона — **поздний** soft-suppress в композере, не boundary; hand-off не гарантирован.
- Eval — **маршрутный, не семантический** → ложное зелёное на протечке.
- Safe-default — слишком общий, логируется как `ok`.
- Композеру отдаётся **вся база без выделенного evidence** → он сам выбирает факты (источник протечек).

## A0 — зафиксированный baseline и target contract

A0 не является задачей «сначала сделать legacy зелёным». Бот не находится в production, поэтому нет продуктовой причины временно ремонтировать удаляемую маршрутизацию.

- frozen suite `preservation` фиксирует **желаемое продуктовое поведение**, а не старую реализацию и не дословные ответы;
- live baseline на старой архитектуре: `3/6`, существующий `smoke`: `24/24`;
- уже зелёные кейсы — защита от регрессии во время strangler-миграции;
- красные кейсы — известный архитектурный долг и target для нового backbone;
- frozen ожидания нельзя ослаблять ради зелёного legacy baseline;
- отдельные ремонты старых router/resolver/composer допустимы только при самостоятельной продуктовой необходимости, но не как предусловие удаления legacy.

Целевой `6/6` должен быть достигнут по мере подключения `TurnFrame → ResponseSpec → scoped evidence → Composer → Verifier`. Формулировка ответа может меняться; сохраняются факты, границы, provenance, деньги и нужный пользователю UI-контракт.

## Текущий strangler-checkpoint

Канонический актуальный статус A-series (чекбоксы A1–A9, последний/следующий checkpoint, authority) — **только** в [`docs/STRANGLER_ROADMAP.md`](STRANGLER_ROADMAP.md). Этот файл на текущий checkpoint не дублирует.

Переход ownership на `TurnFrame` разрешён только отдельными последующими задачами после проверки telemetry; сам факт появления frame в ctx не означает переключение архитектуры.

### Offline S28 downstream boundary

S28 не реализует и не переопределяет канонический `ResponseSpec` из шага 3 target
цепочки. Настоящий ResponsePolicy/ResponseSpec остаётся **до** evidence assembly и будет
владеть tone, allowed/forbidden topics, required facts, handoff и допустимыми
deterministic cards.

Отдельный S28 `TargetResponseMaterializationPlan` находится **после** проверенной S27
offline assembly. Он только проецирует identity уже выбранных материалов для будущего
materializer: exact content ref, projected offer IDs, linked doctor IDs и уже выбранные
marketing/consultation/CTA identities. Missing required component отмечается явно без
fallback; S28 не решает clarify/defer, не читает MD/followups, не формирует текст и не
подключён к product path. Такое разделение не меняет порядок target chain и не создаёт
второго смысла для имени `ResponseSpec`.

S29 materializes follow-up candidates только из уже выбранных S28/S27 sources. Content
candidates берутся из `suggest_h3` одного selected MD и разрешаются в explicit H3 того
же документа; price candidates — только из projected offers с сохранением provenance.
Два tuple не смешиваются. S29 не выбирает UI source, не применяет session suppression и
не подключён к product path; эти решения остаются следующей отдельной policy boundary.

S30 принимает явно заданный будущим ResponseSpec/caller source `content`, `price` или
`None` и пропускает соответствующий S29 tuple целиком. Policy не выводит фокус из порядка
components, не смешивает, не ранжирует, не обрезает и не подставляет другую family при
пустом результате. Widget/session/runtime и product path по-прежнему не подключены.

---

## Порядок работ — strangler, две кучи

### Куча A — must-fix ПЕРЕД тем как доверять пилоту (безопасность + честность + **самосогласованность**)

A должна быть **самодостаточной**: её собственные критерии требуют **минимальных** версий пары вещей из B — вносим сюда (минимум, не полный каркас).

1. **Медзона → boundary до генерации** (детект-флаг + enforcement), `response_mode=medical_handoff`.
2. **Минимальная настоящая ось `topic`** (включая `whitening`) + **снос врачебного regex** из topic-адаптера. Иначе `expected_topic` в eval не на чём проверять.
3. **Field-level санитизация всех текущих полей `TurnPlan`** (`brand_filter/service_id/needs_clarify`) → `field_errors`, не крашить весь план.
4. **Семантические ассерты в emotion eval:** `expected_topic`, `expected_emotion`, `required_signals`, `forbidden_signals`, `must_handoff`, `must_not_discuss`, groundedness.
5. **Safe-default уважает жёсткие сигналы** + лог `degraded`.
6. **Фикс протечки через scoped primary evidence** для reassurance (**минимальная** версия слоя evidence, **с fail-safe** из п.4 цепочки). `(topic,aspect)`-таблицу **не растить**.

→ После A пилот **честный, безопасный, самосогласованный**, семантический eval зелёный. **Только тогда коммит.**

### Куча B — структурная стройка, по кирпичу (НЕ в пилот)

1. `topic` — **конфигурируемая taxonomy** по client pack (не хардкод enum).
2. Единый `TurnFrame` + декларативный `ResponseSpec` как контракт (снять `(topic,aspect)`-таблицу целиком).
3. **Каркас `Evidence assembly`** (общий, с полным fail-safe).
4. Field-level валидация — **общий механизм** с provenance по полям.
5. `Verifier` как **компонент** (рантайм: числа/медзона + high-risk протечка; eval: остальное).
6. Перенос ownership по осям (aspects → dialog_focus → patient_scope), затем удаление legacy. **Метрики:** per-axis accuracy, semantic pass rate, planner degraded rate, число LLM-вызовов, p50/p95, стоимость хода.
7. **Trust/P3 — только после** общего evidence/policy механизма.

---

## Статус пилота (emotion)

**P0/P1 НЕ завершён.** Ось `emotion` + убийство price-fail-open — сделано и ценно. До коммита — **Куча A** целиком. Не отмечать «готово», пока A не закрыта.
