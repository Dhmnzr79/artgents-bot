// No server/provider/browser needed: exercise actual JSON/SSE client with mocked fetch.
import assert from "node:assert/strict";
import fs from "node:fs";
const source = fs.readFileSync(new URL("../../static/widget/api.js", import.meta.url), "utf8");
const { postAsk, streamAsk, friendlyErrorMessage, TECHNICAL_ERROR_MESSAGE } =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
assert.equal(friendlyErrorMessage(""), "");
for (const code of ["d2_invalid_turn", "d2_turn_failed", "request_in_progress", "private exception details"])
  assert.equal(friendlyErrorMessage(code), TECHNICAL_ERROR_MESSAGE);
const body = { sid: "offline", client_id: "demo", request_id: "stable", q: "test" };
let calls = 0;
const response = (events) => new Response(events.map(([event, data]) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join(""),
  { headers: { "content-type": "text/event-stream" } });
for (const mode of ["http", "sse", "network"]) {
  calls = 0;
  let errors = [], ui = 0, done = 0;
  globalThis.fetch = async (_, options) => {
    calls++;
    assert.deepEqual(JSON.parse(options.body), body);
    if (mode === "network") throw new Error("private network detail");
    if (mode === "http") return Response.json({ error: "d2_turn_failed" }, { status: 503 });
    return response([["error", { error: "d2_invalid_turn" }]]);
  };
  await streamAsk("", body, { onError: (code, retryable) => errors.push([friendlyErrorMessage(code), retryable]),
    onUi: () => ui++, onDone: () => done++ });
  assert.deepEqual(errors, [[TECHNICAL_ERROR_MESSAGE, mode === "network"]]);
  assert.equal(calls, mode === "network" ? 2 : 1); // Existing same-ID transport replay only.
  assert.equal(ui, 0); assert.equal(done, 0);
}
for (const mode of ["http", "network", "invalid_json"]) {
  calls = 0;
  globalThis.fetch = async () => {
    calls++;
    if (mode === "network") throw new Error("private error");
    return mode === "http" ? Response.json({ error: "d2_turn_failed" }, { status: 503 }) : new Response("broken");
  };
  await assert.rejects(postAsk("", body), { message: TECHNICAL_ERROR_MESSAGE });
  assert.equal(calls, 1);
}
let completed = 0, published = 0, failed = 0;
globalThis.fetch = async () => response([
  ["ui", { ...body, answer: "Сохранённый ответ", ui: {}, revision: 1 }],
  ["error", { error: "d2_stream_transport_failed" }],
]);
await streamAsk("", body, { onUi: () => published++, onDone: () => completed++, onError: () => failed++ });
assert.deepEqual([published, completed, failed], [1, 1, 0]);
console.log("PASS: friendly error copy, JSON/SSE/network, same-ID replay, committed UI preservation");

for (const code of ["demo_session_limit", "demo_daily_limit"])
  assert.match(friendlyErrorMessage(code), /Вы посмотрели возможности демо/);
assert.match(friendlyErrorMessage("demo_ip_limit"), /Подождите минуту/);
calls = 0;
let quotaErrors = [];
globalThis.fetch = async () => {
  calls++;
  return response([["error", { error: "demo_daily_limit" }]]);
};
await streamAsk("", body, { onError: (code, retryable) => quotaErrors.push([code, retryable]) });
assert.deepEqual(quotaErrors, [["demo_daily_limit", false]]);
assert.equal(calls, 1);
globalThis.fetch = async () => Response.json({ error: "demo_session_limit" }, { status: 429 });
await assert.rejects(postAsk("", body), { message: friendlyErrorMessage("demo_session_limit") });
console.log("PASS: demo limit messages and no automatic retry");
