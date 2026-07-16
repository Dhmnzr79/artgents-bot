# Технический слой маркетинговой карты

**Статус:** парный документ к [`MARKETING_QUESTION_FOUNDATION.md`](MARKETING_QUESTION_FOUNDATION.md), 16 июля 2026 года.
**Для кого:** разработка, Cursor — маршруты, источники, операции пайплайна.
**Не является:** маркетинговым описанием экрана; текстом ответов.

Нумерация разделов совпадает с foundation. Колонка **«На экране»** там; здесь — **«Технически»**.

## Обязательные продуктовые требования

Этот раздел описывает **требуемое поведение**, а не утверждает, что оно уже полностью реализовано в текущем runtime.

1. **Authority базы над содержанием ответа.** Согласованные md, pricebook, marketing и policies конкретной клиники определяют факты и силу утверждений. Это не связано с запрещённой product authority A9 `patient_scope`: A9 остаётся shadow-only и не управляет ответом.
2. **Запрет семантического смягчения.** Composer может добавлять только связующий текст. Числа, проценты, модальность, гарантии, обещания, отрицания и оговорки источника должны сохраняться точно; будущая проверка должна обнаруживать их ослабление, усиление или подмену.
3. **Promo eligibility.** Активная акция допускается, когда она релевантна теме, включая страх, боль без острых признаков и противопоказания. Общий запрет по одному лишь аспекту `pain`/`safety`/`contraindications` противоречит согласованной продуктовой политике.
4. **Promo cadence.** Первая релевантная реплика показывает акцию и сохраняет факт показа этой акции в сессии. Повтор той же акции подавляется; другая релевантная акция может быть показана при смене темы. Явный вопрос об акции всегда обрабатывается независимо от предыдущего показа.
5. **CTA cadence отделена от promo cadence.** Одна основная CTA может появляться повторно в следующих подходящих ответах и не блокируется тем, что акция уже была показана.
6. **Manual-contact boundary.** Срочная боль, острое осложнение после лечения, жалоба, спор или отзыв, требующий реакции, должны завершаться до retrieval/composer/UI-policy и возвращать только фиксированный шаблон с номером из client config.
7. **Отзывы разделяются по смыслу.** Обычный вопрос о том, где посмотреть отзывы, остаётся content/trust-вопросом. Негативный отзыв или претензия включают manual contact.

Точный требуемый manual-contact шаблон:

> Чтобы вам быстрее помогли, пожалуйста, свяжитесь с администратором клиники. Если вопрос срочный, лучше сразу позвоните: **[номер клиники]**.

После шаблона запрещены свободная генерация, CTA, акция, quick replies, видео, situation-кнопка и дополнительные рекомендации.

---

## Легенда

### Источник данных

| Код | Откуда |
|---|---|
| `comparison` | `comparison__*.md` (5 в demo) |
| `service` / `info` / `faq` | md-документы клиента |
| `clinic` | `clinic__info__*.md`, doctors md |
| `pricebook` | `pricebook/services/*.json` |
| `marketing` | `marketing.yaml` |
| `clinic_policies` | `clinic_policies.yaml` |
| `policy` | ingress, playbook, lead, шаблоны |
| `fallback` | guided-меню, переспрос |

### Операции

| Операция | Суть |
|---|---|
| `retrieval` → `composer` | Поиск md, сборка ответа |
| `catalog` | Fast-path через `service_catalog.json` |
| `price_route` | Матч услуги → карточка(и) pricebook |
| `price_unavailable` | Услуга без `price_key` → сниппет + шаблон |
| `group_overview` | Общий ценовой запрос → несколько карточек |
| `clarify` | `needs_clarify`, `build_clarify_payload` |
| `continuation_clarify` | Меню без контекста |
| `carry` | `dialog_focus`, `last_subject`, session |
| `playbook` | `patient_situation` |
| `comparison_route` | `query_mode=comparison`, skip catalog |
| `composite` | `is_composite_question`, 2+ аспекта |
| `not_offered` | `clinic_policies` + альтернатива |
| `lead_flow` | Имя → телефон → demo-msg |
| `handoff_template` | Фиксированный шаблон §10 |
| `policy_ui` | CTA, `suggest_h3`, video, situation |

**Порядок (упрощённо):** ingress / resolver → маршрут (catalog | price | composer | playbook | lead) → сборка текста → `policy_ui`.

### Контекст (как в foundation)

| Код | Значение |
|---|---|
| `standalone` | Хватает одного сообщения |
| `carry` | Нужен предыдущий ход |
| `clarify` | Переспрос по оси услуга / масштаб / этап |

---

## 1. Обычные вопросы по базе знаний

| Подтип | Технически | Контекст |
|---|---|---|
| Что это за услуга | `service`/`faq` → `retrieval` → `composer`; `policy_ui`: CTA `plan`, `suggest_h3` | `standalone` |
| Как проходит лечение | `service`/`info` → `retrieval` → `composer`; `suggest_h3`, CTA `plan` | `standalone` / `carry` |
| Вопрос о направлении | `catalog` или `retrieval` → `composer`; + `price_route` если цена | `standalone` |
| Клиника и доверие | `clinic` → `retrieval` → `composer`; CTA `booking`/`callback` | `standalone` |

---

## 2. Цены

| Подтип | Технически | Контекст |
|---|---|---|
| Простая цена | `price_route` → 1 карточка; CTA `price`; price UI без `suggest_h3` | `standalone` / `carry` |
| Сложная цена | `price_route` → N карточек; pricebook `followups` | `standalone` / `carry` |
| Слишком общий вопрос | `group_overview` или `clarify` | `standalone` |
| Цена по ситуации | `playbook`/`carry` → `price_route`; иначе `clarify` | `standalone` |
| Что дешевле | `price_route` (бренды одной услуги); иначе `clarify` | `standalone` |
| Состав цены | `faq`/`service` → `retrieval` → `composer`; pricebook `followups` | `standalone` / `carry` |
| Услуга есть, цены нет | `price_unavailable`: service-md сниппет + шаблон; `suggest_refs` опц. | `standalone` |

---

## 3. Сравнение методов

### 3.1. Три ситуации по материалу

| Ситуация | Технически |
|---|---|
| **A. Есть comparison-док** | `comparison` → `comparison_route` → `retrieval` → `composer`; CTA `consult` |
| **B. Два service-дока** | `service` ×2 → `retrieval` → `composer`; `clarify` опц. |
| **C. Одна сторона в базе** | `retrieval` 1 md → `composer`; CTA `consult`/`booking` |

### 3.2. Прочие подтипы

| Подтип | Технически |
|---|---|
| Сравнение по ситуации | `playbook` / `comparison_route` → `composer`; `clarify`/`suggest_h3` |
| Нелогичное сравнение | Шаблон + `clarify`; без `price_route` |

---

## 4. Врачи

| Подтип | Технически |
|---|---|
| Команда | `clinic`/doctors overview → `retrieval` → `composer`; CTA `booking` |
| Кто делает услугу | doctors md → `retrieval`; CTA `doctor` |
| Конкретный врач | doctors md по имени; doctor UI (без follow-up md) |

---

## 5. Акции, скидки и способы сэкономить

| Подтип | Технически |
|---|---|
| Какие акции сейчас | `marketing.yaml` → текст |
| Акция на услугу | `marketing` + `pricebook`; фильтр по услуге |
| Как сделать дешевле | `retrieval` clinic md + `price_route`; `marketing` опц. |
| Условия оплаты | `clinic__info__payment_terms` → `composer`; `suggest_h3`, CTA `callback` |
| Скидка у врача | `marketing.yaml`; без персональных скидок |

**Текущий долг:** runtime блокирует промо на `pain`/`safety`/`contraindications` через `blocked_aspects_for_promo`. Это не соответствует утверждённому требованию выше и должно меняться отдельной code/runtime-задачей с тестами.

---

## 6. Запись и контакт

| Подтип | Технически |
|---|---|
| Простая запись | booking-intent → `lead_flow`; CTA `booking` |
| Запись на дату/время | Пожелание в session; `lead_flow`; defer-шаблон |
| Запись к врачу | Врач в session → `lead_flow`; CTA `doctor` |
| Обратный звонок | contacts md или `lead_flow` `callback` |
| Передумал | Сброс lead-state |

---

## 7. Ситуация пациента

| Механизм | Технически |
|---|---|
| Playbook | `playbook` → опции; + `price_route` |
| «Рассказать о ситуации» | `situation_allowed` + `policy_ui` → `lead_flow` |

### 7.1. Playbook

| Подтип | Технически |
|---|---|
| Отсутствующие зубы | `playbook` + `price_route` |
| Вся челюсть | `playbook` + `retrieval`; CTA `consult`/`plan` |
| Имплант уже стоит | `carry`/`catalog` → `price_route` |
| Мало кости | `info`/`comparison` → `composer`; CTA `consult` |

### 7.2. «Рассказать о ситуации»

| Условие | Технически |
|---|---|
| Материал разрешает, есть слот | `situation_allowed` + `policy_ui` |
| Клик | Заметка в session → `lead_flow` |
| Конкуренция слота | video / `suggest_h3` приоритет |

---

## 8. Страх, боль и восстановление

| Подтип | Технически |
|---|---|
| Страх перед лечением | `faq` pain → `composer`; video; CTA `consult` |
| Страх неприживления | `faq` osseointegration, `empathy_enabled`; `suggest_h3` |
| Восстановление | `info` aftercare → `composer`; `suggest_h3` |
| Сравнение боли | `faq`/`service` → `composer` |

Требование: неострый страх/боль не блокируют релевантную акцию; показ регулируется общей promo eligibility/cadence, а не отдельным тематическим маршрутом.

---

## 9. Безопасность и противопоказания

| Подтип | Технически |
|---|---|
| Заболевания | `info` contraindications → `composer`; по требованию релевантное промо разрешено |
| Возраст, курение | `info`/`faq` → `composer` |
| Факт приживаемости | `faq` osseointegration → `composer` |
| Риск и гарантии | `faq` + `clinic` warranty; CTA `consult` |
| Гарантия клиники | `clinic__info__warranty` → `composer` |

Один md `osseointegration` для факта и страха — разные chunk/H3 по retrieval.

---

## 10. Срочный вопрос, жалоба и ручной контакт

| Подтип | Технически |
|---|---|
| Срочная боль / острое осложнение после лечения / жалоба / спор / негативный отзыв | Boundary до retrieval/composer; только фиксированный шаблон и телефон из `clinic` config; без любого UI |
| Вопрос «где посмотреть отзывы?» | Обычный content/trust path; не `manual_contact` |

Текущий runtime уже использует `manual_contact` до основного ответа и не добавляет CTA, но текст шаблона отличается от согласованного. Замена шаблона и проверка классификации — отдельная code/runtime-задача.

---

## 11. Услуги, бренды и условия, которых нет

| Подтип | Технически |
|---|---|
| Есть альтернатива | `not_offered` → policies → `retrieval` alt-md |
| Нет бренда | `info` implant_systems; + `price_route` |
| Политика клиники | `clinic_policies` шаблон |
| Неизвестная услуга | policy шаблон |

≠ §2 `price_unavailable`: там услуга есть в каталоге, но нет прайса.

---

## 12. Непонятный запрос, off-topic и spam

| Подтип | Технически |
|---|---|
| Пустой / короткий | policy шаблон + меню |
| Ничего не найдено | `fallback` guided-меню |
| Off-topic | ingress off-topic шаблон |
| Повтор / spam | policy шаблон |

---

## 13. Многоходовые цепочки

| Сценарий | Технически | Контекст |
|---|---|---|
| Услуга → цена | `carry` → `price_route` | `carry` |
| Услуга → сроки | `carry` → `retrieval` service-md | `carry` |
| Общий → цена | `group_overview` / `clarify` | `clarify` |
| Цена без контекста | `continuation_clarify` | `clarify` |
| Ситуация → цена | session → `price_route` | `carry` |
| Короткое продолжение | `carry` → `dialog_focus` | `carry` |

---

## 14. Составные вопросы в одном сообщении

| Подтип | Технически |
|---|---|
| Услуга + цена | `composite`: catalog/`retrieval` + `price_route` |
| Цена + боль | `composite`; по требованию релевантное промо разрешено с общей session-cadence |
| Два факта | `composite`: 2 md-chunk |
| Сравнение + цена | `composite` + `comparison_route` + price |

Риск: `is_composite_question` не ловит все формулировки.

---

## 15. Редкие вопросы (edge FAQ)

| Пример | Технически |
|---|---|
| «Может ли имплант повредить нерв?» | `retrieval` miss → §12 `fallback` |
| «Второе мнение с чужим планом?» | Нет md → `fallback` |
| «Удалять или лечить — кому верить?» | miss → `composer`/fallback |

План базы: `clinic__faq__edge_cases.md` — пока не в demo.

---

## Текущее состояние и обязательные расхождения

1. `retrieval` / `composer` / `price_route` — основные пути контента.
2. `policy_ui` решает, показать ли CTA и follow-up.
3. `clarify` — только услуга / масштаб / этап.
4. Текущий promo-блок на `pain`/`safety`/`contraindications` требуется заменить проверкой релевантности, активности и session-cadence.
5. Текущий composer/verifier требуется отдельно проверить на точное сохранение силы согласованных утверждений.
6. Demo: `lead_flow` не шлёт в CRM.
7. `handoff_template` (§10) уже исключает retrieval и CTA, но должен получить новый согласованный текст и строгую проверку границы.
8. `comparison_route` — catalog fast-path не перебивает comparison-md.

---

## Что дальше

1. Сверить с foundation «На экране» в виджете.
2. Отметить расхождения маршрут ↔ UI.
3. Regression — ключевые сценарии §3, §13, §14.
