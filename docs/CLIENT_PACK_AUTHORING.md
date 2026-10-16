# Client pack authoring

Один canonical source на домен. Новая клиника **не создаёт** root legacy mirrors
(`service_catalog.json`, `pricebook/`, `marketing.yaml`, `price_brand_aliases.json`).

## Что меняю → какой файл

### Стартовое меню по страницам сайта

В `clients/nikadent/widget_config.json` уже настроены общее меню, All-on-4,
съёмные протезы и коронки. Это настройки внешнего вида; MD-база ответов прежняя.

- Верхние `welcomeText` и `starterPrompts` — общее приветствие и стартовые кнопки
  на главной и всех страницах без отдельной настройки (включая врачей и цены).
- `pageMenus` — список исключений. `paths` содержит адреса страниц **после домена**,
  например `/all-on-4/`. Одному меню можно назначить несколько адресов.
- В каждом меню `welcomeText` — приветствие, `starterPrompts` — ровно три кнопки.
  `label` — короткая надпись, `q` — полный вопрос, который отправляется при клике.
- `topicId` — необязательный canonical ID из `target_response/service_topics.json`.
  Он сообщает модели тему исходной страницы только при первом вопросе новой
  беседы. Это не утверждение пациента о нужной ему услуге. Общие кнопки могут
  сохранять прежнее видео; правило трёх вопросов относится к отдельным меню.
- `welcomePromotion` в верхней части файла — одна акция на весь сайт. Внутри
  `pageMenus` акции не задаются. Её тексты должны соответствовать действующей базе;
  изменение карточки само по себе не меняет условия в фактах/MD.

Пример элемента `pageMenus`:

```json
{
  "paths": ["/all-on-4/"],
  "topicId": "implantation",
  "welcomeText": "Здравствуйте! Помогу разобраться в имплантации All-on-4.",
  "starterPrompts": [
    {"label": "Стоимость All-on-4", "q": "Сколько стоит All-on-4 в НикаДент?"},
    {"label": "Этапы лечения", "q": "Как проходит лечение All-on-4 в НикаДент?"},
    {"label": "Консультация", "q": "Как записаться на консультацию по имплантации?"}
  ]
}
```

Совпадение точное: `/all-on-4` и `/all-on-4/` равнозначны; UTM и `#якорь`
игнорируются. Подстраницы, похожие слова, другой регистр и маски `*` не
подбираются автоматически. Повтор одного адреса в разных меню — ошибка настройки.
При переходах с перезагрузкой страницы меню определяется заново; для сайта с
SPA-переходами без перезагрузки отдельная интеграция пока не реализована.
В новой беседе/reset адрес читается заново; активный разговор не сбрасывается.
URL/UTM в модель не отправляются. Сервер принимает только pathname, сам проверяет
его по captured настройкам клиента и определяет тему. Переход на другую страницу
в активной беседе не меняет начальную тему. Переписка восстанавливается из
сохранённых ответов сервера; пациент может написать вопрос на любую тему клиники.

Проверка: локальная панель `/static/widget-test.html?client=nikadent`, поле
«Страница сайта», затем «Открыть чат». Обновить страницу после правки JSON.
На клиентском сайте адрес определяется автоматически; отдельный embed-код для
каждой страницы не нужен. До выкладки новая функция работает только локально.

Готовая инструкция для Codex: «В `clients/nikadent/widget_config.json` измени
меню для `/all-on-4/`: приветствие …; три кнопки: надпись …, вопрос …; …; … .
Общее меню и общую акцию сохрани. Проверь конфигурацию и тестовую панель.
Без merge/deploy и платных вызовов». Для нового клиента тот же формат.

| Задача | Единственный файл |
|---|---|
| Название услуги, aliases, active, family | `clients/{id}/target_response/service_catalog.json` |
| Цена, billing unit, пакет, payment stages | `clients/{id}/target_response/pricebook/services/{offer_id}.json` |
| Commercial facts (акции, рассрочка, гарантия) | `clients/{id}/target_response/pricebook/facts.json` |
| Broad family price (опционально) | `clients/{id}/target_response/pricebook/family_prices.json` |
| Бренды и aliases | `clients/{id}/target_response/brand_catalog.json` |
| Коммерческие профили, усилители, «Также», несовместимость | `clients/{id}/target_response/d2_commercial.json` |
| Явный порядок готовых offers в ценовом обзоре направления | `clients/{id}/target_response/d2_direction_prices.json` |
| Разделы вкладки каталога и распределение услуг | `clients/{id}/target_response/widget_catalog.json` |
| Текст услуги / FAQ (FullContext) | `clients/{id}/md/{content_ref}` |
| Врачи и привязка к услугам | `clients/{id}/doctor_catalog.json` |
| Контакты, часы, парковка, «не оказываем» | `clients/{id}/clinic_policies.yaml` → `contact:` (structured: phone, whatsapp, address, hours, parking) |
| Виджет: имя, цвета, логотип | `clients/{id}/brand.yaml` |
| CTA-формулировки | `clients/{id}/tone.yaml` |
| UI labels / fallback меню | `clients/{id}/ui.yaml` |
| Видео (опционально) | `clients/{id}/video_catalog.yaml` |
| Приветствие, стартовые вопросы, меню по страницам, общая акция виджета | `clients/{id}/widget_config.json` |
| Разрешённые домены установки виджета | `clients/{id}/widget_integration.json` |
| Runtime capabilities | `clients/{id}/features.yaml` |
| Доставка заявок и согласие перед отправкой формы | `clients/{id}/lead_config.yaml` |

### Каталог и форма в трёх вкладках

`widget_catalog.json` содержит `version: 1`, `client_id`, `label` (например,
«Стоматология»), `unpriced_text` и `sections`: `section_id`, `title`, `subtitle`,
`service_ids`. `subtitle` — короткая подпись серой плитки направления, без числа
услуг или цены. `label` и `subtitle` — оформление каталога, не контекст модели.
Обязательная карта `service_subtitles` задаёт короткую подпись каждой услуги:
ключ — `service_id`, значение — непустое пояснение для посетителя, например
`"denture_repair": "Восстановление повреждённого съёмного протеза"`.
Ключи карты должны точно совпадать с объединением `service_ids` разделов.
Эта подпись выводится в списке и поиске вместо названия первого варианта
и счётчика; полный текст услуги остаётся в MD. Автоматических подстановок нет.
Каждая активная услуга входит
ровно в один раздел; неизвестные, чужие, неактивные и пропущенные IDs — ошибка.
Названия, суммы, варианты и условия повторно здесь не записываются. Каталог и
чат используют один сборщик offers, commercial selector и renderer карточки.
Без offer услуга остаётся видимой с `unpriced_text`, без выдуманной цены.

Просмотр каталога не меняет заявку. Явная кнопка переносит service/offer в один
черновик формы; поля синхронны в чате, каталоге и вкладке «Запись».
Контакты вводятся до галочки, отправляются только кнопкой после согласия.
Форма не проходит через модель или историю беседы; повтор запроса использует
тот же request_id. После подтверждения показывается благодарность.
Локально запускать `scripts/start_local_widget.ps1`; панель поддерживает
`demo`, `demo_medical`, `nikadent`. Launcher разрешает их только своему процессу,
не меняя production registry или `.env`. После обновления runtime запускать
новую беседу: миграция старых сохранённых receipts не входит в эту задачу.

`brand.yaml` ≠ `target_response/brand_catalog.json`  
`clinic_policies.yaml` задаёт контакты и ограничения; коммерческие профили — отдельный домен.

`family` и `price.billing_unit` — непустые идентификаторы из данных клиники.
Новые направления не требуют расширять встроенный список специальностей.
Человеческая подпись единицы и объёма уже задаётся обязательным `package.label`:
например, «за один первичный приём», «за зону подмышек» или «за одну челюсть».
Код форматирует fixed/from/range суммы; no_public_price сохраняет approved_text.
Цена не умножается по единице. Service/option/offer/brand/fact IDs по-прежнему
проверяются на связь и принадлежность каталогу.

Operational validator, startup и readiness используют тот же D2 snapshot/model
view, что диалог. Старые `target_response/marketing.yaml` и
`target_response/clinic_strategy.yaml` не читаются этим путём, не влияют на
результат проверки и новым клиникам не нужны. В существующих packs они могут
сохраняться для исторических инструментов; это не действующая настройка D2.

**FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE:** canonical contact facts live **only** in
`clinic_policies.yaml` `contact:` block. **Не дублировать** телефон, адрес, часы, WhatsApp,
парковку в `md/`. Прямые контактные вопросы — typed `contacts` aspect + PRIMARY_EVIDENCE
`clinic_contact`, не regex и не MD.

**FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING:** `service_catalog.json` — authority for
**service availability** (standalone treatment/procedure). `content_ref` optional for yes/no
availability answer. Clinic capability/info (materials, equipment, safety standards) — **only** in
`md/` via Generic FullContext; **не добавлять** capability facts as catalog services. Inactive
services: `active=false` in catalog (authored); not shown in planner compact list but preserved in bundle.

**FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE:** service may have **price offer without `content_ref`**
(e.g. `tomography` + `pricebook/services/tomography.default.json`). Price-only answers use structured
`offer:*` evidence — **не** добавлять MD-заглушку только ради Composer. `content_ref` остаётся обязательным
для content-only, content+price, FAQ/description, marketing claims. Missing offer → `data_gap` /
`no_public_price`, not source mismatch.

**FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING:** FAQ про своё/имеющееся КТ — canonical MD
(`diagnostics__service__tomography.md`) + `content_ref` в catalog. **Не** класть текст в catalog facts,
pricebook или marketing. Availability yes/no и price 3 000 ₽ — отдельные пути (structured availability /
price-only offer).

## Новая клиника (чеклист)

1. Скопировать `clients/_template/` → `clients/{new_id}/`.
2. Заменить placeholder IDs (`sample_service`, `template_brand`, …) на уникальные.
3. Добавить MD-файлы под каждый `content_ref` в `service_catalog.json`.
4. Описать врачей и их услуги в MD. При необходимости заполнить текущие
   `d2_commercial.json` профили; цены и условия оставить в offers/facts.
5. Прогнать offline validator:

```powershell
python scripts/validate_client_pack.py --client-id {new_id}
```

Шаблон начинает с `leads.enabled:false`, `admin.enabled:false` и
`postgres_events.enabled:false`. Для реальной отправки заполнить получателя и
`lead_config.yaml -> consent`: версию согласия, утверждённую фразу, HTTPS-ссылки
на согласие и политику клиники. Затем включить `leads.enabled` и повторить
проверку. Пустое согласие при включённых реальных заявках — ошибка валидатора,
включая режим `--scaffold`. Админку и PostgreSQL включать только при их настройке.

### MD и CTA после первой чистки базы

Не добавлять в новые MD `empathy_enabled`, `situation_allowed`, `suggest_refs`
и HTML-комментарии `<!-- aliases: ... -->`: текущий D2 их не использует как
управление, а они расходуют FullContext. Общие aliases в YAML-шапках пока сохранены.
Сохранять `topic`, `suggest_h3`, `cta_key`, `cta_action`, `video_key` и якоря
разделов — у них есть действующие читатели.

Если `cta_action: lead`, значение `cta_key` должно существовать в
`tone.yaml -> lead.cta_variants`. Валидатор проверяет это. Шаблон содержит тот же
словарь из семи существующих вариантов, что demo и НикаДент: default_consult,
booking, consult, callback, plan, price, doctor. Тексты/ключи существующих вариантов
не менять при копировании без задачи клиента.

В `service_catalog.json -> aliases` не повторять `name` с отличием только в
регистре/пробелах. Синонимы, варианты написания и алиасы брендов сохраняются.

## Required files

- `target_response/service_catalog.json`
- `target_response/brand_catalog.json`
- `target_response/pricebook/facts.json`
- `target_response/pricebook/services/*.json` (≥1 offer)
- `md/*.md` (≥1)
- `brand.yaml`, `clinic_policies.yaml`, `features.yaml`, `lead_config.yaml`, `tone.yaml`, `ui.yaml`, `widget_config.json`

## Optional

- `target_response/d2_commercial.json` (пустой текущий пример есть в шаблоне)
- `target_response/d2_direction_prices.json` (только явный обзор направления;
  существующие dental controls пока требуют отдельного этапа обобщения)
- `target_response/pricebook/family_prices.json`
- `video_catalog.yaml`
- `target_response/context_groups.json` (future, not yet implemented — see
  `FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW` / PERF-6 governance,
  `docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md` § 3). Proposed
  shape: `{"schema_version": 1, "groups": [{"group_id": "...", "topics": ["...", "..."]}]}` — an
  explicit authored cross-topic grouping (e.g. "tooth restoration" spanning `implantation` +
  `prosthetics` + `diagnostics`), used only by a future Scoped FullContext `context_group` tier.
  **Does not exist yet; no client currently has this file.**

## Свёрнутый виджет клиента

Клиентский launcher (`demoLauncher:false`) — белая капсула concept1. Иконку
заменяет `brand.yaml -> avatar_url` с зелёной точкой, стрелка фирменного цвета. Через10с
капсула расширяется вверх/влево с неподвижным правым нижним углом. Крестик/Escape
сворачивают приглашение, нижняя кнопка открывает настоящий чат. Demo с
`demoLauncher:true` сохраняет прежнюю кнопку «Посмотреть демо».

Все тексты находятся в существующем `clients/{id}/widget_config.json`:

- `launcherCtaLabel` — надпись нижней кнопки, например «Задать вопрос»;
- `launcherSubtitle` — короткая подпись под кнопкой;
- `launcherTagline` — заголовок раскрытого приглашения;
- `launcherTeaserText` — короткий текст приглашения;
- `launcherTeaser` — включить/выключить автоматическое раскрытие.

Автоприглашение показывается один раз за browser session для данного клиента,
как и до этой правки. Открытие чата до10с отменяет таймер. В локальной панели
кнопка «Повторить приглашение ·10с» сворачивает чат и повторяет анимацию, не
сбрасывая SID, беседу или заявку. Доступна только для клиента с включённым teaser.
На телефонах капсула адаптируется к ширине; prefers-reduced-motion убирает morph.
Тексты меню, согласие и ответы бота эта настройка не меняет.

Аватар и основной цвет каждого клиента задаются в `clients/{id}/brand.yaml`:

```yaml
avatar_url: "/static/clients/nikadent/avatar.png"
colors:
  brand: "#762E94"
  promo_background: "#F5EFF8"
  promo_accent: "#762E94"
```

Файл аватара хранится в `static/clients/{id}/`. У НикаДент подключён avatar.png;
для замены фотографии сохранить новое изображение под тем же именем.
`colors.brand` — единый цвет кнопки отправки, стрелки приглашения и обводки поля
ввода, включая фокус. Фон капсулы остаётся белым, online-точка зелёной.
Виджет уже получает цвет через `theme.brand`; дублировать его в widget_config.json
или в коде виджета не требуется. После правки обновить панель. Если сервер продолжает
отдавать прежние настройки, перезапустить его для сброса кэша brand.yaml.

`colors.promo_background` — фон стартовой карточки акции, `colors.promo_accent`
— её иконка, ссылка «Условия акции» со стрелкой и рамка клавиатурного фокуса.
Hover-фон вычисляется из фона (на 2,5% темнее), заголовок/описание остаются тёмными.
Формат новых цветов: `#RRGGBB`. Пустые или некорректные значения оставляют CSS
по умолчанию. Эти настройки работают и без заданного `colors.brand`.
У demo явно записаны прежний светло-голубой фон и приглушённый синий акцент;
в `_template` поля готовы к заполнению для следующего клиента.

### Аудит цветов текущего виджета — 2026-10-15

Источник: `static/widget/widget.css`, `applyWidgetTheme` в `widget.js`,
`widget_theme_from_brand` в `core/client_config_loader.py`. Это аудит клиентского
виджета; изображения/видео и интерфейс тестовой панели имеют собственные цвета.

| Где используется | Цвет / источник | Настройка клиента |
| --- | --- | --- |
| Отправить, стрелка launcher, обводка ввода, ссылки/CTA, согласие, focus | `colors.brand`; у НикаДент `#762E94` | Да |
| Тени, подсветка, фон ввода, скроллбар | Оттенки основного цвета с белым/прозрачностью; hover основного акцента темнее на 10% | Автоматически от brand |
| Стартовая карточка акции | Фон `promo_background`, акценты `promo_accent`; НикаДент `#F5EFF8` / `#762E94` | Да, отдельно |
| Фон чата/launcher, линии, текст | Белый; серые/тёмные `#211632`, `#6b6280`, `#9a92ad`, `#6e7887`, `#e0e5ed` и др. | Пока общие CSS-токены/правила |
| Кнопки стартового меню, стрелки меню | Фон `#f4f6f9`, hover `#ecedf0`, текст `#293447`, стрелки `#6f7886` | Пока общие |
| Ценовые карточки, галерея | Белый, серые границы/подписи, голубые подложки `#f0f4ff` / `#f3f6ff`; часть акцентов от brand | Смешанная палитра; promo_* сюда не применяется |
| Онлайн / непрочитанное / ошибка | Зелёный `#28c13a` / `#32d33d`, красный `#ef4444`, ошибка `#b91c1c` на `#fef2f2` | Общие смысловые цвета |
| Видео, модальные подложки | Чёрный/тёмный `#000` / `#0f172a`, полупрозрачные маски | Общие |

После чистки §69 (2026-10-15) загрузчик передаёт только три действующих поля
палитры: `brand`, `promoBackground`, `promoAccent`. Старые `action`, `button_1`,
`button_2` удалены из настроек НикаДент/шаблона и из карты загрузчика; у demo их
уже не было. Основной цвет по-прежнему задаёт `colors.brand`.
Удалены 18 классов без создаваемой разметки (старые launcher, видео-модалка и
кнопки), четыре неиспользуемые CSS-переменные и обращения к трём отсутствующим
элементам. Розовый цвет `#d52a7d` удалён вместе со старым launcher-link.
Динамические классы горизонтального/вертикального видео сохранены: они используются.
Действующие голубые подложки ценовых карточек остаются частью общей палитры.

## Согласие перед сбором контактов

В реальном режиме доставки заявок нужен раздел `consent` в
`clients/{id}/lead_config.yaml`. У НикаДент он заполнен; demo_stub его не требует.
При отсутствии корректной настройки реальная заявка блокируется.

```yaml
consent:
  version: "2026-10-15-v1"
  checkbox_text: "Даю согласие на обработку имени и телефона для связи по моей заявке."
  consent_url: "https://nikadent41.ru/personal-data-consent/"
  policy_url: "https://nikadent41.ru/privacy-policy-2/"
```

`checkbox_text` — короткая подпись; `consent_url` — самостоятельное согласие;
`policy_url` — политика клиники. Нужны полные HTTPS-ссылки без логина/пароля.
Тексты документов и цели/состав обработки утверждает клиника. Ссылки НикаДент
сохранены ровно как передал владелец, временно: при проверке consent URL открыл
текст о cookies/внешних сервисах, а не об имени/телефоне заявки. До публичного
запуска уточнить соответствующий документ/ссылку у клиники.

При изменении согласия поменять `version`; сервер также учитывает отпечаток
подписи/ссылок. Перезапустить локальный сервер после настройки, затем обновить
панель. Прежнее подтверждение другой версии не открывает сбор контактов.
Изменение содержимого документа по прежнему URL без смены версии сервер сам
не отслеживает: содержимое удалённой страницы он не скачивает.

Виджет показывает компактный блок с пустой галочкой и кнопками «Продолжить» /
«Без записи». До подтверждения поле контактов заблокировано; «Без записи»
возвращает обычные вопросы. Галочка не сохраняется в браузере между беседами.
Сервер проверяет опубликованное действие/tenant/session/revision; имя, телефон
или слово «да» вместо галочки не считаются согласием. Прямой `/lead` в реальном
режиме без доверенного серверного подтверждения отклоняется.

Доказательство (дата UTC, версия, подпись и ссылки, client/session/request)
сохраняется в существующем D2 completion. Имени/телефона в нём нет. Private
lead session хранит только ссылку на это подтверждение для текущей заявки;
результат отправки также ссылается на него. Отмена/завершение/новая запись
сбрасывают активную ссылку, исторический replay не разрешает новую запись.
Данные согласия не добавляются в контекст модели. Это техническая механика,
не проверка юридической достаточности документов или новые сроки хранения.

Инструкция Codex: «Обнови `consent` в `clients/nikadent/lead_config.yaml`:
ссылка на согласие …, политика …, версия …, подпись … . Проверь gate и компактный
виджет, сохрани demo_stub без согласия. Без live-вызовов и выкладки».

## ID consistency

Автоматическая акция ограничивается `allowed_service_ids` / `allowed_topics` и
`excluded_service_ids` самого факта. Если она относится к конкретным вариантам,
добавьте `allowed_offer_ids`: это дополнительное сужение, а не замена услуги.
Каждый offer должен существовать и принадлежать явно разрешённой, не исключённой
услуге. Отсутствующее поле или `[]` сохраняет область всей услуги. Узкая акция
показывается автоматически только в подробной карточке соответствующего offer;
список вариантов ещё ничего не выбирает. `fact_refs` предложения остаётся ссылкой
на факт и не расширяет область акции. Цены и условия берутся из данных клиента.

- `service_catalog` keys = `service_id` в offers.
- `offer_id` уникален; файл `{offer_id}.json`.
- `brand_id` в offer ∈ `brand_catalog.brands`.
- `fact_refs` в offer ∈ `pricebook/facts.json`.
- `content_ref` в service → существующий `md/{content_ref}`.
- `profile_ref` врача → `kb:...md#anchor` в `md/`.

## Validator

```powershell
python scripts/validate_client_pack.py --client-id demo
python scripts/validate_client_pack.py --path clients/_template --scaffold
```

Exit code ≠ 0 при invalid pack; path-specific errors в stderr.


## Ограничения реального клиента (features.yaml → usage_limits)

НикаДент и шаблон следующего клиента содержат отдельный блок:

```yaml
usage_limits:
  visitor_messages_per_minute: 10
  ip_messages_per_minute: 40
  visitor_ai_questions_per_day: 40
  tenant_model_calls_per_day: 1000
  message_max_chars: 1500
  request_max_bytes: 16384
  visitor_leads_per_hour: 3
```

Все значения — положительные целые числа. Окна скользящие:60секунд,24часа,
3600секунд для заявок. Вопрос списывается при первой попытке вызова модели;
ценовой ответ с двумя вызовами занимает один вопрос и два вызова в общем бюджете.
Неудачная попытка тоже расходует квоту. Повтор законченного запроса бесплатный;
кнопки без модели не расходуют AI-квоту, но подчиняются минутному ограничению.
Demo сохраняет отдельные прежние квоты; отсутствие блока не включает эти новые
ограничения автоматически. Публичный HTTP-вход ограничен максимальным размером
из настроенных клиентов (16КиБ сейчас), затем проверяется меньший предел клиента.

Случайный visitor_id хранится в localStorage сайта отдельно для клиента и
передаётся в обоих transport. Новый чат и переход страницы его не меняют. Это
не идентификация человека: другой браузер/очистка хранилища могут его изменить.
При отсутствии visitor_id используется IP-бакет, не новый sid. Не включены
fingerprinting, CAPTCHA или внешние сервисы. IP доверяется только за настроенным
Caddy hop; счётчики и резервации общие между процессами в SQLite клиента.
В таблице d2_usage_event нет имени/телефона/вопросов, IP/visitor хешированы.
Дедупликация запросов сохраняется вместе с durable учётом; это не удаление старых
диалогов и не новая семантическая память модели.

При исчерпании AI-квоты сохраняются контакты из clinic_policies и штатная CTA
записи с согласием перед контактами. Незаконченная ценовая карточка не публикуется.
Частотный лимит просит подождать минуту. Лимит3заявок/час проверяется перед
отправкой; четвёртая не отправляется и не объявляется успешной. Ошибочные попытки
отправки тоже считаются, автоматического resend нет. Прямой /lead по-прежнему
не принимает произвольное клиентское согласие вместо доверенного D2 receipt.
