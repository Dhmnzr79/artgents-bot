const state = {
  clients: [],
  defaultClientId: "demo",
  expandedVisit: null,
  threadCache: {},
};

function visitCacheKey(sid, visitIndex) {
  return `${sid}:${visitIndex}`;
}

function q(id) {
  return document.getElementById(id);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function readUrlClientId() {
  return (new URLSearchParams(window.location.search).get("client_id") || "").trim();
}

function syncUrlClientId(clientId) {
  const url = new URL(window.location.href);
  url.searchParams.set("client_id", clientId);
  window.history.replaceState({}, "", url);
}

function currentClientId() {
  const sel = q("clientId");
  return (sel.value || state.defaultClientId).trim() || state.defaultClientId;
}

function resolveClientId(raw) {
  const cid = (raw || "").trim();
  const allowed = new Set(state.clients.map((c) => c.client_id));
  if (cid && allowed.has(cid)) {
    return cid;
  }
  return state.defaultClientId;
}

async function getJson(path, clientId, extraParams = {}) {
  const params = new URLSearchParams({ client_id: clientId, ...extraParams });
  const url = path.includes("?") ? `${path}&${params}` : `${path}?${params}`;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 6000);
  let r;
  try {
    r = await fetch(url, {
      signal: ctrl.signal,
    });
  } finally {
    clearTimeout(t);
  }
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${path} -> ${r.status} ${txt.slice(0, 200)}`);
  }
  return r.json();
}

const OVERVIEW_PERIODS = new Set(["today", "week", "month"]);

function overviewPeriod() {
  const raw = (q("overviewPeriod")?.value || "today").trim();
  return OVERVIEW_PERIODS.has(raw) ? raw : "today";
}

function readUrlPeriod() {
  return (new URLSearchParams(window.location.search).get("period") || "").trim();
}

function syncUrlPeriod(period) {
  const url = new URL(window.location.href);
  if (period && period !== "today") {
    url.searchParams.set("period", period);
  } else {
    url.searchParams.delete("period");
  }
  window.history.replaceState({}, "", url);
}

function periodRangeLabel(data) {
  const from = data?.range_from;
  const to = data?.range_to;
  if (from && to) {
    if (from === to) {
      return `${data.period_label || "сегодня"} · ${from} (UTC)`;
    }
    return `${data.period_label || "период"} · ${from} — ${to} (UTC)`;
  }
  return `${data?.period_label || "сегодня"} (UTC)`;
}

async function deleteSession(sid) {
  const sidClean = String(sid || "").trim();
  if (!sidClean) return;
  const ok = window.confirm(
    `Удалить всю сессию?\n\nДиалоги, заявки и ошибки этой сессии исчезнут из админки и статистики.\nРасход токенов (LLM) останется.\n\nsid: ${sidClean}`,
  );
  if (!ok) return;
  const clientId = currentClientId();
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 10000);
  let r;
  try {
    r = await fetch(
      `/api/dialogs/${encodeURIComponent(sidClean)}/purge?client_id=${encodeURIComponent(clientId)}`,
      { method: "POST", signal: ctrl.signal },
    );
  } finally {
    clearTimeout(t);
  }
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`delete -> ${r.status} ${txt.slice(0, 200)}`);
  }
  if (state.expandedVisit && state.expandedVisit.sid === sidClean) {
    state.expandedVisit = null;
    closeDialogViewer();
  }
  Object.keys(state.threadCache).forEach((key) => {
    if (key.startsWith(`${sidClean}:`)) {
      delete state.threadCache[key];
    }
  });
  await refreshAll();
}

function setError(id, e) {
  q(id).innerHTML = `<div class="muted">Ошибка: ${esc(String(e))}</div>`;
}

function formatTs(iso) {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function previewText(text, maxLen = 140) {
  const s = String(text || "").trim();
  if (!s) return "—";
  if (s.length <= maxLen) return s;
  return `${s.slice(0, maxLen)}…`;
}

function statusLabel(status) {
  if (status === "lead") return "лид";
  if (status === "problem") return "проблема";
  return "ok";
}

function renderThreadTurns(turns) {
  if (!turns.length) {
    return `<div class="muted">Ходов нет.</div>`;
  }
  return `<div class="chat-thread">${turns
    .map((t, idx) => {
      const turnNo = t.turn_number || idx + 1;
      const route = t.route ? `<span class="chat-route">${esc(t.route)}</span>` : "";
      const doc = t.doc_id ? `<span class="chat-doc">${esc(t.doc_id)}</span>` : "";
      const lat =
        t.latency_ms > 0 ? `<span class="chat-lat">${Math.round(t.latency_ms)} ms</span>` : "";
      const piiNote =
        t.route === "lead_flow" || t.route === "situation_collect" || t.pii_withheld
          ? '<span class="chat-pii muted">без ПД</span>'
          : "";
      return `
        <div class="chat-turn">
          <div class="chat-turn-meta">
            <span>Ход ${esc(turnNo)} · ${esc(formatTs(t.ts))}</span>
            ${route}${doc}${lat}${piiNote}
          </div>
          <div class="bubble bubble-user">${esc(t.user_text || "—")}</div>
          <div class="bubble bubble-bot">${esc(t.bot_text || "—")}</div>
        </div>
      `;
    })
    .join("")}</div>`;
}

async function loadDialogThread(sid, visitIndex) {
  const key = visitCacheKey(sid, visitIndex);
  if (state.threadCache[key]) {
    return state.threadCache[key];
  }
  const data = await getJson(
    `/api/dialogs/${encodeURIComponent(sid)}/thread?visit_index=${encodeURIComponent(visitIndex)}`,
    currentClientId(),
  );
  state.threadCache[key] = data;
  return data;
}

function closeDialogViewer() {
  state.expandedVisit = null;
  q("dialogThreadViewer").hidden = true;
  q("dialogThreadBody").innerHTML = "";
  q("dialogViewerTitle").textContent = "";
  q("dialogs").querySelectorAll(".dialog-card.is-selected").forEach((card) => {
    card.classList.remove("is-selected");
  });
  q("dialogs").querySelectorAll(".dialog-toggle").forEach((btn) => {
    btn.textContent = btn.dataset.openLabel || "Показать диалог";
  });
}

function setSelectedCard(sid, visitIndex) {
  q("dialogs").querySelectorAll(".dialog-card").forEach((card) => {
    const match =
      card.dataset.sid === sid && String(card.dataset.visitIndex) === String(visitIndex);
    card.classList.toggle("is-selected", match);
  });
  q("dialogs").querySelectorAll(".dialog-toggle").forEach((btn) => {
    const match =
      btn.dataset.sid === sid && String(btn.dataset.visitIndex) === String(visitIndex);
    if (match) {
      btn.textContent = "Открыт";
      return;
    }
    btn.textContent = btn.dataset.openLabel || "Показать диалог";
  });
}

async function openDialogViewer(sid, meta, { force = false } = {}) {
  if (!sid) return;
  const visitIndex = Number(meta?.visitIndex ?? 0);

  if (
    !force &&
    state.expandedVisit &&
    state.expandedVisit.sid === sid &&
    state.expandedVisit.visitIndex === visitIndex &&
    !q("dialogThreadViewer").hidden
  ) {
    closeDialogViewer();
    return;
  }

  state.expandedVisit = { sid, visitIndex };
  setSelectedCard(sid, visitIndex);

  const turns = meta?.turns || 0;
  const turnWord = turns === 1 ? "ход" : turns < 5 ? "хода" : "ходов";
  const visitLabel =
    meta?.visitsTotal > 1 ? ` · визит ${visitIndex + 1}/${meta.visitsTotal}` : "";
  q("dialogViewerTitle").textContent = `Диалог${visitLabel} · ${sid} · ${turns} ${turnWord} · ${formatTs(meta?.last_ts)}`;

  const viewer = q("dialogThreadViewer");
  const body = q("dialogThreadBody");
  viewer.hidden = false;
  body.innerHTML = `<div class="muted">Загрузка диалога…</div>`;

  try {
    const data = await loadDialogThread(sid, visitIndex);
    body.innerHTML = renderThreadTurns(data.turns || []);
    viewer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    body.innerHTML = `<div class="muted">Ошибка: ${esc(String(e))}</div>`;
  }
}

function bindDialogCards() {
  q("dialogs").querySelectorAll(".dialog-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sid = btn.dataset.sid || "";
      const card = btn.closest(".dialog-card");
      openDialogViewer(sid, {
        visitIndex: Number(card?.dataset.visitIndex || 0),
        visitsTotal: Number(card?.dataset.visitsTotal || 1),
        turns: Number(card?.dataset.turns || 0),
        last_ts: card?.dataset.lastTs || "",
      });
    });
  });
  q("dialogs").querySelectorAll(".sid-link").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSidInExplorer(btn.dataset.sid || "");
    });
  });
  q("dialogs").querySelectorAll(".dialog-delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteSession(btn.dataset.sid || "").catch((err) => {
        window.alert(String(err));
      });
    });
  });
}

function renderDialogs(data) {
  const rows = data.items || [];
  if (!rows.length) {
    closeDialogViewer();
    q("dialogs").innerHTML = `<div class="muted">Диалогов пока нет. Поговорите с ботом (client_id=${esc(data.client_id || currentClientId())}) и обновите.</div>`;
    return;
  }

  q("dialogs").innerHTML = `<div class="dialog-list">${rows
    .map((r) => {
      const status = r.status || "ok";
      const turns = r.turns || r.turn_number || 0;
      const openLabel = turns > 1 ? `Показать (${turns} хода)` : "Показать диалог";
      const visitIndex = Number(r.visit_index ?? 0);
      const visitsTotal = Number(r.visits_total ?? 1);
      const isSelected =
        state.expandedVisit &&
        state.expandedVisit.sid === r.sid &&
        state.expandedVisit.visitIndex === visitIndex;
      const visitBadge =
        visitsTotal > 1
          ? `<span class="tag visit">визит ${visitIndex + 1}/${visitsTotal}</span>`
          : "";
      return `
      <article
        class="dialog-card${isSelected ? " is-selected" : ""}"
        data-sid="${esc(r.sid || "")}"
        data-visit-index="${esc(visitIndex)}"
        data-visits-total="${esc(visitsTotal)}"
        data-turns="${esc(turns)}"
        data-last-ts="${esc(r.last_ts || "")}"
      >
        <div class="dialog-head">
          <div class="dialog-head-main">
            <div class="dialog-meta">
              <span>${esc(formatTs(r.last_ts))}</span>
              <span>${esc(turns)} ${turns === 1 ? "ход" : turns < 5 ? "хода" : "ходов"}</span>
              ${visitBadge}
              <span class="tag ${esc(status)}">${esc(statusLabel(status))}</span>
              ${r.has_lead ? '<span class="tag lead">заявка</span>' : ""}
            </div>
            <div class="dialog-preview">${esc(previewText(r.first_user_text || r.last_user_text))}</div>
            <div class="dialog-sub muted">
              sid: <button type="button" class="link-btn sid-link" data-sid="${esc(r.sid || "")}">${esc(r.sid || "-")}</button>
              ${r.last_route ? ` · route: ${esc(r.last_route)}` : ""}
            </div>
          </div>
          <div class="dialog-actions">
            <button
              type="button"
              class="dialog-toggle"
              data-sid="${esc(r.sid || "")}"
              data-visit-index="${esc(visitIndex)}"
              data-open-label="${esc(openLabel)}"
            >${isSelected ? "Открыт" : esc(openLabel)}</button>
            <button
              type="button"
              class="dialog-delete"
              data-sid="${esc(r.sid || "")}"
              title="Удалить всю сессию (sid)"
            >Удалить</button>
          </div>
        </div>
      </article>
    `;
    })
    .join("")}</div>`;

  bindDialogCards();

  if (state.expandedVisit) {
    const { sid, visitIndex } = state.expandedVisit;
    const card = q("dialogs").querySelector(
      `.dialog-card[data-sid="${CSS.escape(sid)}"][data-visit-index="${visitIndex}"]`,
    );
    if (card) {
      openDialogViewer(
        sid,
        {
          visitIndex,
          visitsTotal: Number(card.dataset.visitsTotal || 1),
          turns: Number(card.dataset.turns || 0),
          last_ts: card.dataset.lastTs || "",
        },
        { force: true },
      );
    } else {
      closeDialogViewer();
    }
  }
}

function renderStatusBar(health, clientId) {
  const bar = q("statusBar");
  if (!health.ok) {
    bar.className = "status-bar status-bar-error";
    bar.innerHTML = `
      <strong>Postgres недоступен:</strong> ${esc(health.postgres || "unknown")}
      · проверьте <code>docker compose up -d postgres</code> и <code>BOT_PG_DSN</code> в .env
    `;
    return;
  }
  bar.className = "status-bar status-bar-ok";
  bar.textContent = `Postgres подключён · client_id=${clientId} · ${health.app_env || "local"}`;
}

function renderClientSelect(items, selectedId) {
  const sel = q("clientId");
  sel.innerHTML = items
    .map(
      (item) =>
        `<option value="${esc(item.client_id)}"${item.client_id === selectedId ? " selected" : ""}>${esc(item.label)} (${esc(item.client_id)})</option>`,
    )
    .join("");
}

function renderOverview(data) {
  const title = q("overviewTitle");
  if (title) {
    title.textContent = `Обзор · ${periodRangeLabel(data)}`;
  }
  const kpis = [
    ["Сообщений", data.user_turns ?? 0, ""],
    ["Диалогов", data.visits ?? data.conversations ?? 0, ""],
    ["Сессий (sid)", data.sessions ?? 0, ""],
    ["Заявок", data.leads ?? 0, "good"],
    ["Конверсия сессий", `${(data.conversion_percent ?? 0).toFixed(1)}%`, "good"],
    ["Ошибок", data.errors ?? 0, (data.errors ?? 0) > 0 ? "bad" : "good"],
    ["Fallback/no_candidates", data.fallbacks_total ?? 0, (data.fallbacks_total ?? 0) > 0 ? "warn" : "good"],
    ["OpenAI USD", `$${(data.estimated_usd ?? 0).toFixed(4)}`, ""],
    ["Средняя latency", `${Math.round(data.avg_latency_ms ?? 0)} ms`, ""],
  ];
  q("overview").innerHTML = kpis
    .map(
      ([label, value, tone]) =>
        `<div class="kpi"><span class="kpi-label">${esc(label)}</span><span class="kpi-value ${tone}">${esc(value)}</span></div>`,
    )
    .join("");
}

function renderCosts(data) {
  const title = q("costsTitle");
  if (title) {
    title.textContent = `Стоимость LLM · ${periodRangeLabel(data)}`;
  }
  const rows = data.items || [];
  if (!rows.length) {
    q("costs").innerHTML = `<div class="muted">За выбранный период вызовов LLM пока нет.</div>`;
    return;
  }
  const body = rows
    .map(
      (r) =>
        `<tr><td>${esc(r.call_type)}</td><td>${esc(r.calls)}</td><td>${esc(r.prompt_tokens)}</td><td>${esc(r.completion_tokens)}</td><td>$${Number(r.estimated_usd || 0).toFixed(4)}</td></tr>`,
    )
    .join("");
  q("costs").innerHTML = `
    <div class="qa-line"><strong>Итого:</strong> $${Number(data.estimated_usd_total || 0).toFixed(4)}</div>
    <div class="table-scroll">
      <table class="simple-table">
        <thead><tr><th>Тип</th><th>Вызовы</th><th>Prompt</th><th>Completion</th><th>USD</th></tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function openSidInExplorer(sid) {
  if (!sid) {
    return;
  }
  q("sidFilter").value = sid;
  q("eventExplorer").open = true;
  refreshAll();
}

function renderProblems(data) {
  const rows = data.items || [];
  if (!rows.length) {
    q("problems").innerHTML = `<div class="muted">Критичных проблем за период не найдено.</div>`;
    return;
  }
  const body = rows
    .map(
      (r) => `
    <tr>
      <td>${esc(r.ts || "-")}</td>
      <td>${esc(r.priority || "-")}</td>
      <td>${r.sid ? `<button type="button" class="link-btn sid-link" data-sid="${esc(r.sid)}">${esc(r.sid)}</button>` : "-"}</td>
      <td class="wrap">${esc(r.user_text || "-")}</td>
      <td>${esc(r.route || "-")}</td>
      <td class="wrap">${esc(r.reason || "-")}</td>
      <td class="wrap">${esc(r.doc_id || "-")}</td>
    </tr>
  `,
    )
    .join("");
  q("problems").innerHTML = `
    <div class="table-scroll">
      <table class="simple-table">
        <thead><tr><th>Время</th><th>Приоритет</th><th>SID</th><th>Вопрос</th><th>Route</th><th>Причина</th><th>Doc</th></tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;

  q("problems").querySelectorAll(".sid-link").forEach((btn) => {
    btn.addEventListener("click", () => openSidInExplorer(btn.dataset.sid || ""));
  });
}

function maskPhone(phone) {
  const p = String(phone || "").trim();
  if (!p) return "-";
  if (p.length <= 4) return "***";
  return `${p.slice(0, 2)}***${p.slice(-2)}`;
}

function renderLeads(data) {
  const rows = data.items || [];
  if (!rows.length) {
    q("leads").innerHTML = `<div class="muted">Заявок пока нет.</div>`;
    return;
  }
  const body = rows
    .map(
      (r) => `
    <tr>
      <td>${esc(formatTs(r.captured_at))}</td>
      <td>${esc(r.delivery_status || r.delivery || "-")}</td>
      <td>${r.after_hours ? "вне часов" : "рабочие"}</td>
      <td>${r.has_situation_note ? "да" : "—"}</td>
      <td>${r.sid ? `<button type="button" class="link-btn sid-link" data-sid="${esc(r.sid)}">${esc(r.sid.slice(0, 8))}…</button>` : "-"}</td>
    </tr>
  `,
    )
    .join("");
  q("leads").innerHTML = `
    <div class="table-scroll">
      <table class="simple-table">
        <thead><tr><th>Время</th><th>Доставка</th><th>Часы</th><th>Ситуация</th><th>SID</th></tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="section-hint muted">Имя, телефон и текст ситуации не хранятся — только на почте клиники.</p>
  `;

  q("leads").querySelectorAll(".sid-link").forEach((btn) => {
    btn.addEventListener("click", () => openSidInExplorer(btn.dataset.sid || ""));
  });
}

function renderEvents(data) {
  q("events").textContent = JSON.stringify(data, null, 2);
}

function readDevFilters() {
  const p = new URLSearchParams();
  const eventType = (q("eventTypeFilter").value || "").trim();
  const sid = (q("sidFilter").value || "").trim();
  const requestId = (q("requestIdFilter").value || "").trim();
  if (eventType) p.set("event_type", eventType);
  if (sid) p.set("sid", sid);
  if (requestId) p.set("request_id", requestId);
  p.set("limit", "100");
  return p.toString();
}

async function refreshAll() {
  const clientId = currentClientId();
  syncUrlClientId(clientId);
  state.threadCache = {};

  q("overview").innerHTML = `<div class="kpi"><span class="kpi-label">Загрузка...</span><span class="kpi-value">...</span></div>`;
  q("costs").innerHTML = `<div class="muted">Загрузка...</div>`;
  q("dialogs").innerHTML = `<div class="muted">Загрузка...</div>`;
  q("problems").innerHTML = `<div class="muted">Загрузка...</div>`;
  q("leads").innerHTML = `<div class="muted">Загрузка...</div>`;

  let health = { ok: false, postgres: "unknown" };
  try {
    const r = await fetch("/api/health");
    health = await r.json();
  } catch (e) {
    health = { ok: false, postgres: String(e) };
  }
  renderStatusBar(health, clientId);

  const period = overviewPeriod();
  syncUrlPeriod(period);
  const eventQuery = readDevFilters();
  await Promise.all([
    getJson("/api/overview", clientId, { period })
      .then(renderOverview)
      .catch((e) => setError("overview", e)),
    getJson("/api/costs", clientId, { period }).then(renderCosts).catch((e) => setError("costs", e)),
    getJson("/api/dialogs?limit=20", clientId).then(renderDialogs).catch((e) => setError("dialogs", e)),
    getJson("/api/problems?limit=40", clientId).then(renderProblems).catch((e) => setError("problems", e)),
    getJson("/api/leads?limit=40", clientId).then(renderLeads).catch((e) => setError("leads", e)),
    getJson(`/api/events?${eventQuery}`, clientId)
      .then(renderEvents)
      .catch((e) => {
        q("events").textContent = JSON.stringify({ error: String(e) }, null, 2);
      }),
  ]);
}

async function initDashboard() {
  state.defaultClientId =
    window.__ADMIN_DEFAULT_CLIENT_ID__ || readUrlClientId() || "demo";

  try {
    const data = await fetch("/api/clients").then((r) => r.json());
    state.clients = data.items || [];
    if (data.default_client_id) {
      state.defaultClientId = data.default_client_id;
    }
  } catch {
    state.clients = [{ client_id: state.defaultClientId, label: state.defaultClientId }];
  }

  const urlParams = new URLSearchParams(window.location.search);
  const selectedId = resolveClientId(urlParams.get("client_id") || state.defaultClientId);
  renderClientSelect(state.clients, selectedId);

  const sidFromUrl = (urlParams.get("sid") || "").trim();
  if (sidFromUrl) {
    q("sidFilter").value = sidFromUrl;
    q("eventExplorer").open = true;
  }

  syncUrlClientId(selectedId);

  const periodSel = q("overviewPeriod");
  const urlPeriod = readUrlPeriod();
  if (periodSel && OVERVIEW_PERIODS.has(urlPeriod)) {
    periodSel.value = urlPeriod;
  }
  periodSel?.addEventListener("change", () => {
    refreshAll();
  });

  q("refreshBtn").addEventListener("click", refreshAll);
  q("dialogViewerClose").addEventListener("click", closeDialogViewer);
  q("clientId").addEventListener("change", () => {
    state.expandedVisit = null;
    state.threadCache = {};
    closeDialogViewer();
    refreshAll();
  });
  for (const id of ["eventTypeFilter", "sidFilter", "requestIdFilter"]) {
    q(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") refreshAll();
    });
  }

  await refreshAll();
}

window.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});
