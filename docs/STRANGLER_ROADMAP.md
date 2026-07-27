# Архитектурная миграция A1–A9 — roadmap для владельца продукта

Этот документ показывает, как мы строим новое внутреннее понимание вопроса пациента в локальном demo. Production-клиентов нет; widget compatibility и сохранность legacy-ответов **не требуются**. Legacy и shadow сейчас — **измерительный контур**, не целевой product path. Целевая архитектура — **FINAL_FULLCONTEXT_ONLY** (см. ниже и [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md)): сразу чистая cached FullContext-цепочка для базы порядка 150–200 небольших MD, без временных response bridges «на потом удалим».

## Как читать чекбоксы

- [x] checkpoint действительно выполнен, проверен checker’ом и зафиксирован в git;
- [ ] checkpoint ещё не завершён;
- завершённый аудит может иметь `[x]`, даже если он честно показал плохой результат;
- `[x]` не означает, что новая функция уже влияет на ответы пациенту;
- отдельно смотрите строку **Authority**: она показывает, разрешено ли новому механизму управлять ответом.

Короткий словарь:

- **Shadow** — новый механизм работает параллельно для измерения, но не управляет ответом.
- **Authority** — право реально влиять на маршрут, факты, цену, текст или UI ответа.
- **Legacy path** — текущий продуктовый путь в локальном demo (измерительный контур до замены на target FullContext chain; не целевой product path и не объект сохранения ответов).
- **TurnFrame** — структурированная «карточка понимания» одного сообщения: тема, намерение, аспекты, ситуация пациента и другие поля.

## Owner law: FINAL_FULLCONTEXT_ONLY

**Статус:** явное architecture decision владельца (2026), зафиксировано docs-only checkpoint.
Канон формулировок — [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md) § «Owner law: FINAL_FULLCONTEXT_ONLY».

Кратко для roadmap:

- **Финальный Composer** получает **весь валидированный MD-корпус** через **cached FullContext**.
- **Scoped turn-specific primary evidence** (S35→S36) **дополняет** FullContext для exact facts и
  verifier — **не заменяет** корпус и **не скрывает** остальную MD-базу от Composer.
- **Structured selectors** разрешены для услуг, цен/этапов оплаты, врачей, marketing/CTA, safety
  policy, provenance/verification.
- **`medical_handoff`** — режим безопасности, не отдельный MD-маршрут; модель видит всю MD-базу.
- **`used_doc_ids` / source refs** — аудит и grounding, не pre-RAG router.
- **Запрещено по умолчанию:** per-MD routing, thematic document routers, vector/chunk retrieval,
  временные product paths, legacy fallback ради текущих ответов, interim shadow bridges без
  постоянной роли, дублирование FullContext routing-таблицами.
- **Исключение** — только явное разрешение владельца + постоянная роль + доказательство, что
  cached FullContext недостаточен.
- **Corpus overflow** → СТОП на architecture decision; **нельзя** молча добавлять RAG/retriever.
- **Eval harness / offline checker** — OK как измерение, если не product response path.

- [x] **Owner decision — FINAL_FULLCONTEXT_ONLY** — docs-only architecture law в
  `ARCH_TARGET_DESIGN.md`, `STRANGLER_ROADMAP.md`, `REVIEW_CHECKLIST.md`, `.cursor/rules/00-guardrails.mdc`.
  Противоречивые формулировки evidence assembly и S35/S36 согласованы: scoped primary evidence
  **дополняет** FullContext, не заменяет. Код, TASK, matrix/harness и product authority не менялись.
- [x] **Owner clarification — Medical question semantics** — docs-only уточнение в каноне:
  urgent hard-stop раньше обычного ответа; `medical_handoff` = safety mode с grounded content
  из MD (не отказ); только `uncertain` → terminal defer; Verifier checklist и организация
  противопоказаний по service families (content, не routing). S42/S43/matrix/harness не менялись.

---

## Текущий статус

| Вопрос | Ответ |
|---|---|
| Текущий этап | **A9 — Native Patient-scope Extraction** |
| Последний завершённый checkpoint | **S57 — compact end-to-end quality eval offline prep (NO LIVE)** |
| Последний завершённый checkpoint | **S58 — one controlled S57 end-to-end live run (AUTOMATED_FAIL 7/9)** |
| Последний завершённый checkpoint | **S61 — target FullContext runtime path (dev flag OFF)** |
| Последний завершённый checkpoint | **S61 test-hardening (pre-live, OFFLINE)** |
| Последний завершённый checkpoint | **S63 — delta target FullContext HTTP live runtime test (AUTOMATED_PASS, manual PASS)** |
| Последний завершённый checkpoint | **S65 — default FullContext product authority (offline)** |
| Текущий S-series checkpoint | **S70 — FullContext migration closeout (completed)** |
| Cleanup-series | **C1 — dead legacy residue cleanup (completed)** → `docs/C1_LEGACY_RESIDUE_REPORT.md` |
| C2 plan | **`docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md`** — plan only; owner decision before code |
| S-series status | **COMPLETE** (`S_SERIES_COMPLETE`) — FullContext path; scope/price product wiring pending AC3 |
| Следующий gate | **AC3 — atomic runtime scope-aware price flow** (`TASK.md`) |
| W1b status | **PARKED** @ `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` |
| Предыдущий checkpoint | **AC2 — offline scope-aware selection** (`5a3a2f8`) |
| Ближайший рабочий focus | **AC3 governance → PRE-CODE → runtime wiring + ResponseStage + scope buttons** |
| Что сейчас отвечает в локальном demo | **Target FullContext path only** — unconditional; legacy modules deleted |
| FullContext authority | **Sole product authority (S69); S65/S66/S67 precursors** |
| Patient-scope authority | **Forbidden** |
| Новый live/LLM run | Только после отдельного разрешения владельца |

## Быстрый список A1–A9

- [x] **A1 — минимальный TurnFrame**
- [x] **A2 — TurnFrame в shadow-наблюдении**
- [x] **A3 — первый аудит TurnFrame**
- [x] **A4 — темы из конфигурации клиента**
- [x] **A5 — native topic в shadow**
- [x] **A6 — измерение качества topic** — checkpoint завершён, sample показал техническую неполноту
- [x] **A7 — независимая валидация полей и повторный topic-аудит**
- [x] **A8 — service/follow-up/clarification в shadow**
- [ ] **A9 — composable patient scope** — инфраструктура построена, native positive quality ещё не готова

Отдельно начата S-series для materialization target schema без подключения к ответам:

- [x] **S1 — schema models/validators** — изолированный offline contract и
  детерминированные unit-тесты независимо проверены. Runtime, client data, session и
  authority не подключены.
- [x] **S2 — offline target-pack loader** — explicit-path loader и synthetic IO/error
  tests независимо проверены. `clients/**`, current loaders и product path не
  подключены.
- [x] **S3 — external source-ref integrity** — pure in-memory проверка `kb:`/`doctor:`
  refs и synthetic tests независимо проверены. Source index builders и product path не
  подключены.
- [x] **S4 — offline KB source-index builder** — exact `kb:` refs строятся только из
  explicit target Markdown root; synthetic tests независимо проверены. `clients/**`,
  legacy loaders и product path не подключены.
- [x] **S5 — minimal doctor data contract** — только имя/ID, должность, стаж,
  service links и exact MD profile ref; synthetic tests независимо проверены. Doctor
  loader/index и product path не подключены.
- [x] **S6 — doctor cross-reference integrity** — pure проверка service/profile refs и
  сборка exact `doctor:<id>` refs независимо проверены. Demo data и product path не
  подключены.
- [x] **S7 — demo doctor template hardening** — approved service links/profile copy и
  overview очищены; real demo S4→S5→S6 acceptance и completion review прошли.
  Runtime code и target wiring не менялись.
- [x] **S8 — strict doctor catalog loader** — explicit JSON→S5 boundary реализован и
  независимо проверен; demo target catalog не создан, runtime/product path не
  подключены.
- [x] **S9 — demo target doctor catalog materialization** — final-wire JSON для шести
  demo-врачей создан, offline проходит S4/S5/S6/S8 и независимо проверен; product path
  не подключён.
- [x] **S10 — target service data context** — pure exact-service join для service,
  full offers и doctor contexts реализован на synthetic target models и независимо
  проверен; product path не подключён.
- [x] **S11 — demo target service catalog materialization** — final-wire S1 JSON для
  всех 21 demo-услуг создан в изолированном неполном target pack; real-data acceptance
  и независимый completion review пройдены. Offers, runtime и product authority не
  подключены.
- [x] **S12 — demo target price offers materialization** — для всех 21 услуг созданы
  31 final-wire offer, три brand records и шесть commercial facts; owner-approved
  units/labels, real S10 common context и независимый completion review пройдены.
  Strategy/marketing, runtime и authority не подключены.
- [x] **S13 — structured payment stages** — target contract расширен optional
  разбивкой оплаты; exact demo stages перенесены только в 12 top offers. Узкие tests и
  независимый completion review пройдены; runtime и authority не подключены.
- [x] **S14 — patient playbook target migration audit** — действующий current playbook
  инвентаризирован и разложен по target owners до создания clinic strategy. Completion
  review `✅`; current tests честно дали `15 passed, 2 failed`: extraction rule проигрывает
  one-tooth rule по specificity, а fallback test отключает только старую секцию, оставляя
  main rules активными. Target catalog: `7 passed`. Client data, code, runtime и authority
  не менялись.
- [x] **S15 — deterministic target strategy resolution** — baseline priorities и
  ordered first-match context overrides формализованы в pure offline resolver.
  Independent completion review `✅`: unit `80 passed`, S2/S10 neighbors `38 passed`,
  target data `15 passed`. Demo strategy data, current playbook, product wiring и
  authority не менялись.
- [x] **S16 — demo target clinic strategy materialization** — семь owner-approved
  situation priorities и шесть current `recommended=true` offer signals перенесены в
  offline target data; generic bone-deficit rule отложено без потери его current intent
  condition. Independent completion review `✅`: S16 data `6 passed`, contract/resolver
  `80 passed`, neighbors `38 passed`, existing target data `15 passed`; skip/xfail нет.
  Current playbook, product wiring, marketing и authority не менялись.
- [x] **S17 — demo target marketing/CTA migration audit** — current combined marketing,
  commercial facts, source refs и CTA owners инвентаризированы до target data. Audit
  не создаёт `target_response/marketing.yaml`, selector/session/runtime или authority.
  Independent completion review `✅`: audit `7 passed`, neighbors `112 passed`,
  skip/xfail нет.
- [x] **S18 — target service consultation value contract** — optional source value
  формализован в frontmatter того же service MD с exact `content_ref` cross-ref и
  universal once-per-document/session cadence law. Independent completion review `✅`:
  contract `36 passed`, neighbors `83 passed`; skip/xfail нет. Demo MD, session/runtime,
  composer и authority не подключены.
- [x] **S19 — demo implantation consultation values** — три owner-approved test values
  опубликованы только в frontmatter classic/one-stage/All-on-4; тела MD и FullContext
  сохранены. Independent completion review `✅`: real data `5 passed`, neighbors
  `40 passed`; skip/xfail нет. Session/runtime, composer и authority не подключены.
- [x] **S20 — demo target marketing policy materialization** — exact limits, initial
  commercial block, пять source-backed scenario pools и semantic CTA map созданы в
  offline target pack; fact/KB/doctor/CTA refs и полный real bundle независимо
  проверены. Completion review `✅`: policy `24 passed`, frozen neighbors `148 passed`,
  skip/xfail нет. Selector, session/runtime, ответы и authority не подключены.
- [x] **S21 — deterministic offline marketing selection** — pure algorithm выбирает
  только eligible source refs по exact service/context/date/shown snapshots, объединяет
  два scenarios round-robin и соблюдает limits/CTA без скрытого context fallback.
  Completion review `✅`: selector/real data `44 passed`, frozen neighbors `73 passed`,
  skip/xfail нет. Session/runtime, ответы и authority не подключены.
- [x] **S22 — unified offline response evidence package** — pure one-service builder
  объединяет S10 service/offers/doctors, S21 marketing selection и optional S18
  consultation close с exact document snapshot и остатком обоих 3/2 slots. Independent
  completion review `✅`: target `34 passed`, S10/S18/S21 neighbors `93 passed`,
  skip/xfail нет. Offer/doctor selection, session/runtime, ответы и authority не
  подключены.
- [x] **S23 — one-service active offer projection** — pure selector фильтрует active
  service/offers/effective options из S10 context и делегирует порядок/limit/explicit pin
  существующему S15 без изменения денег и payment stages. Independent completion review
  `✅`: target `30 passed`, S10/S15/S22 neighbors `63 passed`, skip/xfail нет.
  Service/brand selection, session/runtime, ответы и authority не подключены.
- [x] **S24 — exact brand offer projection** — pure wrapper фильтрует exact brand ID
  внутри уже выбранной service и делегирует active/option/order/limit существующему
  S23/S15. Independent completion review `✅`: target `25 passed`, required neighbors
  `65 passed`, skip/xfail нет. Brand recognition, service selection, session/runtime,
  ответы и authority не подключены.
- [x] **S25 — deterministic target brand term resolution** — pure dictionary lookup
  разрешает один уже выделенный brand term по exact ID/canonical/alias после
  `strip().casefold()` и fail-closed обрабатывает cross-brand collision. Independent
  completion review `✅`: target `51 passed`, required neighbors `122 passed`, skip/xfail
  нет. Full-message recognition, runtime, ответы и authority не подключены.
- [x] **S26 — deterministic active service term resolution** — последний минимальный
  lookup разрешает один already-extracted term в exact active service ID по
  ID/name/authored alias без fuzzy, patient-scope selection или diagnosis. Independent
  completion review `✅`: target `51 passed`, required neighbors `185 passed`, skip/xfail
  нет. Следующий focus — vertical offline end-to-end assembly, не новый lookup layer.
- [x] **S27 — first vertical offline response materials assembly** — один pure facade
  над S26/S25→S22→S23/S24 превращает exact service/optional brand terms в projected
  offers, linked doctors, marketing и consultation materials, не раскрывая unprojected
  offers. Governance `f98b8df`; independent completion review `✅`: target `18 passed`,
  required neighbors `191 passed`, skip/xfail нет. Product path не подключён; следующий
  focus — minimal downstream materialization plan над proven materials; канонический
  ResponsePolicy/ResponseSpec остаётся отдельной upstream boundary до evidence assembly.
- [x] **S28 — minimal target response materialization plan** — identity-only декларация
  над S27 materials сохраняет explicit content/price/doctors components, exact selected
  additions и fail-closed unfulfilled signal без fallback/reselection. Governance
  `cc692ae`; independent completion review `✅`: target `26 passed`, required neighbors
  `94 passed`, skip/xfail нет. MD/follow-up materialization и product wiring не входят в
  checkpoint. Канонический upstream ResponsePolicy/ResponseSpec до evidence assembly
  остаётся отдельной будущей границей и не переопределяется S28.
- [x] **S29 — selected-source follow-up materialization** — отдельные content candidates
  строятся только из selected MD `suggest_h3`, price candidates — только из selected
  offers, с сохранением порядка и provenance. Governance `b91ff4e`; independent
  completion review `✅`: target `37 passed`, четыре S27/S28 neighbors `44 passed`, всего
  `81 passed`, skip/xfail нет. UI merge, session suppression и product wiring не входят
  в checkpoint; следующий focus — минимальная UI-source policy над proven tuples.
- [x] **S30 — minimal follow-up source policy** — caller явно задаёт `content`, `price`
  или отсутствие ссылок; policy сохраняет exact tuple выбранного типа без inference,
  merge/ranking/truncation/fallback. Governance `04a9f8b`; independent completion review
  `✅`: target `23 passed`, S29 neighbors `37 passed`, всего `60 passed`, skip/xfail нет.
  Следующий focus — end-to-end offline response assembly над proven components.
- [x] **S31 — integrated offline response package** — один прозрачный offline-вызов
  возвращает exact S27→S28→S29→S30 results без новых решений или error wrapping.
  Governance `729fdf9`; independent completion review `✅`: target `11 passed`, восемь
  S27–S30 neighbor files `104 passed`, всего `115 passed`, skip/xfail нет. Это не
  финальный bot path; следующий focus — минимальный канонический upstream ResponseSpec.
- [x] **S32 — canonical target ResponseSpec contract** — strict immutable декларация
  режима, scope, required facts/components и permissions с обязательной семантикой
  medical no-diagnosis boundary. Governance `77547d8`, protected-test correction
  `ee930f1`; independent completion review `✅`: target `23 passed`, шесть S28/S30/S31
  neighbor files `60 passed`, всего `83 passed`, skip/xfail нет. TurnFrame/A9 authority
  и product path не подключены; следующий focus — deterministic offline ResponsePolicy.
- [x] **S33 — minimal deterministic ResponsePolicy builder** — explicit non-A9 request
  превращается в S32 spec; builder сам выбирает только follow-up family из exact component
  focus без repair/fallback. Governance `a2caf08`; independent completion review `✅`:
  target `22 passed`, S32 + S30/S31 neighbors `57 passed`, всего `79 passed`, skip/xfail
  нет. Следующий focus — прямая S33→S31 offline-интеграция, не новый inference layer.
- [x] **S34 — spec-bound offline package integration** — composition-поля S33/S32
  permission-gated связаны с S31; raw materials остаются internal candidates, а
  consumable view закрыт plan/selected follow-ups/selected CTA. Governance `89f288c`;
  independent completion review `✅`: target/demo `21 passed`, S33/S32/S31 neighbors
  `56 passed`, всего `77 passed`, skip/xfail нет. Topic scope и required-fact coverage
  ещё не доказаны, поэтому Composer/product wiring запрещены до следующего checkpoint.
- [x] **S35 — scoped response evidence** — S34 consumable identities превращаются в
  закрытый **scoped primary evidence** view без raw materials/candidates; topic берётся только
  из уже выбранных service/doctor/KB MD (без document retrieval/ranking). View **дополняет**
  cached FullContext под **FINAL_FULLCONTEXT_ONLY**, не заменяет его как knowledge input Composer.
  Required facts покрываются только реально выбранными commercial facts. Canonical S28 plan и
  S30 follow-up selection пересобираются и сравниваются exact, поэтому candidate injection
  закрыт. Governance `84182a9`; independent completion review `✅`: target/demo `15 passed`,
  S34/S31 neighbors `32 passed`, всего `47 passed`, skip/xfail нет. Live/LLM, A9,
  Composer/Verifier и product authority не подключены.
- [x] **S36 — target Composer request materialization** — exact S35 scope records
  разворачиваются один-к-одному в immutable model-ready blocks **поверх** cached FullContext:
  выбранное MD body/section, offers с payment stages без candidate refs, согласованные doctor
  fields/profile section, commercial fact и consultation value. S36 materialize strict blocks
  для verifier/exact-fact layer; **не** ищет и **не** подменяет FullContext cache. Provider/model
  call отсутствует. Governance `b0fe669`; independent completion review `✅`: target/demo
  `25 passed`, S35/S34 neighbors `36 passed`, всего `61 passed`, skip/xfail нет. Composer
  execution/live proof, Verifier, A9 и product authority не подключены.
- [x] **S37 — minimal target Composer executor** — exact S36 request проходит closed-shape
  validation, детерминированно превращается в stable policy + directives + primary evidence
  и передаётся одному injected backend ровно один раз. Follow-ups/CTA остаются sidecars и
  не попадают в invocation; retry/repair/fallback отсутствуют; результат всегда явно
  `unverified`. Governance `c4c9502`; independent completion review `✅`: target/demo
  `22 passed`, S36/S35 neighbors `40 passed`, всего `62 passed`, skip/xfail нет.
  Provider/live quality proof, Verifier, A9, runtime/UI и product authority не подключены.
- [x] **S38 — target runtime Verifier** — exact adjacent S36/S37 response сначала проходит
  fail-closed digit-number provenance и verbatim selected strict facts, затем ровно одну
  provider-neutral semantic assessment для grounding (включая числа словами), topic scope,
  medical boundary и всех selected facts. Text не repair/rewrite: mismatch блокирует,
  success сохраняет exact text/spec/follow-ups/CTA в отдельном verified contract.
  Governance `1d00804`; independent completion review `✅`: target/demo `30 passed`,
  S37/S36 neighbors `47 passed`, всего `77 passed`, skip/xfail нет. Recording backends
  доказывают только offline orchestration; provider/live quality proof, A9, runtime/UI и
  product authority не подключены.
- [x] **S39 — offline verified response pipeline** — thin straight-line orchestration
  вызывает public S36→S37→S38 по одному разу, передаёт exact request/unverified identities и
  напрямую возвращает exact verified response. Existing typed failures short-circuit без
  catch/rename/retry/fallback; follow-ups/CTA сохраняются sidecars. Governance `5a7e927`;
  independent completion review `✅`: target/demo `11 passed`, S38/S37/S36 neighbors
  `77 passed`, всего `88 passed`, skip/xfail нет. Это structural offline vertical от exact
  S34 package и точка handoff основной реализации в Cursor; TurnFrame/A9 authority,
  provider/live quality, runtime/UI/session и product authority остаются отдельными gates.

- [x] **S40 — policy-bound offline verified response pipeline** — thin straight-line
  orchestration вызывает public S33→S34→S39 по одному разу, передаёт exact policy request,
  assembly inputs и pipeline backends/identities и напрямую возвращает exact verified
  response. Existing typed failures short-circuit без catch/rename/retry/fallback.
  Governance `5eea9ed`; independent completion review `✅`: target/demo `14 passed`, S39/S34/S33
  neighbors `54 passed`, всего `68 passed`, skip/xfail нет. Это structural offline entry
  point от explicit policy request; TurnFrame/A9 authority, provider/live quality,
  runtime/UI/session и product authority остаются отдельными gates.

- [x] **S41 — TurnFrame-bound offline response dispatch** — deterministic dispatch maps
  `TurnFrame` + explicit envelope to `materialize | terminal` without reading
  `patient_scope`; materialize calls public S40 once. Confident `medical_handoff` may
  materialize when `service_id` usable; otherwise terminal `medical_handoff_nonmaterializable`
  (offline gap до FullContext path — см. ARCH § Medical question semantics). Clarify/defer —
  terminal modes. Owner mapping: `payment → price`, `stages → content` always; valid confident
  topic must match envelope scope. Governance `65c87bd`; independent completion review `✅`:
  S41 target/demo `17 passed`, S40/S33 neighbors `36 passed`, всего `53 passed`, skip/xfail нет.
  Message→TurnFrame, runtime/UI/session, live/LLM and product authority remain separate gates.

- [x] **S42 — provider-neutral target medical boundary detector** — offline classifier
  executor with injected backend, three-way semantics (`none | medical_handoff | uncertain`),
  structured-output validation, canonical reason codes, and deterministic envelope enforcement.
  Low confidence/malformed/backend failure/ambiguity never become `none`; **only `uncertain`**
  maps to terminal defer enforcement. Confident `medical_handoff` sets safety mode (content from
  clinic MD allowed under ARCH § Medical question semantics); does not implement answer content.
  Recognition quality unproven until separately permitted live eval. Governance `4bd3411`;
  independent completion review `✅`: S42 target/enforcement `19 passed`, S41 dispatch neighbor
  `12 passed`, всего `31 passed`, skip/xfail нет. Runtime wiring, live adapters, dispatch-only
  shadow hook, and product authority remain separate gates.

- [x] **S43 — medical boundary live eval preparation** — separate frozen matrix (26 cases,
  8 kinds), offline harness with immutable raw capture, isolated eval backend adapter,
  separate quality/transport buckets, and proposed acceptance thresholds pending owner
  approval. **Scope:** S42 boundary classification only — not medical answer content, Verifier,
  or FullContext integration. No A9 reuse, no live/LLM, no runtime. Governance `1262fb1`;
  independent completion review `✅`: matrix/harness `18 passed`, S42 neighbor `20 passed`, всего
  `38 passed`, skip/xfail нет. First live run requires explicit owner permission and
  threshold approval.
- [x] **S43 correction — pre-live freeze & harness hardening** — owner-approved confidence
  floors (`none` 0.80, `medical_handoff` 0.70) passed explicitly to S42 executor; acceptance
  thresholds frozen; `excessive_false_medical_handoff_rate` denominator fixed (expected=none
  only); `mb_noise_02` → `имплант цена?`; artifact absent-before-run + exclusive-create guards;
  deterministic threshold PASS/FAIL evaluator. No live/LLM, no runtime. Governance `da8b835`;
  completion after independent checker `✅`. Matrix hash updated; tests `54 passed`.
  First live run still requires explicit delegate injection; existing live artifacts must not
  be overwritten.
- [x] **S43 first live eval audit capture** — owner-authorized first live run captured
  byte-identical: raw SHA-256 `3D32B768…`, result SHA-256 `F6B33E447…`, matrix blob
  `7218e044…`, 26/26 calls, exit 0, verdict **PASS**, exact **25/26**, sole non-exact
  `mb_border_01`. Eval-only `--live` wiring committed; audit manifest +
  `medical_boundary_eval_live_audit_manifest.json`; offline CLI tests. **DO_NOT_RERUN**.
  Governance `fe5d6ed`. A9/runtime/UI/session/product authority untouched.
- [x] **S44 — deterministic cached FullContext Composer input** — bootstrap builder
  `build_target_cached_full_context(md_root)` создаёт immutable `TargetCachedFullContext`
  (все 54 demo `.md` включая doctors, stable order, explicit boundaries, SHA-256); тот же
  prebuilt объект inject/reuse через S37/S39/S40/S41 без per-turn rebuild. Composer invocation
  разделяет `cached_full_context` и scoped `primary_evidence_json`. Provider prompt caching —
  **не** реализован (отдельный live gate). **S34/S41 service_id gate не менялся.** Следующий
  offline focus — service-optional FullContext materialization. Governance `3ce09f8`. No live.
- [x] **S45 — FullContext-grounded service-optional verified response** — dual authority:
  cached FullContext для общих MD/medical content; structured primary evidence для strict
  commercial facts. `service_id=None` + content-only materialize через dispatch envelope
  sanitization и minimal bound package; Composer policy и Verifier contract честно разделяют
  `general_grounding_ok` / `strict_commercial_grounding_ok`; Verifier получает тот же prebuilt
  `TargetCachedFullContext` без rebuild. Missing-base и pain/diabetes offline acceptance без
  live. Governance `e7c312c`. No live.
- [x] **S46 — boundary-enforced FullContext verified response** — thin orchestrator
  `run_target_offline_boundary_enforced_fullcontext_response`: готовый `TurnFrame` +
  `TargetMedicalBoundaryResult` → S42 enforce×1 → uncertain terminal | S41/S45×1 → verified |
  terminal. Без detector/live/новых слоёв. Governance `9ad4614`. No live.
- [x] **S47 — FullContext response quality eval preparation** — frozen 20-case matrix +
  provider-neutral offline harness (`run_fullcontext_response_eval.py`) для будущего одного
  permitted live прогона S46→Composer→Verifier; semantic rubric без verbatim prose;
  `--dry-run` validate; default/`--live` → `LIVE_NOT_CONFIGURED`. Governance `5c96d54`. No live.
- [x] **S47 correction — manual review verdict semantics** — automated vs final verdict split;
  mandatory append-only manual review artifact; global + case-specific rubrics; proposed final
  gates + model recommendation (`pending_owner_approval`); matrix hash update before first live.
  Governance `643be1c`. No live.
- [x] **S47 first permitted live eval** — owner-approved run; **AUTOMATED_FAIL** (5 semantic
  rejects); 76-call incident overrun; artifacts run-2 only. Governance `fd23040` incident capture.
  **Not S47 pass.** No re-run without new owner approval.
- [x] **S48a — harness measurement hardening** — diagnostic literal hits vs semantic reject
  flags; candidate text preserved on verifier rejection; frozen S47 replay read-only. Governance
  `a796ce4`. **S48b blocked** until separate owner command.
- [x] **S48a-correction — measurement contract honesty** — remove always-green
  forbidden/dangerous gates; semantic assessment denominators; `NOT_EVALUATED` dangerous medical
  reporting. Governance `5f70039`. **S48b blocked**.
- [x] **S48b — FullContext medical response semantic hardening** — Composer/Verifier
  universal medical grounding, missing-base, CTA/consultation directives; offline contract
  tests only. Governance `6a377ad`. **No live** — model quality unproven until separate
  approved re-eval.
- [x] **S49 — FullContext response re-eval v2 offline prep** — matrix v2 (fc_boundary_02
  fixture scope), isolated v2 artifacts, attempt-marker pre-call block, S48a measurement
  reuse. Governance `d63d69e`. **No live** — awaits separate owner approval.
- [x] **S50 — live re-eval v2 incident audit capture** — 40-call incident (2+38),
  diagnostic-only run-2 artifacts, Verifier FN taxonomy, harness dirty patch archived.
  **AUTOMATED_FAIL**; rerun forbidden. Governance `ec829d1`.
- [x] **S50b — offline harness correction (Checkpoint B)** — narrow audit-proxy
  `captures` delegation; post-marker output preflight (`preflight_exclude_paths`).
  Harness reliability only; Verifier FN (`fc_missing_01`/`fc_medical_03`) still open.
  **NO LIVE**. Governance `85e64ce`.
- [x] **S51 — lightweight risk-based semantic Verifier** — replace active five-boolean
  `TargetSemanticVerification` with issue-based `TargetSemanticAssessment`; deterministic
  numeric/strict-fact layer unchanged; historical five-boolean readers for frozen S47/S50
  replay only. Offline contract/wiring tests only — **NO LIVE**. Governance `1231742`;
  implementation `a2596f9`.
- [x] **S51 correction — stale neighbor test + ARCH sync** — migrate
  `test_demo_target_turn_frame_bound_response.py` to issue-based contract; ARCH § S51
  documents active Verifier. **NO LIVE**. Governance `e847228`; correction `239a405`.
- [x] **S52 — Verifier-only replay prep** — isolated offline harness on 19 frozen S50 v2
  candidate texts; replay matrix metadata-only; frozen Composer injection + fake
  issue-based semantic backend; future-live artifact paths and gates pinned
  `pending_owner_approval`. **NO LIVE**. Governance `33b08fc`/`2ac1e72`.
- [x] **S53 — verifier-only live replay** — one owner-approved live run:
  `qwen3.7-plus`, 19 Verifier / 0 Composer calls; immutable artifacts +
  manual review. **AUTOMATED_FAIL** (decision_match 13/19; false blocks on
  fc_boundary_01–03; missed block fc_missing_01). Governance `2a9f3b1`.
- [x] **S54 — S53 post-live audit + verifier offline calibration** — frozen S53 artifacts
  byte-identical; canonical replay issue parser fix; honest causal taxonomy (v1 15/19, v2 17/19
  diagnostic recompute, frozen FAIL unchanged); replay matrix v2 (14 pass / 5 block); minimal
  semantic policy clarification; future v2 live paths wired `pending_owner_approval`. **NO LIVE**.
- [x] **S55 — verifier-only live replay v2** — one owner-approved live run on matrix v2:
  `qwen3.7-plus`, 19 Verifier / 0 Composer calls; immutable v2 artifacts + manual review.
  **AUTOMATED_FAIL** (decision_match 17/19; missed blocks fc_missing_01, fc_boundary_03).
  S53/S50 artifacts unchanged.
- [x] **S56 — topic-scoped consultation facts + missing-base Composer guard** — OFFLINE ONLY:
  optional `allowed_topics` on commercial facts; topic-scoped consultation selector for
  `service_id=None` FullContext path; PRIMARY_EVIDENCE wiring; minimal Composer rule 7 strengthen.
  Verifier unchanged. Targeted pytest 142 passed. **NO LIVE**.
- [x] **S57 — compact end-to-end quality eval offline prep** — OFFLINE ONLY:
  9-case matrix `s57_fullcontext_quality_eval_matrix` (frozen hash `89616cb…`);
  harness reuses S47 `run_case` + single cached FullContext; fail-closed live CLI;
  18 future LLM budget (9 Composer + 9 Verifier). Targeted pytest 47 passed.
  **NO LIVE / NO LLM** — real model quality not yet measured.
- [x] **S58 — one controlled S57 end-to-end live run** — OWNER APPROVED, **one attempt**:
  `qwen3.7-plus` Composer + Verifier, **18 calls**, retry 0. **AUTOMATED_FAIL** 7/9 materialized;
  blocks: `s57_missing_01` (external immune claim), `s57_medical_02` (lactation/hormones extension).
  Immutable S58 artifacts committed. **RERUN_BLOCKED** without new owner approval.
- [x] **S59 — final semantic Verifier medical policy simplification** — OFFLINE ONLY:
  lightweight blocking: diagnosis, personal conclusion, dangerous/absurd/contradicting claims only;
  plausible external medical detail → non-blocking `minor_external_detail`; strict clinic facts unchanged.
  **NO LIVE**.
- [x] **S61 — target FullContext runtime path (dev flag OFF by default)** — wire S39–S59 chain into `/ask`
  behind `TARGET_FULLCONTEXT_DEV=0`; flag ON = target-only (no legacy RAG, no fallback). Bootstrap +
  TurnFrame bridge + widget materializer + session bridge. **OFFLINE ONLY / NO LIVE in S61**.
- [x] **S61 correction** — target-only ingress precedence, effective CTA clamp (`client_cta_capability AND spec.allow_cta`), session frequency IDs,
  service-derived strategy context, HTTP `/ask`/`/ask/stream` integration tests. **OFFLINE ONLY**. COMPLETION checker ✅ on diff `8d7463f…7c5fb13`.
- [x] **S61 test-hardening (pre-live)** — stale CTA pipeline test, session/frequency, legacy-bypass coverage, HTTP follow-up + two-turn session. **OFFLINE ONLY**.
- [x] **S62 — one controlled target FullContext HTTP live runtime test** — OWNER APPROVED, **one attempt**:
  4 HTTP turns via Flask test client, `TARGET_FULLCONTEXT_DEV=1` in isolated process only;
  real providers (`qwen3.6-flash` ingress/planner, `qwen3.7-plus` boundary/composer/verifier);
  **18 actual LLM calls** (10 audited in target-runtime ledger; ingress/planner via separate transport frames).
  Frozen harness `AUTOMATED_PASS` **erroneous** (scorer/harness bug). **Official: S62_NOT_PASSED** — diagnostic evidence only.
  Post-live audit (`396a226`): stdout capture SHA-pinned, frozen artifacts immutable, `RERUN_BLOCKED`.
  Offline correction: session hydration for doctors/price/payment follow-ups, CTA widget mapping, harness gates/ledger accounting.
  **NO LIVE / NO RERUN**.
- [x] **S63 — delta target FullContext HTTP live runtime test** — OWNER APPROVED, **one attempt** (`520e34a`):
  3 HTTP turns, `TARGET_FULLCONTEXT_DEV=1`, real providers; **AUTOMATED_PASS**, **manual PASS**;
  3/3 `target_fullcontext_materialized`, legacy/RAG/chunk = 0, 14/15 provider calls, retry = 0,
  FullContext build = 1. Artifacts `evals/v5/artifacts/s63_*`. **RERUN_BLOCKED**.
- [x] **S64 — FullContext authority audit (read-only)** — code-traced audit of `/ask` + `/ask/stream`
  OFF/ON chains, pre-target short-circuits, legacy component matrix, blockers, S65 minimal plan,
  rollback semantics. Deliverable: `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md`. **NO product code / NO authority switch**.
- [x] **S65 — default FullContext product authority (offline)** — `TARGET_FULLCONTEXT_DEV` default ON;
  `=0` manual legacy kill-switch at process start; fail-closed target errors without in-turn legacy fallback;
  offline acceptance tests A–H (`tests/test_s65_authority_switch_offline.py`). **NO LIVE / legacy not deleted**.
- [x] **S66 — default authority live verification** — OWNER APPROVED, **one attempt** (`f8541eb` prep → `c23d00f` artifacts):
  PRE-CODE on `0d4d92a` = **❌**; implementation/live continued without retroactive PRE-CODE PASS (governance incident).
  1 HTTP turn without `TARGET_FULLCONTEXT_DEV` env; `authority_source=config_default`; route `target_fullcontext_materialized`;
  legacy=0; 5/5 provider calls. **AUTOMATED_FAIL** (harness `fullcontext_build_count=0` counter miss; composer 32334 tokens).
  Manual PASS does not upgrade official verdict. **Official: S66_NOT_PASSED**; product authority live verified separately.
  Process/measurement incident, not proven product failure. **RERUN_BLOCKED**. Audit: `docs/S66_GOVERNANCE_CORRECTION_AUDIT.md`.
- [x] **S67 — legacy answer path isolation** — default FullContext path no longer eagerly imports legacy
  answer-production stack (`ask_turn`, `chunk_responder`, `source_routing`, `composer_flow`). Legacy modules
  load lazily only behind manual kill-switch `TARGET_FULLCONTEXT_DEV=0` or `chunk`/`composer` dispatch.
  Target `service_reply` skips legacy answer-plan post-processing. Legacy files **not deleted**.
  Offline acceptance A–J (`tests/test_s67_legacy_isolation_offline.py`). **NO LIVE / NO A9**.
  Next separate milestone: read-only deletion inventory + mechanical removal (owner-approved).
- [x] **S68 — legacy deletion inventory (read-only)** — `docs/S68_LEGACY_DELETION_INVENTORY.md`: evidence-backed
  map of 7 legacy-only modules (~3.3k LOC), shared dependencies (`query_selector`, `dialog_focus`, `md_chunks`
  for lead_flow), single S69 deletion milestone with 8 ordered phases. **NO product code changes / NO LIVE**.
  S69 blocked until owner-approved TASK.
- [x] **S69 — legacy product answer path deletion** — removed kill-switch `TARGET_FULLCONTEXT_DEV`,
  deleted 7 legacy modules (~3.3k LOC), answer_packet/plan_apply stack, legacy-only tests.
  FullContext is the **only** product authority. Offline acceptance:
  `tests/test_s69_checkpoint_a_offline.py`, `tests/test_s69_legacy_deleted_offline.py`.
  **NO LIVE / NO A9**.
- [x] **S70 — FullContext migration closeout (read-only)** — `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md`:
  verdict `S_SERIES_COMPLETE`; single target FullContext product chain verified; provider prompt caching
  and token streaming classified as deferred; no must-fix blockers. **NO product code / NO LIVE**.
## Какой roadmap актуален

Этот файл — единственный актуальный roadmap **A-series**. Он описывает безопасную пошаговую замену внутреннего «мозга» понимания вопроса.

Старый накопительный [FULLCONTEXT_ROADMAP.md](archive/FULLCONTEXT_ROADMAP.md) перенесён в archive: он сохраняет историю composer/clarify/marketing работ, но больше не задаёт текущий порядок checkpoint-ов.

A1–A9 не были целиком придуманы заранее как неизменяемый master-plan. Макронаправление задано [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md), а следующий маленький checkpoint выбирается по результатам предыдущего аудита. Но он не придумывается во время написания кода: сначала появляется `TASK.md`, затем независимый checker-review, и только после этого начинается работа.

После A9 пока **не утверждены** ни A10, ни отдельный B-series roadmap. Следующий этап определяется только отдельным architecture/governance решением, а не из этого файла.

---

## Подробно по этапам

### A1 — минимальный TurnFrame

**Статус:** завершён (`631abc1` → `0761213`).

**Authority:** отсутствует; contract foundation only.

**Что сделали:** создали первую единую карточку понимания сообщения и адаптер от старой структуры.

**Как это сказалось на логике и маркетинге:** прямого изменения ответов не было. Появился фундамент, на котором можно постепенно объединять разрозненные классификаторы и в будущем лучше удерживать тему, намерение и контекст.

**Что увидел пациент:** ничего нового — бот продолжил отвечать старым путём.

### A2 — TurnFrame в shadow-наблюдении

**Статус:** завершён (`5e8b63c` → `3746d77`).

**Authority:** shadow-only.

**Что сделали:** TurnFrame начал строиться параллельно на реальных planner-turn и попадать в техническое наблюдение.

**Как это сказалось на логике и маркетинге:** мы получили возможность измерять новое понимание вопроса без риска для продаж, цен и текста ответа.

**Что увидел пациент:** ответ не изменился; shadow-frame не участвовал в решениях.

### A3 — первый аудит TurnFrame

**Статус:** завершён (`0486e87`, audit `0cb8ca3`).

**Authority:** forbidden.

**Что сделали:** проверили, насколько новая карточка действительно заполняется на живом pipeline. Planner-success coverage был `5/5`, но topic отсутствовал в `4/5` scoreable frames.

**Как это сказалось на логике и маркетинге:** вместо преждевременного включения мы обнаружили, что бот ещё не умеет надёжно записывать тему в новый contract. Это защитило ответы от ошибочного переключения.

**Что увидел пациент:** никаких изменений. Результат этапа — честная диагностика, а не новый ответ.

Подробнее: [TURN_FRAME_SHADOW_AUDIT_A3.md](evidence/a_series/TURN_FRAME_SHADOW_AUDIT_A3.md).

### A4 — темы из конфигурации клиента

**Статус:** завершён (`de66ebc` → `2757cae`).

**Authority:** contract/shadow preparation only.

**Что сделали:** разрешённые темы стали браться из настроек клиентского пакета, а не из жёстко зашитого общего списка.

**Как это сказалось на логике и маркетинге:** архитектура стала лучше готова к разным клиентам и направлениям: набор тем можно определять контентом клиента. Это уменьшает риск, что логика одного бизнеса случайно попадёт в другой.

**Что увидел пациент:** пока ничего нового — product routing не переключался на native topic.

### A5 — native topic в shadow

**Статус:** завершён (`cfc438b` → `8662300`).

**Authority:** shadow-only.

**Что сделали:** существующий planner начал возвращать и валидировать native topic в том же вызове. Product downstream продолжил использовать legacy `DecisionFrame.service_topic`.

**Как это сказалось на логике и маркетинге:** появилась более чистая тематическая ось для будущего выбора релевантного контента и защиты от тематических протечек. Сначала её только измеряли.

**Что увидел пациент:** прежние ответы и маршруты; native topic ещё ничего не выбирал.

### A6 — измерение качества topic

**Статус:** checkpoint завершён (`3f205f4` … audit `4a6c867`), но результат не был quality-green.

**Authority:** forbidden.

**Что сделали:** заранее заморозили 33 ожидания, создали harness и выполнили один контролируемый live run. Получили `26/33` scoreable cases; семь topic-наблюдений потерялись, потому что unrelated поле `aspects=[]` делало весь strict plan недоступным.

**Как это сказалось на логике и маркетинге:** обнаружили техническую причину потери полезного понимания. Качество topic в семи unavailable cases не было измерено, поэтому мы не объявляли, что модель поняла или не поняла их.

**Что увидел пациент:** product не переключался. Аудит измерял внутреннюю ось, а не качество текста ответа.

Подробнее: [TOPIC_SHADOW_AUDIT_A6.md](evidence/a_series/TOPIC_SHADOW_AUDIT_A6.md).

### A7 — field-level planner outcome и topic re-audit

**Статус:** завершён; final audit `596e809`.

**Authority:** shadow topic измерен, но product authority не передана.

**Что сделали:** один planner JSON разделили на две независимые ветви:

- partial shadow-frame сохраняет валидные поля, даже если соседнее поле ошибочно;
- strict legacy plan по-прежнему определяет текущий product path и его fail-open.

Повторный frozen audit получил topic scoreability `33/33` на этой выборке.

**Как это сказалось на логике и маркетинге:** ошибка одного технического поля больше не прячет остальные понятные сигналы. Это делает измерения честнее и подготавливает более устойчивую будущую логику ответов.

**Что увидел пациент:** прежний безопасный fallback и прежняя продуктовая логика. `33/33` — результат shadow measurement, а не доказательство точности всех ответов бота.

Подробнее: [FIELD_LEVEL_PLANNER_OUTCOME_A7.md](evidence/a_series/FIELD_LEVEL_PLANNER_OUTCOME_A7.md) и [TOPIC_SHADOW_REAUDIT_A7.md](evidence/a_series/TOPIC_SHADOW_REAUDIT_A7.md).

### A8 — service/follow-up/clarification в shadow

**Статус:** завершён (`3a3b445` → `38d29f3`).

**Authority:** shadow-only.

**Что сделали:** добавили независимую проверку service id, признака продолжения диалога и необходимости уточнения.

**Как это сказалось на логике и маркетинге:** стало проще видеть, какая именно часть понимания сломалась: тема, услуга, продолжение контекста или clarify. Это снижает риск чинить не тот слой.

**Что увидел пациент:** prompt, routing, цена, текст и UI не менялись.

### A9 — composable patient scope

**Статус:** этап открыт.

**Authority:** **forbidden**.

**Product firewall:** сохранён.

**Зачем нужен этап:** бот должен независимо понимать немедицинские признаки ситуации пациента:

- один зуб, несколько зубов или вся дуга/челюсть;
- верхняя, нижняя или обе челюсти;
- удаление обсуждается или имплант уже установлен;
- пациент явно сообщил, что врач говорил о нехватке кости.

Это не диагноз и не автоматический выбор All-on-4, All-on-6, синус-лифтинга или другой услуги.

#### Чекбоксы A9

- [x] Original patient-scope design (`9ee8c34`)
- [x] Nested contract (`2a34b6c`)
- [x] Scalar compatibility bridge (`0cc9042`)
- [x] Shadow wiring и product-firewall proof (`33966e4`)
- [x] Frozen quality matrix (`15d2ae7`)
- [x] Quality harness (`3f11857`)
- [x] One-run audit (`10b4739`)
- [x] Native extraction design (`16ced47`)
- [x] Native container metadata contract (governance `375ac13`, contract/tests reviewed)
- [x] Native raw contract и prompt spec (governance `405a6ac`, frozen fixture/tests reviewed)
- [x] Native extraction implementation (governance `e46a428`, implementation/tests reviewed)
- [x] Native shadow wiring/firewall proof (governance `4162111`, runtime/tests reviewed)
- [x] Manual-contact `not_applicable` taxonomy (governance `083bdcd`, revision `0eb8566`, helper/tests reviewed)
- [x] Frozen matrix/harness v2 review (governance `71aa405`, matrix/harness/tests independently reviewed)
- [ ] **A9R governance** — re-audit + frozen matrix + PRE-CODE (`TASK.md`)
- [ ] A9R1 offline contract/merge/eval
- [ ] A9R2 one live planner eval (owner permission)
- [ ] A9R3 authority decision + wiring
- [ ] Legacy retirement — только после принятой authority architecture

#### Что доказано сейчас

- инфраструктура и первый raw признаны целыми;
- deterministic scalar bridge прошёл `10/10`;
- в первом immutable v1 raw live-positive exact = `0` для `extent`, `jaw`, `stage`, `modifiers`;
- исторический v1 aggregate composite exact = `0/9` (7 live + 2 deterministic rows); нового live-результата ещё нет;
- current product path не читает новый nested scope;
- реальные тексты ответов, цены и UI этим harness не оценивались;
- authority запрещена;
- frozen v2 matrix сохранила все 30 live-вопросов и исходные ожидания без подгонки под первый raw;
- v2 harness отделяет 30 live-наблюдений от 14 локальных deterministic fixtures: positive denominators `13/9/4/3`, live composite total `7`;
- manual-contact остаётся в полном total как `not_applicable`, но не притворяется ошибкой распознавания; transport, runtime и malformed-frame ошибки остаются видимыми отдельно;
- offline fake-run и privacy/contract проверки зелёные (`68 passed`), но новый live/LLM run не выполнялся;

**Как это сказалось на логике и маркетинге:** мы построили безопасную измерительную инфраструктуру и увидели, что на первом frozen live sample measured shadow не материализовал ни одного exact positive axis. Следовательно, включать его в реальные ответы рано.

**Что увидел пациент:** ничего нового от A9 scope. Ответ по-прежнему формирует действующий legacy path.

После будущего подтверждения качества эта ось сможет помогать делать ответ релевантнее масштабу ситуации, но только через отдельное product/authority решение. Она не должна сама ставить диагноз или назначать лечение.

Подробнее: [PATIENT_SCOPE_DESIGN_A9.md](PATIENT_SCOPE_DESIGN_A9.md), [PATIENT_SCOPE_SHADOW_AUDIT_A9.md](evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md), [PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md](PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md) и [PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md](PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md).

## Следующий технический checkpoint — A9R (governance)

### A9R Patient scope authority re-audit

**Baseline:** AC3 complete @ `aa8e6dd`. **Authority:** forbidden. **Live/LLM:** forbidden in A9R.

A9R re-opens patient-scope work after AC3 cutover without modifying frozen v1/v2 shadow matrices or v1 live raw. Deliverables: read-only seam audit (`docs/A9R_GOVERNANCE.md`), `TASK.md`, new frozen matrix `evals/v5/demo/patient_scope_a9r_matrix.json`, PRE-CODE checker.

Gate sequence after A9R PRE-CODE ✅:

1. **A9R1** — offline projection `PatientScopeFrame` → `EffectiveScope`, merge rules, deterministic harness
2. **A9R2** — one owner-approved live eval using **existing** planner (no second LLM)
3. **A9R3** — authority wiring into `resolve_effective_scope` after quality gates
4. Post-authority widget E2E (separate TASK)

Старые frozen A9 v1/v2 artifacts и `PATIENT_SCOPE_SHADOW_AUDIT_A9.md` **не менять**.

---

## Следующий технический checkpoint — FULLCONTEXT_PRESENTATION_PARITY (governance)

**Baseline:** `codex/stage-a` @ `50c6cf9`. **Authority:** forbidden in governance commit.
**Live/LLM:** forbidden.

Восстановить механизмы представления и маркетинга, потерянные при переходе на
FullContext-only, без возврата legacy policy/RAG и без второго pipeline.

Owner decisions (binding):

- **Choice menu — max 4** governed buttons (`UiScopeAction`, `UiStageAction`, typed choices).
- **Secondary UI — max 2** slots (content followups, video, situation; separate price-detail slots).

Deliverables (Phase 1): read-only seam audit
(`docs/evidence/presentation/FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md`), `TASK.md`,
doc sync, PRE-CODE checker `tests/test_fullcontext_presentation_parity_governance.py`.

Gate sequence after PRE-CODE ✅:

1. **Implementation** — typed presentation layer on ResponseSpec + validated source identity
2. Post-implementation COMPLETION + frozen pin guards

Gaps A–G documented in seam audit. **NO PRODUCT CHANGE** in governance commit.

---

## Historical — A9 One-run Live Re-audit (v2, superseded by A9R gate plan)

Frozen matrix/harness v2 подготовлены и независимо проверены **до** live. Первый A9 raw, v1 matrix/harness/summary и исторический audit не переписаны. Product path и ответы бота не менялись; patient-scope authority остаётся запрещённой.

Следующий A9 шаг — один контролируемый live/LLM re-audit по 30 frozen turns, один attempt без retry, с новым raw `eval_patient_scope_a9_v2_last.txt`. Он не запускается автоматически и требует:

1. отдельного явного разрешения владельца на live/LLM;
2. нового `TASK.md`;
3. governance checker-review до запуска;
4. сохранения raw без повторного прогона или «улучшения» результата.

**Как это скажется на боте:** пока никак — мы лишь сделали будущую проверку честной. Когда владелец разрешит один live-run, отчёт отдельно покажет, распознаёт ли новая архитектура реальные положительные признаки пациента, а не смешает их с локальными fixtures или передачей обращения администратору.

До такого разрешения A9 стоит на паузе. Карта вопросов,
[target-архитектура услуг и цен](PRICE_SERVICE_ARCHITECTURE.md) и
[target-архитектура маркетинговых сценариев](MARKETING_SCENARIO_ARCHITECTURE.md) уже
документированы.

### Product/schema checkpoints вне A-series

- [x] Маркетинговая карта вопросов и базовые правила ответа.
- [x] Product/UI composition: лимит 3/2, content/price slots и стабильная CTA.
- [x] **Response Data Schema Governance** — единый target-канон услуг, применимости,
  брендов, prices, client strategy, marketing refs и session/UI state материализован и
  независимо проверен checker-ом; runtime/client data не менялись.

Три product/UI решения перед schema/runtime закрыты: composition первого marketing-concern
ответа, content/price navigation slots и стабильная CTA по смысловому контексту. Для
schema design создан отдельный governance TASK `dbf2c46`; runtime и client data заранее
не меняются.

## Как поддерживать чекбоксы

1. Новый checkbox сначала добавляется в governance `TASK.md`.
2. `[x]` ставится только в completion commit соответствующего checkpoint после checker `✅`.
3. Если аудит завершён, но показал красное качество, checkbox закрывается, а красный результат остаётся написан рядом.
4. Завершённый design не закрывает implementation или parent stage.
5. Live checkbox не закрывается без immutable raw, audit и отдельного разрешения владельца.
6. Authority меняется только отдельным продуктовым решением.
7. Подробный текущий статус A-series обновляется здесь; [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md) только ссылается на этот канон, чтобы снова не устареть.
