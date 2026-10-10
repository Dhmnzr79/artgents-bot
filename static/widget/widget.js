import { streamAsk } from "./api.js";
import { setBotAnswerBody } from "./answer_format.js";
import { friendlyErrorMessage } from "./api.js";

const STORAGE_SID = "clinic_widget_sid";
const STORAGE_LAUNCHER_TEASER = "clinic_widget_launcher_teaser_shown";
const DEFAULT_AVATAR_URL = "/static/avatar.png";
const LAUNCHER_TEASER_DELAY_MS = 30000;
const WELCOME_LEAVE_MS = 240;
const TEXTAREA_MAX_HEIGHT = 112;
const MOBILE_MAX_WIDTH_PX = 520;
const SCROLL_NEAR_BOTTOM_PX = 80;
const TURN_SCROLL_TOP_GAP_PX = 12;
const SCROLLBAR_IDLE_MS = 900;
const VIDEO_REVEAL_LABEL = "Посмотреть видео с врачом";
const TYPING_WRITING_MIN_MS = 200;
const BOT_SOURCE_ATTRIBUTION = "по материалам клиники";
const LEAD_ATTRIBUTION_LABEL = "Запись на консультацию";

/** @typedef {'content'|'lead'|'plain'} TurnAttributionKind */

const PLAIN_ATTRIBUTION_ROUTES = new Set([
  "lead_cancelled",
  "lead_deferred",
  "lead_offer_declined",
  "bare_affirmative",
  "guided",
  "continuation_clarify",
  "duplicate_short_circuit",
  "booking_flow",
  "rate_limited",
  "retrieval_no_candidates",
  "low_score_fallback",
  "error",
  "offtopic",
  "situation_collect",
  "situation_back",
  "target_fullcontext_terminal_clarify",
  "target_fullcontext_terminal_defer",
  "target_fullcontext_terminal_medical_handoff_nonmaterializable",
  "target_fullcontext_boundary_uncertain",
  "target_fullcontext_error",
  "target_fullcontext_verifier_blocked",
  "target_fullcontext_followup_unknown",
]);
/** Скрытый сброс сессии: «::reset <token>» (только demoLauncher / dev-хост). */
const SECRET_SESSION_RESET_RE = /^::reset\s+(\S+)\s*$/i;
const SECRET_SESSION_RESET_TOKEN = "x7k9m2p4";

const SEND_BTN_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const LINK_ARROW_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path d="M4 12h16M14 6l6 6-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const CTA_CALENDAR_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="5" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.75"/><path d="M8 3v4M16 3v4M3 10h18" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/></svg>`;

const SOURCE_BOOK_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v15M12 5C8 2 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-2-10 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
const MESSAGE_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 15a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h11a3 3 0 0 1 3 3Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
const SEARCH_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="6" stroke="currentColor" stroke-width="1.5"/><path d="m15 15 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
const CHECK_DOCUMENT_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 14l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const WRITE_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m15 4 5 5M3 21l2-7L17 2l5 5-12 12-7 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

/** @param {string} hex */
function _hexToRgb(hex) {
  const h = String(hex || "").replace("#", "").trim();
  if (h.length !== 6) return null;
  const n = Number.parseInt(h, 16);
  if (Number.isNaN(n)) return null;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** @param {[number, number, number]} rgb */
function _rgbCss(rgb) {
  return `${rgb[0]}, ${rgb[1]}, ${rgb[2]}`;
}

/** Light tint for composer/capsule (mix brand with white). */
function _mixHexWithWhite(hex, whiteRatio) {
  const rgb = _hexToRgb(hex);
  if (!rgb) return "";
  const w = Math.min(1, Math.max(0, whiteRatio));
  const mix = (c) => Math.round(c + (255 - c) * w);
  return `#${mix(rgb[0]).toString(16).padStart(2, "0")}${mix(rgb[1])
    .toString(16)
    .padStart(2, "0")}${mix(rgb[2]).toString(16).padStart(2, "0")}`;
}

/** Darken hex for fallback action / hover (ratio 0…1). */
function _darkenHex(hex, ratio = 0.1) {
  const rgb = _hexToRgb(hex);
  if (!rgb) return hex;
  const f = 1 - Math.min(1, Math.max(0, ratio));
  return `#${rgb
    .map((c) => Math.round(c * f).toString(16).padStart(2, "0"))
    .join("")}`;
}

/**
 * Apply ``config.theme`` CSS variables on the widget shell (overrides widget.css defaults).
 * Primary color: ``brand`` from brand.yaml, shared by buttons and outlines.
 * @param {HTMLElement | null} shellEl
 * @param {Record<string, string> | undefined} theme
 */
function applyWidgetTheme(shellEl, theme) {
  if (!shellEl || !theme || typeof theme !== "object") return;
  const brand = String(theme.brand || "").trim();
  if (!brand) return;
  const action = brand;
  const actionHover = _darkenHex(action, 0.1);

  shellEl.style.setProperty("--clinic-brand", brand);
  shellEl.style.setProperty("--clinic-action", action);
  shellEl.style.setProperty("--clinic-action-hover", actionHover);

  const brandRgb = _hexToRgb(brand);
  const actionRgb = _hexToRgb(action);
  if (brandRgb) {
    const rgb = _rgbCss(brandRgb);
    shellEl.style.setProperty("--clinic-brand-rgb", rgb);
    shellEl.style.setProperty("--clinic-bg-subtle", `rgba(${rgb}, 0.06)`);
    shellEl.style.setProperty("--clinic-chip-border", brand);
    shellEl.style.setProperty("--clinic-shadow", `0 8px 32px rgba(${rgb}, 0.14)`);
    shellEl.style.setProperty("--clinic-shadow-soft", `0 4px 16px rgba(${rgb}, 0.1)`);
    shellEl.style.setProperty("--clinic-bg-tint", _mixHexWithWhite(brand, 0.96));
    shellEl.style.setProperty("--clinic-composer-bg", _mixHexWithWhite(brand, 0.97));
    shellEl.style.setProperty("--clinic-composer-border", brand);
    shellEl.style.setProperty("--clinic-composer-focus-border", brand);
    shellEl.style.setProperty(
      "--clinic-composer-focus-shadow",
      `0 10px 28px rgba(${rgb}, 0.12)`
    );
  }
  if (actionRgb) {
    const argb = _rgbCss(actionRgb);
    shellEl.style.setProperty("--clinic-action-rgb", argb);
    shellEl.style.setProperty(
      "--clinic-focus",
      `0 0 0 2px rgba(255, 255, 255, 0.95), 0 0 0 4px rgba(${argb}, 0.32)`
    );
  }
}

/** @param {string | undefined} apiBase @param {string | undefined} path */
function resolvePackAssetUrl(apiBase, path) {
  const src = String(path || "").trim();
  if (!src) return "";
  if (/^https?:\/\//i.test(src)) return src;
  const base = (apiBase || "").replace(/\/$/, "");
  return base ? `${base}${src.startsWith("/") ? src : `/${src}`}` : src;
}

/**
 * @param {HTMLElement} el
 * @param {WidgetConfig} config
 */
function fillHeaderStatus(el, config) {
  const clinicName = String(config.clinicName || "").trim() || "клиники";
  el.textContent = `ИИ-консультант ${clinicName}`;
}


/** @param {unknown} meta */
function leadMetaPhoneStep(meta) {
  return Boolean(
    meta && typeof meta === "object" && meta.lead_flow && meta.lead_step === "phone"
  );
}

/** @param {unknown} payload */
function isActiveLeadFlowPayload(payload) {
  return Array.isArray(payload?.ui?.quick_replies) &&
    payload.ui.quick_replies.some((item) => String(item?.reply_id || "").startsWith("lead:"));
}

/** 10 цифр после «7» (пользователь может ввести 9… или 8… или уже +7…) */
function extractNational10Digits(raw) {
  let d = String(raw || "").replace(/\D/g, "");
  if (!d.length) return "";
  if (d.startsWith("8")) d = "7" + d.slice(1);
  if (d.startsWith("7")) return d.slice(1, 11);
  return d.slice(0, 10);
}

/** Отображение: +7(000) 000-00-00 */
function formatRuMobileDisplay(nationalUpTo10) {
  const n = nationalUpTo10.replace(/\D/g, "").slice(0, 10);
  if (!n.length) return "+7";
  let s = "+7(" + n.slice(0, 3);
  if (n.length <= 3) return s;
  s += ") " + n.slice(3, 6);
  if (n.length <= 6) return s;
  s += "-" + n.slice(6, 8);
  if (n.length <= 8) return s;
  s += "-" + n.slice(8, 10);
  return s;
}

function ruPhoneToBackendE164(inputVal) {
  const n = extractNational10Digits(inputVal);
  if (n.length !== 10) return "";
  return "+7" + n;
}

/**
 * @typedef {Object} StarterPrompt
 * @property {string} label
 * @property {string} [q]
 * @property {string} [videoKey] — открыть каталог клиента без текста запроса
 * @property {boolean} [soon] — кнопка видна, но пока не подключена
 */

/**
 * @typedef {Object} WidgetConfig
 * @property {string} [apiBase]
 * @property {string} clientId
 * @property {string} botName
 * @property {string} [avatarUrl]
 * @property {string} onlineLabel
 * @property {string} welcomeText
 * @property {StarterPrompt[]} starterPrompts
 * @property {Record<string, {src?: string, title?: string}>} [videoCatalog]
 * @property {"vertical"|"horizontal"} [videoAspect] — пропорции блока в ленте (9:16 или 16:9)
 * @property {boolean} [demoLauncher] — крупная карточка-превью с кнопкой (по умолчанию true)
 * @property {string} [launcherCtaLabel] — подпись кнопки запуска
 * @property {string} [clinicName] — название клиники из brand.yaml
 * @property {string} [logoUrl] — логотип первого экрана из brand.yaml
 * @property {number} [logoWidth] — ширина лого в px (как в Figma)
 * @property {number} [logoHeight] — высота лого в px (как в Figma)
 * @property {string} [launcherSubtitle] — должность на превью (fallback без clinicName)
 * @property {string} [launcherTagline] — вторая строка на превью
 * @property {boolean} [launcherTeaser] — подсказка у лаунчера через ~30 с (по умолчанию true)
 * @property {string} [launcherTeaserText] — текст подсказки
 */

/**
 * @param {unknown} data D2 HTTP payload saved for this turn.
 * @param {string} expectedClientId
 */
function botTurnFromPayload(data, expectedClientId) {
  if (!data || typeof data !== "object") return null;
  if (data.client_id !== expectedClientId || !Number.isInteger(data.revision)) return null;
  const ui = data.ui && typeof data.ui === "object" ? data.ui : {};
  const quickReplies = (Array.isArray(ui.quick_replies) ? ui.quick_replies : [])
    .filter((x) => x && x.source_client_id === expectedClientId && x.reply_id && x.label)
    .map((x) => ({ ref: String(x.reply_id), label: String(x.label) }));
  const ctaRaw = (Array.isArray(ui.buttons) ? ui.buttons : [])
    .find((x) => x && x.source_client_id === expectedClientId && x.action_kind === "cta");
  const cta = ctaRaw ? { text: String(ctaRaw.label), ref: `button:${ctaRaw.button_id}` } : null;
  const vk = ui.video?.source_client_id === expectedClientId ? String(ui.video.video_id || "") : "";

  return {
    role: "bot",
    text: String(data.answer || "").trim(),
    bodyParts: Array.isArray(ui.body_parts) ? ui.body_parts : [],
    followups: [],
    quickReplies,
    revision: data.revision,
    linksDismissed: false,
    videoKey: vk,
    videoSrc: "",
    videoTitleText: "",
    videoRevealed: false,
    situation: null,
    cta,
    trailingDismissed: false,
    attributionKind: resolveTurnAttributionKind(data),
    serviceRoute: "",
  };
}

function dismissTrailingsAll(messages) {
  for (const m of messages) {
    if (m.role === "bot") m.trailingDismissed = true;
  }
}

function dismissLinksAll(messages) {
  for (const m of messages) {
    if (m.role === "bot") m.linksDismissed = true;
  }
}

/** @returns {boolean} */
function isMobileViewport() {
  return (
    typeof matchMedia !== "undefined" &&
    matchMedia(`(max-width: ${MOBILE_MAX_WIDTH_PX}px)`).matches
  );
}

function autoResizeTextarea(textarea) {
  textarea.style.height = "auto";
  const next = Math.min(textarea.scrollHeight, TEXTAREA_MAX_HEIGHT);
  textarea.style.height = `${next}px`;
  textarea.style.overflowY =
    textarea.scrollHeight > TEXTAREA_MAX_HEIGHT ? "auto" : "hidden";
}

/** @param {string} [botName] */
function displayBotName(botName) {
  const name = String(botName || "").trim();
  return name || "Бот";
}

/** @param {string} [botName] */
function botSourceAttributionLabel(botName) {
  return `${displayBotName(botName)} · ${BOT_SOURCE_ATTRIBUTION}`;
}

/** @param {"searching"|"writing"} phase @param {string} [botName] */
function typingStatusLabel(phase, botName) {
  return phase === "writing"
    ? "Печатает ответ"
    : phase === "checking" ? "Проверяет информацию" : "Ищет в базе клиники";
}

/** @param {unknown} meta */
function isLeadFlowBotMeta(meta) {
  if (!meta || typeof meta !== "object" || !meta.lead_flow) return false;
  const step = String(meta.lead_step || "");
  return Boolean(step && step !== "done");
}

/**
 * @param {Record<string, unknown>} [body]
 * @param {unknown} lastPayload
 */
function isLeadFlowAskBody(body, lastPayload) {
  const ref = String(body?.ref || "");
  if (ref.startsWith("lead:") || ref.startsWith("button:")) return true;
  return isActiveLeadFlowPayload(lastPayload);
}

/** @returns {HTMLElement} */
function createLeadAttributionEl() {
  const el = document.createElement("div");
  el.className = "clinic-msg__attribution clinic-msg__attribution--lead";
  const icon = document.createElement("span");
  icon.className = "clinic-msg__attribution-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = CTA_CALENDAR_SVG;
  const text = document.createElement("span");
  text.className = "clinic-msg__attribution-text";
  text.textContent = LEAD_ATTRIBUTION_LABEL;
  el.appendChild(icon);
  el.appendChild(text);
  return el;
}

/** @param {string} route */
function isPlainAttributionRoute(route) {
  const r = String(route || "").trim();
  if (!r) return false;
  if (PLAIN_ATTRIBUTION_ROUTES.has(r)) return true;
  return r.startsWith("ingress_");
}

/** @param {unknown} meta @returns {TurnAttributionKind} */
function resolveTurnAttributionKind(meta) {
  if (meta && typeof meta === "object") {
    const explicit = String(meta.attribution_kind || "").trim().toLowerCase();
    if (explicit === "content" || explicit === "lead" || explicit === "plain") {
      return /** @type {TurnAttributionKind} */ (explicit);
    }
  }
  if (isLeadFlowBotMeta(meta)) return "lead";
  if (meta && typeof meta === "object") {
    if (meta.offtopic) return "plain";
    if (meta.situation_collect) return "plain";
    const route = String(meta.service_route || "");
    if (isPlainAttributionRoute(route)) return "plain";
  }
  return "plain";
}

/**
 * @param {Record<string, unknown>} [body]
 * @param {unknown} lastPayload
 * @returns {TurnAttributionKind}
 */
function predictLiveAttributionKind(body, lastPayload) {
  const ref = String(body?.ref || "").trim();
  if (ref === "lead:cancel") return "plain";
  if (isLeadFlowAskBody(body, lastPayload)) return "lead";
  return "plain";
}

/** @param {TurnAttributionKind} kind @param {string} [botName] @returns {HTMLElement} */
function createAttributionElForKind(kind, botName) {
  if (kind === "lead") return createLeadAttributionEl();
  if (kind === "plain") return createPlainAttributionEl(botName);
  return createBotAttributionEl(botName);
}

/** @param {string} [botName] @returns {HTMLElement} */
function createPlainAttributionEl(botName) {
  const el = document.createElement("div");
  el.className = "clinic-msg__attribution clinic-msg__attribution--plain";
  appendAttributionContent(el, MESSAGE_SVG, displayBotName(botName));
  return el;
}

/** @param {string} [botName] @param {{ attributionKind?: TurnAttributionKind }} [m] @returns {HTMLElement} */
function createTurnAttributionEl(botName, m) {
  const kind = m?.attributionKind || "plain";
  return createAttributionElForKind(kind, botName);
}

/** @param {string} [botName] @returns {HTMLElement} */
function createBotAttributionEl(botName) {
  const el = document.createElement("div");
  el.className = "clinic-msg__attribution";
  appendAttributionContent(el, SOURCE_BOOK_SVG, botSourceAttributionLabel(botName));
  return el;
}

function appendAttributionContent(el, svg, label) {
  const icon = document.createElement("span");
  icon.className = "clinic-msg__attribution-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = svg;
  const text = document.createElement("span");
  text.className = "clinic-msg__attribution-text";
  text.textContent = label;
  el.append(icon, text);
}

/**
 * Создаёт «живой» ответ в feed перед typing-wrap и скрывает typing indicator.
 * Вызывается лениво — только при первом text_delta.
 * @param {HTMLElement} feed
 * @param {string} [botName]
 * @param {TurnAttributionKind} [attributionKind]
 * @returns {HTMLElement} bubble
 */
function _createLiveBubble(feed, botName, attributionKind = "content") {
  const typingWrap = feed.querySelector(".clinic-shell__typing-wrap");
  const bubble = document.createElement("div");
  bubble.className = "clinic-msg clinic-msg--bot clinic-msg--bot--streaming";
  bubble.setAttribute("data-live-bubble", "");
  bubble.appendChild(createAttributionElForKind(attributionKind, botName));
  const body = document.createElement("div");
  body.className = "clinic-msg__body";
  bubble.appendChild(body);
  feed.insertBefore(bubble, typingWrap);
  if (typingWrap) typingWrap.classList.remove("is-visible");
  return bubble;
}

/**
 * Обновляет текст в живой bubble и скроллит вниз.
 * @param {HTMLElement} row
 * @param {string} text
 * @param {HTMLElement} feed
 */
/**
 * @param {HTMLElement} feedEl
 * @returns {HTMLElement | null}
 */
function getChatScroller(feedEl) {
  const feed = feedEl.closest(".clinic-shell__feed");
  if (!feed) return feedEl.closest(".clinic-shell__main");
  let node = feed;
  while (node) {
    const { overflowY } = getComputedStyle(node);
    if (overflowY === "auto" || overflowY === "scroll") return node;
    node = node.parentElement;
  }
  return feed.closest(".clinic-shell__main");
}

/**
 * Скроллбар: на десктопе полоска 2px, место в layout всегда; цвет ползунка — только при scroll.
 * @param {HTMLElement | null} scroller
 */
function bindTransientChatScrollbar(scroller) {
  if (!scroller || scroller.dataset.clinicScrollbarBound === "1") return;
  scroller.dataset.clinicScrollbarBound = "1";
  scroller.classList.add("clinic-chat-scrollbar");
  let hideTimer = 0;
  scroller.addEventListener(
    "scroll",
    () => {
      scroller.classList.add("is-scrolling");
      window.clearTimeout(hideTimer);
      hideTimer = window.setTimeout(() => {
        scroller.classList.remove("is-scrolling");
      }, SCROLLBAR_IDLE_MS);
    },
    { passive: true }
  );
}

/**
 * @param {HTMLElement} feedEl
 * @param {{ force?: boolean }} [opts]
 */
function scrollChatPaneToEnd(feedEl, opts = {}) {
  const scroller = getChatScroller(feedEl);
  if (!scroller) return;
  if (!opts.force) {
    const dist =
      scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    if (dist >= SCROLL_NEAR_BOTTOM_PX) return;
  }
  scroller.scrollTop = scroller.scrollHeight;
}

/**
 * Скроллит так, чтобы начало последнего bot-turn'а было видно сверху,
 * учитывая высоту липкой шапки внутри scroller'а.
 * @param {HTMLElement} feedEl
 */
function scrollToLastTurnStart(feedEl) {
  const scroller = getChatScroller(feedEl);
  if (!scroller) return;
  const turns = feedEl.querySelectorAll(".clinic-turn");
  const last = turns[turns.length - 1];
  if (!last) {
    scroller.scrollTop = scroller.scrollHeight;
    return;
  }
  const main = feedEl.closest(".clinic-shell__main");
  const header =
    scroller.querySelector(".clinic-shell__header--sticky") ||
    main?.querySelector(".clinic-shell__header--sticky");
  const headerH = header ? header.getBoundingClientRect().height : 0;
  const turnRect = last.getBoundingClientRect();
  const scrollerRect = scroller.getBoundingClientRect();
  const effectiveViewH = scroller.clientHeight - (scroller === main ? headerH : 0);

  if (turnRect.height + TURN_SCROLL_TOP_GAP_PX > effectiveViewH) {
    const target =
      scroller.scrollTop +
      (turnRect.top - scrollerRect.top) -
      (scroller === main ? headerH : 0) -
      TURN_SCROLL_TOP_GAP_PX;
    scroller.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
  } else {
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
  }
}

function _updateLiveBubble(bubble, text, feed) {
  const body = bubble.querySelector(".clinic-msg__body");
  if (body) setBotAnswerBody(body, text);
  scrollChatPaneToEnd(feed);
}

function isDevHost() {
  const host = location.hostname;
  if (host === "localhost" || host === "127.0.0.1" || host === "[::1]") return true;
  if (new URLSearchParams(location.search).get("dev") === "1") return true;
  return false;
}

/**
 * @param {string} text
 * @param {WidgetConfig} config
 */
function isSecretSessionResetCommand(text, config) {
  if (!config.demoLauncher && !isDevHost()) return false;
  const m = (text || "").trim().match(SECRET_SESSION_RESET_RE);
  if (!m) return false;
  return m[1] === SECRET_SESSION_RESET_TOKEN;
}

/**
 * Временно: кнопка сброса sid слева сверху (только dev-хост).
 * @param {() => void} onReset
 */
function attachDevResetControl(onReset) {
  if (!isDevHost()) return;
  if (document.querySelector("[data-clinic-dev-reset]")) return;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "clinic-dev-reset";
  btn.setAttribute("data-clinic-dev-reset", "");
  btn.textContent = "DEV · сброс sid";
  btn.title = "Очистить sid и историю. Ctrl+Alt+R";
  btn.addEventListener("click", onReset);
  document.body.appendChild(btn);

  if (!window.__clinicDevResetKeyBound) {
    window.__clinicDevResetKeyBound = true;
    document.addEventListener("keydown", (ev) => {
      if (!isDevHost()) return;
      if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === "r") {
        ev.preventDefault();
        onReset();
      }
    });
  }
}

/**
 * @param {HTMLElement} root
 * @param {WidgetConfig} config
 * @returns {{ resetSession: () => void }}
 */
/** Required presentation field: key must be present as string or null. */
function isRequiredNullableString(value) {
  return value === null || typeof value === "string";
}

/** Optional presentation field: may be omitted, null, or string. */
function isOptionalNullableString(value) {
  return value === undefined || value === null || typeof value === "string";
}

/** @param {unknown} prompts */
function starterPromptsValid(prompts) {
  if (!Array.isArray(prompts)) return false;
  for (const item of prompts) {
    if (!item || typeof item !== "object") return false;
    const s = /** @type {Record<string, unknown>} */ (item);
    if (typeof s.label !== "string" || !s.label.trim()) return false;
    if (s.q !== undefined && s.q !== null && typeof s.q !== "string") return false;
    if (s.videoKey !== undefined && s.videoKey !== null && typeof s.videoKey !== "string") {
      return false;
    }
    if (s.soon !== undefined && s.soon !== null && typeof s.soon !== "boolean") return false;
  }
  return true;
}

function isWidgetPresentationContractValid(config) {
  if (!config || typeof config !== "object") return false;
  if (config.schemaVersion !== 1) return false;
  if (typeof config.clientId !== "string" || !config.clientId.trim()) return false;
  if (typeof config.botName !== "string" || !config.botName.trim()) return false;
  if (typeof config.onlineLabel !== "string" || !config.onlineLabel.trim()) return false;
  if (typeof config.launcherCtaLabel !== "string" || !config.launcherCtaLabel.trim()) {
    return false;
  }
  if (!("welcomeText" in config) || !isRequiredNullableString(config.welcomeText)) {
    return false;
  }
  if (!("launcherSubtitle" in config) || !isRequiredNullableString(config.launcherSubtitle)) {
    return false;
  }
  if (!isOptionalNullableString(config.launcherTagline)) return false;
  if (!isOptionalNullableString(config.launcherTeaserText)) return false;
  if (!isOptionalNullableString(config.launcherMobileCtaLabel)) return false;
  if (typeof config.demoLauncher !== "boolean") return false;
  if (typeof config.launcherTeaser !== "boolean") return false;
  if (config.videoAspect !== "horizontal" && config.videoAspect !== "vertical") return false;
  if (!starterPromptsValid(config.starterPrompts)) return false;
  if (config.launcherTeaser === true) {
    if (typeof config.launcherTeaserText !== "string" || !config.launcherTeaserText.trim()) {
      return false;
    }
  }
  return true;
}

/** @param {HTMLElement} root */
function renderWidgetConfigError(root) {
  root.innerHTML = `
    <div class="clinic-shell clinic-shell--config-error" role="alert">
      <p class="clinic-shell__error clinic-shell__error--config">Виджет временно недоступен.</p>
    </div>`;
}

export function mountWidget(root, config) {
  let waitingLabelTimers = [];

  function clearWaitingLabelTimers() {
    waitingLabelTimers.forEach(window.clearTimeout);
    waitingLabelTimers = [];
  }
  if (!isWidgetPresentationContractValid(config)) {
    renderWidgetConfigError(root);
    return { resetSession: () => {} };
  }

  const apiBase = config.apiBase ?? "";
  const clientId = String(config.clientId).trim();
  const resolvedAvatarUrl = resolvePackAssetUrl(
    apiBase,
    (config.avatarUrl || "").trim() || DEFAULT_AVATAR_URL
  );

  const state = {
    isOpen: false,
    messages: [],
    lastPayload: null,
    retryBody: null,
    priceUpdate: null,
    pending: false,
    /** @type {"searching"|"writing"} */
    typingPhase: "searching",
    unread: false,
    started: false,
    errorLine: "",
    // PERF-0: local-only perf timestamp (ms via performance.now()), never
    // sent over the network — see PERF-0 seam audit client-timing finding.
    perfPendingStartMs: null,
    perfFirstLocalStatusLogged: false,
    // PERF-1: real-time status text from event: status (optional — old
    // servers/clients simply never set this, falling back to the existing
    // typingLabelForPhase() canned text unchanged).
    statusMessage: null,
  };

  /** @type {Record<string, { src: string, title: string }>} */
  const videoCatalogResolved = {};

  /** @param {unknown} patch */
  function ingestVideoCatalog(patch) {
    if (!patch || typeof patch !== "object") return;
    for (const [k, raw] of Object.entries(patch)) {
      if (!raw || typeof raw !== "object") continue;
      const src = String(/** @type {{ src?: unknown }} */ (raw).src || "").trim();
      if (!src) continue;
      videoCatalogResolved[String(k)] = {
        src,
        title: String(/** @type {{ title?: unknown }} */ (raw).title || "").trim(),
      };
    }
  }
  ingestVideoCatalog(config.videoCatalog);

  function mediaPlayUrl(key) {
    const base = (apiBase || "").replace(/\/$/, "");
    return `${base}/api/media/${encodeURIComponent(key)}?client_id=${encodeURIComponent(clientId)}`;
  }

  /** @param {string} [src] @param {string} [key] */
  function resolvePlaySrc(src, key) {
    const k = String(key || "").trim();
    if (k) return mediaPlayUrl(k);
    const s = String(src || "").trim();
    if (!s) return "";
    if (s.startsWith("/api/media/")) {
      const base = (apiBase || "").replace(/\/$/, "");
      return base ? `${base}${s}` : s;
    }
    return s;
  }

  let catalogFetchPromise = null;

  function fetchVideoCatalog() {
    if (!catalogFetchPromise) {
      catalogFetchPromise = (async () => {
        const base = (apiBase || "").replace(/\/$/, "");
        const url = `${base}/api/video-catalog?client_id=${encodeURIComponent(clientId)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error("video_catalog_failed");
        const data = await res.json();
        ingestVideoCatalog(data.videos);
      })().catch(() => {
        catalogFetchPromise = null;
      });
    }
    return catalogFetchPromise;
  }

  const useDemoLauncher = config.demoLauncher === true;
  const launcherCtaLabel = String(config.launcherCtaLabel || "").trim();
  const launcherMobileCtaLabel = String(
    config.launcherMobileCtaLabel || launcherCtaLabel
  ).trim();
  const clinicName = String(config.clinicName || "").trim();
  const launcherSubtitle = clinicName
    ? `ИИ-консультант «${clinicName}»`
    : config.launcherSubtitle == null
      ? ""
      : String(config.launcherSubtitle).trim();
  const launcherTagline =
    config.launcherTagline == null ? "" : String(config.launcherTagline).trim();
  const launcherTeaserEnabled = !useDemoLauncher && config.launcherTeaser === true;
  const launcherTeaserText =
    config.launcherTeaserText == null ? "" : String(config.launcherTeaserText).trim();

  const launcherHtml = useDemoLauncher
    ? `
      <button
        type="button"
        class="clinic-shell__launcher clinic-shell__launcher--demo"
        data-clinic-launcher-open
        aria-expanded="false"
        aria-controls="clinic-panel"
      ></button>`
    : `
      <button type="button" class="clinic-shell__launcher" data-clinic-launcher aria-expanded="false" aria-controls="clinic-panel">
        <span class="clinic-shell__unread" data-clinic-unread aria-hidden="true"></span>
        <div class="clinic-shell__launcher-row">
          <div class="clinic-shell__launcher-avatar">
            <span class="clinic-shell__avatar-fallback clinic-shell__avatar-fallback--launcher" data-clinic-avatar-fb>
              <img class="clinic-shell__avatar-fallback-img" alt="" width="40" height="40" data-clinic-avatar />
            </span>
            <span class="clinic-shell__header-online-dot clinic-shell__header-online-dot--launcher" aria-hidden="true"></span>
          </div>
          <div class="clinic-shell__launcher-text">
            <span class="clinic-shell__name" data-clinic-name></span>
            <span class="clinic-shell__launcher-subtitle" data-clinic-launcher-subtitle></span>
            <span class="clinic-shell__launcher-tagline" data-clinic-launcher-tagline></span>
            <span class="clinic-shell__launcher-mobile-headline" data-clinic-launcher-mobile-headline></span>
            <span class="clinic-shell__launcher-mobile-online">Онлайн 24/7</span>
          </div>
        </div>
      </button>`;

  root.innerHTML = `
    <div class="clinic-shell" data-clinic-root>
      <button
        type="button"
        class="clinic-shell__launcher-teaser"
        data-clinic-launcher-teaser
        hidden
        aria-label="Открыть чат с консультантом"
      >
        <span class="clinic-shell__launcher-teaser-text" data-clinic-launcher-teaser-text></span>
      </button>
      ${launcherHtml}
      <div class="clinic-shell__panel" id="clinic-panel" role="dialog" aria-modal="true" aria-label="Чат" data-clinic-panel>
        <main class="clinic-shell__main" aria-label="Сообщения">
          <header class="clinic-shell__header clinic-shell__header--sticky">
            <div class="clinic-shell__header-main">
              <div class="clinic-shell__header-avatar">
                <span class="clinic-shell__avatar-fallback clinic-shell__avatar-fallback--header" data-clinic-header-fb>
                  <img class="clinic-shell__avatar-fallback-img" alt="" width="48" height="48" data-clinic-header-avatar />
                </span>
                <span class="clinic-shell__header-online-dot" aria-hidden="true"></span>
              </div>
              <div class="clinic-shell__header-text">
                <span class="clinic-shell__header-name" data-clinic-header-name></span>
                <span class="clinic-shell__header-status" data-clinic-header-online></span>
              </div>
            </div>
            <div class="clinic-shell__header-actions">
              <button type="button" class="clinic-shell__header-close clinic-btn-icon clinic-btn-ghost" data-clinic-close title="Свернуть" aria-label="Свернуть чат">✕</button>
            </div>
          </header>
          <div class="clinic-shell__feed" data-clinic-feed></div>
        </main>
        <form class="clinic-shell__composer" data-clinic-composer-form>
          <div class="clinic-shell__composer-inner">
            <textarea class="clinic-shell__textarea" rows="1" data-clinic-input placeholder="Введите сообщение" aria-label="Введите сообщение"></textarea>
            <button type="submit" class="clinic-btn-send" data-clinic-send disabled aria-label="Отправить сообщение">${SEND_BTN_SVG}</button>
          </div>
        </form>
      </div>
    </div>
  `;

  const shell = root.querySelector("[data-clinic-root]");
  applyWidgetTheme(shell, config.theme);
  const launcher = root.querySelector("[data-clinic-launcher]");
  const launcherOpenBtn = root.querySelector("[data-clinic-launcher-open]");
  const launcherControl = launcherOpenBtn || launcher;
  const launcherLinkEl = root.querySelector(".clinic-shell__launcher-link");
  if (launcherLinkEl) launcherLinkEl.textContent = launcherCtaLabel;
  if (launcherOpenBtn && useDemoLauncher) {
    launcherOpenBtn.textContent = launcherCtaLabel;
    launcherOpenBtn.setAttribute("aria-label", launcherCtaLabel);
  }
  for (const el of root.querySelectorAll("[data-clinic-launcher-mobile-headline]")) {
    el.textContent = launcherMobileCtaLabel;
  }
  if (launcher) launcher.setAttribute("aria-label", launcherMobileCtaLabel);
  const panel = root.querySelector("[data-clinic-panel]");
  const feed = root.querySelector("[data-clinic-feed]");
  const chatMain = root.querySelector(".clinic-shell__main");
  bindTransientChatScrollbar(chatMain);
  bindTransientChatScrollbar(feed);
  const input = root.querySelector("[data-clinic-input]");
  const sendBtn = root.querySelector("[data-clinic-send]");
  const composerForm = root.querySelector("[data-clinic-composer-form]");
  const unreadDot = root.querySelector("[data-clinic-unread]");
  const btnClose = root.querySelector("[data-clinic-close]");
  const launcherTeaserEl = root.querySelector("[data-clinic-launcher-teaser]");
  const launcherTeaserTextEl = root.querySelector("[data-clinic-launcher-teaser-text]");

  const avatarImg = root.querySelector("[data-clinic-avatar]");
  const hAvatar = root.querySelector("[data-clinic-header-avatar]");

  const launcherNameEl = root.querySelector("[data-clinic-launcher-name]");
  if (launcherNameEl) launcherNameEl.textContent = config.botName;
  const compactNameEl = root.querySelector("[data-clinic-name]");
  if (compactNameEl) compactNameEl.textContent = config.botName;
  for (const el of root.querySelectorAll("[data-clinic-launcher-subtitle]")) {
    el.textContent = launcherSubtitle;
  }
  for (const el of root.querySelectorAll("[data-clinic-launcher-tagline]")) {
    el.textContent = launcherTagline;
  }
  root.querySelector("[data-clinic-header-name]").textContent = config.botName;
  fillHeaderStatus(root.querySelector("[data-clinic-header-online]"), config);

  const alt = (config.botName || "Бот").trim();
  if (avatarImg) {
    avatarImg.alt = alt;
    avatarImg.src = resolvedAvatarUrl;
  }
  hAvatar.alt = alt;
  hAvatar.src = resolvedAvatarUrl;

  const videoAspectMode =
    config.videoAspect === "horizontal" ? "horizontal" : "vertical";

  /** @param {object} m */
  function getVideoPlayInfo(m) {
    const key = String(m.videoKey || "").trim();
    const src = resolvePlaySrc(m.videoSrc, key);
    if (!src) return null;
    const title =
      String(m.videoTitleText || "").trim() ||
      (key && videoCatalogResolved[key]?.title) ||
      "";
    return { src, title, key };
  }

  /** @param {HTMLVideoElement} except */
  function pauseOtherInlineVideos(except) {
    feed.querySelectorAll(".clinic-msg__video-player").forEach((node) => {
      if (node !== except && node instanceof HTMLVideoElement) {
        try {
          node.pause();
        } catch {
          /* ignore */
        }
      }
    });
  }

  /**
   * @param {HTMLElement} bubble
   * @param {object} m
   */
  function appendInlineVideo(bubble, m) {
    const info = getVideoPlayInfo(m);
    if (!info) return;

    const wrap = document.createElement("div");
    wrap.className = `clinic-msg__video clinic-msg__video--${videoAspectMode}`;

    const vid = document.createElement("video");
    vid.className = "clinic-msg__video-player";
    vid.controls = true;
    vid.playsInline = true;
    vid.preload = "metadata";
    vid.setAttribute("aria-label", info.title || "Видео");
    vid.src = info.src;
    vid.addEventListener("play", () => pauseOtherInlineVideos(vid));
    vid.addEventListener("error", () => {
      const err = document.createElement("p");
      err.className = "clinic-msg__video-error";
      err.textContent = "Не удалось загрузить видео.";
      if (!wrap.querySelector(".clinic-msg__video-error")) wrap.appendChild(err);
    });

    wrap.appendChild(vid);
    if (info.title) {
      const cap = document.createElement("p");
      cap.className = "clinic-msg__video-caption";
      cap.textContent = info.title;
      wrap.appendChild(cap);
    }

    bubble.classList.add("clinic-msg--has-video");
    bubble.appendChild(wrap);
  }

  /**
   * @param {HTMLElement} bubble
   * @returns {HTMLElement}
   */
  function getOrCreateLinksBox(bubble) {
    let box = bubble.querySelector(".clinic-msg__links");
    if (!box) {
      box = document.createElement("div");
      box.className = "clinic-msg__links";
      bubble.appendChild(box);
    }
    return box;
  }

  /**
   * Кнопка «Посмотреть видео…» или плеер после нажатия.
   * @param {HTMLElement} bubble
   * @param {object} m
   * @param {number} msgIndex
   */
  function appendVideoOffer(bubble, m, msgIndex) {
    const info = getVideoPlayInfo(m);
    if (!info) return;

    if (m.videoRevealed) {
      appendInlineVideo(bubble, m);
      return;
    }

    const box = getOrCreateLinksBox(bubble);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "clinic-msg__link";
    const lab = document.createElement("span");
    lab.className = "clinic-msg__link-text";
    lab.textContent = VIDEO_REVEAL_LABEL;
    const chev = document.createElement("span");
    chev.className = "clinic-msg__link-chevron";
    chev.setAttribute("aria-hidden", "true");
    chev.innerHTML = LINK_ARROW_SVG;
    btn.appendChild(lab);
    btn.appendChild(chev);
    btn.setAttribute("aria-label", VIDEO_REVEAL_LABEL);
    btn.addEventListener("click", () => {
      const target = state.messages[msgIndex];
      if (!target || target.role !== "bot") return;
      target.videoRevealed = true;
      renderFeed();
    });
    box.appendChild(btn);
  }

  /**
   * @param {string} key
   * @param {string} userLabel
   */
  async function pushWelcomeVideoTurn(key, userLabel) {
    const vk = String(key || "").trim();
    if (!vk) return;
    await fetchVideoCatalog();
    const cat = videoCatalogResolved[vk];
    state.messages.push({ role: "user", text: userLabel });
    state.messages.push({
      role: "bot",
      text: "",
      videoKey: vk,
      videoSrc: cat?.src || mediaPlayUrl(vk),
      videoTitleText: cat?.title || "",
      videoRevealed: true,
      followups: [],
      quickReplies: [],
      linksDismissed: false,
      situation: null,
      cta: null,
      trailingDismissed: false,
      attributionKind: "plain",
    });
    renderFeed();
  }

  autoResizeTextarea(input);

  let launcherTeaserTimer = 0;

  function wasLauncherTeaserShown() {
    try {
      return sessionStorage.getItem(STORAGE_LAUNCHER_TEASER) === "1";
    } catch {
      return false;
    }
  }

  function markLauncherTeaserShown() {
    try {
      sessionStorage.setItem(STORAGE_LAUNCHER_TEASER, "1");
    } catch {
      /* ignore */
    }
  }

  function clearLauncherTeaserTimer() {
    if (launcherTeaserTimer) {
      clearTimeout(launcherTeaserTimer);
      launcherTeaserTimer = 0;
    }
  }

  function dismissLauncherTeaser() {
    shell.classList.remove("is-launcher-teaser");
    if (launcherTeaserEl) launcherTeaserEl.hidden = true;
  }

  function showLauncherTeaser() {
    if (!launcherTeaserEnabled || state.isOpen || wasLauncherTeaserShown()) return;
    markLauncherTeaserShown();
    if (launcherTeaserTextEl) launcherTeaserTextEl.textContent = launcherTeaserText;
    if (launcherTeaserEl) launcherTeaserEl.hidden = false;
    shell.classList.add("is-launcher-teaser");
  }

  function scheduleLauncherTeaser() {
    if (!launcherTeaserEnabled || wasLauncherTeaserShown()) return;
    clearLauncherTeaserTimer();
    launcherTeaserTimer = window.setTimeout(() => {
      launcherTeaserTimer = 0;
      if (!state.isOpen) showLauncherTeaser();
    }, LAUNCHER_TEASER_DELAY_MS);
  }

  function cancelLauncherTeaser() {
    clearLauncherTeaserTimer();
    markLauncherTeaserShown();
    dismissLauncherTeaser();
  }

  function getSid() {
    try {
      return localStorage.getItem(STORAGE_SID) || "";
    } catch {
      return "";
    }
  }

  function setSid(sid) {
    if (!sid) return;
    try {
      localStorage.setItem(STORAGE_SID, sid);
    } catch {
      /* ignore */
    }
  }

  function clearStoredSid() {
    try {
      localStorage.removeItem(STORAGE_SID);
    } catch {
      /* ignore */
    }
  }

  function resetSession() {
    clearWaitingLabelTimers();
    if (state.pending) return;
    clearStoredSid();
    state.messages = [];
    state.lastPayload = null;
    state.retryBody = null;
    state.priceUpdate = null;
    state.typingPhase = "searching";
    state.started = false;
    state.unread = false;
    unreadDot?.classList.remove("is-visible");
    setError("");
    pauseOtherInlineVideos(/** @type {HTMLVideoElement} */ (null));
    input.value = "";
    renderFeed();
  }

  async function runSecretSessionReset() {
    if (state.pending) return;
    input.value = "";
    autoResizeTextarea(input);
    syncSendState();
    resetSession();
  }

  function openChatFromLauncher() {
    if (state.isOpen) return;
    setOpen(true);
    renderFeed();
  }

  /** @type {number} */
  let bodyScrollLockY = 0;
  /** @type {(() => void) | null} */
  let mobileViewportHandler = null;

  function updateMobileViewportHeight() {
    const h = window.visualViewport?.height ?? window.innerHeight;
    shell.style.setProperty("--clinic-vvh", `${Math.round(h)}px`);
  }

  function lockHostPageScroll() {
    bodyScrollLockY = window.scrollY;
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${bodyScrollLockY}px`;
    document.body.style.left = "0";
    document.body.style.right = "0";
    document.body.style.width = "100%";
  }

  function unlockHostPageScroll() {
    document.documentElement.style.overflow = "";
    document.body.style.overflow = "";
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.left = "";
    document.body.style.right = "";
    document.body.style.width = "";
    window.scrollTo(0, bodyScrollLockY);
  }

  function bindMobileViewportListeners() {
    if (mobileViewportHandler) return;
    shell.classList.add("is-mobile-fullscreen");
    updateMobileViewportHeight();
    mobileViewportHandler = () => updateMobileViewportHeight();
    window.visualViewport?.addEventListener("resize", mobileViewportHandler);
    window.visualViewport?.addEventListener("scroll", mobileViewportHandler);
    window.addEventListener("resize", mobileViewportHandler);
  }

  function unbindMobileViewportListeners() {
    if (!mobileViewportHandler) return;
    window.visualViewport?.removeEventListener("resize", mobileViewportHandler);
    window.visualViewport?.removeEventListener("scroll", mobileViewportHandler);
    window.removeEventListener("resize", mobileViewportHandler);
    mobileViewportHandler = null;
    shell.classList.remove("is-mobile-fullscreen");
    shell.style.removeProperty("--clinic-vvh");
  }

  function syncMobileShellClass() {
    shell.classList.toggle("is-mobile", isMobileViewport());
  }

  function setOpen(open) {
    state.isOpen = open;
    syncMobileShellClass();
    shell.classList.toggle("is-open", open);
    if (launcherControl) {
      launcherControl.setAttribute("aria-expanded", open ? "true" : "false");
    }
    panel.setAttribute("aria-hidden", open ? "false" : "true");
    if (open) {
      cancelLauncherTeaser();
      state.unread = false;
      unreadDot?.classList.remove("is-visible");
      if (isMobileViewport()) {
        lockHostPageScroll();
        bindMobileViewportListeners();
      } else {
        input.focus();
      }
    } else {
      if (isMobileViewport()) {
        unlockHostPageScroll();
        unbindMobileViewportListeners();
      }
      launcherControl?.focus();
    }
  }

  /** @returns {string} */
  function typingLabelForPhase(phase) {
    return typingStatusLabel(phase, config.botName);
  }

  function fillTypingLabel(labelWrap, text) {
    const base = labelWrap.querySelector(".clinic-shell__typing-label-base");
    const shine = labelWrap.querySelector(".clinic-shell__typing-label-shine");
    if (base) base.textContent = text;
    if (shine) shine.textContent = text;
  }

  function createTypingLabelEl() {
    const wrap = document.createElement("span");
    wrap.className = "clinic-shell__typing-label";
    const icon = document.createElement("span");
    icon.className = "clinic-shell__typing-icon";
    icon.setAttribute("aria-hidden", "true");
    wrap.appendChild(icon);
    const words = document.createElement("span");
    words.className = "clinic-shell__typing-words";
    const base = document.createElement("span");
    base.className = "clinic-shell__typing-label-base";
    const shine = document.createElement("span");
    shine.className = "clinic-shell__typing-label-shine";
    shine.setAttribute("aria-hidden", "true");
    words.appendChild(base);
    words.appendChild(shine);
    wrap.appendChild(words);
    return wrap;
  }

  function updateTypingIndicatorText() {
    const bubble = feed.querySelector(".clinic-shell__typing");
    const labelWrap = feed.querySelector(".clinic-shell__typing-label");
    if (!bubble || !labelWrap) return;
    fillTypingLabel(labelWrap, typingLabelForPhase(state.typingPhase));
    const icon = labelWrap.querySelector(".clinic-shell__typing-icon");
    if (icon) icon.innerHTML = state.typingPhase === "writing" ? WRITE_SVG
      : state.typingPhase === "checking" ? CHECK_DOCUMENT_SVG : SEARCH_SVG;
    bubble.classList.toggle("clinic-shell__typing--shimmer", state.typingPhase === "searching");
  }

  /** PERF-1: honest early status text (event: status). No-op for old servers —
   * state.statusMessage simply stays null and the existing canned phase label
   * (typingLabelForPhase) keeps rendering exactly as before this milestone.
   * @param {string} message */
  function setStatusMessage(message) {
    if (!message || message === state.statusMessage) return;
    state.statusMessage = message;
    updateTypingIndicatorText();
  }

  function beginPendingRequest(body) {
    clearWaitingLabelTimers();
    state.pending = true;
    const leadRequest = isLeadFlowAskBody(body, state.lastPayload)
      || state.lastPayload?.attribution_kind === "lead";
    state.typingPhase = leadRequest ? "writing" : "searching";
    state.perfPendingStartMs = performance.now();
    state.perfFirstLocalStatusLogged = false;
    state.statusMessage = null;
    renderFeed();
    updateTypingIndicatorText();
    if (!leadRequest && !state.priceUpdate) {
      // Cosmetic waiting sequence, not backend stages or a second model check.
      for (const [delay, phase] of [[1500, "checking"], [3500, "writing"]]) {
        waitingLabelTimers.push(window.setTimeout(() => {
          if (!state.pending) return;
          state.typingPhase = phase;
          updateTypingIndicatorText();
        }, delay));
      }
    }
  }

  /** @param {"searching"|"writing"} phase */
  function setTypingPhase(phase) {
    const next = phase === "writing" ? "writing" : "searching";
    if (next === "writing") clearWaitingLabelTimers();
    if (next === "searching" && state.typingPhase !== "searching") return;
    if (state.typingPhase === next) return;
    state.typingPhase = next;
    updateTypingIndicatorText();
  }

  function endPendingRequest() {
    clearWaitingLabelTimers();
    state.pending = false;
    state.typingPhase = "searching";
    state.statusMessage = null;
  }

  /**
   * @param {HTMLElement} feed
   * @param {string} apiBase
   * @param {Record<string, unknown>} body
   */
  const PSEUDO_STREAM_MAX_MS = 1200;
  const PSEUDO_WORDS_PER_STEP = 5;

  function shouldSkipPseudoStream() {
    if (typeof document !== "undefined" && document.hidden) return true;
    return (
      typeof matchMedia !== "undefined" &&
      matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  /** @param {string} text */
  function pseudoStreamChunks(text) {
    const chunks = [];
    const re = /\S+\s*/gu;
    let match = re.exec(text);
    while (match) {
      chunks.push(match[0]);
      match = re.exec(text);
    }
    return chunks;
  }

  function runStreamAsk(feed, apiBase, body) {
    let liveBubble = null;
    let fullText = "";
    let uiData = null;
    let writingRevealTimer = 0;
    let pseudoStreamTimer = 0;
    let turnFinalized = false;
    let streamAborted = false;
    let liveAttributionKind = predictLiveAttributionKind(body, state.lastPayload);

    const clearWritingRevealTimer = () => {
      if (writingRevealTimer) {
        clearTimeout(writingRevealTimer);
        writingRevealTimer = 0;
      }
    };

    const clearPseudoStreamTimer = () => {
      if (pseudoStreamTimer) {
        clearTimeout(pseudoStreamTimer);
        pseudoStreamTimer = 0;
      }
    };

    const clearStreamTimers = () => {
      clearWritingRevealTimer();
      clearPseudoStreamTimer();
    };

    const revealLiveBubble = () => {
      if (turnFinalized) return;
      clearWritingRevealTimer();
      if (!liveBubble && fullText.length > 0) {
        liveBubble = _createLiveBubble(feed, config.botName, liveAttributionKind);
        _updateLiveBubble(liveBubble, fullText, feed);
      } else if (liveBubble) {
        _updateLiveBubble(liveBubble, fullText, feed);
      }
    };

    const commitStreamMismatch = () => {
      if (turnFinalized) return;
      turnFinalized = true;
      streamAborted = true;
      clearStreamTimers();
      liveBubble = null;
      fullText = "";
      uiData = null;
      if (typeof console !== "undefined" && console.error) {
        console.error("[widget] stream_final_answer_mismatch");
      }
      setError("Не удалось отобразить ответ. Попробуйте ещё раз.");
      endPendingRequest();
      renderFeed();
      syncSendState();
    };

    const commitFinalTurn = () => {
      if (turnFinalized) return;
      const preserveScroll = state.priceUpdate?.requestId === body.request_id;
      turnFinalized = true;
      clearStreamTimers();
      const streamedText = fullText.trim();
      if (uiData) {
        if (uiData.sid) setSid(uiData.sid);
        const turn = botTurnFromPayload(uiData, clientId);
        if (turn) {
          const update = state.priceUpdate;
          if (update?.requestId === body.request_id) {
            const old = update.message;
            const cardIndex = old.bodyParts.findIndex((part) => part.kind === "price_card");
            const nextCardIndex = turn.bodyParts.findIndex((part) => part.kind === "price_card");
            const oldCard = old.bodyParts[cardIndex];
            const nextCard = turn.bodyParts[nextCardIndex];
            if (!state.messages.includes(old) || !nextCard || !oldCard
                || nextCard.price?.rows?.length !== 1
                || nextCard.price.rows[0].service_id !== oldCard.price.rows[0].service_id
                || body.ref !== `price_select:${nextCard.price.rows[0].offer_id}`) {
              setError("Не удалось отобразить ответ. Попробуйте ещё раз.");
            } else {
              // Replace price-owned content at its existing anchors. Independent
              // text (e.g. an address between price and promotion) stays in place.
              const before = turn.bodyParts.slice(0, nextCardIndex).filter(p => p.price_owned);
              const after = turn.bodyParts.slice(nextCardIndex + 1).filter(p => p.price_owned);
              const merged = [];
              let beforeInserted = false, afterInserted = false;
              old.bodyParts.forEach((part, index) => {
                if (part.price_owned) {
                  if (index < cardIndex && !beforeInserted) { merged.push(...before); beforeInserted = true; }
                  if (index > cardIndex && !afterInserted) { merged.push(...after); afterInserted = true; }
                } else if (index === cardIndex) {
                  if (!beforeInserted) { merged.push(...before); beforeInserted = true; }
                  merged.push(nextCard);
                } else merged.push(part);
              });
              if (!afterInserted) merged.push(...after);
              Object.assign(old, turn, {bodyParts: merged});
            }
          } else state.messages.push(turn);
        }
        state.priceUpdate = null;
        state.lastPayload = uiData;
        state.retryBody = null;
        if (!state.isOpen) state.unread = true;
      } else if (streamedText) {
        state.messages.push({
          role: "bot",
          text: streamedText,
          followups: [],
          quickReplies: [],
          linksDismissed: false,
          videoKey: "",
          videoSrc: "",
          videoTitleText: "",
          videoRevealed: false,
          situation: null,
          cta: null,
          trailingDismissed: false,
          attributionKind: liveAttributionKind,
        });
      }
      liveBubble = null;
      endPendingRequest();
      if (state.unread && !state.isOpen) unreadDot?.classList.add("is-visible");
      renderFeed({preserveScroll});
      syncSendState();
    };

    const revealPseudoToFinal = (finalText) => {
      if (turnFinalized || streamAborted) return;
      if (!finalText.startsWith(fullText)) {
        commitStreamMismatch();
        return;
      }
      if (fullText === finalText || shouldSkipPseudoStream()) {
        fullText = finalText;
        commitFinalTurn();
        return;
      }
      const suffix = finalText.slice(fullText.length);
      const chunks = pseudoStreamChunks(suffix);
      if (chunks.length <= 3) {
        fullText = finalText;
        commitFinalTurn();
        return;
      }
      const steps = Math.max(1, Math.ceil(chunks.length / PSEUDO_WORDS_PER_STEP));
      const interval = Math.min(PSEUDO_STREAM_MAX_MS / steps, 400);
      let index = 0;
      const prefix = fullText;
      state.typingPhase = "writing";
      clearWaitingLabelTimers();
      updateTypingIndicatorText();
      const tick = () => {
        if (turnFinalized || streamAborted) return;
        index = Math.min(chunks.length, index + PSEUDO_WORDS_PER_STEP);
        fullText = prefix + chunks.slice(0, index).join("");
        if (!liveBubble && fullText) {
          liveBubble = _createLiveBubble(feed, config.botName, liveAttributionKind);
        }
        if (liveBubble) {
          _updateLiveBubble(liveBubble, fullText, feed);
        }
        if (index >= chunks.length) {
          fullText = finalText;
          commitFinalTurn();
          return;
        }
        pseudoStreamTimer = window.setTimeout(tick, interval);
      };
      tick();
    };

    const finalizeTurn = () => {
      if (turnFinalized || streamAborted) return;
      if (!uiData) {
        commitFinalTurn();
        return;
      }
      const turn = botTurnFromPayload(uiData, clientId);
      const finalText = turn ? String(turn.text || "") : "";
      // A card is complete structured content, not prose to type and replace.
      if (turn?.bodyParts.some((part) => part.kind === "price_card")) {
        if (fullText.trim() && !finalText.startsWith(fullText.trim())) commitStreamMismatch();
        else commitFinalTurn();
        return;
      }
      if (!finalText) {
        commitFinalTurn();
        return;
      }
      const streamedText = fullText.trim();
      if (!streamedText) {
        revealPseudoToFinal(finalText);
        return;
      }
      if (streamedText === finalText) {
        commitFinalTurn();
        return;
      }
      if (finalText.startsWith(streamedText)) {
        revealPseudoToFinal(finalText);
        return;
      }
      commitStreamMismatch();
    };

    const logFirstLocalStatusOnce = () => {
      if (state.perfFirstLocalStatusLogged || typeof state.perfPendingStartMs !== "number") return;
      state.perfFirstLocalStatusLogged = true;
      if (typeof console !== "undefined" && console.debug) {
        console.debug("[perf] time_to_first_local_status_ms", Math.round(performance.now() - state.perfPendingStartMs));
      }
    };

    return streamAsk(apiBase, body, {
      onStatus(message) {
        // PERF-1: the real first local status now — old servers never send
        // event: status, so this simply never fires and onTyping below is the
        // fallback measurement point, exactly like before this milestone.
        logFirstLocalStatusOnce();
        setStatusMessage(message);
      },
      onTyping(phase) {
        logFirstLocalStatusOnce();
        setTypingPhase(phase);
      },
      onDelta(delta) {
        if (turnFinalized) return;
        const chunk = String(delta || "");
        if (!chunk) return;
        fullText += chunk;

        if (!liveBubble) {
          if (state.typingPhase !== "writing") {
            setTypingPhase("writing");
            if (!writingRevealTimer) {
              writingRevealTimer = window.setTimeout(revealLiveBubble, TYPING_WRITING_MIN_MS);
            }
            return;
          }
          if (state.typingPhase === "writing" && !writingRevealTimer) {
            revealLiveBubble();
            return;
          }
        }

        if (liveBubble) {
          _updateLiveBubble(liveBubble, fullText, feed);
        }
      },
      onUi(data) {
        if (turnFinalized || uiData) return;
        uiData = data;
        liveAttributionKind = resolveTurnAttributionKind(data);
        if (liveBubble) {
          liveBubble.querySelector(".clinic-msg__attribution")?.replaceWith(
            createAttributionElForKind(liveAttributionKind, config.botName));
        }
      },
      onDone() {
        finalizeTurn();
      },
      onError(msg, retryable) {
        if (turnFinalized) return;
        const preserveScroll = state.priceUpdate?.requestId === body.request_id;
        streamAborted = true;
        clearStreamTimers();
        state.retryBody = retryable ? body : null;
        if (!retryable) state.priceUpdate = null;
        setError(msg);
        endPendingRequest();
        renderFeed({preserveScroll});
        syncSendState();
      },
    });
  }

  function setError(msg) {
    state.errorLine = friendlyErrorMessage(msg) || "";
  }

  function renderErrorTurn() {
    if (!state.errorLine) return;
    const wrap = document.createElement("div");
    wrap.className = "clinic-turn clinic-turn--error";
    wrap.setAttribute("data-clinic-err", "");
    wrap.setAttribute("aria-live", "polite");
    wrap.appendChild(createPlainAttributionEl(config.botName));
    const bubble = document.createElement("div");
    bubble.className = "clinic-msg clinic-msg--bot";
    const text = document.createElement("div");
    text.className = "clinic-msg__body";
    text.textContent = state.errorLine;
    bubble.appendChild(text);
    wrap.appendChild(bubble);
    const controls = document.createElement("div");
    controls.className = "clinic-turn__error-actions";
    if (state.retryBody) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "clinic-btn-ghost";
      retry.textContent = "Повторить запрос";
      retry.addEventListener("click", () => {
        const body = state.retryBody;
        if (!body || state.pending) return;
        setError("");
        beginPendingRequest(body);
        void runStreamAsk(feed, apiBase, body);
      });
      controls.appendChild(retry);
    }
    if (clientId === "demo") {
      const fresh = document.createElement("button");
      fresh.type = "button";
      fresh.className = "clinic-btn-ghost";
      fresh.textContent = "Новая беседа";
      fresh.addEventListener("click", resetSession);
      controls.appendChild(fresh);
    }
    if (controls.children.length) wrap.appendChild(controls);
    feed.appendChild(wrap);
  }

  /**
   * @param {HTMLElement} bubble
   * @param {object} m
   * @param {number} msgIndex
   */
  function renderInlineLinks(bubble, m, msgIndex) {
    if (m.linksDismissed || m.revision !== state.lastPayload?.revision) return;
    const items = (m.quickReplies || []).filter((it) => !String(it.ref).startsWith("price_select:"));
    if (!items.length) return;

    const box = getOrCreateLinksBox(bubble);
    if (items.some((it) => String(it.ref || "").startsWith("volume:"))) {
      box.classList.add("clinic-msg__links--with-volume");
    }
    for (const it of items) {
      if (!it.ref) continue;
      const btn = document.createElement("button");
      btn.type = "button";
      const isVolume = String(it.ref).startsWith("volume:");
      btn.className = isVolume ? "clinic-msg__volume-chip" : "clinic-msg__link";
      const lab = document.createElement("span");
      lab.className = "clinic-msg__link-text";
      lab.textContent = it.label || it.ref;
      const chev = document.createElement("span");
      chev.className = "clinic-msg__link-chevron";
      chev.setAttribute("aria-hidden", "true");
      chev.innerHTML = LINK_ARROW_SVG;
      btn.appendChild(lab);
      if (!isVolume) btn.appendChild(chev);
      btn.addEventListener("click", () => {
        const target = state.messages[msgIndex];
        if (target && target.role === "bot") target.linksDismissed = true;
        dismissTrailingsAll(state.messages);
        const echo = (it.label || it.ref || "").trim();
        void sendAsk({ ref: it.ref, ui_revision: m.revision, q: "", userEcho: echo });
      });
      box.appendChild(btn);
    }
  }

  /**
   * @param {HTMLElement} wrap
   * @param {object} m
   * @param {number} msgIndex
   */
  function renderTrail(wrap, m, msgIndex) {
    if (m.role !== "bot" || m.trailingDismissed) return;

    const trail = document.createElement("div");
    trail.className = "clinic-turn__trail";

    if (m.cta && m.cta.text && m.revision === state.lastPayload?.revision) {
      const c = document.createElement("button");
      c.type = "button";
      c.className = "clinic-turn__btn clinic-turn__btn--cta-primary";
      const ctaLabel = (m.cta.text || "Записаться на консультацию").trim();
      c.textContent = ctaLabel;
      c.addEventListener("click", () => {
        dismissTrailingsAll(state.messages);
        dismissLinksAll(state.messages);
        const echo = (m.cta.text || "Запись").trim();
        void sendAsk({ ref: m.cta.ref, ui_revision: m.revision, q: "", userEcho: echo });
      });
      trail.appendChild(c);
    }

    if (trail.children.length) wrap.appendChild(trail);
  }

  function renderFeed({preserveScroll = Boolean(state.priceUpdate)} = {}) {
    // Updating an existing card is not a new turn. Keep the reader's viewport
    // through both the pending render and the confirmed replacement.
    const scroller = preserveScroll ? getChatScroller(feed) : null;
    const scrollTop = scroller?.scrollTop;
    const prevWelcome = feed.querySelector(".clinic-shell__welcome-screen");
    const keepWelcome = prevWelcome && !state.started;

    if (keepWelcome && prevWelcome) {
      prevWelcome.remove();
    }

    feed.textContent = "";
    const typing = document.createElement("div");
    typing.className = "clinic-shell__typing";
    if (state.typingPhase === "searching") {
      typing.classList.add("clinic-shell__typing--shimmer");
    }
    typing.setAttribute("aria-live", "polite");
    const typingLabel = createTypingLabelEl();
    typing.appendChild(typingLabel);

    if (keepWelcome && prevWelcome) {
      feed.appendChild(prevWelcome);
    } else if (!state.started) {
      const screen = document.createElement("section");
      screen.className = "clinic-shell__welcome-screen";
      screen.setAttribute("aria-label", "Приветствие");

      const card = document.createElement("section");
      card.className = "clinic-shell__welcome-card";

      const lead = document.createElement("div");
      lead.className = "clinic-shell__welcome-lead";
      const textP = document.createElement("p");
      textP.className = "clinic-shell__welcome-text";
      const textBody = document.createElement("span");
      textBody.className = "clinic-shell__welcome-text-body";
      textBody.textContent = String(config.welcomeText || "").trim();
      textP.classList.add("is-done");
      textP.appendChild(textBody);
      lead.appendChild(textP);

      card.appendChild(lead);

      const actions = document.createElement("div");
      actions.className = "clinic-shell__welcome-actions";
      const linksBox = document.createElement("div");
      linksBox.className = "clinic-msg__links";
      for (const s of config.starterPrompts || []) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "clinic-msg__link";
        if (s.soon) b.classList.add("clinic-msg__link--soon");
        const lab = document.createElement("span");
        lab.className = "clinic-msg__link-text";
        lab.textContent = s.label;
        const chev = document.createElement("span");
        chev.className = "clinic-msg__link-chevron";
        chev.setAttribute("aria-hidden", "true");
        chev.innerHTML = LINK_ARROW_SVG;
        b.appendChild(lab);
        b.appendChild(chev);
        if (s.soon) {
          b.disabled = true;
          b.setAttribute("aria-disabled", "true");
          b.title = "Скоро";
        } else if (s.videoKey) {
          const vk = String(s.videoKey).trim();
          const label = s.label || "Видео";
          b.addEventListener("click", () => {
            transitionFromWelcome(() => {
              void pushWelcomeVideoTurn(vk, label);
            });
          });
        } else {
          b.addEventListener("click", () => {
            transitionFromWelcome(() => {
              input.value = String(s.q || s.label || "").trim();
              void sendFromComposer();
            });
          });
        }
        linksBox.appendChild(b);
      }
      actions.appendChild(linksBox);

      screen.appendChild(card);
      screen.appendChild(actions);
      feed.appendChild(screen);
    }

    state.messages.forEach((m, idx) => {
      if (m.role === "user") {
        const row = document.createElement("div");
        row.className = "clinic-row clinic-row--user";
        const bubble = document.createElement("div");
        bubble.className = "clinic-msg clinic-msg--user";
        bubble.textContent = m.text;
        row.appendChild(bubble);
        feed.appendChild(row);
        return;
      }

      const wrap = document.createElement("div");
      wrap.className = "clinic-turn";

      wrap.appendChild(createTurnAttributionEl(config.botName, m));

      const bubble = document.createElement("div");
      bubble.className = "clinic-msg clinic-msg--bot";
      const text = String(m.text || "").trim();
      if (m.bodyParts?.some((part) => part.kind === "price_card")) {
        renderPriceBody(bubble, m);
      } else if (text) {
        const body = document.createElement("div");
        body.className = "clinic-msg__body";
        setBotAnswerBody(body, text);
        bubble.appendChild(body);
      }
      appendVideoOffer(bubble, m, idx);
      renderInlineLinks(bubble, m, idx);
      wrap.appendChild(bubble);
      renderTrail(wrap, m, idx);
      feed.appendChild(wrap);
    });

    renderErrorTurn();
    const typingWrap = document.createElement("div");
    typingWrap.className = "clinic-shell__typing-wrap";
    fillTypingLabel(typingLabel, typingLabelForPhase(state.typingPhase));
    typingLabel.querySelector(".clinic-shell__typing-icon").innerHTML =
      state.typingPhase === "writing" ? WRITE_SVG
      : state.typingPhase === "checking" ? CHECK_DOCUMENT_SVG : SEARCH_SVG;
    typingWrap.appendChild(typing);
    typingWrap.classList.toggle("is-visible", state.pending && !state.priceUpdate);
    feed.appendChild(typingWrap);

    const lastMsg = state.messages.length
      ? state.messages[state.messages.length - 1]
      : null;
    if (scroller) {
      scroller.scrollTo({top: scrollTop, behavior: "instant"});
    } else if (lastMsg && lastMsg.role === "bot") {
      requestAnimationFrame(() => scrollToLastTurnStart(feed));
    } else {
      scrollChatPaneToEnd(feed, { force: state.messages.length > 0 });
    }
    syncComposerLeadUi();
    syncSendState();
  }

  function renderPriceBody(bubble, message) {
    let texts = [];
    const flushText = () => {
      if (!texts.length) return;
      const body = document.createElement("div");
      body.className = "clinic-msg__body";
      setBotAnswerBody(body, texts.join("\n\n"));
      bubble.appendChild(body);
      texts = [];
    };
    for (const part of message.bodyParts) {
      if (part.kind === "text") { texts.push(part.text); continue; }
      if (part.kind !== "price_card" || part.price?.source_client_id !== clientId) continue;
      flushText();
      const rows = part.price.rows || [];
      if (!rows.length || rows.some((row) => row.source_client_id !== clientId)) continue;
      const card = document.createElement("section");
      card.className = "clinic-price-card";
      card.setAttribute("aria-label", rows[0].service_name);
      const title = document.createElement("h3");
      title.className = "clinic-price-card__title";
      title.textContent = rows[0].service_name;
      card.appendChild(title);
      if ((part.choices || []).length > 1) {
        const tabs = document.createElement("div");
        tabs.className = "clinic-price-card__tabs";
        tabs.setAttribute("role", "group");
        tabs.setAttribute("aria-label", "Вариант");
        for (const choice of part.choices) {
          const active = choice.reply_id === `price_select:${rows[0].offer_id}`;
          const tab = document.createElement("button");
          tab.type = "button";
          tab.className = "clinic-price-card__tab";
          tab.textContent = choice.label;
          tab.setAttribute("aria-pressed", String(active));
          tab.disabled = state.pending || message.linksDismissed || message.revision !== state.lastPayload?.revision;
          tab.addEventListener("click", () => {
            if (!active) void sendAsk({ref: choice.reply_id, ui_revision: message.revision,
              q: "", priceMessage: message});
          });
          tabs.appendChild(tab);
        }
        card.appendChild(tabs);
      }
      const terms = rows.map((row) => [...new Set([row.scope_text, ...(row.condition_texts || [])].filter(Boolean))]);
      const common = terms[0].filter((term) => terms.every((list) => list.includes(term)));
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const item = document.createElement("div");
        item.className = "clinic-price-card__variant";
        if (row.variant_label && !(part.choices || []).length) {
          const label = document.createElement("span");
          label.className = "clinic-price-card__brand";
          label.textContent = row.variant_label;
          item.appendChild(label);
        }
        const price = document.createElement("strong");
        price.className = "clinic-price-card__amount";
        if (row.mode === "no_public_price") price.classList.add("clinic-price-card__amount--description");
        else if (rows.length === 1) price.classList.add("clinic-price-card__amount--single");
        price.textContent = row.price_display_text;
        item.appendChild(price);
        card.appendChild(item);
        for (const term of terms[i].filter((text) => !common.includes(text))) {
          const note = document.createElement("p");
          note.className = "clinic-price-card__condition";
          note.textContent = term;
          card.appendChild(note);
        }
      }
      for (const term of common) {
        const note = document.createElement("p");
        note.className = "clinic-price-card__condition";
        note.textContent = term;
        card.appendChild(note);
      }
      bubble.appendChild(card);
    }
    flushText();
  }

  /**
   * @param {() => void} done
   */
  function transitionFromWelcome(done) {
    const welcome = feed.querySelector(".clinic-shell__welcome-screen");
    if (!welcome || state.started) {
      done();
      return;
    }
    welcome.classList.add("is-leaving");
    window.setTimeout(() => {
      state.started = true;
      done();
    }, WELCOME_LEAVE_MS);
  }

  async function sendAsk(extra = {}) {
    if (state.pending || state.retryBody) return;
    const userEcho =
      typeof extra.userEcho === "string" ? extra.userEcho.trim() : "";
    const apiFields = { ...extra };
    delete apiFields.userEcho;
    delete apiFields.priceMessage;

    if (userEcho) {
      const applyUserEcho = () => {
        dismissTrailingsAll(state.messages);
        dismissLinksAll(state.messages);
        if (userEcho) {
          state.messages.push({ role: "user", text: userEcho });
        }
      };
      if (!state.started && feed.querySelector(".clinic-shell__welcome-screen")) {
        await new Promise((resolve) => {
          transitionFromWelcome(() => {
            applyUserEcho();
            resolve();
          });
        });
      } else {
        if (!state.started) {
          state.started = true;
        }
        applyUserEcho();
      }
    }

    const sid = getSid();
    const body = {
      client_id: clientId,
      sid,
      request_id: crypto.randomUUID(),
      q: "",
      ...apiFields,
    };
    if (body.q === undefined) body.q = "";
    state.priceUpdate = extra.priceMessage ? {message: extra.priceMessage, requestId: body.request_id} : null;

    setError("");
    beginPendingRequest(body);
    await runStreamAsk(feed, apiBase, body);
  }

  async function sendFromComposer() {
    if (state.pending || state.retryBody) return;

    const raw = input.value.trim();
    if (isSecretSessionResetCommand(raw, config)) {
      await runSecretSessionReset();
      return;
    }

    let q = raw;
    let userBubbleText = q;

    if (isLeadPhoneStep()) {
      const backend = ruPhoneToBackendE164(input.value);
      if (backend.length !== 12) return;
      q = backend;
      userBubbleText = formatRuMobileDisplay(extractNational10Digits(input.value));
    } else if (!q) {
      return;
    }

    const runSend = async () => {
      dismissTrailingsAll(state.messages);
      dismissLinksAll(state.messages);
      state.messages.push({ role: "user", text: userBubbleText });
      input.value = "";
      autoResizeTextarea(input);
      sendBtn.disabled = true;
      setError("");

      const sid = getSid();
      const askBody = { client_id: clientId, sid, request_id: crypto.randomUUID(), q };
      beginPendingRequest(askBody);
      await runStreamAsk(feed, apiBase, askBody);
    };

    if (!state.started && feed.querySelector(".clinic-shell__welcome-screen")) {
      transitionFromWelcome(() => {
        void runSend();
      });
      return;
    }
    if (!state.started) {
      state.started = true;
    }
    await runSend();
  }

  function isLeadPhoneStep() {
    const m = state.lastPayload?.meta;
    return leadMetaPhoneStep(m);
  }

  function syncComposerLeadUi() {
    const phone = isLeadPhoneStep();
    input.inputMode = phone ? "numeric" : "text";
    input.classList.toggle("clinic-shell__textarea--phone", phone);
    input.placeholder = phone ? "+7(900) 000-00-00" : "Введите сообщение";
  }

  function onComposerInput() {
    if (isLeadPhoneStep()) {
      const nat = extractNational10Digits(input.value);
      const next = formatRuMobileDisplay(nat);
      if (next !== input.value) {
        input.value = next;
        input.selectionStart = input.selectionEnd = next.length;
      }
    }
    autoResizeTextarea(input);
    syncSendState();
  }

  function syncSendState() {
    if (state.pending || state.retryBody) {
      sendBtn.disabled = true;
      return;
    }
    if (isLeadPhoneStep()) {
      sendBtn.disabled = extractNational10Digits(input.value).length !== 10;
      return;
    }
    sendBtn.disabled = !input.value.trim();
  }

  if (launcherTeaserEl) {
    launcherTeaserEl.addEventListener("click", () => {
      openChatFromLauncher();
    });
  }

  if (launcherOpenBtn) {
    launcherOpenBtn.addEventListener("click", () => {
      openChatFromLauncher();
    });
  } else if (launcher) {
    launcher.addEventListener("click", () => {
      setOpen(!state.isOpen);
      renderFeed();
    });
  }

  btnClose.addEventListener("click", () => {
    setOpen(false);
  });

  input.addEventListener("input", onComposerInput);

  input.addEventListener("focus", () => {
    if (!isMobileViewport()) return;
    requestAnimationFrame(() => scrollChatPaneToEnd(feed, { force: true }));
  });

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      void sendFromComposer();
    }
  });

  composerForm.addEventListener("submit", (ev) => {
    ev.preventDefault();
    void sendFromComposer();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && state.isOpen) {
      setOpen(false);
    }
  });

  syncMobileShellClass();
  if (typeof matchMedia !== "undefined") {
    matchMedia(`(max-width: ${MOBILE_MAX_WIDTH_PX}px)`).addEventListener("change", () => {
      syncMobileShellClass();
      if (!state.isOpen) return;
      if (isMobileViewport()) {
        lockHostPageScroll();
        bindMobileViewportListeners();
      } else {
        unlockHostPageScroll();
        unbindMobileViewportListeners();
      }
    });
  }

  renderFeed();
  if (launcherTeaserEnabled) scheduleLauncherTeaser();

  void fetchVideoCatalog().then(() => renderFeed());

  attachDevResetControl(resetSession);

  setOpen(false);

  return { resetSession };
}
