# TASK — Define Marketing Scenario Architecture

Один documentation-only checkpoint. Зафиксировать согласованную target-архитектуру базовых коммерческих предложений, CTA и маркетинговых сценариев до schema/runtime-реализации.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

## Цель

Создать компактный канонический product/design-документ, который честно отделяет:

- основной ответ по базе;
- базовые коммерческие факты;
- сценарные усилители;
- CTA и lead-flow;
- жёсткую границу manual contact.

Синхронизировать с ним маркетинговую карту, технический слой, docs-index и точечные переходные ссылки в ценовом черновике и A-series roadmap.

Документ не меняет runtime, prompts, client pack, UI или authority.

## Согласованные product-решения

### 1. Режимы ответа

- обычный первый вопрос об услуге: ответ по базе → базовые предложения → CTA;
- обычное продолжение: ответ по базе → CTA;
- маркетинговое сомнение: естественно отреагировать → ответить только по источникам → выбрать marketing facts → CTA;
- прямой вопрос о враче, гарантии, рассрочке и т. п. получает прямой ответ по источнику, а не принудительный маркетинговый сценарий.

### 2. Общий лимит маркетинговых фактов

- максимум три рекламных/маркетинговых факта за ответ независимо от сценария;
- усилителей среди них максимум два;
- лимит считает консультацию, рассрочку, скидку/подарок, вычет, гарантию/врача и другой факт, если он добавлен для убеждения;
- основной ответ по базе, цены/карточки услуг, CTA и follow-up кнопки в лимит не входят;
- необязательно заполнять все три слота.

### 3. Базовые коммерческие факты

- для обычного первого вопроса по услуге при наличии показываются: одна бесплатная консультация, один вариант рассрочки и одна главная акция/подарок;
- если категории нет, её слот может занять следующий применимый факт по приоритету клиники;
- при прямом вопросе об акциях показываются до трёх применимых акций/подарков по приоритету;
- бесплатная консультация не означает бесплатную КТ; отдельная акция на КТ хранится отдельным фактом;
- налоговый вычет не входит в базовый первый блок; он доступен в финансовом сценарии, при прямом вопросе или как усилитель.

### 4. Усилители

- усилители — клинико-настраиваемые ссылки на факт из KB, Pricebook/commercial facts или профиля врача;
- в `marketing.yaml` хранятся правила, порядок и ссылки, а не дубли утверждённого контента;
- каждый сценарий имеет короткий упорядоченный pool; обычно 2–4 усилителя, но schema не хардкодит этот общий размер;
- порядок ссылок задаёт приоритет; отдельные числа `priority` не обязательны;
- обычное нейтральное продолжение не прокручивает усилители без сценария;
- прямой вопрос о факте всегда получает ответ независимо от истории автопоказа.

### 5. Сценарии и формат ответа

- на этом этапе достаточен короткий стандартный набор: `pain_fear`, `cost`, `time`, `doctor_trust`, `result_reliability`;
- поле `marketing_scenarios` — список из 0–2 значений, чтобы не терять составные сомнения;
- один общий declarative flow для сомнений: `acknowledge_concern` → `answer_from_sources` → `select_marketing_facts` → `cta`;
- flow задаёт порядок смысловых операций, а не текст фраз;
- заготовленные вступления и `scenario_openings` запрещены; композер формулирует реакцию живо, но не изменяет силу, цифры, модальность или смысл источника;
- прямой вопрос «кто у вас врач?» не равен `doctor_trust`; сценарий нужен для выраженного сомнения/недоверия.

### 6. CTA

- CTA и commercial/amplifier cadence независимы;
- одна основная CTA может показываться после каждого содержательного коммерчески релевантного ответа, включая пять последовательных вопросов по одной услуге;
- внутри темы CTA желательно стабильна и меняется при явном изменении намерения;
- CTA не показывается в hard-stop, spam/off-topic, после явного отказа, в ходе уже начатого lead-flow и в узком clarify без содержательного ответа;
- название CTA и первая lead-flow реакция остаются в CTA/tone config; они не являются сценарными заготовками ответа.

### 7. Session cadence и несовместимость

- `shown_fact_ids` и `shown_amplifier_ids` живут внутри текущего `session_id`;
- новый диалог/сброс чата создаёт новую сессию; TTL на этом этапе не вводится;
- одинаковый ID не повторяется автоматически; другой факт для новой услуги может быть показан;
- прямой вопрос о факте обходит только подавление автопоказа и не отменяет точность/применимость источника;
- у коммерческого факта может быть `incompatible_with` с другими `fact_id`;
- точное условие совместимости/несовместимости приходит из утверждённых данных клиники;
- несовместимые предложения показываются как альтернативы; бот не выбирает за пациента;
- универсального правила «скидка не суммируется с рассрочкой» нет.

### 8. Manual-contact boundary

- любая текущая личная боль, осложнение, жалоба или отзыв, требующий реакции, завершаются раньше marketing/retrieval/composer/UI-policy;
- возвращается только согласованная человечная заглушка с номером клиники;
- свободная генерация, факты, акции, CTA, quick replies, video и другие элементы после неё запрещены;
- общий вопрос о будущей боли/страхе лечения — `pain_fear`, а не manual contact.

## Target ownership

- `clients/<client_id>/marketing.yaml`: limits, scenario rules, ordered amplifier refs, applicability, CTA key selection and cadence policy; no duplicated approved source text;
- Pricebook/commercial facts: consultation, installment, discount/gift, deduction, warranty when represented as commercial fact, dates, exact conditions and incompatibilities;
- KB/md: substantive approved content and clinic claims;
- doctor layer: doctor identity, applicability and approved doctor facts;
- CTA/tone config: visible CTA labels and lead-flow copy;
- session state: shown fact/amplifier IDs and current conversation state;
- common planner/TurnFrame target: `marketing_scenarios` as structured understanding; no separate regex/classifier per scenario.

## Allowlist

- `TASK.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` (new);
- `docs/MARKETING_QUESTION_FOUNDATION.md`;
- `docs/MARKETING_QUESTION_TECH.md`;
- `docs/README.md`;
- `docs/STRANGLER_ROADMAP.md`;
- `drafts/PRICE_RESPONSE_RULES_DRAFT.md`.

## Protected / forbidden

- любой Python/JS/CSS/HTML код, tests, evals, prompts и client configs;
- `clients/**`, Pricebook data, service catalog, doctor data;
- A9 raw, frozen matrix/harness, audit/evidence и любой live/LLM run;
- authority, route, composer, UI и session runtime;
- реальное наполнение pool усилителей для demo, кроме 1–2 явно помеченных ненормативных schema-примеров;
- заготовленные ответы/вступления для маркетинговых сценариев;
- расширение ценовой/сервисной модели за пределы точечной ссылки на новую marketing policy.

## Verification

До правок документов independent checker проверяет governance TASK на:

- совпадение с принятыми product-решениями;
- отсутствие скрытой runtime/authority-реализации;
- сохранение product firewall A9 и no-live;
- отсутствие заготовленных сценарных фраз.

После правок checker независимо проверяет:

1. все согласованные правила явно описаны в каноническом документе;
2. foundation и tech не противоречат канону;
3. ценовой черновик не дублирует marketing architecture и больше не хранит закрытый session-cadence как открытый;
4. current personal pain везде отделена от future/generic pain fear;
5. общий лимит 3/2, CTA cadence, session semantics и incompatibility описаны однозначно;
6. нет предписанного клинике набора усилителей или готовых фраз;
7. изменены только allowlist-файлы;
8. `git diff --check` проходит, все локальные markdown-ссылки разрешаются;
9. code/tests/client configs/A9 evidence не затронуты; pytest/live не запускались.

## Definition of Done

1. Governance checker дал `✅` до изменения docs.
2. Новый канонический документ компактен и содержит все принятые product laws.
3. Связанные docs синхронизированы без копипасты всего канона.
4. Final checker дал `✅`.
5. Docs-checkpoint закоммичен и отправлен только в `origin/codex/stage-a`; дерево чистое.
