const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync("static/widget/widget.js", "utf8").replace(/\r\n/g, "\n");
const helpers = source.slice(source.indexOf("/** Phone-shaped"), source.indexOf("/**\n * @typedef {Object} StarterPrompt"));
const handlers = source.slice(source.indexOf("  function isLeadPhoneStep()"), source.indexOf("  if (launcherTeaserEl)", source.indexOf("  function isLeadPhoneStep()")));
const context = {state: {lastPayload: {ui:{composer_input_mode:"phone"}}}, input: {value:"",selectionStart:0,selectionEnd:0,classList:{toggle(){}}}, sendBtn:{},autoResizeTextarea(){}};
vm.createContext(context);
vm.runInContext(helpers + handlers, context);
const run = code => vm.runInContext(code, context);
for (const raw of ["+7(999) 999-99-99", "89999999999", "9999999999"]) {
 context.input.value=raw; context.input.selectionStart=raw.length;
 run("onComposerInput({inputType:'insertFromPaste'})");
 assert.equal(context.input.value,"+7(999) 999-99-99");
 assert.equal(run("ruPhoneToBackendE164(input.value)"),"+79999999999");
 assert.equal(context.sendBtn.disabled,false);
}
for (const raw of ["+7(999) 999-99-991", "+1(999) 999-99-99", "99999", "+", "+7"]) {
 context.input.value=raw; context.input.selectionStart=raw.length;
 run("onComposerInput({inputType:'insertFromPaste'})");
 assert.equal(context.sendBtn.disabled,true);
 assert.equal(run("ruPhoneToBackendE164(input.value)"),"");
 if (raw.length > 10) assert.equal(context.input.value,raw);
}
for (const raw of ["А где вы?", "Отменить запись", ""]) {
 context.input.value=raw; context.input.selectionStart=raw.length;
 run("onComposerInput({inputType:'insertText'})");
 assert.equal(context.input.value,raw);
 assert.equal(context.sendBtn.disabled,!raw);
}
context.input.value="+7(999) 999-99-9";
run("onComposerInput({inputType:'deleteContentBackward'})");
assert.equal(context.input.value,"+7(999) 999-99-9");
context.input.value="";
run("onComposerInput({inputType:'deleteContentBackward'})");
assert.equal(context.input.value,"");
run("syncComposerLeadUi()");
assert.equal(context.input.inputMode,"tel");
assert.equal(context.input.placeholder,"+7(999) 999-99-99");
context.state.lastPayload={ui:{composer_input_mode:"text"}};
run("syncComposerLeadUi()");
assert.equal(context.input.inputMode,"text");
assert.equal(context.input.placeholder,"Введите сообщение");
console.log("Phone mask: paste, overflow, foreign prefix, text, deletion and mode transitions PASS");


context.state.lastPayload={ui:{composer_input_mode:"phone"}};
for (const raw of ["9999999999", "89999999999", "79999999999"]) {
 context.input.value="";
 for (const digit of raw) {
  context.input.value += digit;
  context.input.selectionStart=context.input.value.length;
  run("onComposerInput({inputType:'insertText'})");
 }
 assert.equal(context.input.value,"+7(999) 999-99-99");
 assert.equal(context.sendBtn.disabled,false);
}

const sends = [];
Object.assign(context, {
 config:{}, clientId:"demo", apiBase:"", crypto:{randomUUID:()=>"offline"},
 feed:{querySelector:()=>null}, isSecretSessionResetCommand:()=>false,
 dismissTrailingsAll(){}, dismissLinksAll(){}, setError(){},
 getSid:()=>"offline", beginPendingRequest(){},
 async runStreamAsk(feed, base, body){sends.push(body);}
});
context.state.started=true;
context.state.messages=[];
const sendFunction = source.slice(source.indexOf("  async function sendFromComposer()"), source.indexOf("  function isLeadPhoneStep()"));
vm.runInContext(sendFunction, context);
(async () => {
 for (const raw of ["+7(999) 999-99-99", "А где вы?", "+7(999) 999-99-991"]) {
  context.input.value=raw;
  await run("sendFromComposer()");
 }
 assert.deepEqual(sends.map(item=>item.q),["+79999999999", "А где вы?"]);
 assert.equal(context.input.value,"+7(999) 999-99-991");
 console.log("Phone mask submission: normalized contact, intact question, overflow blocked PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
