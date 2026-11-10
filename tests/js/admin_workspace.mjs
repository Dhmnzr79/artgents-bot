// Offline DOM harness: actual dashboard functions, no browser/provider/network.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.attrs={};this.hidden=false;this.value='';this.scrollTop=0;this.scrollHeight=0;this.classList={add(){},remove(){}};}
  set textContent(v){this.text=String(v??'');this.children=[];}
  get textContent(){return (this.text||'')+this.children.map(x=>x.textContent).join('');}
  append(...xs){this.children.push(...xs);}
  appendChild(x){this.children.push(x);return x;}
  prepend(x){this.children.unshift(x);}
  replaceChildren(...xs){this.text='';this.children=xs;}
  setAttribute(k,v){this.attrs[k]=v;}
  removeAttribute(k){delete this.attrs[k];}
  addEventListener(){} focus(){} scrollIntoView(){} querySelector(){return null;}
}
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),createTextNode:t=>{const n=new Element('#text');n.textContent=t;return n;},createDocumentFragment:()=>new Element('fragment'),querySelectorAll:()=>[]};
const context=vm.createContext({document,Node:Element,AbortController,DOMException,URLSearchParams,window:{addEventListener(){}},setTimeout,clearTimeout,fetch:async()=>{throw Error('unexpected fetch');}});
const source=fs.readFileSync(new URL('../../admin_dashboard/static/dashboard.js',import.meta.url),'utf8').replace(/void init\(\);\s*$/,'');
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);
run("state.client='demo';state.controller=new AbortController();");
// A stale tenant response must not render even if transport ignores abort.
let resolve;
context.fetch=()=>new Promise(r=>resolve=r);
const pending=run("get('/api/dialogs')");
run("state.client='nikadent';state.generation++;");
resolve({ok:true,json:async()=>({items:[]})});
await assert.rejects(pending,{name:'AbortError'});
// Search responses arriving out of order must not replace a newer list.
const responses=[];
context.fetch=()=>new Promise(r=>responses.push(r));
const old=run('loadDialogs()');const recent=run('loadDialogs()');
responses[1]({ok:true,json:async()=>({items:[{session_id:'b'.repeat(64),preview:'new',questions:1,actions:0}],next_cursor:null})});await recent;
responses[0]({ok:true,json:async()=>({items:[{session_id:'a'.repeat(64),preview:'old'}],next_cursor:null})});await old;
assert.equal(run('state.dialogs[0].preview'),'new');
// Foreign thread response cannot reappear after clinic switch / clear.
context.fetch=()=>new Promise(r=>resolve=r);
const thread=run("showThread('b'.repeat(64))");
run("clearThread();state.client='demo';state.generation++;");
resolve({ok:true,json:async()=>({items:[{answer:'FOREIGN',request_key:'r',revision:1}],next_cursor:null})});await thread;
assert.equal(document.getElementById('dialogThreadBody').textContent,'');
// Formatting never creates HTML or executable links from model output.
const safe=run("formatted('<img src=x onerror=alert(1)> **bold** [link](javascript:alert(1))')");
assert.equal(safe.children.filter(x=>x.tagName==='strong').length,1);
assert.ok(safe.children.every(x=>['#text','strong'].includes(x.tagName)));
assert.ok(safe.textContent.includes('<img'));
console.log('PASS: stale tenant/thread/search rejection and safe answer formatting');
// Refresh must not steal navigation after slow background requests finish.
run("state.session='b'.repeat(64);state.page='statistics';state.controller=new AbortController();");
const queue=[];
context.fetch=(url)=>new Promise(r=>queue.push({url,resolve:r}));
run('state.cursors.turns=42');
const refreshing=run('refresh()');
assert.equal(run('state.cursors.turns'),42);
run("setPage('applications')");
for(const item of queue){const payload=item.url.startsWith('/api/overview')?{sessions:0,saved_turns:0,forms:0,metrics_available:false}:{available:false,items:[],next_cursor:null};item.resolve({ok:true,json:async()=>payload});}
await refreshing;
assert.equal(run('state.page'),'applications');
console.log('PASS: refresh preserves newer navigation');
