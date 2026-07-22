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
   - **Первый target-рантайм:** deterministic digit-number provenance + одна компактная
     semantic assessment на каждый ответ. Accuracy-first решение владельца закрывает
     numbers-as-words, grounding, topic/medzone и selected facts до накопления live-данных.
   - **Будущая оптимизация:** high-risk/sampling вместо каждого semantic check допустимы
     только отдельным governance-решением после измерений качества, задержки и стоимости.

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

S31 объединяет proven S27→S30 segment одним прозрачным offline facade и возвращает exact
materials, plan, follow-up candidates и selected follow-ups. Он не меняет решений и не
перехватывает ошибки стадий. Это проверка сквозной совместимости текущего downstream
участка, а не финальный target path и не замена upstream ResponseSpec.

S32 вводит канонический immutable `TargetResponseSpec`: response mode, tone key,
allowed/forbidden topic scope, required facts/components, follow-up family и permissions
для marketing/consultation/CTA. `medical_handoff` сам является обязательной downstream
границей no-diagnosis/differential/personal-eligibility/treatment-choice; forbidden topics
лишь дополнительно сужают evidence. Manual-contact hard-stop происходит до ResponseSpec.
S32 валидирует explicit spec offline, но ещё не строит его из TurnFrame и не имеет authority.

S33 строит S32 spec из strict explicit non-A9 request и принимает только одно policy-
решение: выбирает content/price/no follow-up по requested + primary component. Mode,
topic scope, facts, components, tone и sales permissions остаются явными входами.
Terminal request-only focus не отбрасывается молча; S32 safety errors не оборачиваются.
TurnFrame/patient_scope, product authority и runtime не подключены.

S34 связывает explicit spec с S31 composition offline. Raw materials и follow-up
candidates остаются внутренними: потребителю разрешены только spec-projected plan
identities, selected follow-ups и отдельно gated `selected_cta_key`; plan CTA — кандидат.
Permission ceilings нельзя расширять inclusion-запросом. Topic allow/forbid и required-fact
coverage пока не доказаны metadata текущего evidence, поэтому Composer/product wiring
запрещены до следующего evidence-scope checkpoint.

S35 строит из S34 отдельный закрытый identity-only evidence view. Он читает topic только
у уже выбранных service/doctor/KB MD, не ищет и не ранжирует документы. Service-linked
offers и commercial facts наследуют topic услуги; врачи сохраняют topic услуги и своего
profile MD. Каждый factual ref обязан пересекаться с allowed topics и не пересекаться с
forbidden topics. Required fact считается покрытым только выбранным commercial fact, а не
его наличием среди raw candidates или offer fact_refs. Missing scope/fact/component
завершается явной ошибкой без whole-base fallback. Composer/Verifier/product wiring всё
ещё отсутствуют; medical_handoff prose safety остаётся их отдельной обязательной границей.

S36 является последним offline-адаптером перед будущим Composer call: exact S35 identities
дословно разворачиваются в immutable request blocks. Content получает только выбранное MD
body без frontmatter; anchored KB/doctor refs — только точную секцию; offers — цену,
package и payment stages без candidate fact_refs/follow-ups; doctors — только имя,
должность, стаж и выбранный profile section; commercial fact/consultation копируются из
точного source object. FullContext cache не перестраивается и не ищется. S36 ещё не
вызывает модель и не создаёт ответ: Composer execution, live quality proof, Verifier и
product wiring остаются отдельными gates.

S37 добавляет минимальную provider-neutral границу Composer execution. Она проверяет
закрытую форму S36 request, детерминированно сериализует response directives и primary
evidence, передаёт их одному injected backend ровно один раз и возвращает только явно
`unverified` текст. Stable policy запрещает user prompt расширять evidence, использовать
невыбранные FullContext-факты, придумывать маркетинг или выводить UI-sidecars; для
`medical_handoff` отдельно запрещены diagnosis/differential/personal eligibility/treatment
choice. Follow-ups и CTA не передаются модели. Retry, repair, fallback, provider wiring,
live quality proof, Verifier и product authority в S37 отсутствуют.

S38 добавляет fail-closed target Verifier. Digit-form numeric claims сверяются по типу и
значению только с exact selected evidence; structured offer/doctor JSON раскрывает цены,
этапы, package/profile text без сканирования IDs, а lexical names вроде `All-on-4` уходят в
semantic grounding. Каждый selected strict commercial fact обязан присутствовать verbatim.
После deterministic checks каждый ответ получает ровно одну provider-neutral semantic
assessment: grounding (включая числа словами и unit/context), topic scope, medical boundary
и все selected facts. Verifier не чинит и не сокращает текст: mismatch/failure блокирует,
success сохраняет exact S37 text и sidecars. Provider/live quality proof, runtime/UI и
product authority всё ещё отсутствуют.

S39 замыкает response-generation vertical от exact S34 upstream package до verified
response одной straight-line композицией `S36 → S37 → S38`. Он не добавляет новую policy,
validation или error semantics: materializer, Composer и Verifier вызываются по одному разу,
а любая typed failure без catch/fallback прекращает downstream. Verified text и sidecars
возвращаются без пересборки. Это structural offline milestone для handoff, а не готовый бот:
TurnFrame/A9 authority, provider/live quality, routes/UI/session и product wiring остаются
отдельными governed этапами.

S40 замыкает offline response-generation vertical от explicit `TargetResponsePolicyRequest`
до verified response одной straight-line композицией `S33 → S34 → S39`. Он не добавляет
новую policy, inference, validation или error semantics: spec builder, spec-bound package
assembly и verified pipeline вызываются по одному разу, а любая typed failure без
catch/fallback прекращает downstream. Verified text и sidecars возвращаются без пересборки.
Это structural offline entry point, а не готовый бот: TurnFrame/A9 authority, provider/live
quality, routes/UI/session и product wiring остаются отдельными governed этапами.

S41 добавляет deterministic TurnFrame dispatch boundary перед S40. Explicit envelope owns
tone, topic scope, required facts, marketing permissions and `boundary_decision`; TurnFrame
contributes only intent/aspects/topic/clarify/service_id mapping. Invalid metadata raises
typed dispatch errors; successful dispatch returns only `materialize | terminal`. Materialize
calls S40 once; clarify/defer/non-materializable medical handoff return payload-free
`TargetResponseSpec` without S34/S40. `patient_scope` is not read.

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
5. `Verifier` как **компонент** (первый target-рантайм: deterministic digits + semantic
   assessment каждого ответа; сужение до high-risk/sampling — только после измерений).
6. Перенос ownership по осям (aspects → dialog_focus → patient_scope), затем удаление legacy. **Метрики:** per-axis accuracy, semantic pass rate, planner degraded rate, число LLM-вызовов, p50/p95, стоимость хода.
7. **Trust/P3 — только после** общего evidence/policy механизма.

---

## Статус пилота (emotion)

**P0/P1 НЕ завершён.** Ось `emotion` + убийство price-fail-open — сделано и ценно. До коммита — **Куча A** целиком. Не отмечать «готово», пока A не закрыта.
