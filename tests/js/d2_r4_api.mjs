import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../../static/widget/api.js", import.meta.url), "utf8");
const { streamAsk } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const body = { client_id: "demo", sid: "synthetic", request_id: "one", q: "test" };
const ui = { answer: "answer", ui: {}, revision: 1, ...body };
const sse = (events) => events.map(([kind, data]) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`).join("");
const response = (events) => new Response(sse(events), {
  status: 200, headers: { "content-type": "text/event-stream" },
});

let requests = [];
globalThis.fetch = async (_url, options) => {
  requests.push(JSON.parse(options.body));
  return requests.length === 1
    ? response([["ui", ui]])
    : response([["ui", ui], ["done", { outcome: "final", committed: true }]]);
};
let shown = 0;
let done = 0;
let errors = 0;
await streamAsk("", body, {
  onUi: () => { shown += 1; },
  onDone: () => { done += 1; },
  onError: () => { errors += 1; },
});
assert.equal(requests.length, 2);
assert.equal(requests[0].request_id, requests[1].request_id);
assert.equal(shown, 1);
assert.equal(done, 1);
assert.equal(errors, 0);

requests = [];
globalThis.fetch = async (_url, options) => {
  requests.push(JSON.parse(options.body));
  return response([["ui", ui], ["error", {
    error: "materializer_failed", stage: "materializer", committed: false,
  }]]);
};
done = 0;
let retryable;
await streamAsk("", body, {
  onDone: () => { done += 1; },
  onError: (_message, retry) => { retryable = retry; },
});
assert.equal(requests.length, 1);
assert.equal(done, 0);
assert.equal(retryable, true);

requests = [];
globalThis.fetch = async (_url, options) => {
  requests.push(JSON.parse(options.body));
  return response([["error", { error: "ui_action_invalid", stage: "d2_gate", committed: false }]]);
};
await streamAsk("", body, { onError: (_message, retry) => { retryable = retry; } });
assert.equal(requests.length, 1);
assert.equal(retryable, false);

requests = [];
globalThis.fetch = async (_url, options) => {
  requests.push(JSON.parse(options.body));
  return response([["error", {
    error: "tenant_binding_failed", stage: "tenant_binding", committed: false,
  }]]);
};
await streamAsk("", body, { onError: (_message, retry) => { retryable = retry; } });
assert.equal(requests.length, 1);
assert.equal(retryable, false);

requests = [];
done = 0;
globalThis.fetch = async (_url, options) => {
  requests.push(JSON.parse(options.body));
  return new Response(JSON.stringify(ui), {
    status: 200, headers: { "content-type": "application/json" },
  });
};
await streamAsk("", body, {
  onDone: () => { done += 1; },
  onError: (_message, retry) => { retryable = retry; },
});
assert.equal(requests.length, 2);
assert.equal(done, 0);
assert.equal(retryable, true);
console.log("D2_R4_API_PASS");
