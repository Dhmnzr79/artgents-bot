/**
 * Слой HTTP к /ask (без UI).
 * @param {string} apiBase — пустая строка = тот же origin
 * @param {Record<string, unknown>} body
 */
export async function postAsk(apiBase, body) {
  const base = (apiBase || "").replace(/\/$/, "");
  const url = `${base}/ask`;
  // PERF-0: local-only timing (no PII, no network report) — see PERF-0 seam
  // audit "Client (widget) has zero timing instrumentation" finding.
  const perfT0 = performance.now();
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    const err = typeof data.error === "string" ? data.error : res.statusText;
    throw new Error(err || "request_failed");
  }
  if (typeof console !== "undefined" && console.debug) {
    console.debug("[perf] ask_client_ms", {
      first_server_event_ms: Math.round(performance.now() - perfT0),
    });
  }
  return data;
}

/**
 * Стриминговый вызов /ask/stream через SSE (fetch + ReadableStream).
 *
 * Протокол:
 *   event: status      data: {"message": "..."}   — PERF-1 честный ранний статус
 *                                                    (опционален: старые клиенты его
 *                                                    просто не обрабатывают, ничего
 *                                                    не ломается — см. onStatus)
 *   event: typing      data: {"phase":"searching"|"writing"} — фаза индикатора
 *   event: text_delta  data: {"delta": "..."}   — токен ответа (пока не используется)
 *   event: ui          data: {полный payload}    — UI после генерации
 *   event: done        data: {}                  — конец стрима
 *
 * @param {string} apiBase
 * @param {Record<string, unknown>} body
 * @param {{
 *   onStatus?: (message: string) => void,
 *   onTyping?: (phase: "searching" | "writing") => void,
 *   onDelta?: (delta: string) => void,
 *   onUi?: (data: unknown) => void,
 *   onDone?: () => void,
 *   onError?: (msg: string, retryable?: boolean) => void,
 * }} callbacks
 */
export async function streamAsk(apiBase, body, { onStatus, onTyping, onDelta, onUi, onDone, onError } = {}) {
  const base = (apiBase || "").replace(/\/$/, "");
  const url = `${base}/ask/stream`;
  // PERF-0: local-only client timing per SSE event kind — no PII, no network
  // report (see PERF-0 seam audit "Client (widget) has zero timing
  // instrumentation" finding). Each key is set once, at first receipt.
  const perfT0 = performance.now();
  const perfMs = { status: null, typing: null, text_delta: null, ui: null, done: null };
  const markPerfOnce = (key) => {
    if (perfMs[key] === null) perfMs[key] = Math.round(performance.now() - perfT0);
  };

  /** @param {unknown} data */
  const isValidUiPayload = (data) =>
    data && typeof data === "object" && !Array.isArray(data) &&
    typeof data.answer === "string" && data.ui &&
    Number.isInteger(data.revision) && typeof data.request_id === "string" &&
    (!body.request_id || data.request_id === body.request_id) &&
    (!body.client_id || data.client_id === body.client_id) &&
    (!body.sid || data.sid === body.sid);

  let uiAccepted = false;
  let finalized = false;

  /** @param {unknown} data */
  const acceptUiOnce = (data) => {
    if (uiAccepted || finalized || !isValidUiPayload(data)) return;
    uiAccepted = true;
    markPerfOnce("ui");
    onUi?.(data);
  };

  const finalizeOnce = () => {
    if (finalized) return;
    finalized = true;
    markPerfOnce("done");
    onDone?.();
  };

  let lastTransportError = "Не удалось получить ответ";
  for (let attempt = 0; attempt < 2 && !finalized; attempt += 1) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let errMsg = res.statusText || "request_failed";
        try {
          const d = await res.json();
          if (typeof d.error === "string") errMsg = d.error;
        } catch { /* ignore */ }
        if (uiAccepted) finalizeOnce();
        else onError?.(errMsg, false);
        return;
      }

      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = await res.json();
        if (!isValidUiPayload(data)) throw new Error("Некорректный ответ сервера");
        acceptUiOnce(data);
        finalizeOnce();
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE: keep an incomplete final line for the next chunk.
        const parts = buffer.split("\n");
        buffer = parts.pop() ?? "";

        for (const line of parts) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (currentEvent === "status") {
                markPerfOnce("status");
                const message = typeof data.message === "string" ? data.message : "";
                if (message) onStatus?.(message);
              } else if (currentEvent === "typing") {
                markPerfOnce("typing");
                const phase = data.phase === "writing" ? "writing" : "searching";
                onTyping?.(phase);
              } else if (currentEvent === "text_delta") {
                markPerfOnce("text_delta");
                onDelta?.(String(data.delta ?? ""));
              } else if (currentEvent === "ui") {
                acceptUiOnce(data);
              } else if (currentEvent === "error") {
                if (uiAccepted) finalizeOnce();
                else onError?.(typeof data.error === "string" ? data.error : "d2_turn_failed", false);
                return;
              } else if (currentEvent === "done" && uiAccepted) {
                finalizeOnce();
              }
            } catch { /* ignore malformed SSE data */ }
            currentEvent = "";
          }
        }
      }

      if (finalized) break;
      if (typeof console !== "undefined" && console.debug) {
        console.debug("[perf] ask_stream_client_ms", perfMs);
      }
    } catch (e) {
      lastTransportError = e instanceof Error ? e.message : "Ошибка сети";
    }
  }
  if (!finalized) {
    if (uiAccepted) finalizeOnce();
    else onError?.(lastTransportError, true);
  }
}
