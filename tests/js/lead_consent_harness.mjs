/** Actual frozen D2 consent UI, compact layout, unchecked/cancel/reset and typed acceptance. */
import {spawn} from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const runner = `
import {mountWidget} from "/static/widget/widget.js";
const originalFetch=globalThis.fetch;
const configs=await originalFetch("/configs.json").then(r=>r.json());
const fixtures=await originalFetch("/payloads.json").then(r=>r.json());
const sent=[];
let rejectedAction=null;
const sse=payload=>'event: ui\\ndata: '+JSON.stringify(payload)+'\\n\\nevent: done\\ndata: {}\\n\\n';
globalThis.fetch=async(url,options={})=>{
  if(String(url).includes('/api/video-catalog'))return new Response('{"videos":{}}');
  if(!String(url).endsWith('/ask/stream'))throw new Error('Unexpected network '+url);
  const body=JSON.parse(options.body);sent.push(body);
  if(rejectedAction&&body.ref===rejectedAction.ref){
    const status=rejectedAction.status;rejectedAction=null;
    return new Response('{"error":"d2_stale_ui_action"}',{status,headers:{'content-type':'application/json'}});
  }
  const payload=body.ref==='lead:consent_accept'?fixtures.accepted:
    body.ref==='lead:cancel'?fixtures.cancelled:fixtures.prompt;
  return new Response(sse({...payload,sid:body.sid,request_id:body.request_id}),{headers:{'content-type':'text/event-stream'}});
};
const assert=(value,why)=>{if(!value)throw new Error(why);};
const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,30));}throw new Error('Wait timeout');};
try{
  const el=document.createElement('div');document.body.appendChild(el);
  const widget=mountWidget(el,configs.nikadent);
  el.querySelector('[data-clinic-launcher]').click();
  const input=el.querySelector('[data-clinic-input]');
  async function start(){
    input.value='Хочу записаться';input.dispatchEvent(new Event('input',{bubbles:true}));
    el.querySelector('[data-clinic-send]').click();await wait(()=>el.querySelector('[data-lead-consent-check]'));
  }
  await start();
  let checkbox=el.querySelector('[data-lead-consent-check]');
  let next=el.querySelector('[data-lead-consent-accept]');
  assert(!checkbox.checked&&next.disabled&&input.disabled,'Consent must start unchecked and lock contacts');
  const links=[...el.querySelectorAll('.clinic-lead-consent a')];
  assert(links.length===2&&links[0].href===fixtures.prompt.ui.lead_consent.consent_url&&
    links[1].href===fixtures.prompt.ui.lead_consent.policy_url,'Configured legal links missing');
  assert(links.every(a=>a.target==='_blank'&&a.rel.includes('noopener')),'Unsafe legal links');
  assert(!el.querySelector('[data-followup-ref="lead:consent_accept"]'),'Consent action duplicated as ordinary link');
  const before=sent.length;next.click();
  input.value='Анна';el.querySelector('[data-clinic-composer-form]').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(r=>setTimeout(r,100));assert(sent.length===before,'Unchecked contact bypass');
  checkbox.checked=true;checkbox.dispatchEvent(new Event('change',{bubbles:true}));
  assert(!next.disabled,'Checked continue unavailable');next.click();
  await wait(()=>!input.disabled&&!el.querySelector('.clinic-lead-consent'));
  const accepted=sent.at(-1);
  assert(accepted.ref==='lead:consent_accept'&&accepted.ui_revision===fixtures.prompt.revision&&accepted.q==='','Acceptance wire mismatch');
  widget.resetSession();await start();
  assert(!el.querySelector('[data-lead-consent-check]').checked,'Consent carried across reset');
  el.querySelector('[data-lead-consent-cancel]').click();
  await wait(()=>!input.disabled&&!el.querySelector('.clinic-lead-consent'));
  assert(sent.at(-1).ref==='lead:cancel','Skip must use published cancellation');
  for(const [ref,status] of [['lead:consent_accept',503],['lead:cancel',400]]){
    widget.resetSession();await start();rejectedAction={ref,status};
    if(ref==='lead:consent_accept'){
      const check=el.querySelector('[data-lead-consent-check]');check.checked=true;
      check.dispatchEvent(new Event('change',{bubbles:true}));el.querySelector('[data-lead-consent-accept]').click();
    }else el.querySelector('[data-lead-consent-cancel]').click();
    await wait(()=>el.querySelector('[data-clinic-error-reset]'));
    el.querySelector('[data-clinic-error-reset]').click();
    assert(!input.disabled&&!el.querySelector('[data-clinic-err]')&&el.querySelector('.clinic-shell__welcome-screen'),
      'Rejected consent action left real client locked');
  }
  widget.resetSession();await start();
  window.__LEAD_CONSENT_RESULT__={passed:true,requests:sent.length,accepts:sent.filter(b=>b.ref==='lead:consent_accept').length};
  window.__LEAD_CONSENT_VISUAL__=()=>{const b=el.querySelector('.clinic-lead-consent');
    return {height:b.getBoundingClientRect().height,scroll:el.querySelector('.clinic-shell__panel').scrollWidth,
      font:parseFloat(getComputedStyle(b).fontSize)};};
}catch(error){window.__LEAD_CONSENT_ERROR__=String(error.stack||error);}
`;

class Cdp {
  constructor(ws) {
    this.ws=ws;this.id=0;this.pending=new Map();
    ws.addEventListener("message",event=>{
      const message=JSON.parse(String(event.data));const pending=this.pending.get(message.id);
      if(!pending)return;this.pending.delete(message.id);clearTimeout(pending.timer);
      message.error ? pending.reject(new Error(JSON.stringify(message.error))) : pending.resolve(message.result);
    });
  }
  send(method,params={}) {
    const id=++this.id;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error("CDP timeout: "+method)),10000);
      this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params}));
    });
  }
}

async function main() {
  const executable=["C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe"].find(fs.existsSync);
  if(!executable)throw new Error("Chrome/Edge required");
  const configs=Object.fromEntries(["demo","nikadent"].map(id=>[id,{
    ...JSON.parse(fs.readFileSync(path.join(root,"clients",id,"widget_config.json"),"utf8")),
    clientId:id,apiBase:"",clinicName:id==="nikadent" ? "НикаДент" : "Artgents",
    avatarUrl:id==="nikadent" ? "/static/clients/nikadent/avatar-placeholder.svg" : "/static/avatar.png"}]));
  const server=http.createServer((req,res)=>{
    const pathname=new URL(req.url,"http://127.0.0.1").pathname;
    if(pathname==="/payloads.json"){res.setHeader("content-type","application/json");res.end(fs.readFileSync(process.env.LEAD_CONSENT_PAYLOADS_FILE));return;}
    if(pathname==="/configs.json"){res.setHeader("content-type","application/json");res.end(JSON.stringify(configs));return;}
    if(pathname==="/runner.mjs"){res.setHeader("content-type","application/javascript");res.end(runner);return;}
    if(pathname==="/"){res.setHeader("content-type","text/html");res.end('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/widget/widget.css"><script type="module" src="/runner.mjs"></script>');return;}
    const target=path.resolve(root,"."+pathname);
    if(!target.startsWith(root+path.sep)||!pathname.startsWith("/static/")||!fs.existsSync(target)){res.writeHead(404);res.end();return;}
    res.setHeader("content-type",target.endsWith(".js")?"application/javascript":
      target.endsWith(".svg")?"image/svg+xml":target.endsWith(".png")?"image/png":"text/css");res.end(fs.readFileSync(target));
  });
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const origin=`http://127.0.0.1:${server.address().port}`;
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),"lead-consent-widget-"));
  const browser=spawn(executable,["--headless=new","--disable-gpu","--no-first-run","--disable-background-networking",
    `--user-data-dir=${profile}`,"--remote-debugging-port=0","about:blank"],{stdio:"ignore",windowsHide:true});
  let ws;
  try {
    const portFile=path.join(profile,"DevToolsActivePort");
    for(let i=0;i<100&&!fs.existsSync(portFile);i++)await sleep(100);
    const port=fs.readFileSync(portFile,"utf8").split("\n")[0].trim();
    const tabs=await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json());
    ws=new WebSocket(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);
    await new Promise(resolve=>ws.addEventListener("open",resolve,{once:true}));
    const cdp=new Cdp(ws);const external=[];
    ws.addEventListener("message",event=>{const m=JSON.parse(String(event.data));
      if(m.method==="Network.requestWillBeSent"&&!m.params.request.url.startsWith(origin)&&
          !m.params.request.url.startsWith("data:"))external.push(m.params.request.url);});
    await cdp.send("Network.enable");await cdp.send("Page.navigate",{url:origin});
    for(let i=0;i<350;i++) {
      const {result}=await cdp.send("Runtime.evaluate",{expression:"({result:window.__LEAD_CONSENT_RESULT__,error:window.__LEAD_CONSENT_ERROR__})",returnByValue:true});
      if(result.value?.error)throw new Error(result.value.error);
      if(result.value?.result) {
        if(external.length)throw new Error("External widget requests: "+JSON.stringify(external));
        for(const width of [390,900]) {
          await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:950,deviceScaleFactor:1,mobile:width<520});
          const geometry=await cdp.send("Runtime.evaluate",{expression:"window.__LEAD_CONSENT_VISUAL__()",returnByValue:true});
          if(geometry.result.value.scroll>width||geometry.result.value.height>210||geometry.result.value.font<13)throw new Error("Overflow/menu size: "+JSON.stringify(geometry));
          if(process.env.LEAD_CONSENT_VISUAL_DIR) {
            const output=path.resolve(process.env.LEAD_CONSENT_VISUAL_DIR);
            if(!output.startsWith(path.resolve(os.tmpdir())+path.sep))throw new Error("Visual output must be in temp");
            fs.mkdirSync(output,{recursive:true});
            await sleep(400); // Finish the existing launcher/open transition before visual QA.
            const screenshot=await cdp.send("Page.captureScreenshot",{format:"png"});
            fs.writeFileSync(path.join(output,`lead-consent-${width}.png`),Buffer.from(screenshot.data,"base64"));
          }
        }
        console.log("LEAD_CONSENT_EVIDENCE:"+JSON.stringify(result.value.result));return;
      }
      await sleep(100);
    }
    throw new Error("Page menu browser timeout");
  } finally {
    ws?.close();browser.kill("SIGTERM");
    await new Promise(resolve=>{browser.once("exit",resolve);setTimeout(resolve,3000);});server.close();
    if(!path.resolve(profile).startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(profile).startsWith("lead-consent-widget-"))throw new Error("Unsafe temp cleanup");
    fs.rmSync(profile,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
