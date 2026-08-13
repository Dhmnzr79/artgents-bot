/**
 * Stage 5.2A offline Widget/SSE evidence harness.
 *
 * Runs real static/widget/api.js + widget.js in headless Chrome (CDP).
 * No provider/network calls — fetch is mocked to return chunked SSE/JSON.
 *
 * CLI: node tests/js/stage52_widget_sse_harness.mjs [E1|E2|...|E8|all]
 * Emits one JSON line prefixed with STAGE52_EVIDENCE:
 */
import { spawn } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CHROME_CANDIDATES = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];

const WHITENING_PARTIAL = "Профессиональное отбеливание";
const WHITENING_FULL =
  "Профессиональное отбеливание проводится без боли. Стоимость от 15 000 ₽.";

const API_SHIM_SOURCE = `import { streamAsk as realStreamAsk, postAsk } from "/__stage52__/api.real.mjs";

export const callbackCounts = { ui: 0, done: 0, error: 0, delta: 0, status: 0, typing: 0 };

export async function streamAsk(apiBase, body, callbacks = {}) {
  const wrapped = {
    ...callbacks,
    onStatus: (m) => { callbackCounts.status++; callbacks.onStatus?.(m); },
    onTyping: (p) => { callbackCounts.typing++; callbacks.onTyping?.(p); },
    onDelta: (d) => { callbackCounts.delta++; callbacks.onDelta?.(d); },
    onUi: (d) => { callbackCounts.ui++; callbacks.onUi?.(d); },
    onDone: () => { callbackCounts.done++; callbacks.onDone?.(); },
    onError: (m) => { callbackCounts.error++; callbacks.onError?.(m); },
  };
  return realStreamAsk(apiBase, body, wrapped);
}

export { postAsk };
`;

const RUNNER_SOURCE = `
const WHITENING_PARTIAL = ${JSON.stringify(WHITENING_PARTIAL)};
const WHITENING_FULL = ${JSON.stringify(WHITENING_FULL)};

import { mountWidget } from "/static/widget/widget.js";
import { callbackCounts } from "/__stage52__/api_shim.mjs";

const params = new URLSearchParams(location.search);
const scenario = params.get("scenario") || "E1";

function sseLine(event, dataObj) {
  return "event: " + event + "\\ndata: " + JSON.stringify(dataObj) + "\\n\\n";
}

function buildSse(events) {
  return events.map(([ev, data]) => sseLine(ev, data)).join("");
}

function makeNetworkGuard() {
  let attempts = 0;
  const allow = (url) => {
    const u = String(url);
    return u.startsWith(location.origin) || u.startsWith("http://127.0.0.1:") || u.startsWith("http://localhost:");
  };
  const realFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (!allow(url)) {
      attempts += 1;
      throw new Error("NETWORK_BLOCKED:" + url);
    }
    if (url.includes("/api/video-catalog")) {
      return realFetch(input, init);
    }
    if (
      url.includes("/__stage52__/t7/") ||
      url.includes("/__stage52__/e-before/") ||
      url.includes("/__stage52__/e-after/")
    ) {
      return realFetch(input, init);
    }
    if (globalThis.__stage52_fetch_mock) {
      return globalThis.__stage52_fetch_mock(url, init);
    }
    throw new Error("UNMOCKED_FETCH:" + url);
  };
  return {
    get attempts() { return attempts; },
  };
}

function sseResponse(body, chunkSize = 7, delayMs = 0) {
  const bytes = new TextEncoder().encode(body);
  let pos = 0;
  const stream = new ReadableStream({
    async pull(controller) {
      if (pos >= bytes.length) {
        controller.close();
        return;
      }
      if (delayMs > 0) await sleep(delayMs);
      const end = Math.min(bytes.length, pos + chunkSize);
      controller.enqueue(bytes.slice(pos, end));
      pos = end;
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function jsonResponse(obj) {
  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function widgetConfig() {
  return {
    apiBase: location.origin,
    clientId: "demo",
    botName: "Тест",
    onlineLabel: "Онлайн",
    welcomeText: "Добро пожаловать",
    starterPrompts: [],
    demoLauncher: false,
    launcherTeaser: false,
  };
}

function feedEl(root) {
  return root.querySelector("[data-clinic-feed]");
}

function countDom(feed) {
  const live = feed.querySelectorAll("[data-live-bubble]").length;
  const finalTurns = feed.querySelectorAll(".clinic-turn").length;
  const streaming = feed.querySelectorAll(".clinic-msg--bot--streaming").length;
  const bodies = [...feed.querySelectorAll(".clinic-turn .clinic-msg__body")].map((el) =>
    (el.textContent || "").trim()
  );
  const liveBodies = [...feed.querySelectorAll("[data-live-bubble] .clinic-msg__body")].map((el) =>
    (el.textContent || "").trim()
  );
  return { live, finalTurns, streaming, bodies, liveBodies, totalBotBubbles: finalTurns + live };
}

function feedVisibleText(feed) {
  return (feed.textContent || "").replace(/\\s+/g, " ").trim();
}

async function openChat(root) {
  const launcher = root.querySelector("[data-clinic-launcher]");
  if (launcher) launcher.click();
  await sleep(50);
}

async function sendComposer(root, text) {
  const input = root.querySelector("[data-clinic-input]");
  const send = root.querySelector("[data-clinic-send]");
  if (!input || !send) throw new Error("composer_missing");
  input.value = text;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await sleep(20);
  send.click();
}

async function waitUntil(fn, timeoutMs = 8000, stepMs = 50) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (fn()) return;
    await sleep(stepMs);
  }
  throw new Error("waitUntil_timeout");
}

function resetCallbackCounts() {
  for (const k of Object.keys(callbackCounts)) callbackCounts[k] = 0;
}

async function runE1(network) {
  const sse = buildSse([
    ["status", { message: "Проверяю вопрос" }],
    ["text_delta", { delta: WHITENING_PARTIAL }],
    ["typing", { phase: "writing" }],
    ["ui", {
      answer: WHITENING_FULL,
      meta: { service_route: "sales_fast_materialized", provider_calls: 1, sid: "e1-sid" },
    }],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 5);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  const before = countDom(feed);
  await sendComposer(root, "Расскажите про отбеливание");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  await sleep(100);
  const after = countDom(feed);
  const visible = feedVisibleText(feed);
  return {
    scenario: "E1",
    sse_sequence: ["status", "text_delta", "typing", "ui", "done"],
    chunk_size: 5,
    callbacks: { ...callbackCounts },
    dom: { before, after, during: null },
    final_visible_text: after.bodies[after.bodies.length - 1] || "",
    control_metadata_visible:
      visible.includes("sales_fast_materialized") || visible.includes("provider_calls"),
    network_attempts: network.attempts,
    stream_matches_final: WHITENING_PARTIAL !== WHITENING_FULL,
  };
}

async function runE2(network) {
  globalThis.__stage52_fetch_mock = () => {
    const part1 = buildSse([
      ["status", { message: "Проверяю вопрос" }],
      ["typing", { phase: "writing" }],
      ["text_delta", { delta: WHITENING_PARTIAL }],
    ]);
    const part2 = buildSse([
      ["ui", { answer: WHITENING_FULL, meta: { sid: "e2-sid" } }],
      ["done", {}],
    ]);
    const bytes1 = new TextEncoder().encode(part1);
    const bytes2 = new TextEncoder().encode(part2);
    let stage = 0;
    const stream = new ReadableStream({
      async pull(controller) {
        if (stage === 0) {
          controller.enqueue(bytes1);
          stage = 1;
          await sleep(350);
          return;
        }
        if (stage === 1) {
          controller.enqueue(bytes2);
          stage = 2;
          return;
        }
        controller.close();
      },
    });
    return new Response(stream, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  };
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Расскажите про отбеливание");
  let during = null;
  const t0 = Date.now();
  while (Date.now() - t0 < 2500) {
    const c = countDom(feed);
    if (c.live > 0 || c.streaming > 0) {
      during = c;
      break;
    }
    await sleep(25);
  }
  await waitUntil(() => countDom(feed).finalTurns >= 1, 10000);
  await sleep(100);
  const after = countDom(feed);
  return {
    scenario: "E2",
    sse_sequence: ["status", "text_delta", "typing", "ui", "done"],
    chunk_size: 6,
    callbacks: { ...callbackCounts },
    dom: { during, after },
    partial_stream_text: WHITENING_PARTIAL,
    final_text: after.bodies[after.bodies.length - 1] || "",
    partial_not_concatenated: !(after.bodies.join("").includes(WHITENING_PARTIAL + WHITENING_FULL)),
    network_attempts: network.attempts,
  };
}

async function runE3(network) {
  const sse = buildSse([
    ["status", { message: "Проверяю вопрос" }],
    ["text_delta", { delta: "Часть" }],
    ["ui", { answer: "Часть ответа", meta: { sid: "e3-sid" } }],
    ["done", {}],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 4);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Тест duplicate done");
  await waitUntil(() => countDom(feed).finalTurns >= 1, 10000);
  await sleep(150);
  const after = countDom(feed);
  return {
    scenario: "E3",
    sse_sequence: ["status", "text_delta", "ui", "done", "done"],
    chunk_size: 4,
    callbacks: { ...callbackCounts },
    dom: { after },
    network_attempts: network.attempts,
  };
}

async function runE4(network) {
  const sse = buildSse([
    ["ui", { answer: "Ответ A", meta: { sid: "e4-sid" } }],
    ["ui", { answer: "Ответ B", meta: { sid: "e4-sid" } }],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 8);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Тест duplicate ui");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  await sleep(100);
  const after = countDom(feed);
  return {
    scenario: "E4",
    sse_sequence: ["ui", "ui", "done"],
    chunk_size: 8,
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    network_attempts: network.attempts,
  };
}

async function runE5(network) {
  const sse = buildSse([["ui", { answer: "OnlyUi", meta: { sid: "e5-sid" } }]]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 3);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Тест EOF");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  const after = countDom(feed);
  return {
    scenario: "E5",
    sse_sequence: ["ui", "EOF"],
    chunk_size: 3,
    callbacks: { ...callbackCounts },
    dom: { after },
    network_attempts: network.attempts,
  };
}

async function runE6(network) {
  const results = {};
  // E6a: ui → done → ui
  {
    const sse = buildSse([
      ["ui", { answer: "Final A", meta: { sid: "e6a-sid" } }],
      ["done", {}],
      ["ui", { answer: "Late B", meta: { sid: "e6a-sid" } }],
    ]);
    globalThis.__stage52_fetch_mock = () => sseResponse(sse, 5);
    const root = document.createElement("div");
    document.body.appendChild(root);
    resetCallbackCounts();
    mountWidget(root, widgetConfig());
    await openChat(root);
    const feed = feedEl(root);
    await sendComposer(root, "E6a");
    await waitUntil(() => countDom(feed).finalTurns >= 1);
    await sleep(100);
    results.E6a = {
      callbacks: { ...callbackCounts },
      dom: countDom(feed),
      final_text: countDom(feed).bodies.join("|"),
    };
    document.body.removeChild(root);
  }
  // E6b: ui → done → extra bytes (ignored by parser if incomplete)
  {
    const body =
      buildSse([
        ["ui", { answer: "Final B", meta: { sid: "e6b-sid" } }],
        ["done", {}],
      ]) + "event: status\\ndata: {\\"message\\":\\"late\\"}\\n\\n";
    globalThis.__stage52_fetch_mock = () => sseResponse(body, 9);
    const root = document.createElement("div");
    document.body.appendChild(root);
    resetCallbackCounts();
    mountWidget(root, widgetConfig());
    await openChat(root);
    const feed = feedEl(root);
    await sendComposer(root, "E6b");
    await waitUntil(() => countDom(feed).finalTurns >= 1);
    await sleep(100);
    results.E6b = {
      callbacks: { ...callbackCounts },
      dom: countDom(feed),
    };
    document.body.removeChild(root);
  }
  return {
    scenario: "E6",
    subcases: results,
    network_attempts: network.attempts,
  };
}

function widgetConfigForApiBase(apiBaseSuffix) {
  return {
    ...widgetConfig(),
    apiBase: location.origin + apiBaseSuffix,
  };
}

function mockStreamResponse(body, readImpl) {
  return {
    ok: true,
    headers: { get: () => "text/event-stream" },
    body: {
      getReader() {
        return { read: readImpl };
      },
    },
  };
}

function sseAbortAfterUiResponse(body) {
  const bytes = new TextEncoder().encode(body);
  let reads = 0;
  return mockStreamResponse(body, async () => {
    reads += 1;
    if (reads === 1) return { value: bytes, done: false };
    throw new TypeError("network error");
  });
}

function sseErrorBeforeUiResponse() {
  return mockStreamResponse("", async () => {
    throw new TypeError("network error");
  });
}

function sseErrorAfterFinalResponse(body) {
  const bytes = new TextEncoder().encode(body);
  let reads = 0;
  return mockStreamResponse(body, async () => {
    reads += 1;
    if (reads === 1) return { value: bytes, done: false };
    throw new TypeError("network error");
  });
}

function sendDisabled(root) {
  return root.querySelector("[data-clinic-send]")?.disabled ?? null;
}

function pendingActive(root) {
  return root.querySelector(".clinic-shell__typing-wrap")?.classList.contains("is-visible") ?? false;
}

async function runE7(network) {
  const sse = buildSse([
    ["ui", { answer: "Ответ A", meta: { sid: "t7-sid" } }],
  ]);
  globalThis.__stage52_fetch_mock = () => sseAbortAfterUiResponse(sse);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "T7 reader error after UI");
  await waitUntil(() => countDom(feed).finalTurns >= 1, 10000);
  await sleep(300);
  await sleep(100);
  const after = countDom(feed);
  return {
    scenario: "E7",
    transport: "reader_error_after_ui_bytes",
    sse_sequence: ["ui", "reader_error"],
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    pending_cleared: !pendingActive(root),
    network_attempts: network.attempts,
  };
}

async function runE10(network) {
  const sse = buildSse([
    ["ui", {}],
    ["ui", { answer: "Ответ B", meta: { sid: "t8-sid" } }],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 6);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "T8 invalid UI then valid UI");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  await sleep(100);
  const after = countDom(feed);
  return {
    scenario: "E10",
    sse_sequence: ["ui({})", "ui(valid)", "done"],
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    network_attempts: network.attempts,
  };
}

async function runE11(network) {
  globalThis.__stage52_fetch_mock = () => sseErrorBeforeUiResponse();
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  const send = root.querySelector("[data-clinic-send]");
  await sendComposer(root, "Error before UI");
  await waitUntil(() => callbackCounts.error >= 1, 10000);
  await sleep(300);
  await sleep(100);
  const after = countDom(feed);
  return {
    scenario: "E11",
    sse_sequence: ["reader_error"],
    callbacks: { ...callbackCounts },
    dom: { after },
    pending_cleared: !pendingActive(root),
    network_attempts: network.attempts,
  };
}

async function runE12(network) {
  const sse = buildSse([
    ["ui", { answer: "Final A", meta: { sid: "e12-sid" } }],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseErrorAfterFinalResponse(sse);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Error after final");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  await sleep(150);
  const after = countDom(feed);
  return {
    scenario: "E12",
    sse_sequence: ["ui", "done", "reader_error"],
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    network_attempts: network.attempts,
  };
}

async function runEJson(network) {
  globalThis.__stage52_fetch_mock = () =>
    jsonResponse({ answer: "Json path", meta: { sid: "e7-sid" } });
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Json fallback");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  const after = countDom(feed);
  return {
    scenario: "EJson",
    response_kind: "json",
    callbacks: { ...callbackCounts },
    dom: { after },
    network_attempts: network.attempts,
  };
}

async function runE8(network) {
  let resolveFirst;
  const firstGate = new Promise((r) => {
    resolveFirst = r;
  });
  let firstFetch = true;
  globalThis.__stage52_fetch_mock = (url) => {
    if (!String(url).includes("/ask/stream")) {
      throw new Error("unexpected_url:" + url);
    }
    if (firstFetch) {
      firstFetch = false;
      const sse = buildSse([
        ["status", { message: "Медленный" }],
        ["text_delta", { delta: "Медленно" }],
      ]);
      const p = sseResponse(sse, 5);
      resolveFirst();
      return p;
    }
    const sse = buildSse([
      ["ui", { answer: "Быстрый второй", meta: { sid: "e8-sid" } }],
      ["done", {}],
    ]);
    return sseResponse(sse, 5);
  };
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  // First turn with followup
  globalThis.__stage52_fetch_mock = () => {
    const sse = buildSse([
      [
        "ui",
        {
          answer: "Первый с кнопкой",
          meta: { sid: "e8-sid" },
          quick_replies: [{ label: "Ссылка", ref: "svc:test" }],
        },
      ],
      ["done", {}],
    ]);
    return sseResponse(sse, 7);
  };
  await sendComposer(root, "Первый");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  await waitUntil(() => feed.querySelector(".clinic-msg__link") !== null, 5000);
  const afterFirst = countDom(feed);
  // Slow second via composer
  let slowReleased = false;
  globalThis.__stage52_fetch_mock = (url) => {
    if (!slowReleased) {
      return new Promise((resolve) => {
        setTimeout(() => {
          slowReleased = true;
          const sse = buildSse([
            ["ui", { answer: "Медленный финал", meta: { sid: "e8-sid" } }],
            ["done", {}],
          ]);
          resolve(sseResponse(sse, 5));
        }, 1200);
      });
    }
    const sse = buildSse([
      ["ui", { answer: "Быстрый followup", meta: { sid: "e8-sid" } }],
      ["done", {}],
    ]);
    return sseResponse(sse, 5);
  };
  const composerPromise = sendComposer(root, "Второй медленный");
  await sleep(100);
  const pendingWhileSlow = {
    sendDisabled: root.querySelector("[data-clinic-send]")?.disabled ?? null,
    dom: countDom(feed),
  };
  const link = feed.querySelector(".clinic-msg__link");
  let followupWhilePending = null;
  if (link) {
    link.click();
    await sleep(400);
    followupWhilePending = {
      dom: countDom(feed),
      userRows: feed.querySelectorAll(".clinic-row--user").length,
    };
  }
  await composerPromise;
  await sleep(1600);
  const afterAll = countDom(feed);
  return {
    scenario: "E8",
    after_first_turn: afterFirst,
    pending_while_slow: pendingWhileSlow,
    followup_while_pending: followupWhilePending,
    followup_blocked_reason:
      followupWhilePending === null ? "links_dismissed_on_composer_send" : null,
    final_dom: afterAll,
    callbacks: { ...callbackCounts },
    network_attempts: network.attempts,
  };
}

async function runE3b(network) {
  const sse = buildSse([
    ["text_delta", { delta: "Только " }],
    ["text_delta", { delta: "стрим" }],
    ["done", {}],
    ["done", {}],
  ]);
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 3);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "Тест stream fallback duplicate done");
  await waitUntil(() => countDom(feed).finalTurns >= 1, 10000);
  await sleep(150);
  const after = countDom(feed);
  return {
    scenario: "E3b",
    sse_sequence: ["text_delta", "text_delta", "done", "done"],
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    network_attempts: network.attempts,
  };
}

async function runE9(network) {
  const sse =
    "event: text_delta\\r\\n" +
    'data: {"delta":"X"}\\r\\n\\r\\n' +
    "event: ui\\r\\n" +
    'data: {"answer":"X","meta":{"sid":"e9-sid"}}\\r\\n\\r\\n' +
    "event: done\\r\\n" +
    "data: {}\\r\\n\\r\\n" +
    "event: done\\r\\n" +
    "data: {}\\r\\n\\r\\n";
  globalThis.__stage52_fetch_mock = () => sseResponse(sse, 3);
  const root = document.createElement("div");
  document.body.appendChild(root);
  resetCallbackCounts();
  mountWidget(root, widgetConfig());
  await openChat(root);
  const feed = feedEl(root);
  await sendComposer(root, "CRLF chunking");
  await waitUntil(() => countDom(feed).finalTurns >= 1);
  const after = countDom(feed);
  return {
    scenario: "E9",
    sse_sequence: ["text_delta", "ui", "done", "done"],
    chunk_size: 3,
    callbacks: { ...callbackCounts },
    dom: { after },
    final_text: after.bodies[after.bodies.length - 1] || "",
    network_attempts: network.attempts,
  };
}

const SCENARIOS = {
  E1: runE1,
  E2: runE2,
  E3: runE3,
  E3b: runE3b,
  E4: runE4,
  E5: runE5,
  E6: runE6,
  E7: runE7,
  E8: runE8,
  E9: runE9,
  E10: runE10,
  E11: runE11,
  E12: runE12,
  EJson: runEJson,
};

export async function runBrowserScenario(scenarioId) {
  const fn = SCENARIOS[scenarioId];
  if (!fn) throw new Error("unknown_scenario:" + scenarioId);
  const network = makeNetworkGuard();
  return fn(network);
}

if (typeof window !== "undefined") {
  const scenario = new URLSearchParams(location.search).get("scenario") || "E1";
  runBrowserScenario(scenario)
    .then((result) => {
      window.__STAGE52_RESULT__ = result;
    })
    .catch((err) => {
      window.__STAGE52_ERROR__ = String(err && err.stack ? err.stack : err);
    });
}
`;

function findChrome() {
  for (const p of CHROME_CANDIDATES) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function waitForProcess(proc, timeoutMs = 5000) {
  return new Promise((resolve) => {
    if (proc.exitCode !== null) {
      resolve(proc.exitCode);
      return;
    }
    const timer = setTimeout(() => resolve(null), timeoutMs);
    proc.once("exit", (code) => {
      clearTimeout(timer);
      resolve(code);
    });
  });
}

async function removeDirWithRetry(dirPath, attempts = 5) {
  for (let i = 0; i < attempts; i++) {
    try {
      fs.rmSync(dirPath, { recursive: true, force: true });
      return;
    } catch {
      if (i < attempts - 1) await sleep(150 * (i + 1));
    }
  }
}

function contentType(filePath) {
  if (filePath.endsWith(".js") || filePath.endsWith(".mjs")) return "application/javascript; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function writeSseAbortAfterUi(res, answer, sid) {
  const payload = JSON.stringify({ answer, meta: { sid } });
  const chunk = `event: ui\ndata: ${payload}\n\n`;
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.write(chunk);
  setImmediate(() => {
    if (res.socket && !res.socket.destroyed) {
      res.socket.destroy();
    } else {
      res.destroy();
    }
  });
}

function startStaticServer() {
  const shimUrl = "/__stage52__/api_shim.mjs";
  const realApiPath = path.join(REPO_ROOT, "static", "widget", "api.js");

  const server = http.createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      if (url.pathname === "/__stage52__/api_shim.mjs") {
        res.writeHead(200, { "Content-Type": "application/javascript; charset=utf-8" });
        res.end(API_SHIM_SOURCE);
        return;
      }
      if (url.pathname === "/__stage52__/api.real.mjs") {
        res.writeHead(200, { "Content-Type": "application/javascript; charset=utf-8" });
        res.end(fs.readFileSync(realApiPath, "utf8"));
        return;
      }
      if (url.pathname === "/__stage52__/runner.mjs") {
        res.writeHead(200, { "Content-Type": "application/javascript; charset=utf-8" });
        res.end(RUNNER_SOURCE);
        return;
      }
      if (url.pathname === "/__stage52__/page.html") {
        const scenario = url.searchParams.get("scenario") || "E1";
        const html = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8" />
<script type="importmap">
{"imports":{"/static/widget/api.js":"${shimUrl}"}}
</script>
<link rel="stylesheet" href="/static/widget/widget.css" />
</head><body>
<script type="module" src="/__stage52__/runner.mjs?scenario=${scenario}"></script>
</body></html>`;
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(html);
        return;
      }
      if (url.pathname === "/__stage52__/t7/ask/stream" && req.method === "POST") {
        void readRequestBody(req)
          .then(() => {
            writeSseAbortAfterUi(res, "Ответ A", "t7-sid");
          })
          .catch(() => {
            if (!res.headersSent) res.writeHead(500);
            res.end();
          });
        return;
      }
      let rel = decodeURIComponent(url.pathname);
      if (rel.startsWith("/")) rel = rel.slice(1);
      const filePath = path.normalize(path.join(REPO_ROOT, rel));
      if (!filePath.startsWith(REPO_ROOT)) {
        res.writeHead(403);
        res.end("forbidden");
        return;
      }
      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": contentType(filePath) });
      res.end(fs.readFileSync(filePath));
    } catch (err) {
      res.writeHead(500);
      res.end(String(err));
    }
  });

  return new Promise((resolve, reject) => {
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({ server, port, origin: `http://127.0.0.1:${port}` });
    });
  });
}

class CdpClient {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 0;
    this.pending = new Map();
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(String(ev.data));
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function runInChrome(origin, scenario) {
  const chromePath = findChrome();
  if (!chromePath) {
    throw new Error("CHROME_NOT_FOUND: no local Chrome/Edge for CDP harness");
  }
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "stage52-chrome-"));
  const proc = spawn(
    chromePath,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--user-data-dir=${userDataDir}`,
      "--remote-debugging-port=0",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] }
  );

  let ws = null;
  try {
    const portFile = path.join(userDataDir, "DevToolsActivePort");
    let cdpPort = null;
    for (let i = 0; i < 80; i++) {
      if (fs.existsSync(portFile)) {
        cdpPort = fs.readFileSync(portFile, "utf8").split("\n")[0].trim();
        break;
      }
      await sleep(100);
    }
    if (!cdpPort) throw new Error("CDP_PORT_TIMEOUT");

    const targets = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then((r) => r.json());
    const page = targets.find((t) => t.type === "page");
    if (!page?.webSocketDebuggerUrl) throw new Error("CDP_PAGE_TARGET_MISSING");

    ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve);
      ws.addEventListener("error", reject);
    });
    const cdp = new CdpClient(ws);
    const consoleLogs = [];
    ws.addEventListener("message", (ev) => {
      try {
        const msg = JSON.parse(String(ev.data));
        if (msg.method === "Runtime.consoleAPICalled") {
          const args = (msg.params?.args || []).map((a) => a.value ?? a.description ?? "");
          consoleLogs.push(args.join(" "));
        }
        if (msg.method === "Runtime.exceptionThrown") {
          const details = msg.params?.exceptionDetails;
          consoleLogs.push(
            "EXCEPTION:" +
              (details?.text || "") +
              " " +
              (details?.exception?.description || "")
          );
        }
      } catch {
        /* ignore */
      }
    });
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable");
    await cdp.send("Page.enable");
    await cdp.send("Page.navigate", {
      url: `${origin}/__stage52__/page.html?scenario=${encodeURIComponent(scenario)}`,
    });

    let result = null;
    let error = null;
    for (let i = 0; i < 160; i++) {
      const evalRes = await cdp.send("Runtime.evaluate", {
        expression: "({r: window.__STAGE52_RESULT__ || null, e: window.__STAGE52_ERROR__ || null})",
        returnByValue: true,
      });
      const payload = evalRes?.result?.value;
      if (payload?.e) {
        error = payload.e;
        break;
      }
      if (payload?.r) {
        result = payload.r;
        break;
      }
      await sleep(100);
    }
    if (error) throw new Error(error);
    if (!result) {
      const debugRes = await cdp.send("Runtime.evaluate", {
        expression: `({
          err: window.__STAGE52_ERROR__ || null,
          href: location.href,
          ready: document.readyState,
          feedTurns: document.querySelectorAll('[data-clinic-feed] .clinic-turn').length,
          live: document.querySelectorAll('[data-live-bubble]').length,
          bodyLen: (document.body && document.body.innerText) ? document.body.innerText.length : 0,
        })`,
        returnByValue: true,
      });
      const dbg = debugRes?.result?.value;
      throw new Error(
        "HARNESS_RESULT_TIMEOUT:" +
          JSON.stringify({ ...dbg, console: consoleLogs.slice(-12) })
      );
    }
    return result;
  } finally {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    } catch {
      /* ignore */
    }
    proc.kill("SIGTERM");
    const exitCode = await waitForProcess(proc, 5000);
    if (exitCode === null) {
      proc.kill("SIGKILL");
      await waitForProcess(proc, 2000);
    }
    await removeDirWithRetry(userDataDir);
  }
}

export async function runScenario(scenario) {
  const { server, origin } = await startStaticServer();
  try {
    const evidence = await runInChrome(origin, scenario);
    return { ...evidence, provider_calls: 0, network_attempts: evidence.network_attempts ?? 0 };
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

async function main() {
  const arg = process.argv[2] || "all";
  if (arg === "--dump-runner") {
    process.stdout.write(RUNNER_SOURCE);
    return;
  }
  if (arg === "--test-parser-b1") {
    const { streamAsk } = await import(pathToFileURL(path.join(REPO_ROOT, "static", "widget", "api.js")).href);
    const sse =
      'event: ui\ndata: {"answer":"Ответ A","meta":{"sid":"t7-sid"}}\n\n';
    let reads = 0;
    const bytes = new TextEncoder().encode(sse);
    globalThis.fetch = async () => ({
      ok: true,
      headers: { get: () => "text/event-stream" },
      body: {
        getReader() {
          return {
            async read() {
              reads += 1;
              if (reads === 1) return { value: bytes, done: false };
              throw new TypeError("network error");
            },
          };
        },
      },
    });
    const counts = { ui: 0, done: 0, error: 0 };
    await streamAsk("", {}, {
      onUi: () => {
        counts.ui += 1;
      },
      onDone: () => {
        counts.done += 1;
      },
      onError: () => {
        counts.error += 1;
      },
    });
    process.stdout.write("PARSER_B1:" + JSON.stringify(counts) + "\n");
    if (counts.ui !== 1 || counts.done !== 1 || counts.error !== 0) process.exit(1);
    return;
  }
  const scenarios =
    arg === "all"
      ? ["E1", "E2", "E3", "E3b", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "EJson"]
      : [arg];
  const out = [];
  for (const sc of scenarios) {
    out.push(await runScenario(sc));
  }
  process.stdout.write("STAGE52_EVIDENCE:" + JSON.stringify(out) + "\n");
}

const isMain =
  process.argv[1] &&
  pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (isMain) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
