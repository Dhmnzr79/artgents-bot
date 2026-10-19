import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto} from 'node:crypto';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const load=source=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const {createWidgetAnalytics}=await load(fs.readFileSync('static/widget/analytics.js','utf8'));
const requests=[];
globalThis.fetch=(url,options)=>{requests.push({url,options,body:JSON.parse(options.body)});return Promise.resolve({});};
let path='/clinic?phone=PRIVATE#secret';
const track=createWidgetAnalytics({apiBase:'https://bot.invalid/',clientId:'demo',readPath:()=>path,paths:['/','/clinic/']});
track('opened');track('opened');track('question');track('question');track('form');
const sid=crypto.randomUUID(),first=crypto.randomUUID(),second=crypto.randomUUID();
track('submit',{sid,request_id:first,name:'PRIVATE',phone:'PRIVATE'});
track('submit',{sid,request_id:first});track('submit',{sid,request_id:second});
assert.equal(requests.length,5);
assert.equal(new Set(requests.map(r=>r.body.view_id)).size,1);
assert(requests.every(r=>r.body.path==='/clinic'&&r.options.credentials==='omit'));
assert(!JSON.stringify(requests).includes('PRIVATE'));
path='/other';track('submit',{sid,request_id:crypto.randomUUID()});assert.equal(requests.at(-1).body.path,'/clinic');
const trackNew=createWidgetAnalytics({apiBase:'',clientId:'nikadent',readPath:()=>'/'});
trackNew('opened');assert.notEqual(requests.at(-1).body.view_id,requests[0].body.view_id);
const privatePath=createWidgetAnalytics({apiBase:'',clientId:'demo',readPath:()=>'/patient/PRIVATE/79991234567'});
privatePath('opened');assert.equal(requests.at(-1).body.path,'(other)');
assert(!JSON.stringify(requests).includes('79991234567'));
globalThis.fetch=()=>Promise.reject(Error('offline'));
trackNew('question');await new Promise(resolve=>setImmediate(resolve));
globalThis.fetch=()=>{throw Error('synchronous offline');};assert.doesNotThrow(()=>trackNew('form'));
assert.doesNotThrow(()=>createWidgetAnalytics({apiBase:'',clientId:'demo',readPath:()=>{throw Error();}})('opened'));

// Run the real booking handler with minimal DOM/network dependencies, no browser/provider.
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.isConnected=true;this.value='';}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  addEventListener(name,fn){this['on'+name]=fn;}
  setAttribute(){} setCustomValidity(value){this.validity=value;}
  closest(){return this.hiddenAncestor?{}:null;}
  querySelectorAll(selector){
    const all=this.children.flatMap(x=>x instanceof Element?[x,...x.querySelectorAll('*')]:[]);
    if(selector==='*')return all;
    if(selector==='input,select,textarea')return all.filter(x=>['input','select','textarea'].includes(x.tagName));
    const field=selector.match(/data-booking-field="(.*?)"/);
    return field?all.filter(x=>x.dataset.bookingField===field[1]):[];
  }
  reportValidity(){return this.querySelectorAll('input,select,textarea').every(x=>!x.validity);}
}
globalThis.document={createElement:tag=>new Element(tag),activeElement:null};
let source=fs.readFileSync('static/widget/booking_form.js','utf8')
  .replace("import { visitorIdForClient } from './api.js';","const visitorIdForClient=()=> 'offline-visitor';")
  .replace("import { createWidgetIcon } from './icons.js';","const createWidgetIcon=()=>document.createElement('svg');");
const {createBookingForm}=await load(source);
const events=[],leads=[];
globalThis.fetch=async(url,options)=>{
  if(url.includes('booking-form'))return {ok:true,json:async()=>({client_id:'demo',checkbox_text:'Согласие',definition_fingerprint:'f'.repeat(64)})};
  leads.push(JSON.parse(options.body));return {ok:true,json:async()=>({ok:true,status:'demo_stub',message:'Готово'})};
};
const mount=new Element('div');
const booking=createBookingForm({apiBase:'',clientId:'demo',getSid:()=>sid,getCatalog:async()=>({services:[]}),onEvent:(kind,ids)=>events.push({kind,ids})});
await booking.render(mount,{extended:true});assert.deepEqual(events.map(e=>e.kind),['form']);
let form=mount.children[0];
await form.onsubmit({preventDefault(){}});assert.equal(leads.length,0);assert.equal(events.length,1);
for(const [key,value] of [['name','PRIVATE NAME'],['phone','+79991234567']]){
  const input=form.querySelectorAll(`[data-booking-field="${key}"]`)[0];input.value=value;input.oninput();
}
const consent=form.querySelectorAll('[data-booking-field="consent"]')[0];consent.checked=true;consent.onchange();
await form.onsubmit({preventDefault(){}});
assert.equal(leads.length,1);assert.equal(events.filter(e=>e.kind==='submit').length,1);
assert.equal(events.find(e=>e.kind==='submit').ids.request_id,leads[0].request_id);
assert(!JSON.stringify(events).includes('PRIVATE NAME'));assert(!JSON.stringify(events).includes('79991234567'));
const throwing=createBookingForm({apiBase:'',clientId:'demo',getSid:()=>sid,getCatalog:async()=>({services:[]}),onEvent:()=>{throw Error('observer broken');}});
await throwing.render(new Element('div')); // observation exceptions cannot fail rendering
const hidden=new Element('div');hidden.hiddenAncestor=true;
const hiddenEvents=[];
const hiddenBooking=createBookingForm({apiBase:'',clientId:'demo',getSid:()=>sid,getCatalog:async()=>({services:[]}),onEvent:kind=>hiddenEvents.push(kind)});
await hiddenBooking.render(hidden);assert.equal(hiddenEvents.length,0);
hidden.hiddenAncestor=false;await hiddenBooking.render(hidden);assert.deepEqual(hiddenEvents,['form']);
console.log('Widget analytics and real booking handler: PASS');
