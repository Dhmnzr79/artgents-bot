import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../../static/widget/widget.js", import.meta.url), "utf8");
function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const open = source.indexOf("{", start);
  let depth = 1, end = open + 1;
  for (; depth; end++) {
    if (source[end] === "{") depth++;
    if (source[end] === "}") depth--;
  }
  return source.slice(start, end);
}
let nextId = 0;
const timers = new Map();
const state = { pending: false, lastPayload: null };
const transitions = [];
const context = vm.createContext({
  state, performance: { now: () => 0 },
  window: {
    setTimeout(fn, delay) { const id = ++nextId; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
  },
  renderFeed() {}, updateTypingIndicatorText() { transitions.push(state.typingPhase); },
  isLeadFlowAskBody(body) { return body?.ref?.startsWith("lead:"); },
});
vm.runInContext("let waitingLabelTimers = [];" + ["clearWaitingLabelTimers",
  "beginPendingRequest", "setTypingPhase", "endPendingRequest", "typingStatusLabel",
  "resolveTurnAttributionKind"].map(functionSource).join("\n")
  + "\nfunction isLeadFlowBotMeta(){return false;} function isPlainAttributionRoute(){return false;}", context);

assert.equal(context.typingStatusLabel("searching"), "Ищет в базе клиники");
assert.equal(context.typingStatusLabel("checking"), "Проверяет информацию");
assert.equal(context.typingStatusLabel("writing"), "Печатает ответ");
for (const kind of ["content", "lead", "plain"]) {
  assert.equal(context.resolveTurnAttributionKind({ attribution_kind: kind }), kind);
}
assert.equal(context.resolveTurnAttributionKind({}), "plain");
context.beginPendingRequest({ q: "Вопрос" });
assert.equal(state.typingPhase, "searching");
const steps = [...timers.values()].sort((a, b) => a.delay - b.delay);
steps[0].fn(); assert.equal(state.typingPhase, "checking");
steps[1].fn(); assert.equal(state.typingPhase, "writing");
context.endPendingRequest(); assert.equal(timers.size, 0);
context.beginPendingRequest({ q: "Следующий вопрос" });
context.setTypingPhase("writing"); assert.equal(timers.size, 0);
context.endPendingRequest();
context.beginPendingRequest({ ref: "lead:continue" });
assert.equal(state.typingPhase, "writing");
assert.equal(timers.size, 0);
context.endPendingRequest();
state.lastPayload = { attribution_kind: "lead" };
context.beginPendingRequest({ q: "Денис" });
assert.equal(state.typingPhase, "writing");
assert.equal(timers.size, 0);
context.endPendingRequest();
assert.deepEqual(transitions.slice(0, 3), ["searching", "checking", "writing"]);
console.log("PASS: waiting labels, attribution and timer cancellation; provider calls 0");
