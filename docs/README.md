# Документация — с чего начинать

## Владельцу продукта нужно читать только два документа

1. [Roadmap A1–A9](STRANGLER_ROADMAP.md) — что уже сделано, что заблокировано и какой
   следующий checkpoint.
2. [Маркетинговая карта ответов](MARKETING_QUESTION_FOUNDATION.md) — как должен вести
   себя бот с точки зрения маркетинга и логики ответа.

Остальные документы нужны агентам и checker-ам для реализации, проверки и сохранения
доказательств. Владельцу не нужно читать их подряд.

## Как разрешать расхождения

Документы разделены по назначению. Нельзя смешивать их правила без учёта статуса:

1. **Product canon** определяет, как бот должен работать в целевой архитектуре.
2. **Target design** объясняет будущую реализацию product canon.
3. **Current runtime** описывает только то, что код делает сейчас; старое ограничение
   runtime не отменяет более новое согласованное target-решение.
4. **Evidence** доказывает результат конкретного checkpoint, но не выдаёт authority.
5. **Archive** хранит происхождение решений и не является текущим планом работ.

Если два active-документа действительно противоречат друг другу, работа останавливается
до решения владельца/Архитектора. Старый archive-текст не используется как действующий
закон.

## Product canon и target design

| Документ | Роль |
|---|---|
| [STRANGLER_ROADMAP.md](STRANGLER_ROADMAP.md) | единственный актуальный статус A1–A9 |
| [MARKETING_QUESTION_FOUNDATION.md](MARKETING_QUESTION_FOUNDATION.md) | продуктовая карта поведения для владельца |
| [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md) | общее архитектурное направление |
| [MARKETING_SCENARIO_ARCHITECTURE.md](MARKETING_SCENARIO_ARCHITECTURE.md) | target marketing facts, усилители, CTA и manual contact |
| [MARKETING_QUESTION_TECH.md](MARKETING_QUESTION_TECH.md) | технические точки интеграции маркетинговой карты |
| [PRICE_SERVICE_ARCHITECTURE.md](PRICE_SERVICE_ARCHITECTURE.md) | единый target-канон услуг, применимости, брендов, стратегии и цен |
| [PATIENT_SCOPE_DESIGN_A9.md](PATIENT_SCOPE_DESIGN_A9.md) | original frozen-linked A9 semantic design |
| [PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md](PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md) | текущий A9 native extraction design |
| [PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md](PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md) | frozen A9 raw/parser/prompt contract |

## Current runtime и эксплуатация

| Документ | Роль |
|---|---|
| [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) | фактический runtime |
| [FLAGS_AND_STATUS.md](FLAGS_AND_STATUS.md) | флаги и канонный набор прогонов |
| [ROUTING_MAP.md](ROUTING_MAP.md) | текущий порядок маршрутов |
| [PRICEBOOK_V2.md](PRICEBOOK_V2.md) | текущая demo Pricebook schema/runtime |
| [MARKETING_EDITING_GUIDE.md](MARKETING_EDITING_GUIDE.md) | текущие demo marketing data/config |
| [MULTICLIENT.md](MULTICLIENT.md) | client packs и sessions |
| [WIDGET_ANSWER_FORMAT.md](WIDGET_ANSWER_FORMAT.md) | текущий формат виджета |
| [DASHBOARD.md](DASHBOARD.md) | observability/admin dashboard |
| [TECH_DEBT.md](TECH_DEBT.md) | открытый технический долг |

## Evidence — не читать без конкретной проверки

| Папка/документ | Что доказывает |
|---|---|
| [evidence/a_series/](evidence/a_series/) | завершённые A3/A6/A7 shadow-аудиты и proof |
| [PATIENT_SCOPE_SHADOW_AUDIT_A9.md](evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md) | первый A9 raw принят по integrity, качество red, authority forbidden |

Evidence не меняется ради нового красивого результата. Первый A9 raw отдельно остаётся
immutable и не перезапускается без разрешения владельца.

## Archive — не текущий канон

| Документ | Почему сохранён |
|---|---|
| [FULLCONTEXT_ROADMAP.md](archive/FULLCONTEXT_ROADMAP.md) | накопительный исторический roadmap, заменён A-series roadmap |
| [ARCH_RECON_REPORT.md](archive/ARCH_RECON_REPORT.md) | разведка, на которой строился target design |

Удалённые разведочные отчёты остаются в Git history и не используются для реализации.

## Постоянные правила

- Код и current-runtime docs синхронизируются в одном checkpoint.
- RAG/search не описывается как действующий content path после Stage 3.4.
- Цены, бренды, порядок и UI-контракты детерминированы; LLM не изобретает их.
- Утверждения клиники, числа и сила формулировок не смягчаются и не усиливаются.
- `clients/demo/` — текущий продуктовый pack; другие packs меняются только по отдельной задаче.
