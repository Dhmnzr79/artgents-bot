/** CP6c offline browser proof: real widget.js + api.js, mocked D2 transport. */
import { spawn } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const browsers = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const runner = `
import { mountWidget } from "/static/widget/widget.js";
import { renderBotAnswerHtml } from "/static/widget/answer_format.js";
const fixture = await fetch("/payloads.json").then((response) => response.json());
const root = document.createElement("div");
document.body.append(root);
const sent = [];
const failures = new Map();
const sse = (events) => events.map(([kind, data]) =>
  "event: " + kind + "\\ndata: " + JSON.stringify(data) + "\\n\\n").join("");
const { first, second, scope, lead, afterUi, manual, terminal, video,
        p2Price, p2Includes, p2Stages } = fixture;
const scopeChoice = first.ui.quick_replies.find((item) => item.reply_id.endsWith("one_tooth"));
const leadButton = second.ui.buttons.find((item) => item.action_kind === "cta");
if (!scopeChoice || !leadButton) throw new Error("real D2 fixture lacks required typed actions");
function response(payload, failAt) {
  const full = sse([["status", { message: "Проверяю вопрос" }], ["typing", { phase: "writing" }],
                    ["ui", payload], ["done", {}]]);
  const partial = failAt === "before" ? sse([["status", { message: "Проверяю вопрос" }]])
    : failAt === "after" ? sse([["status", { message: "Проверяю вопрос" }], ["ui", payload]]) : full;
  const bytes = new TextEncoder().encode(partial);
  let read = false;
  return new Response(new ReadableStream({
    pull(controller) {
      if (!read) { read = true; controller.enqueue(bytes); return; }
      if (failAt) { controller.error(new TypeError("simulated disconnect")); return; }
      controller.close();
    },
  }), { status: 200, headers: { "content-type": "text/event-stream" } });
}
globalThis.fetch = async (url, options = {}) => {
  const path = String(url);
  if (path.includes("/api/video-catalog")) return new Response('{"videos":{}}',
    { status: 200, headers: { "content-type": "application/json" } });
  if (!path.endsWith("/ask/stream")) throw new Error("unexpected network: " + path);
  const body = JSON.parse(options.body);
  sent.push(body);
  const count = (failures.get(body.request_id) || 0) + 1;
  failures.set(body.request_id, count);
  const forRequest = (payload) => ({ ...payload, request_id: body.request_id });
  if (body.ref === scopeChoice.reply_id) return response(forRequest(scope));
  if (body.ref === "button:" + leadButton.button_id) return response(forRequest(lead));
  if (body.q === "после UI") return response(forRequest(afterUi), count === 1 ? "after" : null);
  if (body.q === "ручной повтор") return response(forRequest(manual), count <= 2 ? "before" : null);
  if (body.q === "terminal") return response(forRequest(terminal));
  if (body.q === "video") return response(forRequest(video));
  if (p2Price && body.q === "детальная цена") return response(forRequest(p2Price));
  if (p2Includes && body.ref === "price_detail:includes") return response(forRequest(p2Includes));
  if (p2Stages && body.ref === "price_detail:stages") return response(forRequest(p2Stages));
  if (body.q === "error") return new Response(sse([["status", { message: "Проверяю вопрос" }],
    ["error", { error: "d2_invalid_turn" }]]),
    { status: 200, headers: { "content-type": "text/event-stream" } });
  if (body.q === "первый") {
    const distinct = new Set(sent.filter((item) => item.q === "первый").map((item) => item.request_id));
    return distinct.size === 1 ? response(forRequest(first), count === 1 ? "before" : null)
      : response(forRequest(second));
  }
  throw new Error("unexpected body: " + JSON.stringify(body));
};
const widget = mountWidget(root, {
  schemaVersion: 1, apiBase: location.origin, clientId: "demo", botName: "Тест",
  onlineLabel: "Онлайн", welcomeText: "Добро пожаловать", starterPrompts: [],
  launcherCtaLabel: "Задать вопрос", launcherSubtitle: null, videoAspect: "horizontal",
  demoLauncher: false, launcherTeaser: false,
});
const launcher = root.querySelector("[data-clinic-launcher]");
launcher.click();
async function waitUntil(fn) {
  for (let i = 0; i < 160; i++) { if (fn()) return; await new Promise(r => setTimeout(r, 50)); }
  throw new Error("browser wait timeout: " + JSON.stringify({ sent, text: root.textContent.slice(-500) }));
}
async function send(text) {
  const input = root.querySelector("[data-clinic-input]");
  input.value = text;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  root.querySelector("[data-clinic-send]").click();
}
function botBodies() { return [...root.querySelectorAll(".clinic-turn .clinic-msg__body")]
  .map(x => x.textContent.trim()); }
const sameRenderedText = (actual, expected) => {
  const box = document.createElement("div");
  box.innerHTML = renderBotAnswerHtml(expected);
  const compact = (value) => value.replace(/\\s+/gu, "");
  return compact(actual) === compact(box.textContent);
};
try {
  await send("первый");
  await waitUntil(() => botBodies().length === 1);
  if (sent.length !== 2 || sent[0].request_id !== sent[1].request_id) throw new Error("before-ui retry ID changed");
  if (!sameRenderedText(botBodies()[0], first.answer))
    throw new Error("wrong first D2 text: " + JSON.stringify({ actual: botBodies()[0], expected: first.answer }));
  if (root.querySelectorAll(".clinic-turn .clinic-msg__body")[0].querySelectorAll("ul li").length !== 3)
    throw new Error("compact price list did not render as three list items");
  const link = root.querySelector(".clinic-msg__link");
  if (!link || link.textContent.trim() !== scopeChoice.label) throw new Error("scope UI missing");
  link.click();
  await waitUntil(() => botBodies().length === 2);
  if (sent.at(-1).ref !== scopeChoice.reply_id || sent.at(-1).ui_revision !== first.revision)
    throw new Error("typed scope wire mismatch");
  if ([...root.querySelectorAll(".clinic-turn")][0].querySelector(".clinic-turn__btn--cta-primary"))
    throw new Error("stale CTA remained interactive");

  await send("первый");
  await waitUntil(() => botBodies().length === 3);
  const secondRequest = sent.at(-1);
  if (secondRequest.request_id === sent[0].request_id) throw new Error("new turn reused request ID");

  const cta = root.querySelector(".clinic-turn:last-of-type .clinic-turn__btn--cta-primary") ||
    [...root.querySelectorAll(".clinic-turn__btn--cta-primary")].at(-1);
  if (!cta) throw new Error("D2 CTA missing");
  cta.click();
  await waitUntil(() => botBodies().length === 4);
  if (sent.at(-1).ref !== "button:" + leadButton.button_id || sent.at(-1).ui_revision !== second.revision)
    throw new Error("typed lead CTA wire mismatch");
  if (!sameRenderedText(botBodies().at(-1), lead.answer)) throw new Error("lead owner answer missing");

  await send("после UI");
  await waitUntil(() => botBodies().length === 5);
  const lastTwo = sent.slice(-2);
  if (lastTwo[0].request_id !== lastTwo[1].request_id) throw new Error("after-ui retry ID changed");
  if (!sameRenderedText(botBodies().at(-1), afterUi.answer)) throw new Error("after-ui final mismatch");
  if (root.querySelectorAll(".clinic-turn").length !== 5) throw new Error("duplicate bot bubble");
  await send("ручной повтор");
  await waitUntil(() => root.querySelector(".clinic-shell__error button") !== null);
  root.querySelector(".clinic-shell__error button").click();
  await waitUntil(() => botBodies().length === 6);
  const manualAttempts = sent.filter((item) => item.q === "ручной повтор");
  if (manualAttempts.length !== 3 || new Set(manualAttempts.map((item) => item.request_id)).size !== 1)
    throw new Error("manual retry changed logical request ID");

  widget.resetSession();
  await send("terminal");
  await waitUntil(() => botBodies().length === 1);
  if ([...root.querySelectorAll(".clinic-turn")].at(-1).querySelector(".clinic-turn__btn--cta-primary"))
    throw new Error("terminal gained an unplanned CTA");
  await send("error");
  await waitUntil(() => root.querySelector("[data-clinic-err]")?.textContent.includes("Не удалось подготовить ответ"));
  if (root.querySelector("[data-clinic-err]")?.textContent.includes("d2_invalid_turn"))
    throw new Error("technical D2 error leaked into widget");
  if (botBodies().length !== 1 || root.querySelector("[data-clinic-err] button"))
    throw new Error("terminal SSE error created UI or retry");
  widget.resetSession();
  await send("video");
  await waitUntil(() => botBodies().length === 1);
  const videoButton = root.querySelector(".clinic-msg__link[aria-label='Посмотреть видео с врачом']");
  if (!videoButton || !sameRenderedText(botBodies()[0], video.answer))
    throw new Error("D2 secondary video projection missing");
  if (p2Price && p2Includes && p2Stages) {
    widget.resetSession();
    await send("детальная цена");
    await waitUntil(() => botBodies().length === 1);
    const detailLinks = [...root.querySelectorAll(".clinic-msg__link")];
    const includesLink = detailLinks.find((item) => item.textContent.trim() === "Что входит");
    const stagesLink = detailLinks.find((item) => item.textContent.trim() === "Этапы оплаты");
    if (!includesLink || !stagesLink) throw new Error("price detail actions missing");
    includesLink.click();
    await waitUntil(() => botBodies().length === 2);
    if (sent.at(-1).ref !== "price_detail:includes" || sent.at(-1).ui_revision !== p2Price.revision)
      throw new Error("includes action wire mismatch");
    if (!sameRenderedText(botBodies().at(-1), p2Includes.answer))
      throw new Error("includes detail render mismatch");
    const nextStages = [...root.querySelectorAll(".clinic-msg__link")]
      .find((item) => item.textContent.trim() === "Этапы оплаты");
    if (!nextStages) throw new Error("stage detail navigation missing");
    nextStages.click();
    await waitUntil(() => botBodies().length === 3);
    if (sent.at(-1).ref !== "price_detail:stages" || sent.at(-1).ui_revision !== p2Includes.revision)
      throw new Error("stages action wire mismatch");
    if (!sameRenderedText(botBodies().at(-1), p2Stages.answer))
      throw new Error("stages detail render mismatch");
  }
  window.__D2_WIDGET_RESULT__ = {
    passed: true, requests: sent.length, before_retry_same_id: true,
    after_retry_same_id: true, one_bubble_per_turn: true,
    manual_retry_same_id: true, terminal_without_cta: true, error_without_ui: true,
    secondary_video_from_d2: true,
    scope_ref: sent.find(x => x.ref?.startsWith("volume:"))?.ref,
    lead_ref: sent.find(x => x.ref?.startsWith("button:"))?.ref,
    price_detail_ref: sent.find(x => x.ref === "price_detail:includes")?.ref,
  };
  window.__D2_PRICE_PREVIEW__ = (text) => {
    const body = root.querySelector(".clinic-turn .clinic-msg__body");
    body.innerHTML = renderBotAnswerHtml(text);
    body.classList.add("clinic-msg__body--rich");
    return body.querySelectorAll("ul li").length;
  };
} catch (error) { window.__D2_WIDGET_ERROR__ = String(error.stack || error); }
`;

function startServer() {
  const payloadPath = process.env.D2_WIDGET_PAYLOADS_FILE;
  if (!payloadPath || !fs.existsSync(payloadPath)) throw new Error("real D2 payload fixture required");
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, "http://127.0.0.1").pathname;
    if (pathname === "/payloads.json") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(fs.readFileSync(payloadPath)); return;
    }
    if (pathname === "/runner.mjs") {
      res.writeHead(200, { "content-type": "application/javascript" });
      res.end(runner); return;
    }
    if (pathname === "/") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end('<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/static/widget/widget.css"></head><body><script type="module" src="/runner.mjs"></script></body></html>'); return;
    }
    const target = path.resolve(root, "." + pathname);
    if (!target.startsWith(root + path.sep) || !fs.existsSync(target)) {
      res.writeHead(404); res.end(); return;
    }
    res.writeHead(200, { "content-type": target.endsWith(".js") ? "application/javascript" : "text/css" });
    res.end(fs.readFileSync(target));
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () =>
    resolve({ server, origin: `http://127.0.0.1:${server.address().port}` })));
}

class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (!this.pending.has(message.id)) return;
      const { resolve, reject, timer } = this.pending.get(message.id);
      clearTimeout(timer);
      this.pending.delete(message.id);
      message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("CDP timeout: " + method));
      }, 10000);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function main() {
  const executable = browsers.find((candidate) => fs.existsSync(candidate));
  if (!executable) throw new Error("Chrome/Edge unavailable");
  const { server, origin } = await startServer();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "d2-widget-"));
  const browser = spawn(executable, ["--headless=new", "--disable-gpu", "--no-first-run",
    "--disable-background-networking",
    `--user-data-dir=${profile}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] });
  let ws;
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await sleep(100);
    if (!fs.existsSync(portFile)) throw new Error("CDP port timeout");
    const port = fs.readFileSync(portFile, "utf8").split("\n")[0].trim();
    const tabs = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json());
    ws = new WebSocket(tabs.find((tab) => tab.type === "page").webSocketDebuggerUrl);
    await new Promise((resolve) => ws.addEventListener("open", resolve, { once: true }));
    const cdp = new Cdp(ws);
    const browserMessages = [];
    const pageRequests = [];
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (message.method === "Network.requestWillBeSent")
        pageRequests.push(message.params.request.url);
      if (message.method === "Runtime.exceptionThrown")
        browserMessages.push(JSON.stringify({
          description: message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text,
          url: message.params.exceptionDetails.url,
          line: message.params.exceptionDetails.lineNumber,
        }));
      if (message.method === "Runtime.consoleAPICalled")
        browserMessages.push((message.params.args || []).map((arg) => arg.value || arg.description).join(" "));
    });
    await cdp.send("Runtime.enable");
    await cdp.send("Network.enable");
    await cdp.send("Page.enable");
    await cdp.send("Page.navigate", { url: origin });
    for (let i = 0; i < 200; i++) {
      const result = await cdp.send("Runtime.evaluate", {
        expression: "({result:window.__D2_WIDGET_RESULT__,error:window.__D2_WIDGET_ERROR__})",
        returnByValue: true,
      });
      if (result.result.value.error) throw new Error(result.result.value.error);
      if (result.result.value.result) {
        if (pageRequests.some((url) => !url.startsWith(origin) && !url.startsWith("data:")))
          throw new Error("external page network request: " + JSON.stringify(pageRequests));
        const visualDir = process.env.D2_P1_VISUAL_DIR;
        if (visualDir) {
          const output = path.resolve(visualDir);
          if (!output.startsWith(path.resolve(os.tmpdir()) + path.sep))
            throw new Error("visual output must be under the temp directory");
          fs.mkdirSync(output, { recursive: true });
          const preview = "**Классическая имплантация**\n\n" +
            "- Implantium — **76 200 ₽**\n" +
            "- Impro — **85 200 ₽**\n" +
            "- Nobel Biocare — **101 200 ₽**\n\n" +
            "за восстановление одного зуба (имплант + постоянная коронка); " +
            "КТ при необходимости и временная коронка — отдельно";
          const previewResult = await cdp.send("Runtime.evaluate", {
            expression: `window.__D2_PRICE_PREVIEW__(${JSON.stringify(preview)})`,
            returnByValue: true,
          });
          if (previewResult.result.value !== 3) throw new Error("price preview list missing");
          for (const width of [360, 768]) {
            await cdp.send("Emulation.setDeviceMetricsOverride", {
              width, height: 900, deviceScaleFactor: 1, mobile: width === 360,
            });
            const geometry = await cdp.send("Runtime.evaluate", {
              expression: "(() => { const b=document.querySelector('.clinic-turn .clinic-msg__body'); return {width:b.clientWidth,scroll:b.scrollWidth,items:b.querySelectorAll('ul li').length}; })()",
              returnByValue: true,
            });
            if (geometry.result.value.scroll > geometry.result.value.width || geometry.result.value.items !== 3)
              throw new Error("price preview overflow: " + JSON.stringify({ width, geometry: geometry.result.value }));
            const screenshot = await cdp.send("Page.captureScreenshot", { format: "png" });
            const target = path.join(output, `price-${width}.png`);
            fs.writeFileSync(target, Buffer.from(screenshot.data, "base64"));
            console.log("D2_PRICE_VISUAL:" + JSON.stringify({ target, width, geometry: geometry.result.value }));
          }
        }
        console.log("D2_WIDGET_EVIDENCE:" + JSON.stringify(result.result.value.result));
        return;
      }
      await sleep(100);
    }
    const debug = await cdp.send("Runtime.evaluate", {
      expression: "({ready:document.readyState,text:document.body.innerText.slice(-600),turns:document.querySelectorAll('.clinic-turn').length,error:window.__D2_WIDGET_ERROR__})",
      returnByValue: true,
    });
    throw new Error("D2 widget browser scenario timed out: " + JSON.stringify({
      debug: debug.result.value, browserMessages: browserMessages.slice(-12),
    }));
  } finally {
    if (ws) ws.close();
    browser.kill("SIGTERM");
    await new Promise((resolve) => { browser.once("exit", resolve); setTimeout(resolve, 3000); });
    server.close();
    const tempRoot = path.resolve(os.tmpdir()) + path.sep;
    if (!path.resolve(profile).startsWith(tempRoot) || !path.basename(profile).startsWith("d2-widget-"))
      throw new Error("unsafe browser profile cleanup path");
    fs.rmSync(profile, { recursive: true, force: true });
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
