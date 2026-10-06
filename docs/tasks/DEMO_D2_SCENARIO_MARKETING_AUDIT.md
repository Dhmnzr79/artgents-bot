# D2 — аудит сценариев и упрощение коммерческого слоя

Дата: 2026-09-21. Baseline: `b66dc5c9d04e0ff94e9a5d1e5773d1b651e86241`.
Статус: **documentation checkpoint до независимого Cursor review**.

Этот аудит не меняет runtime, tenant data или пользовательские ответы. Он
фиксирует, что следует сохранить из CP1–CP5, где возник риск лишней сложности и
какой единый механизм должен быть реализован до продолжения массового
подключения сценариев.

## 1. Короткий вывод

Доказанные A08, CP5-A10a и CP5-B13a не создали отдельный production-сценарий
на каждую услугу: все они идут через `run_d2_dialogue_turn`, production D1R
parser, tenant snapshot, общий materializer/renderer и один store. В production
коде нет ветки с названием `caries` или другой тестовой услуги.

Однако продолжать тем же способом по одной услуге опасно. Уже появились
временный флаг `common_route_direct_service_only`, ограничение «ровно один
active offer» и D2-gate, полностью запрещающий `fact_refs`. Добавление следующей
услуги отдельной веткой превратит acceptance-примеры в архитектуру.

Главная накопленная сложность находится в унаследованном маркетинговом слое:

- `marketing.yaml` одновременно содержит `initial_commercial_blocks`,
  `priority_service_promos`, `service_automatic_commercial`, общий
  `ordered_amplifier_refs`, `promotion_overview` и отменённые для D2
  `scenario_rules`;
- один и тот же fact связан с услугой через несколько списков и иногда через
  `offer.fact_refs`;
- старый contract различает promo, automatic amplifier, service value и
  requested fact там, где целевому D2 нужен простой набор готовых блоков;
- действующее поле `incompatible_with` хранит попарные ссылки без готового
  текста пациенту, а D2-046 требует группы ID с утверждённым пояснением;
- все `incompatible_with` в текущем demo pack пусты, поэтому реальная
  несовместимость demo-данными сейчас не доказана;
- D2 common route пока намеренно отвергает любой service-price offer с
  `fact_refs`, поэтому A02/A11/B08 и коммерческий ответ All-on-4 ещё не собраны.

Вывод: уже доказанную основу не переписывать. До новых коммерческих сценариев
нужно один раз собрать D2-native коммерческий блок, а затем проверять на нём
несколько услуг без новых service-specific веток.

## 2. Что сохраняем без перепроектирования

| Область | Решение аудита |
|---|---|
| Один D1R prompt/parser | Сохранить. Второй marketing parser не нужен. |
| `run_d2_dialogue_turn` и один store | Сохранить как common internal entry и owner state/result/replay. |
| Production tenant loader/snapshot | Сохранить. Коммерческие данные добавляются в тот же snapshot. |
| Typed situation carry A08/A10a | Сохранить; это общий механизм контекста, не услуговый сценарий. |
| Простая цена B13a | Сохранить как минимальное доказательство price-only ответа. Временное ограничение одного offer не расширять копированием. |
| Frozen final plan и один renderer | Сохранить. Маркетинговые блоки должны попасть в plan до render/freeze. |
| Result replay и history показов | Сохранить. Replay не выбирает акции повторно; auto promo считается показанной только в сохранённом final result. |

### Проверка уже выполненных checkpoint

| Checkpoint | Результат аудита | Нюанс |
|---|---|---|
| S2-V0 / A08 | Архитектурно полезен: впервые собрал parser → snapshot → plan → renderer → persisted state. | Большой fixture и assembled test не должны стать шаблоном копирования под каждую услугу. |
| CP1 | Небольшое развитие единственного D1R contract; второго parser нет. | Требования A08 не должны навсегда оставаться в error names общего route. |
| CP2 | Правильно перенёс A08 с test-only данных на production demo pack. | `d2_direction_prices.json` остаётся специальным authority для direction overview; его нельзя использовать как второй общий price/marketing contract. |
| CP3 | Live harness изолирован, имеет call budget и не подключён к runtime. | CP3-specific provider/harness нельзя превращать во второй production provider path. |
| CP4 | Сложность store/replay/atomic commit оправдана требованиями C04–C06/C09–C10. | Lead receipt доказывает effect lifecycle, но не полный A12 и не реальный transport. |
| CP5-A10a | Same-topic carry является общим typed continuity mechanism, не услугой. | Проверки carry частично повторяются в materializer и persistence; при расширении нужен один invariant owner, а не новые ветки. |
| CP5-B13a | Доказал data-driven простую цену: `caries` существует только в test input/data. | `common_route_direct_service_only` + «ровно один active offer» — допустимый узкий checkpoint, но первый явный сигнал остановить посервисное расширение. |

Размер diff сам по себе не доказывает переусложнение: значительная часть CP3–CP5
приходится на tests, harness и evidence. Риск создают не строки тестов, а рост
временных режимов в общем route и смешение D2/legacy authority в одном большом
materializer. Поэтому аудит не предлагает переписать store, parser или session;
он меняет порядок следующей работы.

### Честный статус сценариев

| Семья | Статус на baseline |
|---|---|
| A08 | Собран через внутренний common D2 route; ограниченно подтверждён live в CP3. |
| A10 | Собрана только часть A10a: same-topic price continuation после существующего контекста. Новая пустая сессия и смена услуги не закрыты. |
| B13 | Собрана только часть B13a: одна простая published service price без commercial facts. Повреждённые условия и остальные варианты B13 не закрыты. |
| A01–A07, A09, A11–A12 | Не собраны. Имеющиеся unit/seam-тесты отдельных деталей не являются assembled evidence. |
| B01–B12, B14–B17 | Не собраны. CP4 lead receipt не равен A12, а price-mode seams не равны B06. |

Документация до аудита противоречила сама себе: таблица Ledger уже содержала
A10a/B13a, но раздел «Явная фиксация» по-прежнему называл собранным только A08;
roadmap всё ещё называла CP2 следующим шагом и требовала отдельный checkpoint на
каждую малую семью. Эти несоответствия исправляются данным diff.

## 3. Упрощённая целевая схема данных

У коммерческого факта один стабильный ID и одно место с содержанием:

```text
commercial_fact
  id
  kind
  short_text        # короткое добавление к услуге или цене
  full_text/ref     # полный ответ при прямом вопросе
  active dates
  applicability
```

Техническая реализация может эволюционно сопоставить это существующим
`microfact_text`, `text_fact` и `detail_ref`; второй fact ID для короткой версии
создавать нельзя.

У услуги один commercial profile:

```text
service_commercial_profile
  promo_refs          # auto: максимум 2 короткие акции
  price_booster_id    # 0 или 1 пакет ценового усилителя
  also_list_id        # 0 или 1 пакет «Также мы предлагаем»
```

В каталоге клиники пакетов каждого вида может быть несколько; у пакета есть
имя и готовое содержание. Профиль хранит только ID, не пункты. Код не
склеивает усилители и не набирает «Также» из fact refs или слотов. Длина
текста внутри пакета — ответственность редактора. Одна и та же гарантия или
рассрочка не должна одновременно появляться как короткая акция, усилитель и
пункт «Также».

Несовместимость хранится отдельно:

```text
incompatibility_group
  offer_or_fact_ids
  explanation_text
```

Группа означает только конкретные перечисленные ID. Если два выбранных элемента
одной группы попали в ответ, они показываются как альтернативы вместе с готовым
пояснением. Код не складывает выгоды, не выбирает вариант за пациента и не
считает все скидки несовместимыми со всеми рассрочками.

## 4. Три режима одного механизма

### Обычный вопрос об услуге

Основной ответ по утверждённому материалу плюс до двух применимых `short_text`
акций. Пакет усилителя и пакет «Также» автоматически не добавляются.

### Прямой вопрос о цене

Один frozen plan содержит:

1. цену, единицу и обязательные условия;
2. до двух применимых коротких акций;
3. необязательный один пакет ценового усилителя;
4. необязательный один пакет «Также мы предлагаем»;
5. при необходимости — готовое пояснение группы несовместимости.

Это один универсальный price response profile, а не сценарии «цена + акция»,
«цена + рассрочка» и «цена + гарантия».

### Прямой вопрос об акциях

Используется полная форма тех же promo ID: `full_text/ref`, до четырёх
применимых акций по D2-019–D2-020. История автоматического показа не скрывает
прямо запрошенную акцию. Короткая форма не подменяет полный ответ.

## 5. Риски и обязательные защиты

| Риск | Защита |
|---|---|
| Размножение веток по услугам | Production код работает по service ID и profile; услуги различаются только tenant data и assembled fixtures. |
| Два владельца одного текста | Fact содержит обе presentation forms акции; пакет усилителя/«Также» — единственный owner своего текста; profile хранит только ID. |
| Дублирование связей | После миграции один D2 profile является owner автоматического состава; legacy lists не читаются D2 route. |
| Слишком длинный ценовой ответ | Не склеивать пакеты: на услугу максимум один усилитель и один «Также»; длину текста задаёт редактор клиники. Promo auto ≤2. |
| Скрытие несовместимого предложения | Не «оставить первое», а показать применимые альтернативы и authored explanation. |
| Модель придумывает акцию/условие | Модель возвращает intent/refs; exact short/full text и compatibility copy добавляет code-owned plan из snapshot. |
| Повтор акции | Auto учитывает сохранённые shown IDs; direct promotion request может повторить. Replay не пересчитывает. |
| Повреждённое optional data скрывает цену | Цена остаётся; сбой optional commercial block диагностируется отдельно по D2-065. |
| Старый selector возвращается в D2 | Dependency observer и assembled tests запрещают `target_marketing_selector`, scenario rules, Composer и sales_fast. |
| Конфликт короткой и полной версии | Loader проверяет один ID, применимость и наличие требуемой presentation form; renderer выбирает форму только по response profile. |

D2-O4 закрыто D2-090: не список `price_booster_refs` и не старый предел `4`,
а 0 или 1 готовый пакет усилителя на услугу плюс 0 или 1 пакет «Также».
Числовые caps «Также 1–3» и «Также 0–5» этим же решением отменены.

## 6. Будущие checkpoint CP5

1. **CP5-M1 — единый commercial data contract.** В существующем tenant contract
   определить две формы одного fact, один service commercial profile
   (`promo_refs` ≤2, необязательный `price_booster_id`, необязательный
   `also_list_id`) и группы несовместимости; loader валидирует ID, порядок,
   applicability и готовый explanation. Мигрировать только approved demo data.
   Runtime ещё не включать.
2. **CP5-M2 — D2-native commercial plan.** Common route выбирает profile по
   typed service ID и intent, создаёт frozen promo / один booster package /
   один also package / compatibility blocks, сохраняет shown IDs. Legacy
   marketing selector не вызывается.
3. **CP5-M3 — assembled marketing family.** Одним checkpoint проверить A02
   (цена + короткая акция), A11 (полный прямой ответ об акциях и повтор) и B08
   (price profile, пакет «Также», несовместимость). Объединение допустимо, потому
   что это три поверхности одного механизма; если M2 потребует разных state или
   resolver rules, пакет разделяется до реализации.
4. **CP5-N — остальные семьи.** Группировать по механизму: continuation,
   multi-part, policy, terminal/lead, directory/UI. Не создавать checkpoint на
   каждую услугу и не считать дополнительную услугу новым поведением.

## 7. Stop conditions реализации

- нет approved short/full text, service profile или compatibility explanation;
- один факт должен иметь разные противоречащие условия в разных местах;
- для выбора требуется перечитывать raw user text после D1R;
- требуется legacy selector, второй tenant contract или новый parser;
- новый service-specific branch нужен только из-за имени услуги;
- optional marketing failure начинает скрывать корректную цену;
- assembled test подменяет provider envelope, state, цены или final plan вместо
  прохода через common route.

## 8. Граница доказательства этого checkpoint

Этот документ и связанные правки governance не доказывают работу маркетинга в
D2. На baseline собраны внутренние A08, CP5-A10a и CP5-B13a; HTTP/SSE/widget,
A02, A11, B08, группы несовместимости и новый commercial profile не реализованы.
Provider/live calls в аудите не выполнялись.
