import { postAsk, streamAsk } from "./api.js";
import { setBotAnswerBody } from "./answer_format.js";

const STORAGE_SID = "clinic_widget_sid";
const STORAGE_LAUNCHER_TEASER = "clinic_widget_launcher_teaser_shown";
const DEFAULT_AVATAR_URL = "/static/avatar.png";
const LAUNCHER_TEASER_DELAY_MS = 30000;
const DEFAULT_LAUNCHER_TEASER_TEXT =
  "Есть вопросы? Задайте их онлайн консультанту.";

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
]);
/** Синхронно с config.BOOKING_INTENT_RE — до ответа сервера не показываем «базу знаний». */
const BOOKING_INTENT_RE =
  /(?:запишите\s+меня|хочу\s+запис(?:аться|ать)\b|запись\s+на\s+(?:консультац|приём|прием)|остав(?:ить|лю)\s+заявку|(?<!\bкак\s)(?<!\bгде\s)(?<!\bкуда\s)\bзапис(?:аться|ать)\b(?:\s+на\s+(?:консультац|приём|прием))?)/iu;

/** Скрытый сброс сессии: «::reset <token>» (только demoLauncher / dev-хост). */
const SECRET_SESSION_RESET_RE = /^::reset\s+(\S+)\s*$/i;
const SECRET_SESSION_RESET_TOKEN = "x7k9m2p4";

const SEND_BTN_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const LINK_CHEVRON_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const CTA_CALENDAR_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="5" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.75"/><path d="M8 3v4M16 3v4M3 10h18" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/></svg>`;

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
 * Palette: ``brand``, ``action``, ``button_1``/``button_2`` (градиент кнопок), и др. from brand.yaml.
 * @param {HTMLElement | null} shellEl
 * @param {Record<string, string> | undefined} theme
 */
function applyWidgetTheme(shellEl, theme) {
  if (!shellEl || !theme || typeof theme !== "object") return;
  const brand = String(theme.brand || "").trim();
  if (!brand) return;
  const action = String(theme.action || "").trim() || _darkenHex(brand, 0.28);
  const actionHover = _darkenHex(action, 0.1);

  const button1 = String(theme.button_1 || "").trim() || brand;
  const button2 = String(theme.button_2 || "").trim() || _darkenHex(brand, 0.12);

  shellEl.style.setProperty("--clinic-brand", brand);
  shellEl.style.setProperty("--clinic-action", action);
  shellEl.style.setProperty("--clinic-action-hover", actionHover);
  shellEl.style.setProperty("--clinic-button-1", button1);
  shellEl.style.setProperty("--clinic-button-2", button2);
  const button1Rgb = _hexToRgb(button1);
  const button2Rgb = _hexToRgb(button2);
  if (button1Rgb) {
    shellEl.style.setProperty("--clinic-button-1-rgb", _rgbCss(button1Rgb));
  }
  if (button2Rgb) {
    shellEl.style.setProperty("--clinic-button-2-rgb", _rgbCss(button2Rgb));
  }
  shellEl.style.setProperty(
    "--clinic-gradient-cta",
    `linear-gradient(130deg, ${button1} 0%, ${button2} 100%)`
  );

  const brandRgb = _hexToRgb(brand);
  const actionRgb = _hexToRgb(action);
  if (brandRgb) {
    const rgb = _rgbCss(brandRgb);
    shellEl.style.setProperty("--clinic-brand-rgb", rgb);
    shellEl.style.setProperty("--clinic-bg-subtle", `rgba(${rgb}, 0.06)`);
    shellEl.style.setProperty("--clinic-chip-border", `rgba(${rgb}, 0.14)`);
    shellEl.style.setProperty("--clinic-bubble-user", `rgba(${rgb}, 0.12)`);
    shellEl.style.setProperty("--clinic-shadow", `0 8px 32px rgba(${rgb}, 0.14)`);
    shellEl.style.setProperty("--clinic-shadow-soft", `0 4px 16px rgba(${rgb}, 0.1)`);
    shellEl.style.setProperty("--clinic-bg-tint", _mixHexWithWhite(brand, 0.96));
    shellEl.style.setProperty("--clinic-composer-bg", _mixHexWithWhite(brand, 0.97));
    shellEl.style.setProperty("--clinic-composer-border", `rgba(${rgb}, 0.18)`);
    shellEl.style.setProperty("--clinic-composer-focus-border", `rgba(${rgb}, 0.42)`);
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
 * @param {HTMLElement} logoWrap
 * @param {HTMLElement} logoEl
 * @param {WidgetConfig} config
 */
function fillWelcomeLogo(logoWrap, logoEl, config) {
  const url = resolvePackAssetUrl(config.apiBase, config.logoUrl);
  const w = Number(config.logoWidth) || 0;
  const h = Number(config.logoHeight) || 32;
  logoEl.textContent = "";
  if (url) {
    const img = document.createElement("img");
    img.className = "clinic-shell__welcome-logo-img";
    img.src = url;
    img.alt = "";
    img.decoding = "async";
    logoEl.appendChild(img);
  } else {
    logoEl.innerHTML = WELCOME_LOGO_SVG;
  }
  if (w > 0) logoWrap.style.setProperty("--clinic-logo-w", `${w}px`);
  else logoWrap.style.removeProperty("--clinic-logo-w");
  logoWrap.style.setProperty("--clinic-logo-h", `${h}px`);
}

/**
 * @param {HTMLElement} el
 * @param {WidgetConfig} config
 */
function fillHeaderStatus(el, config) {
  const clinicName = String(config.clinicName || "").trim() || "клиники";
  el.textContent = "";
  el.appendChild(document.createTextNode(`ИИ-консультант ${clinicName} `));
  const badge = document.createElement("span");
  badge.className = "clinic-shell__header-status-badge";
  badge.textContent = "24/7";
  el.appendChild(badge);
}

const WELCOME_LOGO_SVG = `<svg viewBox="0 0 101 26" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path d="M85.1918 4.41158H88.1628V7.95266H85.1918V14.1348C85.1918 14.755 85.3319 15.1951 85.612 15.4552C85.8921 15.7153 86.3322 15.8453 86.9324 15.8453C87.4725 15.8453 87.8827 15.8054 88.1628 15.7254V19.0265C87.5826 19.2666 86.8324 19.3866 85.9121 19.3866C84.4716 19.3866 83.3311 18.9865 82.4908 18.1862C81.6505 17.366 81.2304 16.2455 81.2304 14.8251V7.95266H78.5596V4.42005H81.5894V2.1355C81.5898 2.11402 81.5905 2.09243 81.5905 2.07071V0H85.1918V4.41158Z" fill="#51246B"/><path d="M88.7988 15.0837L92.22 14.3335C92.26 14.9737 92.5101 15.5139 92.9702 15.954C93.4504 16.3742 94.1006 16.5842 94.9209 16.5842C95.5411 16.5842 96.0213 16.4442 96.3614 16.1641C96.7015 15.884 96.8716 15.5339 96.8716 15.1137C96.8716 14.3735 96.3414 13.8933 95.281 13.6732L93.3304 13.2231C91.9499 12.923 90.9095 12.3828 90.2093 11.6026C89.5291 10.8223 89.189 9.89197 89.189 8.81161C89.189 7.47116 89.7091 6.33077 90.7495 5.39046C91.8098 4.45014 93.1303 3.97998 94.7108 3.97998C95.7112 3.97998 96.5915 4.13003 97.3517 4.43013C98.112 4.71023 98.7022 5.08035 99.1223 5.54051C99.5425 5.98066 99.8626 6.43081 100.083 6.89096C100.303 7.35112 100.443 7.80127 100.503 8.24142L97.1717 8.99167C97.0916 8.4715 96.8515 8.01134 96.4514 7.61121C96.0713 7.21107 95.5011 7.011 94.7408 7.011C94.2207 7.011 93.7705 7.15105 93.3904 7.43114C93.0303 7.71124 92.8502 8.06136 92.8502 8.4815C92.8502 9.20174 93.3003 9.64189 94.2007 9.80194L96.3014 10.2521C97.7218 10.5522 98.8022 11.1024 99.5425 11.9027C100.303 12.7029 100.683 13.6632 100.683 14.7836C100.683 16.1041 100.183 17.2445 99.1823 18.2048C98.182 19.1651 96.7715 19.6453 94.9509 19.6453C93.9106 19.6453 92.9802 19.4952 92.16 19.1951C91.3397 18.875 90.6995 18.4749 90.2393 17.9947C89.7992 17.4945 89.4591 17.0044 89.219 16.5242C88.9989 16.024 88.8588 15.5439 88.7988 15.0837Z" fill="#51246B"/><path d="M68.7843 10.7179V19.2108H64.793V4.4458H68.6643V6.27641C69.0844 5.55617 69.6846 5.00598 70.4649 4.62586C71.2451 4.24573 72.0654 4.05566 72.9257 4.05566C74.6663 4.05566 75.9867 4.60585 76.887 5.70622C77.8074 6.78658 78.2675 8.18706 78.2675 9.90764V19.2108H74.2762V10.5979C74.2762 9.71757 74.0461 9.00733 73.5859 8.46715C73.1458 7.92697 72.4656 7.65688 71.5452 7.65688C70.705 7.65688 70.0347 7.94698 69.5346 8.52717C69.0344 9.10737 68.7843 9.83761 68.7843 10.7179Z" fill="#51246B"/><path d="M0 15.1796C0 13.9192 0.410138 12.9088 1.23041 12.1486C2.05069 11.3883 3.11105 10.9082 4.41149 10.7081L8.04271 10.1679C8.78296 10.0679 9.15309 9.71777 9.15309 9.11757C9.15309 8.55738 8.93301 8.09723 8.49286 7.7371C8.07272 7.37698 7.46252 7.19692 6.66225 7.19692C5.82196 7.19692 5.15174 7.427 4.65157 7.88716C4.17141 8.34731 3.90132 8.9175 3.8413 9.59773L0.300101 8.84748C0.440148 7.56705 1.07036 6.43667 2.19074 5.45634C3.31112 4.47601 4.79162 3.98584 6.63224 3.98584C8.83298 3.98584 10.4535 4.51602 11.4939 5.57638C12.5342 6.61673 13.0544 7.95718 13.0544 9.59773V16.8602C13.0544 17.7405 13.1144 18.5207 13.2345 19.201H9.57323C9.47319 18.7608 9.42318 18.1706 9.42318 17.4304C8.48286 18.8909 7.03237 19.6211 5.07171 19.6211C3.5512 19.6211 2.32078 19.181 1.38047 18.3007C0.460155 17.4204 0 16.38 0 15.1796ZM5.91199 16.6501C6.85231 16.6501 7.62257 16.39 8.22277 15.8698C8.84298 15.3297 9.15309 14.4494 9.15309 13.229V12.5687L5.82196 13.0789C4.60155 13.259 3.99135 13.8792 3.99135 14.9395C3.99135 15.4197 4.1614 15.8298 4.50152 16.1699C4.84163 16.4901 5.31179 16.6501 5.91199 16.6501Z" fill="#BD35D8"/><path d="M22.8439 4.38619V8.40755C22.4437 8.32752 22.0436 8.28751 21.6435 8.28751C20.5031 8.28751 19.5828 8.61762 18.8825 9.27784C18.1823 9.91806 17.8322 10.9784 17.8322 12.4589V19.2112H13.8408V4.44621H17.7121V6.63695C18.4324 5.09643 19.8328 4.32617 21.9135 4.32617C22.1336 4.32617 22.4437 4.34618 22.8439 4.38619Z" fill="#BD35D8"/><path d="M33.3418 19.9782L36.943 19.0178C37.0831 19.8381 37.4632 20.5083 38.0834 21.0285C38.7036 21.5487 39.4739 21.8088 40.3942 21.8088C43.0151 21.8088 44.3255 20.4383 44.3255 17.6974V16.617C43.9854 17.1572 43.4652 17.6074 42.765 17.9675C42.0647 18.3276 41.2145 18.5077 40.2141 18.5077C38.2535 18.5077 36.6129 17.8274 35.2925 16.467C33.992 15.1065 33.3418 13.3959 33.3418 11.3352C33.3418 9.33457 33.992 7.63399 35.2925 6.23352C36.5929 4.83305 38.2334 4.13281 40.2141 4.13281C41.2945 4.13281 42.1948 4.33288 42.915 4.73302C43.6353 5.11314 44.1354 5.5833 44.4155 6.14349V4.4029H48.2568V17.5773C48.2568 19.7981 47.6166 21.6387 46.3362 23.0992C45.0557 24.5797 43.1151 25.32 40.5142 25.32C38.5736 25.32 36.943 24.7998 35.6226 23.7594C34.3221 22.7191 33.5619 21.4587 33.3418 19.9782ZM40.9043 15.0865C41.9247 15.0865 42.755 14.7464 43.3952 14.0662C44.0554 13.3859 44.3855 12.4756 44.3855 11.3352C44.3855 10.2149 44.0454 9.31456 43.3652 8.63433C42.705 7.9541 41.8847 7.61399 40.9043 7.61399C39.884 7.61399 39.0337 7.9541 38.3535 8.63433C37.6933 9.31456 37.3632 10.2149 37.3632 11.3352C37.3632 12.4756 37.6933 13.3859 38.3535 14.0662C39.0137 14.7464 39.864 15.0865 40.9043 15.0865Z" fill="#51246B"/><path d="M53.4286 10.0881H60.0308C59.9908 9.26783 59.6907 8.5776 59.1305 8.01741C58.5903 7.45722 57.7901 7.17713 56.7297 7.17713C55.7694 7.17713 54.9891 7.47723 54.3889 8.07743C53.7887 8.67763 53.4686 9.34786 53.4286 10.0881ZM60.4209 13.9294L63.7521 14.9197C63.3519 16.2802 62.5617 17.4006 61.3813 18.2809C60.2209 19.1612 58.7704 19.6013 57.0298 19.6013C54.9091 19.6013 53.1085 18.8911 51.628 17.4706C50.1475 16.0301 49.4072 14.1095 49.4072 11.7087C49.4072 9.42789 50.1275 7.56726 51.568 6.12677C53.0084 4.66628 54.709 3.93604 56.6697 3.93604C58.9504 3.93604 60.731 4.61626 62.0115 5.97672C63.3119 7.33718 63.9621 9.20781 63.9621 11.5886C63.9621 11.7487 63.9521 11.9287 63.9321 12.1288C63.9321 12.3289 63.9321 12.4889 63.9321 12.609L63.9021 12.819H53.3386C53.3786 13.7794 53.7587 14.5796 54.4789 15.2198C55.1992 15.8601 56.0595 16.1802 57.0598 16.1802C58.7604 16.1802 59.8808 15.4299 60.4209 13.9294Z" fill="#51246B"/><path d="M30.0834 4.41158H33.0544V7.95266H30.0834V14.1348C30.0834 14.755 30.2235 15.1951 30.5036 15.4552C30.7837 15.7153 31.2238 15.8453 31.824 15.8453C32.3641 15.8453 32.7743 15.8054 33.0544 15.7254V19.0265C32.4742 19.2666 31.724 19.3866 30.8037 19.3866C29.3632 19.3866 28.2227 18.9865 27.3824 18.1862C26.5421 17.366 26.122 16.2455 26.122 14.8251V7.95266H23.4512V4.42005H26.481V2.1355C26.4814 2.11402 26.4821 2.09243 26.4821 2.07071V0H30.0834V4.41158Z" fill="#BD35D8"/><rect x="33.0547" y="21.3281" width="3.99161" height="33.0546" transform="rotate(90 33.0547 21.3281)" fill="#BD35D8"/></svg>`;

/** @param {unknown} meta */
function leadMetaPhoneStep(meta) {
  return Boolean(
    meta && typeof meta === "object" && meta.lead_flow && meta.lead_step === "phone"
  );
}

/** @param {unknown} payload */
function isActiveLeadFlowPayload(payload) {
  const m = payload?.meta;
  if (!m || typeof m !== "object" || !m.lead_flow) return false;
  const step = String(m.lead_step || "");
  return Boolean(step && step !== "done");
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
 * @param {import("./api.js").postAsk} _
 * @param {unknown} data
 */
function botTurnFromPayload(data) {
  if (!data || typeof data !== "object") return null;
  const meta = /** @type {Record<string, unknown>} */ (data.meta || {});
  const followups = Array.isArray(meta.followups) ? meta.followups : [];
  const quickReplies = Array.isArray(data.quick_replies) ? data.quick_replies : [];
  const sit = data.situation && typeof data.situation === "object" ? data.situation : null;
  const ctaRaw = data.cta;
  const cta =
    ctaRaw && typeof ctaRaw === "object" && ctaRaw.text
      ? {
          text: String(ctaRaw.text),
          action: String(ctaRaw.action || "lead"),
          key: ctaRaw.key ? String(ctaRaw.key) : "",
        }
      : null;
  const vp = data.video && typeof data.video === "object" ? data.video : null;
  const vk = vp?.key ? String(vp.key).trim() : "";
  const vSrc = vp?.src ? String(vp.src).trim() : "";
  const vTit = vp?.title ? String(vp.title).trim() : "";
  const hasPlayableVideo = Boolean(vSrc);

  return {
    role: "bot",
    text: String(data.answer || "").trim(),
    followups: followups.filter((x) => x && x.ref),
    quickReplies: quickReplies.filter((x) => x && x.ref),
    linksDismissed: false,
    videoKey: hasPlayableVideo ? vk : "",
    videoSrc: hasPlayableVideo ? vSrc : "",
    videoTitleText: hasPlayableVideo ? vTit : "",
    videoRevealed: false,
    situation: sit ? { show: Boolean(sit.show), mode: sit.mode || "normal" } : null,
    cta,
    trailingDismissed: false,
    attributionKind: resolveTurnAttributionKind(meta),
    serviceRoute: String(meta.service_route || ""),
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
  const name = displayBotName(botName);
  return phase === "writing"
    ? `${name} печатает ответ`
    : `${name} ищет в базе знаний`;
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
  if (body?.cta_action === "lead") return true;
  const ref = String(body?.ref || "");
  if (ref.startsWith("lead:")) return true;
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
  if (isLeadFlowBotMeta(meta)) return "lead";
  if (meta && typeof meta === "object") {
    if (meta.offtopic) return "plain";
    if (meta.situation_collect) return "plain";
    const route = String(meta.service_route || "");
    if (isPlainAttributionRoute(route)) return "plain";
  }
  return "content";
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
  return "content";
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
  el.textContent = displayBotName(botName);
  return el;
}

/** @param {string} [botName] @param {{ attributionKind?: TurnAttributionKind }} [m] @returns {HTMLElement} */
function createTurnAttributionEl(botName, m) {
  const kind = m?.attributionKind || "content";
  return createAttributionElForKind(kind, botName);
}

/** @param {string} [botName] @returns {HTMLElement} */
function createBotAttributionEl(botName) {
  const el = document.createElement("div");
  el.className = "clinic-msg__attribution";
  el.textContent = botSourceAttributionLabel(botName);
  return el;
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
    scroller.querySelector(".clinic-shell__header--glass") ||
    main?.querySelector(".clinic-shell__header--glass");
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
export function mountWidget(root, config) {
  const apiBase = config.apiBase ?? "";
  const clientId = config.clientId || "default";
  const resolvedAvatarUrl = resolvePackAssetUrl(
    apiBase,
    (config.avatarUrl || "").trim() || DEFAULT_AVATAR_URL
  );

  const state = {
    isOpen: false,
    messages: [],
    lastPayload: null,
    pending: false,
    /** @type {"searching"|"writing"} */
    typingPhase: "searching",
    unread: false,
    started: false,
    errorLine: "",
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

  const useDemoLauncher = config.demoLauncher !== false;
  const launcherCtaLabel = String(config.launcherCtaLabel || "Запустить демо").trim();
  const launcherMobileCtaLabel = String(
    config.launcherMobileCtaLabel || launcherCtaLabel
  ).trim();
  const clinicName = String(config.clinicName || "").trim();
  const launcherSubtitle = clinicName
    ? `ИИ-консультант «${clinicName}»`
    : String(config.launcherSubtitle || "Демо ИИ-консультанта клиники").trim();
  const launcherTagline = String(
    config.launcherTagline || "Подскажу по лечению, ценам и записи."
  ).trim();
  const launcherTeaserEnabled = !useDemoLauncher && config.launcherTeaser !== false;
  const launcherTeaserText = String(
    config.launcherTeaserText || DEFAULT_LAUNCHER_TEASER_TEXT
  ).trim();

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
          <header class="clinic-shell__header clinic-shell__header--glass">
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
          <div class="clinic-shell__error" data-clinic-err hidden></div>
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
  const errBox = root.querySelector("[data-clinic-err]");
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
    chev.innerHTML = LINK_CHEVRON_SVG;
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
    if (state.pending) return;
    clearStoredSid();
    state.messages = [];
    state.lastPayload = null;
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
    const sid = getSid();
    input.value = "";
    autoResizeTextarea(input);
    syncSendState();
    if (sid) {
      try {
        await postAsk(apiBase, { client_id: clientId, sid, q: "/reset" });
      } catch {
        /* best-effort server cleanup */
      }
    }
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
    const base = document.createElement("span");
    base.className = "clinic-shell__typing-label-base";
    const shine = document.createElement("span");
    shine.className = "clinic-shell__typing-label-shine";
    shine.setAttribute("aria-hidden", "true");
    wrap.appendChild(base);
    wrap.appendChild(shine);
    return wrap;
  }

  function updateTypingIndicatorText() {
    const bubble = feed.querySelector(".clinic-shell__typing");
    const labelWrap = feed.querySelector(".clinic-shell__typing-label");
    if (!bubble || !labelWrap) return;
    fillTypingLabel(labelWrap, typingLabelForPhase(state.typingPhase));
    bubble.classList.toggle("clinic-shell__typing--shimmer", state.typingPhase === "searching");
  }

  /** @param {Record<string, unknown>} body */
  function shouldShowKbSearchTyping(body) {
    if (body.cta_action === "lead") return false;
    const ref = String(body.ref || "");
    if (ref.startsWith("lead:")) return false;
    if (body.situation_action || body.action === "situation") return false;
    if (isActiveLeadFlowPayload(state.lastPayload)) return false;
    const q = String(body.q || "").trim();
    if (q.length >= 2 && BOOKING_INTENT_RE.test(q)) return false;
    return true;
  }

  /** @param {Record<string, unknown>} [body] */
  function beginPendingRequest(body = {}) {
    state.pending = true;
    state.typingPhase = shouldShowKbSearchTyping(body) ? "searching" : "writing";
    renderFeed();
  }

  /** @param {"searching"|"writing"} phase */
  function setTypingPhase(phase) {
    const next = phase === "writing" ? "writing" : "searching";
    if (state.typingPhase === next) return;
    state.typingPhase = next;
    updateTypingIndicatorText();
  }

  function endPendingRequest() {
    state.pending = false;
    state.typingPhase = "searching";
  }

  /**
   * @param {HTMLElement} feed
   * @param {string} apiBase
   * @param {Record<string, unknown>} body
   */
  function runStreamAsk(feed, apiBase, body) {
    let liveBubble = null;
    let fullText = "";
    let uiData = null;
    let writingRevealTimer = 0;
    const liveAttributionKind = predictLiveAttributionKind(body, state.lastPayload);

    const revealLiveBubble = () => {
      if (writingRevealTimer) {
        clearTimeout(writingRevealTimer);
        writingRevealTimer = 0;
      }
      if (!liveBubble && fullText.length > 0) {
        liveBubble = _createLiveBubble(feed, config.botName, liveAttributionKind);
        _updateLiveBubble(liveBubble, fullText, feed);
      } else if (liveBubble) {
        _updateLiveBubble(liveBubble, fullText, feed);
      }
    };

    return streamAsk(apiBase, body, {
      onTyping(phase) {
        setTypingPhase(phase);
      },
      onDelta(delta) {
        const chunk = String(delta || "");
        if (!chunk) return;
        fullText += chunk;

        if (!liveBubble) {
          if (state.typingPhase === "searching") {
            state.typingPhase = "writing";
            updateTypingIndicatorText();
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
        uiData = data;
      },
      onDone() {
        if (writingRevealTimer) {
          clearTimeout(writingRevealTimer);
          writingRevealTimer = 0;
        }
        if (!liveBubble && fullText.length > 0) {
          revealLiveBubble();
        }
        const streamedText = fullText.trim();
        if (uiData) {
          if (uiData.meta && uiData.meta.sid) setSid(uiData.meta.sid);
          const turn = botTurnFromPayload(uiData);
          if (turn) {
            // Текст ответа: единственный источник правды — то, что уже показали в стриме.
            if (streamedText) turn.text = streamedText;
            state.messages.push(turn);
          }
          state.lastPayload = uiData;
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
        endPendingRequest();
        if (state.unread && !state.isOpen) unreadDot?.classList.add("is-visible");
        renderFeed();
        syncSendState();
      },
      onError(msg) {
        if (writingRevealTimer) {
          clearTimeout(writingRevealTimer);
          writingRevealTimer = 0;
        }
        setError(msg);
        endPendingRequest();
        renderFeed();
        syncSendState();
      },
    });
  }

  function setError(msg) {
    state.errorLine = msg || "";
    if (msg) {
      errBox.textContent = msg;
      errBox.hidden = false;
    } else {
      errBox.textContent = "";
      errBox.hidden = true;
    }
  }

  /**
   * @param {HTMLElement} bubble
   * @param {object} m
   * @param {number} msgIndex
   */
  function renderInlineLinks(bubble, m, msgIndex) {
    if (m.linksDismissed) return;
    const items = [];
    for (const f of m.followups || []) {
      items.push({ label: (f.label || f.ref || "").trim(), ref: f.ref });
    }
    for (const r of m.quickReplies || []) {
      items.push({ label: (r.label || r.ref || "").trim(), ref: r.ref });
    }
    if (!items.length) return;

    const box = getOrCreateLinksBox(bubble);
    for (const it of items) {
      if (!it.ref) continue;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "clinic-msg__link";
      const lab = document.createElement("span");
      lab.className = "clinic-msg__link-text";
      lab.textContent = it.label || it.ref;
      const chev = document.createElement("span");
      chev.className = "clinic-msg__link-chevron";
      chev.setAttribute("aria-hidden", "true");
      chev.innerHTML = LINK_CHEVRON_SVG;
      btn.appendChild(lab);
      btn.appendChild(chev);
      btn.addEventListener("click", () => {
        const target = state.messages[msgIndex];
        if (target && target.role === "bot") target.linksDismissed = true;
        dismissTrailingsAll(state.messages);
        const echo = (it.label || it.ref || "").trim();
        void sendAsk({ ref: it.ref, q: "", userEcho: echo, _linkOnly: true });
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

    const sit = m.situation;
    if (sit && sit.show && sit.mode === "normal") {
      const sb = document.createElement("button");
      sb.type = "button";
      sb.className = "clinic-turn__btn clinic-turn__btn--cta-secondary";
      sb.textContent = "Рассказать о ситуации";
      sb.addEventListener("click", () => {
        dismissTrailingsAll(state.messages);
        dismissLinksAll(state.messages);
        void sendAsk({ action: "situation", q: "", userEcho: "Рассказать о ситуации" });
      });
      trail.appendChild(sb);
    }

    if (sit && sit.show && sit.mode === "pending") {
      const back = document.createElement("button");
      back.type = "button";
      back.className = "clinic-turn__btn clinic-turn__btn--ghost-wide";
      back.textContent = "Назад к диалогу";
      back.addEventListener("click", () => {
        dismissTrailingsAll(state.messages);
        dismissLinksAll(state.messages);
        void sendAsk({ situation_action: "back", q: "", userEcho: "Назад к диалогу" });
      });
      trail.appendChild(back);
    }

    if (m.cta && m.cta.text) {
      const c = document.createElement("button");
      c.type = "button";
      c.className = "clinic-turn__btn clinic-turn__btn--cta-primary";
      const ctaLabel = (m.cta.text || "Записаться на консультацию").trim();
      c.textContent = ctaLabel;
      c.addEventListener("click", () => {
        dismissTrailingsAll(state.messages);
        dismissLinksAll(state.messages);
        const echo = (m.cta.text || "Запись").trim();
        void sendAsk({
          cta_action: "lead",
          cta_key: m.cta.key || "",
          cta_label: ctaLabel,
          q: "",
          userEcho: echo,
        });
      });
      trail.appendChild(c);
    }

    if (trail.children.length) wrap.appendChild(trail);
  }

  function renderFeed() {
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

      const logoWrap = document.createElement("div");
      logoWrap.className = "clinic-shell__welcome-logo-wrap";
      logoWrap.setAttribute("aria-hidden", "true");

      const logo = document.createElement("div");
      logo.className = "clinic-shell__welcome-logo";
      fillWelcomeLogo(logoWrap, logo, config);
      logoWrap.appendChild(logo);

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

      card.appendChild(logoWrap);
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
        chev.innerHTML = LINK_CHEVRON_SVG;
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
      if (text) {
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

    const typingWrap = document.createElement("div");
    typingWrap.className = "clinic-shell__typing-wrap";
    fillTypingLabel(typingLabel, typingLabelForPhase(state.typingPhase));
    typingWrap.appendChild(typing);
    typingWrap.classList.toggle("is-visible", state.pending);
    feed.appendChild(typingWrap);

    const lastMsg = state.messages.length
      ? state.messages[state.messages.length - 1]
      : null;
    if (lastMsg && lastMsg.role === "bot") {
      requestAnimationFrame(() => scrollToLastTurnStart(feed));
    } else {
      scrollChatPaneToEnd(feed, { force: state.messages.length > 0 });
    }
    syncComposerLeadUi();
    syncSendState();
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
    const userEcho =
      typeof extra.userEcho === "string" ? extra.userEcho.trim() : "";
    const linkOnly = Boolean(extra._linkOnly);
    const apiFields = { ...extra };
    delete apiFields.userEcho;
    delete apiFields._linkOnly;

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
      q: "",
      ...apiFields,
    };
    if (body.q === undefined) body.q = "";

    setError("");
    beginPendingRequest(body);
    await runStreamAsk(feed, apiBase, body);
  }

  async function sendFromComposer() {
    if (state.pending) return;

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
      const askBody = { client_id: clientId, sid, q };
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
    if (state.pending) {
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
