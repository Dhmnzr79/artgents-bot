# Аудит контента `clients/demo`

**Дата:** 2026-06-23  
**Обновлено:** 2026-06-23 — правки по политике demo применены  
**Режим:** content-editor → исправления в `clients/demo/`  
**Ориентиры:** `.cursor/agents/content-editor.md`, `docs/DEMO_TEST_INVENTORY.md`

---

## Команды проверки

```bash
python scripts/lint_content.py --client demo
python scripts/lint_content.py --client demo --collisions
python scripts/lint_pricebook.py demo
```

| Команда | Результат |
|---------|-----------|
| `lint_content.py --client demo` | **OK** (после правок) |
| `lint_content.py --client demo --collisions` | см. §3 — остались некритичные |
| `lint_pricebook.py demo` | **OK** — 0 предупреждений |

Дополнительно: ручной проход слотов `clinic_note` / `consult_value`, cross-doc aliases (price, full jaw, upper jaw, classic vs all-on), `suggest_refs` в catalog и `ui.yaml`, согласованность catalog ↔ policies ↔ md.

---

## 1. Сводка по приоритетам

| Приоритет | Кол-во | Суть |
|-----------|--------|------|
| **Критично** | 0 | Исправлено: extraction frontmatter, catalog price/full-jaw, синус-лифтинг |
| **Средне** | ~5 | Остаточные cross-doc (methods_overview, doctors), пограничные aliases |
| **Мелочь** | 2 | Устаревший inventory; eval-кейсы §9 |

**PriceBook:** manifest, services и facts согласованы — блокеров нет.

---

## 2. Находки

| # | Приоритет | Файл / зона | Поле / чанк | Проблема | Риск для бота |
|---|-----------|-------------|-------------|----------|---------------|
| 1 | **Критично** | `extraction__service__tooth_extraction.md` | frontmatter | `missing_frontmatter`: нет закрывающего `---`, списки через `*` вместо YAML `-`, разделитель из длинных `-` | Документ может не индексироваться; catalog `tooth_extraction` → битый md |
| 2 | **Критично** | `service_catalog.json` → `classic` | aliases | `"сколько стоит имплантация"` и кластер price-фраз (4 шт.) | Generic price → цена **classic**, не group overview `implantation` |
| 3 | **Критично** | `service_catalog.json` → `all_on_4` | aliases | `"имплантация всей челюсти"` | Full-jaw вопрос → **all_on_4**, минуя `full_jaw` / comparison |
| 4 | **Критично** | `bone_graft` ↔ `sinus_lift` | frontmatter alias | `"синус-лифтинг"` в обоих md | Неверный retrieval: info vs price_lookup на одну фразу |
| 5 | Средне | `comparison__classic_vs_one_stage` ↔ `methods_overview` | alias | `"классическая или одномоментная имплантация"` | Comparison vs обзор — случайный чанк |
| 6 | Средне | `pterygoid_implants` ↔ `sinus_lift` | alias | `"мало кости сверху"` | Две услуги на один симптом |
| 7 | Средне | `pterygoid` (md+catalog) ↔ `zygomatic` (catalog) | alias | `"сложная имплантация верхней челюсти"` в pterygoid; zygomatic — `"сильная атрофия верхней челюсти"` | Конкурирующие маршруты на верхнюю челюсть |
| 8 | Средне | `comparison__all_on_4_vs_all_on_6` | frontmatter | 11 aliases; `"имплантация верхней челюсти"`, jaw-фразы | Погранично по лимиту; часть дублирует h3 |
| 9 | Средне | `comparison__all_on_4_vs_all_on_6` | h3 `#verhnyaya-chelust-i-nagruzka` | `"нет зубов на верхней челюсти"`, `"восстановить верхнюю челюсть"` уже в frontmatter | Дубль doc-level ↔ chunk-level |
| 10 | Средне | catalog ↔ md | `classic`, `one_stage`, `all_on_4`, `all_on_6`, `sinus_lift` | Те же norm-key в catalog и frontmatter service | Двойной владелец; по канону матч — **только catalog** |
| 11 | Средне | `implantation__service__sinus_lift.md` | frontmatter | 11 aliases (норма service ≤7) | Раздуто; часть уже в catalog (13 aliases) |
| 12 | Средне | `implantation__info__bone_graft.md` | h3 `#sinus-lifting-i-stoimost` | h3-alias `"сколько стоит синус-лифтинг"` | Price-вопрос в info, не catalog |
| 13 | Средне | `implantation__service__classic.md` | `h3_overrides.sroki-i-ogranicheniya.clinic_note` | Повтор **«3–6 месяцев»** из `#korotko` / h3 | Пациент видит срок дважды |
| 14 | Средне | `implantation__service__all_on_4.md` | `clinic_note` | «временный протез в день операции» ≈ `#korotko` | Лёгкий дубль слота |
| 15 | Средне | `ui.yaml` | quick_reply | `"Стоимость имплантации"` → `price:classic` | Generic implant price → classic, не overview |
| 16 | Средне | `implantation__info__steps.md` | `suggest_refs` | `"Цены на импланты"` → `price:classic` | На вопрос про этапы/визиты на челюсть — кнопка на classic |
| 17 | Средне | `extraction__service__tooth_extraction.md` | frontmatter alias | `"удалить зуб и поставить имплант"` | Пересечение с `one_stage` (catalog) |
| 18 | Мелочь | `doctors__doctor__orlov` ↔ `overview` | 3 aliases | «кто делает/занимается имплантацией» | Коллизия врач vs обзор |
| 19 | Мелочь | `implantation__faq__what_included.md` | frontmatter | 9 aliases (faq max 8) | Пограничное раздувание |
| 20 | Мелочь | `implantation__faq__cost.md` | h3 | `"как сэкономить на имплантации"` дублирует frontmatter | Лишний alias в чанке |
| 21 | Мелочь | `docs/DEMO_TEST_INVENTORY.md` | — | Нет `what_included`; у extraction старые h3 в инвентаре | Eval-ориентир устарел |

---

## 3. Cross-doc alias collisions (линтер)

```
'классическая или одномоментная имплантация'
  → comparison__classic_vs_one_stage.md, implantation__info__methods_overview.md

'кто делает имплантацию'
  → doctors__doctor__orlov.md, doctors__doctor__overview.md

'кто занимается имплантацией'
  → doctors__doctor__orlov.md, doctors__doctor__overview.md

'кто у вас по имплантам'
  → doctors__doctor__orlov.md, doctors__doctor__overview.md

'мало кости сверху'
  → implantation__service__pterygoid_implants.md, implantation__service__sinus_lift.md

'синус-лифтинг'
  → implantation__info__bone_graft.md, implantation__service__sinus_lift.md
```

**Опасные зоны (ручная оценка):** price, full jaw, upper jaw, classic vs all-on — см. находки #2–#4, #7–#10, #15–#16.

---

## 4. Слоты ответа (`clinic_note` / `consult_value`)

Ручной проход: `classic`, `all_on_4`, `all_on_6`, `one_stage`, `what_included`.

| Документ | `clinic_note` | `consult_value` | Вердикт |
|----------|---------------|-----------------|---------|
| `implantation__service__classic` | УТП (опыт, 3D, смета) — ок | Ок | **Дубль** в `h3_overrides` по срокам 3–6 мес. |
| `implantation__service__all_on_4` | УТП — ок, лёгкий overlap с korotko | Ок | Приемлемо |
| `implantation__service__all_on_6` | УТП | Сравнение 4 vs 6 — уместно | Ок |
| `implantation__service__one_stage` | УТП, протокол | Ок | Ок |
| `implantation__faq__what_included` | Смета/этапы — не дублирует korotko | Ок | Ок; aliases чуть раздуты |

Линтер проверяет только длину слотов; семантические дубли — в таблице выше.

---

## 5. `suggest_refs` и quick replies

| Источник | Содержание | Замечание |
|----------|------------|-----------|
| `service_catalog.json` | Все `suggest_refs: []` | Нет кнопок после price-ответов (в т.ч. на `what_included`) |
| `ui.yaml` → guided_menu | `price:classic`, pain faq, consultation, lead | Generic «стоимость имплантации» → classic |
| `implantation__info__steps.md` | `{ label: "Цены на импланты", ref: "price:classic" }` | Риск неверной кнопки на вопросы про этапы / челюсть |
| `clinic_policies.yaml` | 4 `suggest_ref` на живые md#anchor | Ок |

---

## 6. Согласованность catalog ↔ policies ↔ md

| Проверка | Статус |
|----------|--------|
| Policies (дети, ОМС, ДМС, брекеты, базальная, мини, Osstem) | Ок; `suggest_ref` живые |
| Скуловые: catalog `zygomatic_implants` + md `bone_graft` | Ок; не «не делаем», а альтернатива после КТ |
| Отбеливание: `professional_whitening` ↔ `whitening__service__teeth_whitening` | Известное расхождение id (документировано) |
| Суммы в md implantation | Нет «от N ₽»; рассрочка `150 000 ₽` только в `clinic__info__payment_terms` |
| Legacy `*__pricing__*.md` | Не найдены |
| `concern_ref` на implant-услугах | → `implantation__faq__cost.md#korotko` — ок |

---

## 7. Политика маршрутизации demo (вместо «вопросов владельцу»)

Типичная имплантологическая клиника; решения зафиксированы для пакета `demo`:

| Ситуация | Маршрут |
|----------|---------|
| «Стоимость имплантации» (меню, steps) | **group overview `implantation`** (`price:implantation/overview`) |
| «Имплантация всей челюсти» (цена) | **`full_jaw`** overview (All-on-4 + All-on-6) |
| Верхняя челюсть без протокола | **Цена** → `upper_jaw`; **содержание** («4 или 6 сверху») → `comparison__all_on_4_vs_all_on_6` |
| «Синус-лифтинг» | **catalog + service** `sinus_lift`; info `bone_graft` — контекст без doc-level alias |
| «Удалить зуб» vs «имплант в день удаления» | **extraction** / **one_stage** в catalog — раздельно |
| «Мало кости» / альтернативы | **info `bone_graft`**; узкие услуги в catalog |
| «Кто делает имплантацию» | **`doctors__overview`**, не карточка одного врача |
| `what_included` | В smoke/eval (§9); кнопка из price-ответа — backlog (runtime: только price_concern) |

---

## 8. Выполненные правки (2026-06-23)

| # | Файл | Что сделано |
|---|------|-------------|
| 1 | `extraction__service__tooth_extraction.md` | Починен YAML frontmatter |
| 2 | `service_catalog.json` → `classic` | Убраны generic price-aliases; цена на **один зуб**; `suggest_ref` → what_included |
| 3 | `service_catalog.json` → `all_on_4` | Убрано «имплантация всей челюсти» |
| 4 | `service_catalog.json` → `pterygoid` | Убрано «сложная имплантация верхней челюсти» |
| 5 | `bone_graft.md` | Убран «синус-лифтинг» из frontmatter; price-alias из h3 |
| 6 | `sinus_lift.md`, `pterygoid.md`, service md | Сжаты frontmatter aliases (матч в catalog) |
| 7 | `classic.md` | h3_override без дубля «3–6 месяцев» |
| 8 | `ui.yaml`, `steps.md` | `price:implantation/overview` |
| 9 | `what_included.md` | Сжат кластер «под ключ» (4 aliases) |
| 10 | `orlov.md`, `comparison`, `faq__cost` | Убраны дубли aliases |

**Out of scope:** `evals/v5/*.json`, `core/*.py`, пакеты cesi/nikadent.

---

## 9. Eval — рекомендуемые кейсы

| Вопрос | Ожидаемый маршрут |
|--------|-------------------|
| «Сколько стоит имплантация?» | group overview `implantation`, не classic |
| «Имплантация всей челюсти — цена» | `full_jaw`, не all_on_4 |
| «Имплантация верхней челюсти» | comparison / `upper_jaw` |
| «Синус-лифтинг» | `sinus_lift` + price_lookup |
| «Что входит в имплант под ключ?» | `implantation__faq__what_included` |
| «Удаление зуба» | `extraction__service__tooth_extraction` (после починки frontmatter) |

Ориентир покрытия: `drafts/test.md`, `docs/DEMO_TEST_INVENTORY.md`.

---

## 10. Итог

PriceBook чистый. Критичные риски маршрутизации **устранены** (extraction, catalog price/full-jaw, синус-лифтинг, ui/steps overview).

Остаточно на следующий проход: cross-doc `methods_overview` ↔ comparison; обновить `DEMO_TEST_INVENTORY.md` и eval §9.

```bash
python build_index.py --client demo
python scripts/gen_demo_test_inventory.py
python scripts/lint_content.py --client demo --collisions
```
