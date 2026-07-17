# TASK — Response Data Schema Governance

**Ветка:** `codex/stage-a`

**Baseline:** `658203b docs: define situation intake target contract`

**Режим:** documentation/schema governance only. Runtime, client data и A9 не меняются.

## Цель

До любой реализации зафиксировать одну целевую схему ответственности для услуг, цен,
брендов, стратегии клиники, marketing facts, усилителей, CTA, UI-навигации и session
state. Схема должна переноситься между стоматологическими клиниками без demo-hardcode,
не превращать coarse patient facts в медицинское назначение и не давать A9
`patient_scope` product authority.

Одновременно уменьшить число активных документов: согласованный ценовой draft и
отдельный документ условий показа должны быть поглощены одним каноническим target-doc,
а не остаться параллельными источниками правил.

## Обязательные решения checkpoint

1. **Каталог услуг** владеет semantic identity услуги/опции, aliases, family/role,
   активностью, KB refs и минимальными coarse-условиями показа.
2. **Brand dictionary** один раз владеет canonical name, country и aliases. Бренд не
   является patient scope, применимостью или видом лечения.
3. **Pricebook offer** связывает услугу/опцию/бренд с типом цены, точной единицей,
   составом пакета, публичностью цены, commercial fact refs и price follow-ups. Pricebook
   не решает, какую услугу продавать первой.
4. **Стратегия клиники** владеет порядком подходящих услуг/offers, лимитом 2–3 и редкими
   context overrides. Она не владеет активностью, медицинской применимостью, деньгами,
   текстами фактов или CTA-copy.
5. **Commercial fact source** владеет точным текстом/числами, видом факта, датами,
   условиями применимости, detail ref и `incompatible_with`. Универсального правила
   несовместимости скидки и рассрочки нет.
6. **Marketing policy** владеет scenario pools, упорядоченными amplifier/fact refs,
   selector limits, cadence и выбором CTA key, но не дублирует source-owned content,
   dates или incompatibility.
7. **KB/md** владеет согласованным содержательным ответом; **doctor layer** — именем,
   специализацией, связями с услугами и утверждёнными фактами врача; **CTA/tone config** —
   видимой подписью CTA и lead-flow copy без готовых сценарных ответов.
8. **Session state** хранит подтверждённые dialog facts отдельно от `shown_fact_ids`,
   `shown_amplifier_ids`, показанных/нажатых content и price follow-ups, video history,
   semantic CTA context и lead/refusal state.
9. **UI policy** разводит scale clarification, service buttons, price follow-ups,
   content/video slots и отдельную CTA. Уточняющий scale-step не показывает content
   follow-up/video; price follow-ups не смешиваются с content follow-ups.
10. **Source fidelity** запрещает LLM придумывать или смягчать числа, проценты, гарантии,
   отрицания, обещания, единицы, сроки и модальность согласованного источника.
11. **Manual contact и situation intake** сохраняют уже согласованные границы и не
   переопределяются schema selector-ом.
12. **A9 firewall** остаётся неизменным: native `patient_scope` shadow-only, authority
    запрещена, первый A9 raw и frozen artifacts не меняются и не запускаются.

## Документационный результат

- новый единый `docs/PRICE_SERVICE_ARCHITECTURE.md` становится target-каноном цен,
  услуг, брендов, стратегии и общей схемы данных;
- `drafts/PRICE_RESPONSE_RULES_DRAFT.md` удаляется после полного поглощения;
- `docs/SERVICE_SELECTION_CONTEXTS.md` удаляется после полного поглощения;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` получает точный schema/ownership contract
  для commercial facts, amplifiers, CTA и session cadence без дубля ценовой модели;
- `docs/MARKETING_QUESTION_TECH.md`, `docs/README.md` и
  `docs/STRANGLER_ROADMAP.md` обновляются только для согласованных ссылок, границ и
  статуса checkpoint.

## Allowlist реализации governance-doc

- `TASK.md`;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` (new);
- `drafts/PRICE_RESPONSE_RULES_DRAFT.md` (delete after absorption);
- `docs/SERVICE_SELECTION_CONTEXTS.md` (delete after absorption);
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md`;
- `docs/MARKETING_QUESTION_TECH.md`;
- `docs/README.md`;
- `docs/STRANGLER_ROADMAP.md`.

## Protected / вне scope

- весь code/runtime, tests, evals, prompts и contracts;
- весь `clients/**`, включая фактическую migration JSON/YAML;
- `docs/PRICEBOOK_V2.md` как current-runtime спецификация;
- реализация selector, loaders, validators, session schema или UI;
- изменение manual-contact текста/runtime и реализация `situation_intake`;
- A9 design/raw/harness/evidence, live/LLM и product authority;
- merge, `main` и любые другие ветки.

## Обязательные invariants схемы

1. Явно названная активная услуга обрабатывается независимо от autosuggest eligibility;
   commercial priority не перебивает прямой выбор пациента.
2. Billing unit и цена не доказывают применимость услуги.
3. Unknown patient fact не считается совпадением с обязательным условием.
4. `one_tooth`, `few_teeth`, `full_arch`, jaw и stage — факты ситуации, а не жёсткие
   методы лечения; `full_arch` означает одну челюсть.
5. Число за одну единицу нельзя автоматически умножать или переносить на другой
   масштаб/пакет; обе челюсти требуют отдельного подтверждённого offer.
6. Поддерживаются fixed, from, range и no-public-price; любой денежный факт имеет
   точную currency и billing unit либо утверждённый no-price текст.
7. Протокол, semantic option и реальный бренд не кодируются одним полем.
8. Shortlist содержит 2–3 подходящие услуги/offers конкретной клиники; уточняется один
   действительно влияющий факт за шаг, без повторного вопроса об уже известном.
9. Первый общий price overview по возможности покрывает один зуб и полную челюсть одной
   подтверждённой позицией на каждый масштаб; третья позиция необязательна и определяется
   стратегией клиники. Отсутствующий масштаб не выдумывается.
10. Brand overview сохраняет покрытие разных масштабов, если scope неизвестен. Сравнение
    «дешевле» разрешено только для одинаковых service, billing unit и сопоставимого
    package; «лучше» — только по утверждённому KB-сравнению.
11. В ответе максимум три marketing facts, из них максимум два amplifiers; CTA отдельно.
12. Прямой вопрос о fact обходит suppression повтора, но не eligibility, active dates,
    source fidelity или manual-contact boundary.
13. Тот же `fact_id`/`amplifier_id` автоматически не повторяется внутри текущего
    `session_id`; новый диалог/сброс создаёт новую сессию, TTL пока отсутствует. Прямой
    вопрос не переписывает history и обходит только suppression автопоказа.
14. Pure scale clarify показывает только кнопки уточнения. Content-ответ имеет ровно два
    secondary slots: video приоритетно показывается один раз на первом ходе материала,
    затем идут ещё не показанные follow-ups; новый материал создаёт новый candidate set.
    Service-detail и «Рассказать о ситуации» конкурируют за эти же два слота.
15. Price-ответ имеет отдельные два navigation slots. Кнопки создаются только из
    `service.followups`, а `fact_refs` дают только текст; прямо запрошенный aspect
    отвечается сразу и не повторяется кнопкой. Показанные/нажатые price follow-ups
    автоматически не повторяются. Content и price follow-ups не смешиваются.
16. CTA не занимает secondary/navigation slots, стабильна внутри semantic context и
    выбирается заново только при явной смене контекста. Если context-specific CTA нет,
    используется clinic default; модель не придумывает CTA. CTA запрещена в manual-contact
    hard-stop, spam/off-topic, pure clarify, после явного отказа и внутри активного
    lead-flow.
17. Данные и session history одной клиники не могут влиять на другую.
18. Target schema не объявляется реализованной и не получает authority этим документом.

## Verification

1. До редактирования allowlist кроме `TASK.md` независимый checker подтверждает scope,
   ownership, отсутствие скрытого runtime/A9 authority и достаточность acceptance laws.
2. После materialization checker подтверждает полное поглощение двух удаляемых документов
   и отсутствие противоречий с product canon/current-runtime docs.
3. `git diff --check` и локальные Markdown links проходят.
4. Поиск не находит активных ссылок на удалённые документы.
5. Diff не затрагивает protected paths и не создаёт client-specific hardcode как общий
   закон.
6. В новом каноне есть section-by-section absorption map для каждого заголовка удаляемых
   документов. Карта отдельно подтверждает перенос полного 21-service inventory,
   стоматологических границ, всех закрытых price decisions и незакрытых требований к
   будущим tests/guards.
7. Новый канон задаёт будущую verification matrix минимум для: повторных уточнений,
   исправления patient facts, неверного метода/масштаба/единицы, brand comparison,
   межклиентского переноса priorities/session state, лимитов UI и marketing 3/2. Узкие
   guards допускаются только как source-backed validation и не создают второй источник
   понимания ситуации.
8. `pytest` не запускается: исполняемое поведение не меняется.

## Definition of Done

- один канонический target-doc отвечает, где хранится каждый вид данных и как источники
  связываются без дублей;
- маркетинговая schema стыкуется с ценами/услугами, UI и session state;
- владелец продукта по-прежнему читает только roadmap и foundation;
- runtime/current-client data честно помечены как ещё не мигрированные;
- checker `✅`, отдельный commit/push только в `origin/codex/stage-a`, дерево чистое.
