/** Actual widget DOM/path/click proof; only local static HTTP and mocked /ask. */
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
const originalFetch = globalThis.fetch;
const configs = await originalFetch("/configs.json").then(r => r.json());
const sent = [];
globalThis.fetch = async (url, options = {}) => {
  if (String(url).includes("/api/video-catalog")) return new Response('{"videos":{}}');
  if (String(url).endsWith('/api/widget-session')) return new Response(JSON.stringify({client_id:JSON.parse(options.body).client_id,entries:[],current:null,actions_current:false}));
  if (!String(url).endsWith("/ask/stream")) throw new Error("Unexpected widget network: " + url);
  sent.push(JSON.parse(options.body));
  // Terminal mocked transport failure keeps the test independent of model semantics.
  return new Response('event: error\\ndata: {"error":"d2_invalid_turn"}\\n\\nevent: done\\ndata: {}\\n\\n',
    {headers:{"content-type":"text/event-stream"}});
};
const assert = (ok, why) => { if (!ok) throw new Error(why); };
const wait = async fn => {
  for (let n=0;n<100;n++) {if(fn())return;await new Promise(r=>setTimeout(r,30));}
  throw new Error("Wait timeout");
};
const mounts = [];
function mount(config, pathname, options) {
  history.replaceState({}, "", pathname);
  const el = document.createElement("div");document.body.appendChild(el);
  const widget = mountWidget(el, config, options);
  const launcher = el.querySelector("[data-clinic-launcher-open], [data-clinic-launcher]");
  assert(launcher,"Widget failed to mount");launcher.click();
  mounts.push(el);
  return {el, widget};
}
const buttons = el => [...el.querySelectorAll(".clinic-shell__welcome-actions .clinic-msg__link")];
const check = (el, menu, promo) => {
  assert(el.querySelector(".clinic-shell__welcome-text-body").textContent === menu.welcomeText, "Wrong welcome");
  assert(JSON.stringify(buttons(el).map(b=>b.querySelector(".clinic-msg__link-text").textContent)) ===
    JSON.stringify(menu.starterPrompts.map(p=>p.label)), "Wrong prompts/extra gallery");
  assert(el.querySelector(".clinic-shell__welcome-promo strong").textContent === promo.title,"Promotion changed");
  assert(el.querySelector(".clinic-shell__welcome-promo small").textContent === promo.subtitle,"Promotion conditions changed");
};
try {
  const nika = configs.nikadent;
  const routes = ["/", "/doctors/", "/prices/", "/unknown/", "/all-on-4", "/all-on-4/?utm_source=secret#anchor",
    "/semnoe-protezirovanie/", "/koronki-i-nesemnoe-protezirovanie/", "/all-on-4/child/", "/ALL-ON-4/"];
  for (const route of routes) {
    const expected = nika.pageMenus.find(m=>m.paths.some(p=>p.replace(/\\/+$/, "") ===
      route.split(/[?#]/)[0].replace(/\\/+$/, ""))) || nika;
    const {el,widget} = mount(nika, route);
    check(el,expected,nika.welcomePromotion);
    for (let i=0;i<3;i++) {
      const before = sent.length;buttons(el)[i].click();
      await wait(()=>sent.length>before && !el.querySelector(".clinic-shell__welcome-screen"));
      const body = sent.at(-1);
      assert(body.q === expected.starterPrompts[i].q,"Configured q not sent");
      assert(body.client_id === "nikadent","Tenant changed");
      assert(!body.ref && !body.ui_revision,"Invented governed UI reference");
      assert(!JSON.stringify(body).includes("utm_source") && !body.pagePath && !body.pageUrl,"Page context leaked");
      assert(body.entry_page_path === (route.split(/[?#]/)[0].replace(/\\/+$/, '') || '/'),"Initial pathname not captured");
      await wait(()=>!el.querySelector(".clinic-shell__typing.is-visible"));
      widget.resetSession();
      await wait(()=>el.querySelector(".clinic-shell__welcome-screen"));
      check(el,expected,nika.welcomePromotion);
    }
    el.remove();
  }
  const {el,widget} = mount(nika,"/");
  history.replaceState({},"","/all-on-4/");
  const initialBefore=sent.length;buttons(el)[0].click();await wait(()=>sent.length>initialBefore);
  assert(sent.at(-1).entry_page_path==='/',"Navigation before first send changed initial page");
  await wait(()=>!el.querySelector(".clinic-shell__typing.is-visible"));
  history.replaceState({},"","/all-on-4/");
  widget.resetSession();check(el,nika.pageMenus[0],nika.welcomePromotion);el.remove();
  const preview = mount(nika,"/static/widget-test.html?client=nikadent",{pagePath:"/semnoe-protezirovanie/"});
  check(preview.el,nika.pageMenus[1],nika.welcomePromotion);preview.el.remove();
  // Explicit mode owns all three buttons even for a tenant with a case gallery.
  const explicitDemo = mount({...nika,clientId:"demo"},"/");
  check(explicitDemo.el,nika,nika.welcomePromotion);explicitDemo.el.remove();
  const demo = mount(configs.demo,"/");
  assert(buttons(demo.el).length === 3,"Existing demo menu changed");
  assert(buttons(demo.el).some(b=>b.textContent.includes('До и после')),"Demo gallery missing");demo.el.remove();
  const promo = mount(nika,"/all-on-4/");
  const before = sent.length;promo.el.querySelector(".clinic-shell__welcome-promo").click();
  await wait(()=>sent.length>before);
  assert(sent.at(-1).q === nika.welcomePromotion.q,"Shared promo q changed");promo.el.remove();
  window.__PAGE_MENU_RESULT__ = {passed:true,routes:routes.length,clicks:sent.length};
  window.__PAGE_MENU_VISUAL__ = () => {
    for(const el of mounts)el.remove();
    const view=mount(nika,"/all-on-4/");
    const box=view.el.querySelector(".clinic-shell__panel") || view.el;
    return {width:box.clientWidth,scroll:box.scrollWidth,buttons:buttons(view.el).length};
  };
} catch(error) {window.__PAGE_MENU_ERROR__=String(error.stack || error);}
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
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),"page-menu-widget-"));
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
      const {result}=await cdp.send("Runtime.evaluate",{expression:"({result:window.__PAGE_MENU_RESULT__,error:window.__PAGE_MENU_ERROR__})",returnByValue:true});
      if(result.value?.error)throw new Error(result.value.error);
      if(result.value?.result) {
        if(external.length)throw new Error("External widget requests: "+JSON.stringify(external));
        for(const width of [390,900]) {
          await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:950,deviceScaleFactor:1,mobile:width<520});
          const geometry=await cdp.send("Runtime.evaluate",{expression:"window.__PAGE_MENU_VISUAL__()",returnByValue:true});
          if(geometry.result.value.scroll>width||geometry.result.value.buttons!==3)throw new Error("Overflow/menu size: "+JSON.stringify(geometry));
          if(process.env.PAGE_MENU_VISUAL_DIR) {
            const output=path.resolve(process.env.PAGE_MENU_VISUAL_DIR);
            if(!output.startsWith(path.resolve(os.tmpdir())+path.sep))throw new Error("Visual output must be in temp");
            fs.mkdirSync(output,{recursive:true});
            await sleep(400); // Finish the existing launcher/open transition before visual QA.
            const screenshot=await cdp.send("Page.captureScreenshot",{format:"png"});
            fs.writeFileSync(path.join(output,`page-menu-${width}.png`),Buffer.from(screenshot.data,"base64"));
          }
        }
        console.log("PAGE_MENU_EVIDENCE:"+JSON.stringify(result.value.result));return;
      }
      await sleep(100);
    }
    throw new Error("Page menu browser timeout");
  } finally {
    ws?.close();browser.kill("SIGTERM");
    await new Promise(resolve=>{browser.once("exit",resolve);setTimeout(resolve,3000);});server.close();
    if(!path.resolve(profile).startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(profile).startsWith("page-menu-widget-"))throw new Error("Unsafe temp cleanup");
    fs.rmSync(profile,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
