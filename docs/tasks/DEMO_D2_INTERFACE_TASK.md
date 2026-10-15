# Текущая карточка — НикаДент

## 70. Nikadent consultant name — owner GO 2026-10-15

Owner requests displayed consultant name Olga instead of Консультант Никадент.
Presentation config bug fix, not architecture simplification; existing botName
owns header, answer attribution, typing labels and avatar alt. Set botName Ольга;
no new personalization fields, prompts or model behavior changes.
Root/top C:/Cursor Projects/artgents-bot-active; branch
codex/nikadent-technical-onboarding; baselinec7b4fee, main/mergebasee93cb12.
Staging clean; local avatar.png WIP +3otzyv preserved/excluded. Exact allowlist:
clients/nikadent/widget_config.json; tests/test_widget_config_contract.py;
this task card. Existing config checks + actual local GET; focused Checker.
Provider/SMTP0; no merge/deploy.
Result:30 config tests PASS; focused Checker PASS; diff--check PASS. Local9001
had no running listener/process, restarted via existing start_local_widget.ps1;
GET widget-config confirms Ольга. No /ask/provider/SMTP calls. Prior baseline
price/replay failures outside scope unchanged. Exact3-file checkpoint only;
local avatar and3otzyv remain unstaged/unpushed.

## 69. Remove unused widget styling — owner GO 2026-10-15

Owner explicitly authorizes cleanup of old styles for demo/Nikadent after audit.
Presentation maintenance/bug fix, not D2 architecture simplification. Remove
18 confirmed non-rendered classes (old launcher fragments, modal video and old
secondary/video/ghost buttons),4 unread CSS tokens,3 stale DOM lookups and
obsolete theme action/button_1/button_2 transport/config. No replacement paths.
Current markup/theme renderer remains presentation owner. Preserve dynamic
clinic-msg__video--horizontal/vertical and all active menu/price/consent styling.
Root/top C:/Cursor Projects/artgents-bot-active; same onboarding branch; HEAD/base
5a9f0ba, main/mergebasee93cb12. Staging clean; local photo avatar.png and foreign
otzyv-1/2/3.jpg preserved/excluded. Exact allowlist:
static/widget/widget.css; static/widget/widget.js; core/client_config_loader.py;
clients/nikadent/brand.yaml; clients/_template/brand.yaml;
tests/test_client_config_loader.py; docs/CLIENT_PACK_AUTHORING.md;
docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_CURRENT_STATUS.md;
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
Baseline test_client_config_loader:7PASS/2FAIL before edits (removed demo gradient
button_1 expectations). Update these to actual brand/promotion contract, retain
all existing loader assertions. Browser launcher/menu/consent/video/price offline
checks as proportionate; independent Checker. No provider/SMTP, merge or deploy.
Result:41 targeted loader/config/HTTP tests PASS, actual launcher DOM PASS
(320/390/900, demo isolation), consent DOM PASS. Eight screenshots SHA256
byte-identical against before-cleanup captures, including full welcome chat.
Independent Checker PASS, independently loader10PASS; no removed class has
current markup producers, no removed tokens/transport fields have active readers.
Post-cleanup scan leaves only two dynamically produced aspect classes outside
literal matching; no unread CSS tokens remain. diff--check PASS.
Known baseline failure: price-detail browser flow StopIteration at
tests/test_d2_price_details_http.py:417 before browser start. Identical failure
reproduced on clean gitarchive5a9f0ba in temp/artgents-style-baseline-5hwe9hsr.
This test is unchanged; price/video browser flow unverified. Earlier historical
replay failures remain outside scope. Two stale loader failures now fixed by
asserting actual palette rather than obsolete gradient. Calls provider/SMTP0.
Checkpoint exact10 allowed paths; local avatar and3otzyv stay unstaged/unpushed.

## 68. Client launcher concept 1 — owner GO 2026-10-15

Promotion palette follow-up frombc3d5bc: owner requests per-client color settings
for shown welcome promotion card and audit of other widget colors. Presentation
feature/bug fix, not architecture simplification. Explicit new brand.yaml fields
colors.promo_background/promo_accent -> theme.promoBackground/promoAccent;
existing loader/theme renderer owns these only. Background+hover, icon/link/focus
of welcome card configurable; dark text stays neutral. Scope is welcome card;
price-card promotions and remaining fixed colors are audited, not recolored.
Root/top C:/Cursor Projects/artgents-bot-active; same onboarding branch; HEAD/base
bc3d5bc, main/mergebasee93cb12; staging clean. Local avatar.png photo WIP and
foreign3otzyv preserved/excluded from staging. Exact allowlist:
clients/{nikadent,demo,_template}/brand.yaml; core/client_config_loader.py;
static/widget/widget.js; static/widget/widget.css;
tests/js/client_launcher_harness.mjs; tests/test_nikadent_technical_onboarding.py;
docs/CLIENT_PACK_AUTHORING.md; this task card. Test actual card styling + HTTP
config and demo isolation; focused independent Checker. No model/SMTP or deploy.
Result: Chrome DOM PASS (card background/icon/link/inner arrow; independent
promo-only theme; demo isolation; existing320/390/900 geometry). HTTP config1PASS;
local9001GET confirms both settings, screenshot inspected. Independent Checker
PASS + focused inner-arrow recheck PASS. diff--check PASS. Historical baseline
failures outside scope unchanged. No provider/SMTP calls, merge or deployment.
Photo remains excluded from commit/push; staging exact10 declared paths only.

Tenant brand follow-up from6744c82, owner GO: shared client color for send button,
launcher arrow and composer border. Owner supplied Nikadent #762E94. Bug fix/
presentation configuration, not simplification. Existing brand.yaml colors.brand
-> loader theme.brand -> applyWidgetTheme is sole source; replace hardcoded
launcher arrow/focus colors with existing token. No new fields or runtime layers.
Avatar folder/path documented. During task owner replaced existing avatar.png
at advised location; expand allowlist to static/clients/nikadent/avatar.png and
connect it through existing avatar_url (no image edits). Treat as task asset,
not unrelated WIP; foreign3otzyv remain excluded.
Root/top C:/Cursor Projects/artgents-bot-active; same onboarding branch; main/base
e93cb12; tracked/staging clean, foreign3otzyv preserved. Exact allowlist:
clients/nikadent/brand.yaml; static/widget/widget.css;
tests/js/client_launcher_harness.mjs; tests/test_nikadent_technical_onboarding.py;
docs/CLIENT_PACK_AUTHORING.md; this task card. Test actual themed DOM+HTTP config,
demo isolation, focused Checker. No provider/SMTP calls, merge or deployment.
Evidence: Chrome DOM harness PASS and HTTP config test1PASS. Actual local9001
GET already returns brand#762E94 without restart. Brand-only Checker PASS;
focused avatar connection recheck PASS. Actual local9001 also returns avatar.png.
Screenshots inspected; historical baseline failures unchanged/outside scope.
No /ask/model/SMTP calls. Foreign3otzyv preserved; no merge/deploy.
Automatic approval review rejected outbound push including the changed photo
without explicit publication consent. User asked for permission; until answered,
checkpoint only the six text/code/config paths, preserve avatar.png as local WIP.

Typography follow-up from b05a411: UI polish/bug fix, not simplification.
Owner requests heading18px (keep weight600), body14px, subtitle12px;
body/subtitle same existing #6e7887 on desktop/mobile. Remove mobile19px override.
Allowlist: static/widget/widget.css and this task card. Same root/branch;
origin/main/mergebasee93cb12; tracked/staging clean; foreign3otzyv preserved.
Existing browser launcher harness + focused Checker; provider/SMTP budget0.
Result: Chrome harness PASS320/390/900, screenshots inspected, focused Checker
PASS, diff--check PASS. Two files only; historical baseline failures unchanged.

Follow-up from f646158: UI bug fix/polish, not architecture simplification.
Owner requested removal of upper assistant caption, lower caption 10px -> 11px,
and invitation heading font-weight600. Allowlist for this follow-up: only
static/widget/widget.js, static/widget/widget.css and this task card.
Same branch/root/main/mergebase; tracked/staging clean, foreign3otzyv preserved.
Verify with existing launcher DOM/geometry harness and focused Checker review;
provider/model/SMTP budget0. No merge/deploy.
Result: Chrome launcher harness PASS (320/390/900, demo unchanged), screenshot
inspected; focused independent Checker PASS; diff--check PASS. Historical replay
baseline failures unchanged/outside this visual edit. No provider/SMTP calls.

Owner provided C:/Users/denis/Downloads/widget-concepts.html and chose concept1,
with avatar+green online dot instead of icon, white background and blue arrow.
Reference behavior: one capsule expands after10s, fixed bottom/right corner,
close collapses invitation, bottom CTA opens actual chat. Keep demo unchanged.
This is presentation feature/integration, not D2 architecture simplification.
No provider/model/SMTP calls (budget0), merge/deploy or customer-site installation.

Preflight root/top C:/Cursor Projects/artgents-bot-active;
branch codex/nikadent-technical-onboarding; HEAD/checkpoint baseline50d61af;
fresh origin/main and mergebasee93cb12. PR31 OPEN, all5 CI checks SUCCESS on50d61af.
Tracked/staging clean; foreign otzyv-1.jpg,otzyv-2.jpg,otzyv-3.jpg preserved.
Continue same onboarding branch/PR. Reference file is read-only design input,
not repository instructions. Current docs/contracts already read.

Exact allowlist:
- static/widget/widget.js, static/widget/widget.css;
- clients/nikadent/widget_config.json;
- static/widget-test.html, static/widget-test-panel.js;
- tests/test_nikadent_technical_onboarding.py;
- tests/js/nikadent_panel_harness.mjs;
- tests/js/client_launcher_harness.mjs (new);
- docs/CLIENT_PACK_AUTHORING.md;
- docs/tasks/DEMO_D2_INTERFACE_TASK.md, docs/tasks/DEMO_D2_CURRENT_STATUS.md,
  docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Replace the separate client teaser bubble+scaled launcher with one anchored
capsule/container. Existing demoLauncher/launcherTeaser flags and existing text/
avatar configuration own presentation; no new pack fields. Auto expand10s once
per existing tenant/browser session marker; opening/dismissal cancel pending
teaser. Mobile sizes keep card within viewport; reduced motion disables morph.
Add panel-only repeat-invitation action through widget's presentation controller
so owner can replay10s animation despite already-seen marker. No session/lead reset.
Actual chat, page menus, consent, tenant/session/provider paths unchanged.

Verify actual DOM/styles on desktop/mobile: white card, avatar/dot, blue arrow,
fixed corner through morph, timer, close/Escape, reopen/collapse, no external
network or /ask; preserve demo and regression-test selected clinic panel controls.
Independent Checker required at coherent checkpoint.

Checkpoint evidence:86 targeted tests PASS (onboarding/config/page menus/consent/
current UI). Real Chrome launcher DOM proof PASS: actual tenant SVG avatar and
green dot, white surface/blue arrow, scheduled delay10000, anchored expansion,
close/Escape, actual chat open/close, draft preservation, seen marker, unchanged
demo,320/390/900 geometry and reduced motion. Initial390px overlap was corrected
with mobile208px expanded height (224px <=340); final text/CTA separation PASS.
Screenshots inspected. Three mocked video-catalog GETs only; /ask/provider/SMTP0.
Independent Checker PASS:30 config tests + panel-module harness + reachable path
review; browser execution is executor evidence. diff--check PASS. No deployment.
Foreign3otzyv.jpg preserved. Existing historical replay2fail unchanged/outside scope.

## 67. Client lead consent — owner GO 2026-10-15

Owner approved empty checkbox BEFORE name/phone collection for real clinics,
not demo; backend enforcement + durable timestamp/version evidence, ordinary
questions available without booking. Nikadent links supplied by owner:
https://nikadent41.ru/privacy-policy-2/ and
https://nikadent41.ru/personal-data-consent/. Temporary links/content pending
owner confirmation. Latest owner steering: small readable inline dialogue block,
not a half-screen or modal. Explicit cancel/continue without booking returns
to ordinary composer; unchecked consent blocks contact collection only.

Type: lead/privacy bug fix + consent feature, not architecture simplification.
Astra consulted; Target Contract §3 and current lead owner remain authoritative.
No semantic route/model changes; no new provider/SMTP calls (budget0), merge,
VPS deployment or site installation. Continuation of onboarding branch/PR31.

Preflight: root/top C:/Cursor Projects/artgents-bot-active; branch
codex/nikadent-technical-onboarding; HEAD/baseline2beb02b; fetched origin/main and
mergebasee93cb12. PR30 fc84066 and PR31 OPEN. Staging/tracked tree clean;
foreign otzyv-1.jpg, otzyv-2.jpg, otzyv-3.jpg preserved. No branch switch.

Exact allowlist:
- contracts/lead_consent.py (new), core/lead_consent.py (new);
- contracts/d2_dialogue.py, contracts/response_plan.py;
- core/d2_dialogue.py, core/d2_lead_bridge.py, core/response_ui_projection.py;
- core/response_plan_resolver.py (carry the frozen consent block unchanged);
- session.py, lead_service.py;
- clients/nikadent/lead_config.yaml;
- static/widget/widget.js, static/widget/widget.css;
- tests/test_lead_consent.py (new), tests/js/lead_consent_harness.mjs (new);
- tests/test_nikadent_technical_onboarding.py;
- tests/test_tenant_lead_routing_context_offline.py;
- tests/release/offline.txt;
- docs/CLIENT_PACK_AUTHORING.md, docs/BOT_BEHAVIOR.md;
- docs/tasks/DEMO_D2_INTERFACE_TASK.md, docs/tasks/DEMO_D2_CURRENT_STATUS.md,
  docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Mechanism: real delivery requires valid tenant-owned consent definition.
Demo-stub delivery skips this gate. Existing lead owner adds collecting_consent
before slot parsers; a typed frozen UI block publishes existing-style
lead:consent_accept + cancel refs. Acceptance uses saved tenant/session/current
revision authority and definition fingerprint; free-text yes/name/phone is not
acceptance. Checkbox enables a compact continue action, input locked until accept
or cancel. Existing cancel exits booking, so ordinary questions stay available.
All booking entry/resume/slot paths share the gate; direct /lead cannot supply
a trusted receipt through HTTP. Internal delivery takes the server-verified
receipt. Durable proof is part of acceptance completion in the existing D2 store;
private lead session holds only its request reference for this booking. Submit
completion links that reference. Cancel/submit/new booking clear active consent
reference; historical acceptance replay cannot authorize a later booking.
No consent data joins model context; no patient fields in audit proof. Existing
rollback applies; cross-database crash atomicity is not newly guaranteed.

Acceptance: JSON/SSE booking -> consent -> name -> phone -> mocked delivery;
bypass/unchecked/foreign/stale/version/replay/cancel/reset/new-booking cases,
unchanged demo, no-contact receipt/provider context, compact mobile UI and links.
Run targeted offline tests plus independent Checker. These links are configured
as supplied, not certified as legally suitable documents.

Evidence:47 targeted PASS before adverse-case extension; full current CI
offline+policy selection884PASS5platformSKIP0FAIL. Latest focused16PASS adds
missing-proof name/phone/paused states and definition change recovery. Chrome
renders actual frozen API fixtures: unchecked block, configured safe links,
composer lock, checked typed acceptance, cancel/reset, compact390/900px geometry.
It explicitly rejects accept503/cancel400, then verifies new-chat recovery.

Independent Checker REJECT: failed consent action hid controls and left the real
composer locked. Fixed using existing reset action when consent payload remains;
no semantic/model path added. Version refresh reissues the current pending
fingerprint, invalidates prior accepted terms before further slots. Focused
Checker recheck PASS (4 independent lifecycle tests). diff--check PASS.
Final UI/phone/consent nonbrowser repeat22PASS; browser already in focused16.
No provider/model/actual SMTP calls. No merge/deploy. ForeignWIP preserved.
Existing historical replay2fail unchanged/outside release scope. The supplied
consent URL displayed cookie/external-service terms; retain owner URL for local
test, require client document confirmation before public install.

## 66. Page-specific welcome menus — owner GO 2026-10-15

Owner explicitly requests implementation now: tenant-authored greeting and three
questions per selected website page, common default elsewhere, one shared top
promotion, local panel page preview, authoring instructions. Continuation of the
same Nikadent onboarding task/branch and open PR #31; no merge/VPS/site installation.
Type: presentation feature / integration of missing page menus, not architecture
simplification or a D2 semantic change. Astra consulted; Target Contract §3 applies.

Preflight root/top: C:/Cursor Projects/artgents-bot-active; branch
codex/nikadent-technical-onboarding; checkpoint baseline/HEAD 8161637;
freshly fetched origin/main = merge base e93cb12. PR #30 fc84066 and #31 still OPEN;
handoff docs read. Tracked checkout/staging clean before edits. Foreign WIP:
otzyv-1.jpg, otzyv-2.jpg, otzyv-3.jpg preserved. No branch switch.

Exact allowlist for this continuation:
- contracts/widget_config.py;
- clients/nikadent/widget_config.json;
- static/widget/widget.js, static/widget-test.html, static/widget-test-panel.js;
- tests/test_widget_config_contract.py, tests/test_widget_page_menus.py;
- tests/js/nikadent_panel_harness.mjs, tests/js/widget_page_menus_harness.mjs;
- tests/release/offline.txt;
- docs/CLIENT_PACK_AUTHORING.md;
- docs/tasks/DEMO_D2_INTERFACE_TASK.md, docs/tasks/DEMO_D2_CURRENT_STATUS.md,
  docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Mechanism: optional pageMenus in existing widget_config.json, exact paths with
trailing slash normalized (case/percent encoding preserved). Query/hash ignored.
Top-level welcomeText/starterPrompts own the default; each explicit menu has
exactly three nonblank label/q pairs. Duplicate normalized paths are invalid;
wildcards/full URLs/query/hash are invalid authored paths. Existing strict model
rejects nested promotion/security overrides. welcomePromotion stays top-level.
Tenant config is sole menu owner: when pageMenus is present, renderer does not
automatically append the gallery shortcut. Existing demo without pageMenus stays
unchanged. Selection occurs on initial welcome/reset; active conversation stays.
Preview pathname is an optional mount argument, separate from tenant/API config.
No new /ask field, model context, semantic route, memory, model call or lead effect.
Buttons remain ordinary authored text questions, not invented verified UI refs.

Acceptance: API exposes only selected tenant's menus; matched/unmatched paths,
slash/query/hash, exactly three rendered prompts, same promotion, configured q
click payload, reset, mobile geometry, unchanged demo/gallery and panel switching.
Run targeted config/onboarding/widget tests + independent read-only Checker.
No live/provider/SMTP calls authorized or needed for this UI checkpoint (budget0).

Remaining limits: texts are editable initial suggestions on current content;
not clinical/content acceptance, deployed rendering or live-model quality proof.

Checkpoint evidence:106 targeted offline tests PASS across widget page menus,
widget config, onboarding, current visual contract, embed CORS, pack validation
and release selection tests. Actual Chrome DOM harness PASS:10 routes/31 mocked
question+promo clicks, correct q/tenant, no fabricated refs or page context;
shared promo, exactly3 buttons including unmatched defaults, reset/preview,
unchanged demo gallery,390/900px geometry. Local running API returns new menus.
Independent Checker PASS:50 nonbrowser tests + panel harness and reachable-path
review. Provider/model/real SMTP calls0. No runtime simplification certified.

Additional historical replay suite:2FAIL/1PASS reproduced on clean archive of
baseline8161637 (same StopIteration expecting removed scope quick_replies,
before JS execution). Outside current release selection, left untouched.
Initial headless browser CDP timeout under sandbox resolved by approved local
browser execution; old Nikadent-promo-None expectation updated to actual authored
promotion. No new app/transport defect found. ForeignWIP preserved.

## 65. Nikadent technical onboarding — owner GO 2026-10-15

LATEST OWNER SCOPE: local test widget only for now. User explicitly deferred
merge/deployment after initial authorization; PR #31 remains OPEN. No VPS changes.

Type: bug fix / integration, not architecture simplification. User approved real
email leads, bot operation using the current Nikadent pack, local demo/Nikadent
switching, deployment and customer-site testing. User installs the supplied embed
code; no customer CMS/browser access. Content authoring and price completion are
explicitly postponed. Existing contact/doctor MD must remain tenant-owned.

Preflight: repository/top C:/Cursor Projects/artgents-bot-active;
branch codex/nikadent-technical-onboarding; HEAD/baseline/origin-main/merge-base
e93cb121e8ea45c31dc45b435720a556fda8033d, fetched before branch creation.
Latest docs read on fc84066 / open PR #30 before switching. Tracked tree clean;
foreign WIP otzyv-1.jpg, otzyv-2.jpg, otzyv-3.jpg preserved.

Exact tracked allowlist:
- core/d2_dialogue.py, core/d2_lead_bridge.py, core/d2_dialogue_store.py;
- lead_service.py;
- clients/nikadent/lead_config.yaml, clients/nikadent/widget_integration.json;
- clients/nikadent/brand.yaml, clients/nikadent/target_response/pricebook/facts.json;
- static/clients/nikadent/avatar-placeholder.svg;
- static/widget/widget.js, static/widget-test.html, static/widget-test-panel.js;
- static/multiclient/index.html;
- tests/test_nikadent_technical_onboarding.py, tests/js/nikadent_panel_harness.mjs;
- tests/test_tenant_lead_routing_context_offline.py (existing failure-status
  assertions updated for honest 503; SMTP mock uses actual existing email status);
- tests/release/offline.txt;
- docs/tasks/DEMO_D2_INTERFACE_TASK.md, docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md,
  docs/tasks/DEMO_D2_CURRENT_STATUS.md.
Local-only allowlist: .env (SMTP nonsecret values + blank password entry, explicit
ALLOWED_CLIENTS demo,nikadent); never stage credentials, .env, DB or dialogue logs.

Mechanism: accepted private slots are captured request-locally before existing
PII cleanup, then existing handle_lead/SMTP selects the tenant delivery mode.
Only actual submission requests an effect. Replace universal stub with actual
delivery; demo still selects demo_stub through its existing pack. Save final
response and existing effect status atomically for terminal replay. Pending or
ambiguous SMTP result never claims success; no automatic retry/queue/exactly-once
claim. Example: missing SMTP -> cannot send; SMTP exception -> delivery unconfirmed.
No model/parser/router changes. Sole delivery result owner is the existing lead
path; ordinary semantic decisions remain with the model per Target Contract §3.
Astra consulted: capture before exit_lead_flow; clear before durable commit; do not
reparse the phone in the adapter or expose active collection during SMTP.

Acceptance: offline actual JSON/SSE + mocked SMTP, correct accepted name/phone,
tenant recipient, demo zero SMTP, sent/failed/unknown + replay, commit failure
zero sends, PII absent from D2 completion; Nikadent snapshot/model view loads;
canonical contacts and own doctor docs reach provider; widget config/origins and
independent browser session keys. CI release union before merge, independent Checker.
Live hard cap 20 model calls + one synthetic test email; record actual counts.
VPS env access, password entry and embed insertion are distinct deployment inputs;
do not claim actual site or inbox verification from offline evidence.

Checkpoint evidence: executor 32 targeted PASS; independent Checker PASS and
13/13 onboarding tests including real panel-module Node harness. Diff check clean.
Full release selection running separately; no live model or email sends so far.
Public GET /health/live and same-origin /api/widget-config both 200 for demo and
nikadent: registry/hostname already present on VPS. Admin SSH was not established;
SMTP production values remain unverified. No customer-site/CMS access performed.

Full Windows union: 882 passed, 5 skipped, 4 failed. Three findings were outdated
success expectations / invalid email_sent mock in the existing tenant lead tests;
update those assertions without weakening recipient/privacy/provider checks.
The config-only test reloads local .env after deleting CHAT_API_KEY; isolate local
dotenv input for the repeat (PYTHON_DOTENV_DISABLED=1), matching CI's absent .env.
Focused repeat: 60 passed; independent focused Checker PASS. CI on the first
checkpoint has the same outdated lead assertions; push corrected tests and
require a successful complete CI before merge/deploy.

Final local evidence: isolated release union **886 passed, 5 platform skipped,
0 failed**; final runtime/UI commit 2164c53 CI all five jobs SUCCESS, run
38719946271. Independent Checker PASS and focused test/CSS rechecks PASS.
Live local only: exactly **5 model calls + 1 actual email**; own Nikadent city,
canonical branches/phones, own doctor MD, real SMTP lead with accepted private
slots; owner confirmed mailbox receipt. Demo retained demo_stub. Both completed
submit replays identical, no second email. Secrets remain local ignored .env.
Local bot running via approved launcher in the current checkout/branch.
No actual customer-site install/render verification; no VPS SMTP confirmation.
The automatic approval reviewer rejected the earlier merge attempt for lacking
separate explicit merge authority; no merge/deploy mutation occurred. Owner then
chose local testing, so no workaround or further merge attempt is authorized.

## Historical cleanup receipts

Действующий checkpoint — §62, ниже. Предыдущие §60–61 — receipts этой же
чистки, не новая очередь и не повторное разрешение на runtime.
Прежние интерфейсные этапы1–59 и полный исходный snapshot сохранены
в [архиве checkpoint](../archive/checkpoints/DEMO_D2_INTERFACE_TASK.md).
Этот перенос не закрывает SIM/REC и не меняет владельцев решений.
Порядок работ — [Roadmap](DEMO_D2_DELIVERY_ROADMAP.md),
правила — [AGENTS](../../AGENTS.md), [Checker](../WORKFLOW_CHECKER.md).

## 60. Cleanup checkpoint — 2026-10-13

Owner GO: после сохранения visual checkpoint привести документацию и tests
к действующему боту; затем отдельно demo KB; совместная итоговая выкладка.
Baseline58c1afa, branchcodex/docs-tests-cleanup, origin/main/mergebase8888fdd,
rootC:/Cursor Projects/artgents-bot-active, foreignWIP0 (EOL originals backed up).
Это CI regression coverage + документационная сверка, не runtime simplification.

Первый allowlist: .github/workflows/ci.yml; .github/workflows/publish-image.yml;
tests/test_g2_pr_ci_contract.py; tests/test_g3_immutable_image_contract.py;
docs/README.md; this card; DEMO_D2_CURRENT_STATUS.md; DEMO_D2_DELIVERY_ROADMAP.md.

### Карта чистки — первоначальная инвентаризация

192 файла docs/artifacts и515 test*.py на baseline. Это размер дерева, не число
устаревших файлов. Не классифицировать автоматически по возрасту/имени.

| Группа | Решение / необходимое доказательство |
|---|---|
| docs/README.md | Исправить вход: старые A1–A9 не текущая очередь; current status и roadmap впереди. |
| CURRENT_ARCHITECTURE.md, ROUTING_MAP.md, FLAGS_AND_STATUS.md, старые A9/S*/hybrid планы | Кандидаты исторического архива; проверить входящие ссылки и вынести ещё действующие гарантии до переноса. CURRENT_ARCHITECTURE сам уже помечен stale. |
| DEMO_D2_CURRENT_STATUS / DELIVERY_ROADMAP | Новый актуальный верхний статус, нижние receipts исторические; дальнейшее сокращение с сохранением evidence в архиве. |
| Interface/Experiment/Ledger | Извлечь текущие принятые решения и unresolved debt; исторические tool/JSON/model trials не самостоятельный current contract. |
| AGENTS / EXECUTION_LOCK | Исправить отрицание VPS deployment, сохранив согласованные protections. Не менять остальной workflow произвольно. |
| tests/test_d2_contact_model_context.py | Уже актуален: включить PR/publish; JSON/SSE prompt факты, snapshot/tenant/branch binding. |
| test_d2_demo_limits.py | Мигрировать полезные replay/free-click/session/daily/IP boundaries, снять obsolete10/JSON fixtures; не удалять файл как «просто старый лимит». |
| test_d2_situation_disabled.py | Сохранить отказ obsolete actions без mutation/provider, PII/history guards; обновить booking fixtures. |
| test_d2_policy_text_refs.py, test_d2_af1b_contacts_http.py | Перенести ещё не покрытые refusal/text_ref/missing/branch/mixed/replay assertions на actual text/native protocol. Baseline35FAIL22PASS на этих двух suites подтверждён ранее. |
| test_one_call_stage3b_offline.py | Отделить полезную endpoint-security проверку от helper, требующего удалённый doctor_catalog; не возвращать doctor JSON. |
| old envelope/selector/price_detail/doctor-catalog-only assertions | Кандидаты удаления после просмотра callers/importers и проверки equivalent current guards. Ни одного удаления только по имени/FAIL. |
| tenant/privacy/lead/PG/G2–G8 safety | Сохранить покрытие; не восстанавливать legacy payload ради fixture. |
| docs/evidence/, audits/, artifacts/ | История не выдаёт implementation authority. Архивировать с восстановлением ссылок, не переименовывать старый FAIL в PASS. |

Удаления ещё не выполнены. Карта задаёт последовательность и сохраняемые
инварианты; не утверждает, что все515 тестов прочитаны или вся архитектура закрыта.
Первый CI delta: существующий contact regression добавлен в явные gate lists,
G2/G3 tests требуют его присутствия. Никакие прежние selected tests не исключены.

Первый checkpoint evidence: contact_model_context + G2/G3 contracts60 PASS,
135 existing datetime deprecation warnings; git diff --check PASS. PR/publish
selection parity: publish = union current PR jobs + G3 (без exclusions).
Current docs entry file links PASS. Live/provider/SMTP0, full suites не запускались.
Историческая карта — inventory/proposal, не выполненное удаление или новая
architecture acceptance. Checker проверяет этот coherent checkpoint; дальнейшая
миграция/архивирование отдельными scope после него. VPS/KB unchanged.

### 60.1 Current architecture and situation regression migration

Baselinec6f4fe3, same branch/root/main. Documentation + fixture bug fix, not
runtime simplification. Allowlist: AGENTS.md; docs/tasks/DEMO_D2_EXECUTION_LOCK.md;
docs/CURRENT_ARCHITECTURE.md; docs/TEST_SUITE_ARCHITECTURE.md; docs/README.md;
new archive/pre-d2 counterparts for the two replaced documents;
tests/test_d2_situation_disabled.py; two workflows; G2/G3 contract tests;
this card; Current Status and Delivery Roadmap.

Removed false no-deployment statement and legacy architecture as current entry.
Archived pre-D2 architecture (relative links adjusted) and old test target; replaced
with actual D2/provider/text/nativeprice/snapshot/contacts/lead/security description.
Owner-provided VPS demo fact preserved separately from unclaimed production users.
No runtime/KB/provider changes or whole architecture certification.

Situation tests: baseline8FAIL10PASS. Old JSON fixtures replaced by prose and
proper line-delimited D2_META start_booking. Existing assertions retained; strengthened
HTTP/SSE success and collecting_name/phone setup. Previous active-case tests could
pass without actually starting booking; no such false positive after migration.
Final targeted18PASS22.38s. Module included in PR/publish gate, G2/G3 require it.
No file deletions/tests skipped/xfail. Quota/policy/contact historic migration remains.

§60.1 final executor evidence: situation18 + demo_release25 + contact4 +
G2/G3 contracts56 =103 PASS57.33s, existing datetime warnings. Link targets
current/new archive files PASS; archived architecture only relative links adjusted,
archived test document preserved exactly. Workflow delta add-only situation module;
all other jobs compare equal to baseline. git diff --check PASS. Provider/SMTP0,
no runtime/KB/VPS changes. Independent Checker follows before checkpoint save.

### 60.2 Demo quota fixture migration

Baseline1568202, root/branch/main unchanged. Test fixture bug fix + documentation,
not runtime simplification. Allowlist: tests/test_d2_demo_limits.py; two workflows;
G2/G3 contract tests; TEST_SUITE_ARCHITECTURE.md; this card; Current Status; Roadmap.

Baseline9FAIL3PASS12cases. Existing10-call assertions/counter seeds moved to30;
native show_price + second completion separately charged, actual published Nobel
selection/free click checked by frozen offer ID and amount. Prose/META replace old
JSON fixtures. Request successes and actual lead start checked before dependent
assertions. State equality uses deepcopy snapshot, no aliased before/after object.
Shared-limit isolation now uses valid synthetic secondary tenant cloned only in
fixture temp directory; real nikadent unfinished, not modified/certified.

All12cases retained: session/replay/free clicks/new SID, daily/IP isolation,
failed-attempt charging/reservation release, persistent atomic concurrent boundary,
window expiry, lead preservation/no transfer to new SID. Targeted12PASS24.38s.
No skips/xfail/assertion removals. Add module PR/publish and G2/G3 selection guards.
Provider/network/SMTP0; runtime/KB/VPS unchanged. Further policy/contact fixture
migration and obsolete-only test deletions remain separate unresolved scope.

§60.2 final executor: quota12 + sessionbudget3 + demogate25 + G2/G3 56 =
96PASS58.00s; existing datetime warnings. Add-only gate delta and equality
publish=PR job union+G3 confirmed; other jobs unchanged. DiffcheckPASS.
Independent Checker follows. Full historical suite not run/closed; live0.

### 60.3 Policy/contact fixture migration

Baseline d166841; same branch/root/main. Test fixture bug fix + docs; runtime0.
Allowlist: test_d2_policy_text_refs.py; test_d2_af1b_contacts_http.py; two workflows;
G2/G3 tests; TEST_SUITE_ARCHITECTURE.md; this card; Current Status; Roadmap.
Baseline two suites35FAIL22PASS57cases. Policy keeps all38cases. Native show_price
with actual code-result/second-response wire replaces old price envelope; policy
text MD mutation verified in tool result before final prose, missing offers/booking
and CTA suppression, replay and exact next-turn published history checked.
Booking uses META. Bad/missing/inline policy refs keep their old integrity guards.

Contacts use META show_contacts. Valid synthetic secondary clone with branch
contact samples only in temp; no real nikadent runtime certification. Exact values,
requested-field isolation, missing parking/address, multiple branches/phones remain.
Two old content_first permutations removed as identical current prose-before-META
wire; JSON/SSE mixed/replay assertions retained. Unknown foreign branch expanded
from1 to4cases (JSON/SSE, with/without valid prose): current rejection is a frozen
contact-unavailable part/failure, not old whole-HTTP400. Assert no canonical contacts,
no address/phone leak or contact buttons, preserved sibling prose and free replay.
Malformed empty fields still rejected whole. Default consultation CTA in a demo
clone is not an arbitrary call button; verify absence of contact action and correct
button tenant rather than old blanket buttons==[]. No product behavior changed.

Old literal contact_branch_id prompt assertion replaced by canonical branch IDs,
public fact grounding and supported ContactOperation schema field. Prompt branch
selection by live model not certified; exact argument-name advertising is absent
from current prose instructions, recorded as potential quality debt outside test migration.
Contact suite now20PASS; policy38cases retained. Gates add both under policy job and
publish; G2/G3 require them. Situation module no longer falsely listed as retired
in G2 (its active coverage remains mandatory in offline job).
Provider/network/SMTP0; no runtime/KB/VPS edits. Broad historical suite still open.

§60.3 final executor evidence: policy38 + contacts20 + modelcontext4 +
G2/G3 56 =118PASS54.68s. Baseline35FAIL22PASS57cases; no case skip/xfail,
only2 duplicate old order permutations removed and3 adverse branch cases added.
Gate delta add-only two suites; other jobs and publish/PR union parity unchanged.
DiffcheckPASS. Current protocol outcomes verified by frozen state, not status-only.
Independent Checker follows; live/provider0 and whole historical suite unresolved.

### 60.4 Obsolete assertions and historical routing/config archive

Baseline3688500, same root/branch/main, foreignWIP0. Test/doc cleanup only.
Allowlist: test_d2_structured_output.py; test_d2_sim2_contract.py;
test_d2_text_reply.py; two workflows; G2/G3 tests; docs/ROUTING_MAP.md;
FLAGS_AND_STATUS.md; tasks/DEMO_D2_ENVELOPE_CORRECTION_TASK.md;
new archive/pre-d2 copies of these3 paths; docs/README.md;
TEST_SUITE_ARCHITECTURE.md; this card; Current Status; Roadmap.

Removed15cases, selected baseline8FAIL7PASS:2 HTTPjson_object/1024 requirements,
6 old JSON prompt examples incl modelprice_detail,7 doctor-envelope validations.
Do not remove shared parse/prompt_example helpers: legacy suites import them.
Strict capability/probe safety tests retained because scripts/check_d2_format_layers
and experiment_d2_interface_comparison still consume prepare_cases. Their remaining
historical failures not migrated/declared green and don't protect currentHTTP.

Current known-task test strengthened: complete frozen binding, target/brand/volume/
source sections, identity, text and ignored foreign metadata. Added ordinary/known
actualHTTP-provider no-response_format checks; known no tools, ordinary nativeprice
only, one call1536tokens. Removed command doctors checked through current META;
native tool schema/bad argument guards remain in test_d2_native_price_runtime.

Text-protocol original baseline8FAIL15PASS23cases reproduced from HEAD in temporary
file. They expected tail show_price still active. Shared malformed-argument7 cases
migrated to actual show_contacts with valid base fields; kept bad-shape/server-field
checks. API-only tail price now explicitly rejected; order/server IDs including
unavailable sibling retained. No runtime modification/adapter/skip/xfail.

Old ROUTING/FLAGS/envelope-card archived (existing valid relative links adjusted);
old paths become brief current indexes/forward links. Historical claim of absent
VPS and stale Composer flag authority removed from current reading path. Evidence
is retained; no production flags or prices changed. Full historical archive/suite
still not closed. Add current text_reply to PR/publish, G2/G3 require it.

§60.4 final executor: text_reply27 + native_price37 + G2/G3 56 =120PASS50.41s.
Exact current publish selection49files:812PASS5SKIP0FAIL192.53s on local Windows.
This is current offline gate only, not full historical tests/ nor real Docker/PG
qualification/deploy. Platform skips remain documented environment limitations.
Entry/index links and archive narrative preservation (only link relocation) PASS;
other workflow jobs unchanged; diffcheckPASS. Independent Checker follows.
Provider/live/SMTP0. Current archived evidence not relabeled as runtime authority.


### 60.5 Current status separated from checkpoint history

Documentation only, not runtime simplification. Baseline2cbbd15; root/top
C:/Cursor Projects/artgents-bot-active; branch codex/docs-tests-cleanup;
origin/main and merge-base8888fdd; status clean, foreignWIP0 before edits.
Allowlist: tasks/DEMO_D2_CURRENT_STATUS.md; archive/pre-d2/tasks counterpart;
docs/README.md; this card; DEMO_D2_DELIVERY_ROADMAP.md.

Old full status preserved in archive, valid relative file links relocated.
Stable original path now states deployed8888fdd versus draft PR27, current model/
price/META/contacts/quotas, local typography, exact latest offline evidence,
unresolved historical suites/docs/SIM/REC and separate KB/deploy scope.
Removed from current status: old branch/WIP/one-call/envelope instructions mixed
with current facts. Not removed: historical evidence or agreed protections.
Roadmap/Interface historical sections remain to classify; no whole-docs PASS.
No runtime, workflow selection, tests, KB or VPS changes. Provider/live/SMTP0.
Verification: archived narrative preservation, relative link relocation, current
file links, five-path allowlist and full branch diffcheck; independent Checker.
No pytest rerun needed for documentation only; previous812PASS5platformSKIP
is dated evidence, not a new run. Commit/push only after coherent Checker PASS.

§60.5 verification PASS: complete439line archive narrative retained; all28
relative Markdown links preserve their original file targets; current/archive
file links valid. Direct whitespace scan includes untracked archive; branch
and working diffcheck PASS. Independent Checker PASS, current claims traced to
config/provider/dialogue/snapshot/quota code; no implementation simplification
or live/whole-bot quality certified. Exact5paths, stagingempty, foreignWIP0.


### 60.6 Shared release test selection

CI maintenance + documentation, no runtime architecture change. Owner GO:
streamline GitHub→VPS updates; don't revive obsolete tests or drop useful safety.
Baseline3fec64e; root/topC:/Cursor Projects/artgents-bot-active;
branchcodex/docs-tests-cleanup; origin/main/mergebase8888fdd; preflightclean/WIP0.
Allowlist: ci.yml,publish-image.yml; G2/G3/G4/G5/G7/G8 workflow contracts;
tests/release/offline.txt,policy.txt,README.md; workflow_test_selection.py;
test_release_test_selection.py; TEST_SUITE_ARCHITECTURE; CurrentStatus; Roadmap; thiscard.

Before:49 unique publish files repeated in3 inline workflow lists.
After:2 plain pytest argument files own selection; PR consumes each directly;
Publish sorts their union and adds G3. Removed dependency: independently edited
PR/publish lists; no new runner/fallback/runtime layer. Every previously selected
file retained; only selection contract added. Policy's existing PR overlaps remain,
publish duplicates eliminated as before. Existing static contracts inspect actual
manifest contents, not comments or filename merely mentioned in workflow.
Job names, permissions, dependencies, secret scans, PG, build/smoke/publish/deploy
unchanged. TODO now calls for useful invariant review, not blind historical restoration.
Historical test classification/retirement and remaining docs archive still open.
Provider/live/SMTP0; targeted contract tests and exact publish selection then Checker.


### 60.7 Owner entry and first bulk historical archive

Documentation only, no runtime simplification. Samebaseline3fec64e; §60.6 own
17pathWIP preserved, no foreignWIP. Owner GO: hide obsolete docs, retain current
behavior/technical protections; don't revive unnecessary historical tests.
Additional exact allowlist: docs/README.md,BOT_BEHAVIOR.md,archive/README.md;
ARCHITECTURE_CONVERGENCE.md,STRANGLER_ROADMAP.md,archive/pre-d2/CURRENT_ARCHITECTURE.md;
thiscard,CurrentStatus,Roadmap; the19 old/new archive paths below.
- `docs/A9R_GOVERNANCE.md` → `docs/archive/legacy-plans/A9R_GOVERNANCE.md`
- `docs/C1_LEGACY_RESIDUE_REPORT.md` → `docs/archive/legacy-plans/C1_LEGACY_RESIDUE_REPORT.md`
- `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` → `docs/archive/legacy-plans/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md`
- `docs/DEMO_READINESS_ROADMAP.md` → `docs/archive/legacy-plans/DEMO_READINESS_ROADMAP.md`
- `docs/ONE_CALL_ARCHITECTURE.md` → `docs/archive/legacy-plans/ONE_CALL_ARCHITECTURE.md`
- `docs/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md` → `docs/archive/legacy-plans/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md`
- `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` → `docs/archive/legacy-plans/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`
- `docs/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md` → `docs/archive/legacy-plans/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md`
- `docs/PREPARED_HYBRID_HANDOFF.md` → `docs/archive/legacy-plans/PREPARED_HYBRID_HANDOFF.md`
- `docs/PREPARED_HYBRID_ROADMAP.md` → `docs/archive/legacy-plans/PREPARED_HYBRID_ROADMAP.md`
- `docs/RESPONSE_CONTRACT.md` → `docs/archive/legacy-plans/RESPONSE_CONTRACT.md`
- `docs/S47_FIRST_LIVE_INCIDENT_AUDIT.md` → `docs/archive/legacy-plans/S47_FIRST_LIVE_INCIDENT_AUDIT.md`
- `docs/S50_LIVE_REEVAL_V2_INCIDENT_AUDIT.md` → `docs/archive/legacy-plans/S50_LIVE_REEVAL_V2_INCIDENT_AUDIT.md`
- `docs/S53_VERIFIER_REPLAY_POST_LIVE_AUDIT.md` → `docs/archive/legacy-plans/S53_VERIFIER_REPLAY_POST_LIVE_AUDIT.md`
- `docs/S62_TARGET_RUNTIME_POST_LIVE_AUDIT.md` → `docs/archive/legacy-plans/S62_TARGET_RUNTIME_POST_LIVE_AUDIT.md`
- `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` → `docs/archive/legacy-plans/S64_FULLCONTEXT_AUTHORITY_AUDIT.md`
- `docs/S66_GOVERNANCE_CORRECTION_AUDIT.md` → `docs/archive/legacy-plans/S66_GOVERNANCE_CORRECTION_AUDIT.md`
- `docs/S68_LEGACY_DELETION_INVENTORY.md` → `docs/archive/legacy-plans/S68_LEGACY_DELETION_INVENTORY.md`
- `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` → `docs/archive/legacy-plans/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md`

All19 basename readers checked across core/tests/scripts/evals/deploy source/data
files:0. Full original narratives retained, relative Markdown targets relocated,
3 incoming-link documents updated. ARCHITECTURE_CONVERGENCE/STRANGLER retain paths
for historical readers but explicit non-current warning added. No old runtime
claims revive product obligations. New owner behavior summary delegates technical
facts to current status/architecture; admitted prose/card residual risk preserved.
Remaining198-doc corpus not declared completely cleaned; active authoring/security,
current contracts and remaining historical-reader bindings preserved/out of scope.
Checks: archive narrative/target preservation, entry links, explicit path mapping,
diffcheck. Provider/live/SMTP0, no pytest required for doc-only delta; CI §60.6
full50-file run separately. Independent Checker reviews archive/entry scope.

§60.6 final evidence: exact50-file publish union821PASS5platformSKIP0FAIL198.41s.
Targeted selection/G2/G3/G4/G5/G7/G8:271PASS5SKIP17.01s; Independent Checker
PASS, ownselection/G2/G3:65PASS. Old49file selection retained; onlyselectiontest
added. Protected CI PG suffix and publish secret/build/smoke/push suffix identical
against baseline. No live/provider/SMTP; no runtime/deploy change. Fullhistorical
suite notgreen/notrun. §60.7 archive preservation confirmed after ignoring EOL and
97 oldMarkdown hardbreak-space formatting lines; all original prose retained.

§60.7 independent Checker PASS:19 original narratives and relative targets
retained, strong historical warnings, baseline reader grep0, owner behavior
matches current code/accepted prose risk. Entry links/whitespace PASS; no pytest
required for docdelta. Combined §60.6/7 exact61paths verified; foreignWIP0,
provider/live/SMTP0, stagingempty before save; allhistorical debt notdeclaredclosed.


### 60.8 Historical task archive and current process pointers

Documentation only; no runtime simplification or new product rules. Owner GO:
keep current docs visible, hide obsolete cards/prompts and don't revive old tests.
Repo/topC:/Cursor Projects/artgents-bot-active; branchcodex/docs-tests-cleanup;
baseline51d4bd2; origin/main/mergebase8888fdd; preflightclean/foreignWIP0.
Prior checkpoint GitHubCI38427577060 SUCCESS, all5jobs; not a new image/deploy.

Scope:50 historical task moves;2 complete Interface/Roadmap snapshots; existing
relative incoming links in15 documents; current task/status/index/roadmap;
AGENTS map pointer and ExecutionLock process references only. Code/test/script
basename readers for all50 moved paths0 across core/tests/scripts/evals/deploy.
No runtime/tests/workflows/clientdata edits, model/provider/SMTP0.
Old executor/mini/checker prompts duplicated workflow and asserted superseded
financial publication rules; archived rather than kept as active instructions.
Sole workflow source remains AGENTS+WORKFLOW_CHECKER+ExecutionLock+current card.
Required protections/review gates and source priority of owner decisions retained.
SIM/REC cards preserved as historical evidence with explicitly unresolved general
acceptance: archiving a card does not mark it done/cancel an invariant.
Current Interface exposes§60 only; CurrentRoadmap exposes current queue only.
Historical section links redirect to full snapshots; current§60 links stay current.

Exact allowlist (old→archive paths plus listed incoming/current pointer paths):
- `docs/tasks/D2_TECHNICAL_PORTRAIT.md` → `docs/archive/task-history/D2_TECHNICAL_PORTRAIT.md`
- `docs/tasks/DEMO_D1_CLINIC_POLICY.md` → `docs/archive/task-history/DEMO_D1_CLINIC_POLICY.md`
- `docs/tasks/DEMO_D1R_MODEL_UNDERSTANDING.md` → `docs/archive/task-history/DEMO_D1R_MODEL_UNDERSTANDING.md`
- `docs/tasks/DEMO_D2_AF1A_PRICE_TASK_TASK.md` → `docs/archive/task-history/DEMO_D2_AF1A_PRICE_TASK_TASK.md`
- `docs/tasks/DEMO_D2_AF1B_CONTACTS_TASK.md` → `docs/archive/task-history/DEMO_D2_AF1B_CONTACTS_TASK.md`
- `docs/tasks/DEMO_D2_AUDIT_FOLLOWUP_TASK.md` → `docs/archive/task-history/DEMO_D2_AUDIT_FOLLOWUP_TASK.md`
- `docs/tasks/DEMO_D2_CODEX_EXECUTOR_PROMPT.md` → `docs/archive/task-history/DEMO_D2_CODEX_EXECUTOR_PROMPT.md`
- `docs/tasks/DEMO_D2_CURRENT_STATUS_INDEX_TASK.md` → `docs/archive/task-history/DEMO_D2_CURRENT_STATUS_INDEX_TASK.md`
- `docs/tasks/DEMO_D2_CURSOR_CHECKER_PROMPT.md` → `docs/archive/task-history/DEMO_D2_CURSOR_CHECKER_PROMPT.md`
- `docs/tasks/DEMO_D2_DEMO_BASE_REVIEW.md` → `docs/archive/task-history/DEMO_D2_DEMO_BASE_REVIEW.md`
- `docs/tasks/DEMO_D2_DOCUMENT_CLICK_TASK.md` → `docs/archive/task-history/DEMO_D2_DOCUMENT_CLICK_TASK.md`
- `docs/tasks/DEMO_D2_ENVELOPE_CORRECTION_TASK.md` → `docs/archive/task-history/DEMO_D2_ENVELOPE_CORRECTION_TASK.md`
- `docs/tasks/DEMO_D2_FULL_AUDIT_TASK.md` → `docs/archive/task-history/DEMO_D2_FULL_AUDIT_TASK.md`
- `docs/tasks/DEMO_D2_LEAD_INTERRUPT_TASK.md` → `docs/archive/task-history/DEMO_D2_LEAD_INTERRUPT_TASK.md`
- `docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md` → `docs/archive/task-history/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md`
- `docs/tasks/DEMO_D2_REBUILD_ROADMAP.md` → `docs/archive/task-history/DEMO_D2_REBUILD_ROADMAP.md`
- `docs/tasks/DEMO_D2_REC2_CORRECTION_TASK.md` → `docs/archive/task-history/DEMO_D2_REC2_CORRECTION_TASK.md`
- `docs/tasks/DEMO_D2_REC4_PRICE_BUTTONS_TASK.md` → `docs/archive/task-history/DEMO_D2_REC4_PRICE_BUTTONS_TASK.md`
- `docs/tasks/DEMO_D2_RECONCILIATION_INVENTORY.md` → `docs/archive/task-history/DEMO_D2_RECONCILIATION_INVENTORY.md`
- `docs/tasks/DEMO_D2_RECOVERY_CONTENT_TASK.md` → `docs/archive/task-history/DEMO_D2_RECOVERY_CONTENT_TASK.md`
- `docs/tasks/DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md` → `docs/archive/task-history/DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md`
- `docs/tasks/DEMO_D2_RECOVERY_MEMORY_TASK.md` → `docs/archive/task-history/DEMO_D2_RECOVERY_MEMORY_TASK.md`
- `docs/tasks/DEMO_D2_RULES_INVENTORY_AUDIT.md` → `docs/archive/task-history/DEMO_D2_RULES_INVENTORY_AUDIT.md`
- `docs/tasks/DEMO_D2_S1_EXECUTION_PLAN.md` → `docs/archive/task-history/DEMO_D2_S1_EXECUTION_PLAN.md`
- `docs/tasks/DEMO_D2_S1_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S1_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C10_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C10_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C11_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C11_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C12_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C12_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C13_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C13_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C14_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C14_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C15_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C15_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C2_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C2_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C3_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C3_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C4_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C4_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C5_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C5_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C6_ARCHITECTURE_GATE.md` → `docs/archive/task-history/DEMO_D2_S2_C6_ARCHITECTURE_GATE.md`
- `docs/tasks/DEMO_D2_S2_C6_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C6_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_S2_C7_ARCHITECTURE_GATE.md` → `docs/archive/task-history/DEMO_D2_S2_C7_ARCHITECTURE_GATE.md`
- `docs/tasks/DEMO_D2_S2_C7_TERRA_TASK.md` → `docs/archive/task-history/DEMO_D2_S2_C7_TERRA_TASK.md`
- `docs/tasks/DEMO_D2_SCENARIO_MARKETING_AUDIT.md` → `docs/archive/task-history/DEMO_D2_SCENARIO_MARKETING_AUDIT.md`
- `docs/tasks/DEMO_D2_SERVICE_VOLUME.md` → `docs/archive/task-history/DEMO_D2_SERVICE_VOLUME.md`
- `docs/tasks/DEMO_D2_SIM1_TASK.md` → `docs/archive/task-history/DEMO_D2_SIM1_TASK.md`
- `docs/tasks/DEMO_D2_SIM2_TASK.md` → `docs/archive/task-history/DEMO_D2_SIM2_TASK.md`
- `docs/tasks/DEMO_D2_SIM3_TASK.md` → `docs/archive/task-history/DEMO_D2_SIM3_TASK.md`
- `docs/tasks/DEMO_D2_SIM4_TASK.md` → `docs/archive/task-history/DEMO_D2_SIM4_TASK.md`
- `docs/tasks/DEMO_D2_STAGE2_MEMORY_UI_TASK.md` → `docs/archive/task-history/DEMO_D2_STAGE2_MEMORY_UI_TASK.md`
- `docs/tasks/DEMO_D2_STAGE3_PRICES_SCOPE_TASK.md` → `docs/archive/task-history/DEMO_D2_STAGE3_PRICES_SCOPE_TASK.md`
- `docs/tasks/DEMO_D2_STAGE4_MIXED_RESPONSE_TASK.md` → `docs/archive/task-history/DEMO_D2_STAGE4_MIXED_RESPONSE_TASK.md`
- `docs/tasks/DEMO_D2_STAGE_TASK_MINI_PROMPT.md` → `docs/archive/task-history/DEMO_D2_STAGE_TASK_MINI_PROMPT.md`
- `docs/tasks/DEMO_MODEL_PRICE_EXPERIMENT.md` → `docs/archive/task-history/DEMO_MODEL_PRICE_EXPERIMENT.md`
- `docs/tasks/DEMO_D2_INTERFACE_TASK.md` → full snapshot `docs/archive/checkpoints/DEMO_D2_INTERFACE_TASK.md`; original path remains current
- `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md` → full snapshot `docs/archive/checkpoints/DEMO_D2_DELIVERY_ROADMAP.md`; original path remains current
- `AGENTS.md`
- `docs/CURRENT_ARCHITECTURE.md`
- `docs/MARKETING_ANSWER_SCENARIOS.md`
- `docs/MARKETING_EDITING_GUIDE.md`
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md`
- `docs/README.md`
- `docs/WIDGET_ANSWER_FORMAT.md`
- `docs/archive/README.md`
- `docs/archive/pre-d2/tasks/DEMO_D2_CURRENT_STATUS.md`
- `docs/tasks/DEMO_D2_ACCEPTANCE.md`
- `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`
- `docs/tasks/DEMO_D2_CURRENT_STATUS.md`
- `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`
- `docs/tasks/DEMO_D2_EXECUTION_LOCK.md`
- `docs/tasks/DEMO_D2_INTERFACE_TASK.md`
- `docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md`
- `docs/tasks/DEMO_D2_TARGET_CONTRACT.md`
- `docs/tasks/README.md`

Validation: original narratives preserved except warnings/link relocation/EOL/
trailing whitespace; file/link/old-fragment targets preserved; current entrylinks
and exactallowlist/diffcheck. IndependentChecker before save. No pytest needed
for docs-only delta; prior821PASS5platformSKIP and GitHubCIgreen are dated evidence,
not a new run or fullhistoricaltestPASS. Remainingrootdocs/readerbindings/evidence,
SIM/REC classification and useful-testinventory still unresolved. KB/VPSuntouched.

§60.8 verification: independentCheckerPASS, planned120/actual119authorizedpaths,
52archivednarratives retained;334existingfiletargets and21fragments valid.
No readers of50movedbasenames; entrylinks and whitespacePASS; ExecutionLock
protections/sourcepriority preserved. No freshpytest/provider/live/SMTPcalls;
no runtime/test/workflow/clientKB/VPSedits, noforeignWIP, stagingemptybeforecheckpoint.


#### 60.8 Focused relocated secret-scan false positive

Baselineb7a49ce, samebranch/root/main, preflightclean. Bug fix in CI finding
metadata, not runtime simplification. Exactadditionalallowlist:.gitleaksignore,
thiscard. GitHubscan38429390522 flagged generic-api-key in the archived snapshot
at2694. Existing explicitfalsepositive approval is bc26997:oldInterface:2673.
Full13linecontext equal byte-for-text atnew/oldlocations; ordinaryoffline test
reportprose, not credential/privatepayload. Preserve oldfingerprint and add only
newfinding b7a49ce:newarchivepath:generic-api-key:2694. No wholepath/ruleallowlist,
no scan bypass/runtime/workflow change. New scan must confirm exact exception;
focusedindependentChecker before save. Provider/live0; foreignWIP0.

FocusedCheckerPASS:13linecontextmatch independentlyconfirmed, preciseexisting
falsepositivefingerprintrelocation, no scanweakening. Allother4GitHubjobs onb7a49ce
SUCCESS; onlysecretjobfailed. Nextcommit must triggerGitHubscan to verify fix.


### 60.9 Historical reference labels and current debt pointer

Documentation only. Owner GO: continue remaining cleanup without runtime/client
changes or revival of obsolete tests. Repo/topC:/Cursor Projects/artgents-bot-active;
branchcodex/docs-tests-cleanup; baseline22917cc; main/base8888fdd; preflightclean/WIP0.
Allowlist: docs/ARCH_TARGET_DESIGN.md; ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md;
PATIENT_SCOPE_DESIGN_A9.md; MARKETING_TARGET_MIGRATION_AUDIT.md; TECH_DEBT.md;
archive/legacy-plans/TECH_DEBT.md; HISTORICAL_READERS.md; README.md; archive/README.md;
CurrentStatus,Roadmap,thiscard undertasks.

Four preserved-path source documents receive historical banner afterfirsttitle;
all originalbytes retained (no body rewrites). Existing ARCH/STRANGLER warnings
remain. Referenceindex distinguishes basename references from actual readers and
lists known tests/evals paths; no authority to execute them or restore legacy.
TECH_DEBT oldJulybacklog preservedinarchive (links/EOL/trailingformat only), stable
path becomes currentpointer to knownunresolved coverage/KB/acceptance/risk/deploy.
No new behavior, modelcalls, tests, workflows, data or requirements introduced.
Current release selection unchanged. Prior22917cc GitHubCI5jobsPASS is dated
proof, not freshpytest/livequality. Validate preservation/entrylinks/exactscope/
diffcheck; independentChecker before checkpoint. Useful-test retirement remains
futureclassifiedwork; not all references mean obsolete-only tests.

§60.9 independentCheckerPASS: exact12docs,4sourcebodies preserved;Julybacklog
retained; referencecounts7/3/2/1/7/12 independentlyconfirmed, core/scripts/deploy0.
No runtime/test/coveragechange; newentrylinks/whitespace/diffcheckPASS;
stagingempty/foreignWIP0 before checkpoint; provider/live0. Freshpytestnotrequired.


### 60.10 Retire cancelled ONE_CALL wiring assertions

Test/doc cleanup, not runtime simplification. Repo/topC:/Cursor Projects/artgents-bot-active;
branchcodex/docs-tests-cleanup; baselinef8c1700; origin/main/mergebase8888fdd;
preflightclean/foreignWIP0. OwnerGO continue cleanup, no revival obsolete tests.
Exactallowlist: tests/test_sales_one_plus_governance.py,test_d2_native_price_runtime.py;
docs/TEST_SUITE_ARCHITECTURE.md,HISTORICAL_READERS.md; taskCurrentStatus,Roadmap,thiscard.

Original7cases baseline2FAIL5PASS. Remove3cases (2FAIL1PASS), not just redones:
app oldhttp_provider_budget_scope/_orchestrate_ask_turn_inner stringrequirements;
planner SALES_ONE_PLUS_ON marker; archivedQwen backend SALES_ONE_PLUS_FLASH_MODEL.
No callers/imports of removedtestfunctions found. Keep4helper/fixturetests and
one_call_stage2_fixture imports: budgetmodule+llmwrappers still serve historical
probe accounting, frozenmedical/admin evidence isn't broad cancellationauthority.
Do not remove actual protections just because these old wiring owners changed.

Trace current /ask,/ask/stream →d2_http_adapter→d2_dialogue→D2HttpProvider._call;
actualmodeluses self.model, currentadmissionviaD2DemoLimits, nativecompletionknown
result→sameprovider. No legacy app budget context/planner selection on this path.
Currentequivalentguards: test_d2_demo_session_budget thirtiethcall/freeReplay/atomic;
test_d2_demo_limits failurecharged/released and pretransportdenial/other-tenant;
native_price_runtime exactinvocationcount/error/commit boundary. Existing native
success2cases/failure6cases strengthened with configured-test-model assertion for
allordinary/selection/completion calls; no extra testcases/calls/semantic decisions.
Runtime/CIselection/clientKB/VPS unchanged; provider/live/SMTP0.
Targeted remaining4helper+native37+session3+limits12+selection/G2/G3 and Checker.
FullcurrentGitHubCI beforemerge, not fullhistorical suite or livequality claim.

§60.10 finaltargeted:4remaininghelper +native37+session3+limits12+selection9+
G2/G3 56=121PASS79.30s. Existingdatetimewarnings only. IndependentCheckerPASS,
own15PASS29deselected,4remainingfunctions ASTidentical and currentcallpath traced.
No runtime/workflow/clientdata change, provider/live0, exact7paths/diffcheckPASS;
fullhistoricalsuite notcertified. Previous2failures belong onlycancelledwiring,
not newregressions. GitHubcurrentCI aftersave validatesreleaseboundary separately.


## 61. Clinic factual grounding and proportionate answer detail

OwnerGO: stronger grounding only for clinic-specific services/materials/prices/terms;
general dental knowledge/comparisons remain permitted. Mild brevity, no fixed caps.
Prompt bugfix/tuning, not architecture simplification. Explicit extension of former
docs/tests-only scope: existing instructions only; no new execution mechanism.
Repo/topC:/Cursor Projects/artgents-bot-active; branchcodex/docs-tests-cleanup;
baseline983c4b4; origin/main/mergebase8888fdd; preflightclean/foreignWIP0.
Exactallowlist: core/one_call_prompt_contract.py; tests/test_d2_text_reply.py;
tests/test_d2_native_price_runtime.py; docs/BOT_BEHAVIOR.md; taskCurrentStatus,
Roadmap,thiscard. Owner writes China MD separately; no clientdata changes.

Shared text appended to existing ordinary/known-task instructions; nativecompletion
retains original system. Existing version46→47. Clinic facts require approved data;
general knowledge doesn't establish offered technique/material. Missing detail isn't
unavailability; explicit policies retained. General dental reasoning permitted without
unsupported clinic promises; medical boundaries intact. Length follows complexity,
removes redundancy/repeated invitations, preserves arguments/conditions/exclusions;
no word/paragraph cap or max_tokens change. No phrase-specific filling/China branch,
classifier/verifier/retry/tool/state/schema/modelcall added.
Offline tests check actual ordinary/known provider inputs and nativecompletion;
existing lead/UI/metadata/price/invocation guards retained. Delivery evidence cannot
prove live model compliance. No live agentcalls for this new checkpoint; no new hard
budget agreed. IndependentChecker+targeted tests; widget/model quality separate.

Ownerrefinement§61: explicitly prefer compact/substantive answers bydefault,
not exhaustive adjacent-topic overviews; still no fixed paragraph/word limit.
Clinic-specific restriction onlythisclinic, general dental/China reasoning permitted.

§61 evidence: executor93PASS80.68s; final compact-default wording followed by
focused4PASS6.61s; independentCheckerPASS64PASS. Exact7paths/diffcheckPASS;
provider/live0. Windows ignoredlogrotation file-in-use and datetimewarnings
observed without assertionfailures; no loggingchanges. LocalhealthGET200, no model
request. Shared instructions delivery verified; actualmodel/widgetbehavior notcertified.


## 62. Document section guidance

Ownerapproved exactinstruction: generalquestion uses#korotko ifpresent; add
relevantmicrofacts/essentialconditions, notwhole-document overview; directsection
question usesmatchingsection(s), clickedfollowup chosenquestion, no automatic
korotko intro; preservefullcurrentanswer/conditions, don'tcopyverbatim.
Prompttuning only, notarchitecture simplification. Baselinea2a90c5, root/top
C:/Cursor Projects/artgents-bot-active; branchcodex/docs-tests-cleanup;
origin/main/mergebase8888fdd; preflightclean, foreignWIP0.
Exactallowlist: core/one_call_prompt_contract.py; docs/BOT_BEHAVIOR.md;
taskInterface/Roadmap/CurrentStatus. Sharedexistingguidance ordinary/known/native
completion, version47→48. No renderer/source selection/UI filtering/change,
no classifier/controlfields/state/schema/tools/calls/retry. Sections staydata,
existingvalidated clickedsource remains solebinding. No content or ChinaMD edits.
Existingproviderdelivery tests verify sharedsystem once and nativeinheritance;
no implementation-mirroring newtests. IndependentChecker before save.
Offline provesdelivery only; no liveproviderbudget for thischeckpoint/calls0;
actualnatural-languagecompliance still ownerwidget review, not certified.

§62 executor5PASS10.42s; independentCheckerPASS/5PASS. ExistingWindows app.jsonl
rotation contention onexecutor (botopen) and datetimewarnings, no assertionfailures
or loggingchanges. Exact5paths/diffcheckPASS, stagingempty/foreignWIP0before save;
provider/live0; sharedguidance delivery established, modelcompliance notcertified.


## 63. Primary document owns follow-up — owner GO 2026-10-14

Bug fix: supplemental document currently erases the shared content_ref, losing
both first-visit follow-ups. Owner agreed for all themes: sources[0] is the
model-declared primary; subsequent entries supply facts only. Sole free-question
primary decision owner is the model. Code validates and executes that order;
known document clicks keep the server-authorized source. No new field/call/state.

Baseline: C:/Cursor Projects/artgents-bot-active, codex/docs-tests-cleanup,
HEAD1653489; origin/main and mergebase8888fdd. Foreign WIP: compact UI/font/promo,
arrow, unknown-tab label, Nobel tab label plus root4originalJPG. Preserve all.
Allowlist: core/one_call_prompt_contract.py; core/response_plan_materialization.py
(existing Nobel WIP preserved); tests/test_d2_primary_source_followups.py;
docs/BOT_BEHAVIOR.md; this card; DEMO_D2_DELIVERY_ROADMAP.md.

Remove all-source-reference equality as the prerequisite for source UI. Validate
all claims, preserve foreign-tenant failure and no UI for invalid primary; never
promote a later source. Preserve common_scope/mixed response-memory behavior,
marketing slot count, secondary UI price restrictions, click/revision ownership,
clicked follow-up suppression and two-slot limit. This is not suggest_refs support.

Acceptance: real offline HTTP/SSE first-visit + consultation sources, two topics
and reversed primary, invalid primary and supplemental sources, clicked document
binding; native price remains unchanged. Targeted tests plus independent Checker;
no live provider calls, no commit/push without a new owner instruction.

§63 evidence: 107 distinct targeted cases passed across primary-source HTTP/SSE,
text-protocol, current UI, native-price and demo release suites. Initial combined
boundary run:74PASS plus one new test failed due to wrong payload path; corrected
assertion uses ui.body_parts, focused recheck1PASS. No runtime change for that
failure. IndependentCheckerPASS; diffcheckPASS; staging empty; provider/live0.
Actual model primary selection quality still requires owner widget review.
