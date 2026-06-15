# Назначение CTA для документов demo

Документ для передачи ИИ: подобрать `cta_key` для каждого md в `clients/demo/md/`.

---

## Механика (кратко)

1. После ответа бота по md-странице под сообщением может появиться **кнопка CTA** (запись / консультация / звонок).
2. Каталог вариантов — `clients/demo/tone.yaml` → `lead.cta_variants`. У каждого `key` **две связанные строки**:
   - `label` — текст **на кнопке**;
   - `name_prompt` — **первая фраза бота после нажатия** (перед вопросом «Как к вам обращаться?»).
3. В frontmatter md указывается только ключ:
   ```yaml
   cta_key: consult      # ключ из каталога (предпочтительно)
   cta_action: lead      # всегда lead для этих кнопок
   ```
4. Цепочка: `cta_key` в md → кнопка с `label` → клик → lead-flow с `name_prompt` для этого ключа (`resolve_lead_name_prompt` в коде).
5. **Не использовать** `cta_text` для новых назначений — только `cta_key`. Старый `cta_text: "Обсудить на консультации"` можно заменить на `cta_key: consult`.
6. Тексты кнопок и фраз после клика **не пишутся в md** — только в `tone.yaml`. ИИ назначает `cta_key`, не придумывает новые фразы.
7. Опционально: `cta_from_turn: 1` — показать CTA только со второго ответа по тому же документу (по умолчанию `0` = сразу).
8. CTA не показывается, если пользователь уже в lead-flow или в сценарии «опишите ситуацию».

**После правок:** пересобрать индекс `python build_index.py demo` (или полный rebuild по процессу проекта).

**Пример (consult):**
```
[Ответ бота по FAQ]
[Кнопка: «Обсудить на консультации»]  ← label
        ↓ клик
Бот: «Отлично, обсудим ваш вопрос на консультации. Как к вам обращаться?»  ← name_prompt
```

---

## Каталог CTA (6 вариантов)

Источник правды: `clients/demo/tone.yaml` → `lead.cta_variants`.

| key | Текст на кнопке (`label`) | Фраза после нажатия (`name_prompt`) | Когда уместен |
|-----|---------------------------|-------------------------------------|---------------|
| `booking` | Записаться на консультацию | Хорошо, помогу с записью. Как к вам можно обращаться? | Общий дефолт: клиника, простые услуги, «хочу прийти» |
| `consult` | Обсудить на консультации | Отлично, обсудим ваш вопрос на консультации. Как к вам обращаться? | FAQ, страхи, сомнения, сравнения — мягкий вход без давления |
| `callback` | Заказать обратный звонок | Хорошо, передам заявку администратору. Как к вам обращаться? | Контакты, оплата, админ-вопросы — удобнее перезвонить |
| `plan` | Составить план лечения | Помогу записаться, чтобы врач составил план лечения. Как к вам обращаться? | Услуги, многоэтапное лечение, имплантация, протезирование |
| `price` | Узнать точную стоимость | Помогу записаться на консультацию — врач рассчитает стоимость под ваш случай. Как к вам обращаться? | Страницы `*__pricing__*`, ценовые FAQ |
| `doctor` | Записаться к врачу | Хорошо, помогу записаться к врачу. Как к вам обращаться? | Карточки врачей `doctors__doctor__*` |

---

## Промпт для ИИ

```
Ты редактор контента стоматологического чат-бота (клиент demo).

Задача: для каждого файла из списка ниже назначить один cta_key из каталога:
booking | consult | callback | plan | price | doctor

Правила:
1. В frontmatter md замени cta_text (если есть) на cta_key + оставь cta_action: lead.
2. Не придумывай новые ключи, label и name_prompt — они заданы в tone.yaml; в md только cta_key.
3. doc_type pricing → чаще price; doctors → doctor; faq про страх/боль/сомнения → consult;
   сравнения (comparison) → consult или plan; услуги (service) → plan или booking;
   clinic info contacts/payment → callback; clinic consultation/advantages → booking.
4. Один файл — один key. Обоснуй выбор одной короткой фразой в колонке «почему».
5. Не трогай тело md (заголовки, текст), aliases, suggest_h3 — только frontmatter CTA.

Формат ответа — таблица:
| файл | cta_key | почему |

Затем — блоки YAML для вставки в frontmatter (по одному на файл):
cta_key: ...
cta_action: lead
```

---

## Список md (demo)

Путь: `clients/demo/md/`

| Файл | Название (рус.) |
|------|-----------------|
| `clinic__info__advantages.md` | Наши преимущества |
| `clinic__info__consultation.md` | Бесплатная консультация |
| `clinic__info__contacts.md` | Адрес и контакты |
| `clinic__info__payment_terms.md` | Стоимость и условия |
| `clinic__info__technology.md` | Наши технологии |
| `clinic__info__warranty.md` | Гарантии в клинике |
| `comparison__bugel_prosthesis_vs_fixed_bridge.md` | Бюгельный протез или несъёмный мост: что выбрать |
| `comparison__implant_vs_bridge.md` | Имплант или мост: что выбрать |
| `doctors__doctor__fedorova.md` | Фёдорова Ирина Михайловна |
| `doctors__doctor__grigoriev.md` | Григорьев Павел Игоревич |
| `doctors__doctor__kuznetsov.md` | Кузнецов Дмитрий Андреевич |
| `doctors__doctor__morozova.md` | Морозова Анна Сергеевна |
| `doctors__doctor__orlov.md` | Орлов Никита Владимирович |
| `doctors__doctor__overview.md` | Наши врачи |
| `doctors__doctor__volkov.md` | Волков Александр Сергеевич |
| `extraction__service__tooth_extraction.md` | Удаление зубов любой сложности |
| `implantation__faq__cost.md` | Почему имплантация стоит дорого |
| `implantation__faq__duration.md` | Длительность имплантации |
| `implantation__faq__osseointegration.md` | Приживаемость имплантов |
| `implantation__faq__pain.md` | Имплантация: боль и анестезия |
| `implantation__faq__safety.md` | Безопасность и стерильность при имплантации |
| `implantation__faq__tooth_loss.md` | Выпал зуб — что делать |
| `implantation__faq__tooth_one_day.md` | Имплантация за 1 день — сразу ли будет зуб |
| `implantation__info__aftercare.md` | После установки импланта |
| `implantation__info__bone_graft.md` | Костная пластика |
| `implantation__info__contraindications.md` | Противопоказания при имплантации |
| `implantation__info__curator.md` | Персональный куратор |
| `implantation__info__implant_systems.md` | Виды имплантов |
| `implantation__info__methods_overview.md` | Виды имплантации — как подбирается метод |
| `implantation__info__steps.md` | Как проходит имплантация |
| `implantation__pricing__all_on_4.md` | Цены на имплантацию All-on-4 |
| `implantation__pricing__all_on_6.md` | Цены на имплантацию All-on-6 |
| `implantation__pricing__implants.md` | Цены на импланты |
| `implantation__service__all_on_4.md` | Имплантация All-on-4 |
| `implantation__service__all_on_6.md` | Имплантация All-on-6 |
| `implantation__service__benefits.md` | Преимущества имплантации |
| `implantation__service__classic.md` | Классическая имплантация |
| `implantation__service__one_stage.md` | Одномоментная имплантация |
| `implantation__service__temporary_teeth.md` | Временные зубы на имплантах |
| `orthodontics__service__aligners.md` | Элайнеры для выравнивания зубов |
| `periodontology__service__periodontitis.md` | Лечение пародонтита |
| `prosthetics__service__clasp_dentures.md` | Бюгельные протезы |
| `prosthetics__service__implant_supported_prosthetics.md` | Протезирование на имплантах |
| `prosthetics__service__removable_dentures.md` | Съёмное протезирование |
| `prosthetics__service__veneers.md` | Виниры E-max |
| `prosthetics__service__zirconia_crowns.md` | Коронки из диоксида циркония |
| `treatment__service__caries.md` | Лечение кариеса |
| `treatment__service__pulpitis.md` | Лечение пульпита |
| `treatment__service__teeth_treatment.md` | Лечение зубов |

**Всего: 49 файлов.**

---

## Пример правки frontmatter

Было:
```yaml
cta_text: "Обсудить на консультации"
cta_action: lead
```

Стало:
```yaml
cta_key: consult
cta_action: lead
```

После клика пользователь увидит фразу из каталога для `consult` (см. таблицу выше), затем ввод имени и телефона.

---

## Рекомендуемое распределение (черновик для проверки ИИ)

| Группа | cta_key |
|--------|---------|
| `*__pricing__*` | `price` |
| `doctors__doctor__*` (кроме overview) | `doctor` |
| `doctors__doctor__overview` | `booking` |
| `*__faq__*` (страх, боль, сомнения) | `consult` |
| `implantation__faq__cost` | `price` |
| `comparison__*` | `consult` |
| `*__service__*` (лечение, имплантация, протезы) | `plan` |
| `clinic__info__contacts`, `payment_terms` | `callback` |
| остальные `clinic__info__*` | `booking` |

ИИ должен сверить с содержанием каждого файла и при необходимости скорректировать.
