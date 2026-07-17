# TASK — Documentation Canon Cleanup, Phase 1

**Ветка:** `codex/stage-a`

**Baseline:** `853788a docs: define marketing scenario architecture`

**Режим:** documentation-only. Код, tests, runtime, client data и A9 raw не меняются.

## Контекст baseline

После baseline остался известный незакоммиченный WIP предыдущего product-gap review:

- `TASK.md`;
- `docs/README.md`;
- `docs/STRANGLER_ROADMAP.md`;
- новый `docs/PRODUCT_GAP_REVIEW.md`.

Этот WIP принадлежит текущему агенту и в данном checkpoint намеренно поглощается:
`PRODUCT_GAP_REVIEW.md` не становится постоянным документом, а README/roadmap
переписываются под новый канон. Другого содержательного pre-existing diff нет.

## Цель

Навести основной порядок в документации без потери необходимых рабочих контрактов:

1. владелец продукта регулярно читает только roadmap и маркетинговый фундамент;
2. current runtime, target design, evidence и archive явно разделены;
3. исторические документы не лежат среди активных;
4. очевидно отменённые разведки удалены из текущего дерева и остаются в Git history;
5. A9 в корне сокращён с четырёх документов до трёх активных; original design временно
   сохраняет старый путь из-за frozen `evidence_refs` и нормативных session laws;
6. первый A9 raw и доказательства его результата не меняются;
7. известные current-vs-target расхождения явно помечены и не выглядят одновременно действующими законами.

## Канон после cleanup

### Владелец продукта

- `docs/STRANGLER_ROADMAP.md` — прогресс A1–A9 и следующий checkpoint;
- `docs/MARKETING_QUESTION_FOUNDATION.md` — маркетинговое поведение бота.

### Активные архитектурные/операционные документы для агентов

- `docs/ARCH_TARGET_DESIGN.md`;
- `docs/CURRENT_ARCHITECTURE.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md`;
- `docs/MARKETING_QUESTION_TECH.md`;
- `docs/SERVICE_SELECTION_CONTEXTS.md`;
- `drafts/PRICE_RESPONSE_RULES_DRAFT.md`;
- `docs/PRICEBOOK_V2.md` — только current runtime schema;
- `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`;
- `docs/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md`;
- `docs/PATIENT_SCOPE_DESIGN_A9.md` — сохраняется по старому пути до отдельной миграции
  frozen matrix refs;
- эксплуатационные документы, перечисленные в README.

Сведение marketing-tech и price/service документов в меньшее число канонов — отдельная
будущая фаза после закрытия текущих product decisions; этот checkpoint не должен
механически склеить документы и потерять детали.

## Удалить из текущего дерева

- `docs/TRUST_INTENT_PHASE1_REPORT.md` — отменённая разведка отдельного thematic route;
- `docs/DOCS_AUDIT.md` — исторический снимок 10 июля, не действующий канон;
- незакоммиченный `docs/PRODUCT_GAP_REVIEW.md` — временный review, решения ещё не приняты.

Tracked-файлы остаются доступны в Git history. `PRODUCT_GAP_REVIEW.md` не имеет Git
history, поэтому перед удалением три непринятых вопроса из него кратко переносятся в
`STRANGLER_ROADMAP.md`: mixed first-concern allocation, UI capacity и CTA semantic set.
Полезные текущие правила не должны ссылаться на удалённые tracked-файлы.

## Переместить в archive

- `docs/ARCH_RECON_REPORT.md` → `docs/archive/ARCH_RECON_REPORT.md`;
- `docs/FULLCONTEXT_ROADMAP.md` → `docs/archive/FULLCONTEXT_ROADMAP.md`;
Archive сохраняет происхождение решений, но не является текущим каноном.

`docs/PATIENT_SCOPE_DESIGN_A9.md` в Phase 1 не перемещается: frozen matrices содержат
защищённые ссылки на его текущие строки, а active native design использует его session laws.

## Переместить в evidence

### Завершённые A-series checkpoints

- `TURN_FRAME_SHADOW_AUDIT_A3.md`;
- `TOPIC_SHADOW_AUDIT_A6.md`;
- `TOPIC_SHADOW_REAUDIT_A7.md`;
- `FIELD_LEVEL_PLANNER_OUTCOME_A7.md`;
- `A7_REGRESSION_LIVE_PROOF.md`;

Target: `docs/evidence/a_series/`.

### Открытый A9

- `PATIENT_SCOPE_SHADOW_AUDIT_A9.md` →
  `docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`.

Evidence не переписывается по смыслу. Допустимы только относительные ссылки после move.
Raw hash, denominators, claims и quality verdict должны остаться byte-for-byte по тексту,
кроме путей ссылок, если без этого они перестают разрешаться.

## Явно устранить конфликты статусов

1. `README.md` задаёт precedence:
   - owner canon;
   - target contracts;
   - current runtime references;
   - evidence;
   - archive.
2. Current runtime документы про promo (`MARKETING_EDITING_GUIDE.md`, `PRICEBOOK_V2.md`)
   прямо предупреждают, что current pain/safety blocking не является новой target policy.
3. Target marketing policy прямо имеет приоритет для будущей реализации:
   - текущая личная боль/осложнение/жалоба → phone-only hard-stop;
   - общий страх будущего лечения/противопоказания → source-grounded ответ и применимый
     marketing layer по target rules.
4. `.cursor/rules/00-guardrails.mdc` различает строгий current-personal-pain hard-stop и
   общую медицинскую/противопоказательную тему, чтобы не противоречить product canon.
5. Конфликт UI capacity не решать за владельца: current widget limit и target три кнопки
   масштаба должны быть явно помечены как открытое product/UI решение.

## Allowlist

- `TASK.md`;
- `.cursor/rules/00-guardrails.mdc`;
- `docs/README.md`;
- `docs/STRANGLER_ROADMAP.md`;
- `docs/ARCH_TARGET_DESIGN.md`;
- `docs/MARKETING_QUESTION_FOUNDATION.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md`;
- `docs/MARKETING_EDITING_GUIDE.md`;
- `docs/PRICEBOOK_V2.md`;
- `docs/FLAGS_AND_STATUS.md`;
- `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`;
- `docs/TRUST_INTENT_PHASE1_REPORT.md` (delete);
- `docs/DOCS_AUDIT.md` (delete);
- `docs/PRODUCT_GAP_REVIEW.md` (delete);
- все source/target paths из разделов archive/evidence выше.

Только правки ссылок после move разрешены внутри перемещаемых archive/evidence файлов.

## Protected / forbidden

- весь код, tests, evals, fixtures, prompts, configs и client data;
- `eval_patient_scope_a9_last.txt` и любой другой raw;
- A9 harness/matrix/evidence claims;
- содержательные правила active patient-scope design/raw contract;
- live/LLM;
- authority;
- merge и push в `main`.

## Verification

1. Governance checker `✅` до move/delete.
2. После cleanup нет содержательных изменений вне allowlist.
3. Все локальные Markdown links разрешаются после перемещений.
4. Поиск старых root-paths не находит битых ссылок.
5. A9 audit сохраняет raw SHA256, exact=0/quality-red и authority forbidden.
6. Три active A9 design/raw documents сохраняют старые frozen refs, shadow-only, raw
   immutable и authority forbidden.
7. `git diff --check` проходит.
8. Никакие tests/live не запускаются: исполняемое поведение не меняется.
9. Финальный независимый checker даёт `✅` до commit/push.

## Definition of Done

- README начинается с двух документов владельца;
- root `docs/` больше не смешивает active, evidence и отменённые разведки;
- A9 имеет три активных root-документа; audit вынесен в evidence, а original design
  остаётся на месте до отдельной безопасной миграции frozen refs;
- удалены три ненужных текущих файла;
- current-vs-target promo/medzone расхождения объяснены precedence, а не замаскированы;
- UI capacity честно отмечен как открытый вопрос;
- commit/push только в `origin/codex/stage-a` после checker `✅`;
- рабочее дерево чистое.
