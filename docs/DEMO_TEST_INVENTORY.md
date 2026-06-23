# Demo — инвентарь контента и цен для тестов

Автосгенерировано из `clients/demo/md/`, `clients/demo/pricebook/services/` и `clients/demo/clinic_policies.yaml`.
Обновить: `python scripts/gen_demo_test_inventory.py`

---

## 1. Темы и чанки (md)

Формат ref для eval: `{doc_id}.md#{anchor}`. Главный чанк почти всегда `#korotko`.

### Клиника (`topic: clinic`) — 6 документов

**clinic__info__advantages** · `info`
- `korotko` — Коротко

**clinic__info__consultation** · `info`
- `korotko` — Коротко

**clinic__info__contacts** · `contacts`
- `korotko` — Коротко

**clinic__info__payment_terms** · `info`
- `korotko` — Коротко

**clinic__info__technology** · `info`
- `korotko` — Коротко
- `kak-planiruetsya-implantatsiya` — Как планируется имплантация
- `kak-povyshaetsya-tochnost` — Как повышается точность?

**clinic__info__warranty** · `info`
- `korotko` — Коротко
- `chto-delat-esli-voznikla-problema` — Что делать, если возникла проблема

### Врачи (`topic: doctors`) — 7 документов

**doctors__doctor__fedorova** · `doctor`
- `korotko` — Коротко

**doctors__doctor__grigoriev** · `doctor`
- `korotko` — Коротко

**doctors__doctor__kuznetsov** · `doctor`
- `korotko` — Коротко

**doctors__doctor__morozova** · `doctor`
- `korotko` — Коротко

**doctors__doctor__orlov** · `doctor`
- `korotko` — Коротко

**doctors__doctor__overview** · `doctor`
- `korotko` — Коротко

**doctors__doctor__volkov** · `doctor`
- `korotko` — Коротко

### Удаление (`topic: extraction`) — 1 документов

**extraction__service__tooth_extraction** · `service`
- `korotko` — Коротко
- `bolno-li-udalyat-zub` — Больно ли удалять зуб
- `chto-posle-udaleniya` — Что после удаления
- `mozhno-li-srazu-implant` — Можно ли сразу поставить имплант

### Имплантация (`topic: implantation`) — 28 документов

**comparison__all_on_4_vs_all_on_6** · `comparison`
- `korotko` — Коротко
- `kogda-dostatochno-chetyreh` — Когда достаточно четырёх имплантов
- `kogda-vybirayut-shest` — Когда выбирают шесть имплантов
- `verhnyaya-chelust-i-nagruzka` — Верхняя челюсть и нагрузка

**comparison__bone_graft_vs_all_on_4** · `comparison`
- `korotko` — Коротко
- `kogda-nuzhna-kostnaya-plastika` — Когда нужна костная пластика
- `kogda-mozhno-all-on-4` — Когда можно All-on-4
- `kak-vybirayut-na-kt` — Как выбирают на КТ

**comparison__classic_vs_one_stage** · `comparison`
- `korotko` — Коротко
- `klassicheskaya-dvuh-etapnaya` — Классическая двухэтапная
- `odnomomentnaya-srazu` — Одномоментная «сразу»
- `chto-vybiraet-vrach` — Что выбирает врач

**comparison__implant_vs_bridge** · `comparison`
- `korotko` — Коротко
- `esli-net-odnogo-zuba` — Если нет одного зуба
- `kogda-chashche-vybirayut-implant` — Когда чаще выбирают имплант
- `kogda-most-mozhet-byt-razumnym-variantom` — Когда мост может быть разумным вариантом

**implantation__faq__cost** · `faq`
- `korotko` — Коротко
- `kak-sdelat-implantatsiyu-dostupnee` — Как сделать имплантацию доступнее

**implantation__faq__duration** · `faq`
- `korotko` — Коротко
- `ot-chego-zavisit-srok-implantatsii` — От чего зависит срок имплантации
- `mozhno-li-uskorit-implantatsiyu` — Можно ли ускорить имплантацию

**implantation__faq__osseointegration** · `faq`
- `korotko` — Коротко
- `a-esli-implant-ne-prizhivetsya` — А если имплант не приживётся
- `ot-chego-zavisit-prizhivlenie` — От чего зависит приживление
- `chto-budet-esli-nichego-ne-delat` — Что будет, если ничего не делать

**implantation__faq__pain** · `faq`
- `korotko` — Коротко
- `kakuyu-anesteziyu-ispolzuyut` — Какую анестезию используют
- `chto-chuvstvuetsya-posle-ustanovki` — Что чувствуется после установки
- `sedatsiya-i-narkoz` — Седация и наркоз

**implantation__faq__safety** · `faq`
- `korotko` — Коротко

**implantation__faq__tooth_loss** · `faq`
- `korotko` — Коротко

**implantation__faq__tooth_one_day** · `faq`
- `korotko` — Коротко

**implantation__faq__what_included** · `faq`
- `korotko` — Коротко
- `kogda-koronka-schitaetsya-otdelno` — Когда коронка считается отдельно
- `koronka-na-implant-ili-na-svoy-zub` — Коронка на имплант или на свой зуб

**implantation__info__aftercare** · `info`
- `korotko` — Коротко
- `chto-proishodit-v-pervye-dni` — Что происходит в первые дни
- `kak-prohodit-vosstanovlenie-do-koronki` — Как проходит восстановление до коронки

**implantation__info__bone_graft** · `info`
- `korotko` — Коротко
- `kak-prohodit-vosstanovlenie` — Как проходит восстановление
- `sinus-lifting-i-stoimost` — Синус-лифтинг и что оплачивается отдельно
- `skulovye-implanty-i-alternativy` — Скуловые импланты и альтернативы

**implantation__info__contraindications** · `info`
- `korotko` — Коротко
- `nuzhna-li-podgotovka-pered-implantatsiey` — Нужна ли подготовка перед имплантацией
- `vozrast-i-all-on` — Возраст и All-on

**implantation__info__curator** · `info`
- `korotko` — Коротко

**implantation__info__implant_systems** · `info`
- `korotko` — Коротко
- `nobel-maksimum-nadezhnosti` — Nobel: максимум надёжности
- `impro-razumnyy-balans` — Impro: разумный баланс
- `implantium-dostupnyy-variant` — Implantium: доступный вариант

**implantation__info__methods_overview** · `info`
- `korotko` — Коротко
- `neskolko-zubov-podryad` — Несколько зубов подряд

**implantation__info__steps** · `info`
- `korotko` — Коротко

**implantation__service__all_on_4** · `service`
- `korotko` — Коротко
- `komu-podhodit-all-on-4` — Кому подходит All-on-4
- `kak-rabotaet-metod-all-on-4` — Как работает метод All-on-4
- `ogranicheniya-i-uhod` — Ограничения и уход

**implantation__service__all_on_6** · `service`
- `korotko` — Коротко
- `komu-podhodit-all-on-6` — Кому подходит All-on-6
- `kak-rabotaet-metod-all-on-6` — Как работает метод All-on-6
- `sroki-i-osobennosti` — Сроки и особенности

**implantation__service__benefits** · `service`
- `korotko` — Коротко

**implantation__service__classic** · `service`
- `korotko` — Коротко
- `pochemu-vybirayut-klassicheskuyu` — Почему выбирают классическую
- `sroki-i-ogranicheniya` — Сроки и ограничения

**implantation__service__one_stage** · `service`
- `korotko` — Коротко
- `kogda-ne-podhodit-odnomomentnaya` — Когда не подходит одномоментная
- `v-chem-osobennost-metoda` — В чём особенность метода

**implantation__service__pterygoid_implants** · `service`
- `korotko` — Коротко
- `kogda-rassmatrivayut-pterygoid` — Когда рассматривают птеригоидные импланты
- `chem-otlichaetsya-ot-obychnyh` — Чем отличаются от обычных имплантов
- `pochemu-nuzhna-diagnostika` — Почему нужна диагностика

**implantation__service__sinus_lift** · `service`
- `korotko` — Коротко
- `kogda-nuzhen-sinus-lift` — Когда нужен синус-лифтинг
- `kak-prohodit-sinus-lift` — Как проходит процедура
- `kogda-stavyat-implant` — Когда после синус-лифтинга ставят имплант

**implantation__service__temporary_teeth** · `service`
- `korotko` — Коротко
- `kogda-stavyat-vremennye-zuby` — Когда ставят временные зубы
- `ogranicheniya-do-postoyannoy-koronki` — Ограничения до постоянной коронки

**implantation__service__zygomatic_implants** · `service`
- `korotko` — Коротко
- `kogda-rassmatrivayut-skulovye-implanty` — Когда рассматривают скуловые импланты
- `pochemu-nuzhna-kt` — Почему нужна КТ
- `est-li-alternativy` — Есть ли альтернативы

### Ортодонтия (`topic: orthodontics`) — 1 документов

**orthodontics__service__aligners** · `service`
- `korotko` — Коротко
- `chto-ispravlyayut-elaynery` — Что исправляют элайнеры
- `etapy-lecheniya-na-elaynerah` — Этапы лечения на элайнерах

### Пародонтология (`topic: periodontology`) — 1 документов

**periodontology__service__periodontitis** · `service`
- `korotko` — Коротко
- `chto-proishodit-s-desnami` — Что происходит с дёснами?
- `mozhno-li-sohranit-zuby` — Можно ли сохранить зубы?

### Протезирование (`topic: prosthetics`) — 6 документов

**comparison__bugel_prosthesis_vs_fixed_bridge** · `comparison`
- `korotko` — Коротко
- `esli-net-neskolkih-zubov` — Если нет нескольких зубов
- `kogda-chashche-vybirayut-byugelnyy-protez` — Когда чаще выбирают бюгельный протез
- `kogda-mozhno-rassmotret-nesemnyy-most` — Когда можно рассмотреть несъёмный мост

**prosthetics__service__clasp_dentures** · `service`
- `korotko` — Коротко
- `podoydet-li-mne-byugelnyy-protez` — Подойдёт ли мне бюгельный протез?
- `budet-li-udobno-nosit` — Будет ли удобно носить?

**prosthetics__service__implant_supported_prosthetics** · `service`
- `korotko` — Коротко
- `kakoy-variant-podoydet` — Какой вариант подойдёт именно вам?
- `budu-li-hodit-bez-zubov` — Буду ли я ходить без зубов?

**prosthetics__service__removable_dentures** · `service`
- `korotko` — Коротко
- `chastichnyy-ili-polnyy-protez` — Частичный или полный протез?
- `mozhno-li-sdelat-udobno-i-estestvenno` — Можно ли сделать удобно и естественно?
- `chto-delat-esli-protez-natiraet` — Что делать, если протез натирает?

**prosthetics__service__veneers** · `service`
- `korotko` — Коротко
- `etapy-ustanovki-vinirov` — Этапы установки виниров
- `bolno-li-stavit-viniry` — Больно ли ставить виниры и нужно ли обтачивать зубы

**prosthetics__service__zirconia_crowns** · `service`
- `korotko` — Коротко
- `kogda-stavyat-koronku` — Когда ставят коронку
- `koronka-na-implant` — Коронка на имплант

### Терапия (лечение зубов) (`topic: treatment`) — 3 документов

**treatment__service__caries** · `service`
- `korotko` — Коротко

**treatment__service__pulpitis** · `service`
- `korotko` — Коротко
- `bolno-li-lechit-kanaly` — Больно ли лечить каналы?

**treatment__service__teeth_treatment** · `service`
- `korotko` — Коротко
- `pochemu-lechenie-zubov-bez-boli` — Почему лечение зубов без боли

### Отбеливание (`topic: whitening`) — 1 документов

**whitening__service__teeth_whitening** · `service`
- `korotko` — Коротко
- `komu-podhodit-otbelivanie` — Кому подходит отбеливание
- `nuzhna-li-chistka` — Нужна ли чистка перед отбеливанием
- `bezopasno-li-otbelivanie` — Безопасно ли отбеливание для эмали

---

## 2. Услуги с ценами (PriceBook)

Источник: `clients/demo/pricebook/services/*.json`. Legacy `prices.json` удалён.

| service_id | Название | Модель | Единица | от ₽ | Примечание |
|------------|----------|--------|---------|------|------------|
| `aligners` | Элайнеры для выравнивания зубов | simple | — | 195 000 | Полный курс лечения; зависит от сложности прикуса и количест |
| `all_on_4` | Имплантация All-on-4 | complex | 1 челюсть | 318 000 | Implantium (Южная Корея) 318 000 ₽; Impro (Германия) 368 000 ₽; Nobel Biocare (Швейцария) 428 000 ₽ |
| `all_on_6` | Имплантация All-on-6 | complex | 1 челюсть | 398 000 | Implantium (Южная Корея) 398 000 ₽; Impro (Германия) 458 000 ₽; Nobel Biocare (Швейцария) 528 000 ₽ |
| `caries` | Лечение кариеса | simple | — | 6 500 | Зависит от глубины поражения и объёма пломбирования |
| `clasp_dentures` | Бюгельные протезы | simple | — | 85 000 | Частичное восстановление; вариант на кламмерах или замках |
| `classic` | Классическая имплантация | complex | 1 зуб | 76 200 | Implantium (Южная Корея) 76 200 ₽; Impro (Германия) 85 200 ₽; Nobel Biocare (Швейцария) 101 200 ₽ |
| `implant_supported_prosthetics` | Протезирование на имплантах | simple | 1 зуб | 31 000 | Ортопедический этап (коронка/мост); имплантация оплачивается |
| `one_stage` | Одномоментная имплантация | complex | 1 зуб | 86 500 | Implantium (Южная Корея) 86 500 ₽; Impro (Германия) 96 500 ₽; Nobel Biocare (Швейцария) 114 500 ₽ |
| `periodontitis` | Лечение пародонтита | simple | — | 15 000 | Комплекс терапии; точный план после диагностики дёсен |
| `professional_whitening` | Профессиональное отбеливание | simple | — | 18 000 | Точная стоимость зависит от выбранного протокола |
| `pterygoid_implants` | Птеригоидные импланты | simple | 1 имплант | 95 000 | За один имплант; коронка или протез — отдельно |
| `pulpitis` | Лечение пульпита | simple | — | 12 000 | Лечение каналов и восстановление зуба; при необходимости — к |
| `removable_dentures` | Съёмное протезирование | complex | 1 челюсть | 45 000 | Частичный съёмный протез 45 000 ₽; Полный съёмный протез 65 000 ₽ |
| `sinus_lift` | Синус-лифтинг | complex | 1 зона | 42 000 | Закрытый синус-лифтинг 42 000 ₽; Открытый синус-лифтинг 68 000 ₽ |
| `teeth_treatment` | Лечение зубов | simple | — | 8 500 |  |
| `temporary_teeth` | Временные зубы на имплантах | simple | 1 зуб | 18 000 | Временный протез на период приживления; постоянная коронка — |
| `tomography` | КТ (компьютерная томография) | simple | — | 3 000 |  |
| `tooth_extraction` | Удаление зубов любой сложности | simple | — | 4 500 | Простое удаление; сложное или зуб мудрости — по результатам  |
| `veneers` | Виниры E-max | simple | 1 зуб | 35 000 | За один зуб; полная реставрация улыбки рассчитывается на кон |
| `zirconia_crowns` | Коронки из диоксида циркония | simple | 1 зуб | 25 000 | Стоимость зависит от сложности работы и типа конструкции (од |
| `zygomatic_implants` | Скуловая имплантация | simple | 1 челюсть | 420 000 | На одну челюсть; временный и постоянный протез — по плану ле |

### Complex — бренды имплантов (unit: 1 зуб под ключ)

**classic**, **one_stage** — по 3 бренда:
- Implantium — от 76 200 / 86 500 ₽
- Impro (recommended) — от 85 200 / 96 500 ₽
- Nobel Biocare — от 101 200 ₽

### Complex — 1 челюсть (All-on)

**all_on_4** — от 318 000 ₽ (Implantium) · **all_on_6** — от 398 000 ₽

### Complex — варианты процедуры (не бренды)

**sinus_lift** (`one_site`): закрытый 42 000 ₽ · открытый 68 000 ₽ — заголовок в ответе «Варианты», не «По брендам»

**removable_dentures** (`jaw`): частичный 45 000 ₽ · полный 65 000 ₽

---

## 3. Что не делаем (`clinic_policies.yaml`)

Источник: `clients/demo/clinic_policies.yaml`. Два механизма:
- **Жёсткие политики** (`policies`) — ingress → `not_offered_policy`, готовый ответ без retrieval.
- **Альтернативы услуг** (`service_alternatives`) — услуги нет в каталоге; ответ с пояснением + quick reply на `suggest_ref`.

### Жёсткие политики (не делаем)

| policy_key | Что не делаем | Триггеры в вопросе | Суть ответа |
|------------|---------------|--------------------|-------------|
| `no_pediatric_dentistry` | Детская стоматология | `детск`, `ребен`, `ребён`, `детей`, `детям`, `малыш`, `несовершеннолет` | Мы работаем только со взрослыми пациентами — детскую стоматологию в клинике не ведём. Если нужна ко… |
| `no_oms` | ОМС (бесплатное лечение по полису) | `омс`, `полис омс`, `по омс` | По полису ОМС мы не работаем — лечение идёт на платной основе. Могу рассказать о стоимости, рассроч… |
| `no_dms` | ДМС (прямое страхование) | `дмс`, `полис дмс`, `по дмс` | По ДМС напрямую не работаем — оплата по договору с клиникой (наличные, карта, рассрочка). Подробнос… |

Примеры для eval (ingress): «Есть детский стоматолог?» → `no_pediatric_dentistry`; «по ОМС» → `no_oms`; «по ДМС» → `no_dms`.

### Альтернативы (нет в каталоге → что предложить)

| Ключевые слова | Не делаем | Предлагаем | suggest_ref |
|----------------|-----------|------------|-------------|
| `брекет` | Брекеты мы не устанавливаем | элайнеры | `orthodontics__service__aligners.md#korotko` |
| `базальн`, `basal` | Базальную имплантацию мы не проводим. Работаем с проверенными протоколами классической и одномомент… | классическая имплантация | `implantation__service__classic.md#korotko` |
| `мини-имплант`, `мини имплант` | Мини-импланты не используем как основной протокол. Для постоянного результата обычно подбираем стан… | классическая имплантация | `implantation__service__classic.md#korotko` |
| `osstem`, `ossstem`, `остем` | Osstem в ассортименте нет. Работаем с Implantium, Impro и Nobel Biocare — могу рассказать про отлич… | Implantium, Impro, Nobel Biocare | `implantation__info__implant_systems.md#korotko` |

Примеры: «ставите брекеты» → не в каталоге, ответ про элайнеры + кнопка `orthodontics__service__aligners.md#korotko`.
«базальная имплантация» / «мини-импланты» / «Osstem» — аналогично, свой `suggest_ref`.

---

## 4. Каталог без md (только facts + цена)

- **tomography** — КТ (компьютерная томография) · `price_display: always` · facts-карточка

---

## 5. Нюансы для eval / smoke

### Маршруты
- **content** — вопрос без явной цены → один md-чанк + слоты
- **price_lookup** — «сколько стоит…» → PriceBook (не md)
- **price_concern** — «почему дорого» → `concern_ref` (обычно `implantation__faq__cost.md#korotko`)
- **group_overview** — «сколько имплантация?» без протокола → manifest `implantation` (5 кнопок)
- **price:classic** ref — widget quick reply → price_lookup без retrieval

### Цены в ответе
- Формат сумм: **`76 200 ₽`** (пробел thousands) — не `76200`
- `price_display: always` — цена **дописывается** в конец контентного ответа (КТ, кариес, пульпит, лечение зубов)
- Синус-лифтинг **не входит** в цену импланта «под ключ» — отдельная услуга

### Конфликты / осторожно
- Generic «сколько имплантация?» → overview, не classic
- «All-on-4 на челюсть» → **all_on_4**, не group full_jaw
- «сколько стоит вся верхняя челюсть» / «нет зубов на верхней» + цена → **upper_jaw** overview (All-on-4 + All-on-6, текст про КТ сверху)
- «имплантация на челюсть» без «верхн» → **full_jaw** overview
- Отбеливание: catalog `professional_whitening`, md `whitening__service__teeth_whitening`

### Shared facts (pricebook/facts.json)
- `installment_12`, `free_implant_consult`, `implant_warranty`, `tax_deduction` — могут дописываться к price-ответу
- Рассрочка от 150 000 ₽ — в `clinic__info__payment_terms.md`, не в PriceBook

### Чего нет в demo (см. также §3)
- Жёсткие отказы: дети, ОМС, ДМС — только через `clinic_policies`, не через md
- Брекеты, базальная/мини-имплантация, Osstem — альтернатива из §3
- Legacy `*__pricing__*.md` удалены — цены только PriceBook

