/**
 * Multiclient embed bootstrap (classic script, no type="module" on host page).
 *
 * Usage:
 *   <script src="https://{client_id}.bot.artgents.ru/static/widget/embed.js" defer></script>
 * Optional override:
 *   <script src="..." data-client-id="cesi" defer></script>
 */
(function clinicWidgetEmbed() {
  const LOG = "[ClinicWidget]";
  const HOST_ID = "clinic-widget-root";
  const GLOBAL_GUARD = "__clinicWidgetEmbedMounted";

  /** @param {unknown} err @param {string} msg */
  function logError(err, msg) {
    console.error(LOG, msg, err);
  }

  if (typeof window !== "undefined" && window[GLOBAL_GUARD]) {
    return;
  }

  const script = document.currentScript;
  if (!script || !(script instanceof HTMLScriptElement) || !script.src) {
    logError(null, "embed.js must be loaded via <script src=...> (currentScript missing).");
    return;
  }

  let apiBase = "";
  try {
    apiBase = new URL(script.src).origin;
  } catch (e) {
    logError(e, "Cannot parse embed script URL.");
    return;
  }

  const dataClientId = (script.dataset.clientId || "").trim();

  /** @param {string} base */
  function clientIdFromApiBase(base) {
    try {
      const host = new URL(base).hostname.toLowerCase();
      const marker = ".bot.";
      const idx = host.indexOf(marker);
      if (idx > 0) {
        return host.slice(0, idx);
      }
    } catch {
      /* ignore */
    }
    return "";
  }

  const clientId = dataClientId || clientIdFromApiBase(apiBase);
  if (!clientId) {
    logError(null, "clientId not resolved; set data-client-id on the script tag.");
    return;
  }

  if (typeof window !== "undefined") {
    window[GLOBAL_GUARD] = true;
  }

  /** @param {ShadowRoot} shadow @param {string} href */
  function loadStylesheet(shadow, href) {
    return new Promise((resolve, reject) => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.onload = () => resolve();
      link.onerror = () => reject(new Error("widget_css_load_failed"));
      shadow.appendChild(link);
    });
  }

  async function boot() {
    let host = document.getElementById(HOST_ID);
    if (!host) {
      host = document.createElement("div");
      host.id = HOST_ID;
      document.body.appendChild(host);
    }

    const shadow = host.attachShadow({ mode: "open" });
    const cssUrl = `${apiBase}/static/widget/widget.css`;
    await loadStylesheet(shadow, cssUrl);

    const configUrl = `${apiBase}/api/widget-config?client_id=${encodeURIComponent(clientId)}`;
    const resp = await fetch(configUrl);
    if (!resp.ok) {
      throw new Error(`widget_config_http_${resp.status}`);
    }

    const config = await resp.json();
    config.apiBase = apiBase;
    config.clientId = clientId;

    const mountRoot = document.createElement("div");
    mountRoot.setAttribute("data-clinic-embed-mount", clientId);
    shadow.appendChild(mountRoot);

    const widgetUrl = `${apiBase}/static/widget/widget.js`;
    const mod = await import(/* webpackIgnore: true */ widgetUrl);
    if (typeof mod.mountWidget !== "function") {
      throw new Error("mountWidget_export_missing");
    }
    mod.mountWidget(mountRoot, config);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      boot().catch((e) => logError(e, "Widget failed to mount."));
    });
  } else {
    boot().catch((e) => logError(e, "Widget failed to mount."));
  }
})();
