/** Actual anchored client launcher, timer/collapse/chat lifecycle, mobile and reduced-motion. */
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
const configs=await originalFetch('/configs.json').then(r=>r.json());
let networkCalls=0;
globalThis.fetch=async url=>{
  networkCalls++;
  if(String(url).includes('/api/video-catalog'))return new Response('{"videos":{}}');
  throw new Error('Launcher must not send /ask or external requests: '+url);
};
const realTimeout=window.setTimeout.bind(window),realClear=window.clearTimeout.bind(window);
const pending=new Map(),delays=[];
window.setTimeout=(fn,delay,...args)=>{
  if(delay===30000){delays.push(delay);const id=realTimeout(()=>{},60000);pending.set(id,()=>fn(...args));return id;}
  return realTimeout(fn,delay,...args);
};
window.clearTimeout=id=>{pending.delete(id);realClear(id);};
const assert=(ok,why)=>{if(!ok)throw new Error(why);};
const wait=async fn=>{for(let i=0;i<120;i++){if(fn())return;await new Promise(r=>realTimeout(r,20));}throw new Error('Wait timeout');};
const sleep=ms=>new Promise(r=>realTimeout(r,ms));
function fire(){assert(pending.size===1,'Exactly one invitation timer expected');const [id,fn]=pending.entries().next().value;pending.delete(id);realClear(id);fn();}
const rect=el=>{const r=el.getBoundingClientRect();return {right:r.right,bottom:r.bottom,width:r.width,height:r.height,left:r.left};};
const sameCorner=(a,b)=>Math.abs(a.right-b.right)<1&&Math.abs(a.bottom-b.bottom)<1;
function mount(id){const el=document.createElement('div');document.body.appendChild(el);return {el,widget:mountWidget(el,configs[id])};}
try{
  sessionStorage.removeItem('clinic_widget_launcher_teaser_shown:nikadent');
  const {el,widget}=mount('nikadent');
  const card=el.querySelector('[data-clinic-launcher-card]');
  const launch=el.querySelector('[data-clinic-launcher]');
  const dismiss=el.querySelector('[data-clinic-launcher-dismiss]');
  assert(card&&launch&&dismiss,'Client capsule missing');
  assert(document.activeElement!==launch,'Mount must not steal focus or show a focus outline');
  assert(getComputedStyle(card).backgroundColor==='rgb(255, 255, 255)','Launcher background must be white');
  const avatar=el.querySelector('[data-clinic-avatar]');await wait(()=>avatar.complete&&avatar.naturalWidth>0);
  assert(avatar.src.includes('/static/clients/nikadent/avatar.png'),'Actual tenant avatar not used');
  const dot=getComputedStyle(el.querySelector('.clinic-shell__header-online-dot--launcher')).backgroundColor;
  assert(dot==='rgb(40, 193, 58)','Online dot is not green');
  assert(launch.textContent.includes('Задать вопрос'),'Wrong launcher label');
  const before=rect(card);assert(dismiss.hidden&&pending.size===1&&delays[0]===30000,'Initial30s state invalid');
  fire();await sleep(450);
  const expanded=rect(card);assert(expanded.width>before.width&&expanded.height>before.height&&sameCorner(before,expanded),'Morph moved anchored corner');
  assert(!dismiss.hidden&&el.querySelector('[data-clinic-launcher-teaser]').getAttribute('aria-hidden')==='false','Invitation not accessible');
  assert(getComputedStyle(el.querySelector('.clinic-shell__launcher-arrow')).color==='rgb(118, 46, 148)','Arrow must use tenant brand');
  dismiss.click();await sleep(400);assert(sameCorner(before,rect(card))&&Math.abs(rect(card).height-before.height)<1,'Dismiss did not collapse in place');
  launch.click();assert(getComputedStyle(card).display==='none'&&launch.getAttribute('aria-expanded')==='true','Actual chat did not open');
  const promotion=el.querySelector('.clinic-shell__welcome-promo');
  assert(getComputedStyle(promotion).backgroundColor==='rgb(245, 239, 248)','Promotion background ignores tenant setting');
  assert(getComputedStyle(el.querySelector('.clinic-shell__promo-icon')).color==='rgb(118, 46, 148)','Promotion accent ignores tenant setting');
  assert(getComputedStyle(el.querySelector('.clinic-shell__promo-more')).color==='rgb(118, 46, 148)','Promotion link ignores tenant setting');
  assert(getComputedStyle(el.querySelector('.clinic-shell__promo-more .clinic-msg__link-chevron')).color==='rgb(118, 46, 148)','Promotion arrow ignores tenant setting');
  const input=el.querySelector('[data-clinic-input]');input.value='Черновик';
  assert(getComputedStyle(el.querySelector('[data-clinic-send]')).backgroundColor==='rgb(118, 46, 148)','Send button must use tenant brand');
  const composer=el.querySelector('.clinic-shell__composer-inner');
  assert(getComputedStyle(composer).borderTopColor==='rgb(118, 46, 148)','Composer border must use tenant brand');
  input.focus();assert(getComputedStyle(composer).borderTopColor==='rgb(118, 46, 148)','Focused composer must keep tenant brand');
  el.querySelector('[data-clinic-close]').click();assert(!pending.size&&dismiss.hidden,'Chat close should return compact capsule without replay');
  assert(document.activeElement===launch,'Closing an open chat must restore launcher focus');
  widget.restartLauncherTeaser();assert(input.value==='Черновик'&&pending.size===1,'Panel replay reset conversation');
  fire();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
  assert(dismiss.hidden,'Escape did not collapse invitation');await sleep(400);
  const savedTheme=configs.nikadent.theme;
  configs.nikadent.theme={promoBackground:'#E0F8EE',promoAccent:'#136943'};
  const second=mount('nikadent');assert(!pending.size,'Seen marker ignored');
  assert(getComputedStyle(second.el.querySelector('.clinic-shell__welcome-promo')).backgroundColor==='rgb(224, 248, 238)','Promotion-only theme needs brand or leaks other tenant');
  assert(getComputedStyle(second.el.querySelector('.clinic-shell__promo-icon')).color==='rgb(19, 105, 67)','Promotion-only accent needs brand');
  assert(getComputedStyle(second.el.querySelector('[data-clinic-send]')).backgroundColor==='rgb(12, 47, 224)','Promotion override changed primary color');
  second.el.remove();configs.nikadent.theme=savedTheme;
  el.remove();const demo=mount('demo');
  assert(!demo.el.querySelector('[data-clinic-launcher-card]')&&demo.el.querySelector('[data-clinic-launcher-open]').textContent.includes('Посмотреть демо'),'Demo launcher changed');
  assert(getComputedStyle(demo.el.querySelector('[data-clinic-send]')).backgroundColor==='rgb(12, 47, 224)','Tenant color leaked into demo');
  assert(getComputedStyle(demo.el.querySelector('.clinic-shell__welcome-promo')).backgroundColor==='rgb(240, 244, 255)','Promotion background leaked into demo');
  assert(!pending.size,'Demo scheduled client invitation');demo.el.remove();
  document.body.appendChild(el);input.value='';
  window.__CLIENT_MOBILE_SCROLL__=async()=>{
    launch.click();
    const feed=el.querySelector('.clinic-shell__feed');
    const filler=document.createElement('div');
    filler.style.cssText='height:4000px;flex-shrink:0';feed.appendChild(filler);
    const viewport=window.visualViewport;
    const heightDescriptor=Object.getOwnPropertyDescriptor(viewport,'height');
    const initialHeight=viewport.height;
    const nextFrame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
    const resize=async height=>{
      Object.defineProperty(viewport,'height',{configurable:true,value:height});
      viewport.dispatchEvent(new Event('resize'));await nextFrame();
      const panel=el.querySelector('.clinic-shell__panel').getBoundingClientRect();
      const composer=el.querySelector('.clinic-shell__composer').getBoundingClientRect();
      assert(Math.abs(panel.height-height)<2,'Mobile panel must follow visible viewport');
      assert(composer.bottom<=panel.bottom+1&&composer.top>=panel.top,'Composer outside visible chat');
    };
    try{
      for(const readingTop of [0,240]){
        input.blur();feed.scrollTop=readingTop;await nextFrame();
        input.focus();await nextFrame();
        assert(Math.abs(feed.scrollTop-readingTop)<2,'Focus lost place in older messages');
        for(const height of [620,460,380,460,620,initialHeight]){
          await resize(height);
          assert(Math.abs(feed.scrollTop-readingTop)<2,'Keyboard resize lost place in older messages: '+JSON.stringify({readingTop,height,actual:feed.scrollTop,scrollHeight:feed.scrollHeight,clientHeight:feed.clientHeight}));
        }
      }
      input.blur();feed.scrollTop=feed.scrollHeight;await nextFrame();
      input.focus();await nextFrame();
      for(const height of [620,460,380,460,620,initialHeight]){
        await resize(height);
        assert(Math.abs(feed.scrollHeight-feed.clientHeight-feed.scrollTop)<2,'Keyboard resize hid latest messages');
      }
      return {passed:true,readingPositions:2,resizeSteps:18};
    }finally{
      if(heightDescriptor)Object.defineProperty(viewport,'height',heightDescriptor);
      else delete viewport.height;
      viewport.dispatchEvent(new Event('resize'));
      filler.remove();input.blur();el.querySelector('[data-clinic-close]').click();
    }
  };
  window.__CLIENT_LAUNCHER_VISUAL__=expanded=>{
    widget.restartLauncherTeaser();const initial=rect(card);if(expanded)fire();
    return {initial};
  };
  window.__CLIENT_LAUNCHER_GEOMETRY__=()=>{
    const body=el.querySelector('[data-clinic-launcher-teaser-text]');
    return {card:rect(card),bodyBottom:body.getBoundingClientRect().bottom,launchTop:launch.getBoundingClientRect().top,
      transition:getComputedStyle(card).transitionDuration};
  };
  window.__CLIENT_LAUNCHER_RESULT__={passed:true,scheduledDelay:delays[0],networkCalls,unchangedDemo:true};
}catch(error){window.__CLIENT_LAUNCHER_ERROR__=String(error.stack||error);}
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
    theme:id==="nikadent" ? {brand:"#762E94",promoBackground:"#F5EFF8",promoAccent:"#762E94"} : {brand:"#0C2FE0"},
    avatarUrl:id==="nikadent" ? "/static/clients/nikadent/avatar.png" : "/static/avatar.png"}]));
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
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),"client-launcher-widget-"));
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
      const {result}=await cdp.send("Runtime.evaluate",{expression:"({result:window.__CLIENT_LAUNCHER_RESULT__,error:window.__CLIENT_LAUNCHER_ERROR__})",returnByValue:true});
      if(result.value?.error)throw new Error(result.value.error);
      if(result.value?.result) {
        if(external.length)throw new Error("External widget requests: "+JSON.stringify(external));
        for(const width of [320,390,900]) {
          await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:800,deviceScaleFactor:1,mobile:width<520});
          if(width<520){
            const check=await cdp.send("Runtime.evaluate",{expression:"window.__CLIENT_MOBILE_SCROLL__()",awaitPromise:true,returnByValue:true});
            if(check.exceptionDetails||!check.result.value?.passed)throw new Error('Mobile scroll: '+JSON.stringify(check));
          }
          for(const expanded of [false,true]) {
            const initial=await cdp.send("Runtime.evaluate",{expression:`window.__CLIENT_LAUNCHER_VISUAL__(${expanded})`,returnByValue:true});
            await sleep(450);
            const geometry=await cdp.send("Runtime.evaluate",{expression:"window.__CLIENT_LAUNCHER_GEOMETRY__()",returnByValue:true});
            const g=geometry.result.value,start=initial.result.value.initial;
            if(g.card.left<0||g.card.right>width||Math.abs(start.right-g.card.right)>1||Math.abs(start.bottom-g.card.bottom)>1)
              throw new Error("Launcher overflow/moved corner: "+JSON.stringify({width,expanded,g,start}));
            if(expanded&&g.bodyBottom>g.launchTop-3)throw new Error("Teaser overlaps launcher: "+JSON.stringify({width,g}));
            if(process.env.CLIENT_LAUNCHER_VISUAL_DIR) {
              const output=path.resolve(process.env.CLIENT_LAUNCHER_VISUAL_DIR);
              if(!output.startsWith(path.resolve(os.tmpdir())+path.sep))throw new Error("Visual output must be in temp");
              fs.mkdirSync(output,{recursive:true});
              const screenshot=await cdp.send("Page.captureScreenshot",{format:"png"});
              fs.writeFileSync(path.join(output,`launcher-${width}-${expanded?'expanded':'compact'}.png`),Buffer.from(screenshot.data,"base64"));
              if(width===900&&expanded){
                const clipped=await cdp.send("Page.captureScreenshot",{format:"png",clip:{
                  x:g.card.left-12,y:g.card.bottom-g.card.height-12,width:g.card.width+24,height:g.card.height+24,scale:1}});
                fs.writeFileSync(path.join(output,"launcher-card-preview.png"),Buffer.from(clipped.data,"base64"));
              }
            }
          }
        }
        await cdp.send("Emulation.setEmulatedMedia",{features:[{name:"prefers-reduced-motion",value:"reduce"}]});
        const reduced=await cdp.send("Runtime.evaluate",{expression:"window.__CLIENT_LAUNCHER_GEOMETRY__().transition",returnByValue:true});
        if(reduced.result.value!=="0s")throw new Error("Reduced-motion transition remains: "+reduced.result.value);
        if(process.env.CLIENT_LAUNCHER_VISUAL_DIR) {
          await cdp.send("Runtime.evaluate",{expression:"document.querySelector('[data-clinic-launcher]').click()"});
          await sleep(300);
          const screenshot=await cdp.send("Page.captureScreenshot",{format:"png"});
          fs.writeFileSync(path.join(path.resolve(process.env.CLIENT_LAUNCHER_VISUAL_DIR),"promotion-chat-preview.png"),Buffer.from(screenshot.data,"base64"));
        }
        console.log("CLIENT_LAUNCHER_EVIDENCE:"+JSON.stringify(result.value.result));return;
      }
      await sleep(100);
    }
    throw new Error("Page menu browser timeout");
  } finally {
    ws?.close();browser.kill("SIGTERM");
    await new Promise(resolve=>{browser.once("exit",resolve);setTimeout(resolve,3000);});server.close();
    if(!path.resolve(profile).startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(profile).startsWith("client-launcher-widget-"))throw new Error("Unsafe temp cleanup");
    fs.rmSync(profile,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
