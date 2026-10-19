import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.listeners={};this.scrollTop=0;this.classList={toggle(){}};}
  append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
  prepend(n){n.parent=this;this.children.unshift(n);}
  replaceChildren(...nodes){this.children=[];this.append(...nodes);}
  set textContent(value){this.text=String(value);this.children=[];}
  get textContent(){return (this.text||'')+this.children.map(x=>x.textContent).join('');}
  addEventListener(type,fn){this.listeners[type]=fn;}
  setAttribute(name,value){this[name]=value;}
  closest(){return panel;}
  remove(){this.parent.children=this.parent.children.filter(x=>x!==this);}
  click(){this.listeners.click();}
}
const panel=new Element('section');
const load=source=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
globalThis.document={createElement:tag=>new Element(tag)};
let source=fs.readFileSync('static/widget/catalog.js','utf8')
 .replace("import { createWidgetIcon } from './icons.js';","const createWidgetIcon=()=>document.createElement('svg');")
 .replace("import { renderPriceBody } from './price_card.js';","const renderPriceBody=(root)=>root.append(document.createElement('article'));");
const {mountCatalog}=await load(source);
const service={service_id:'service',section_id:'section',name:'Консультация «ЛОР» <text>',subtitle:'Подробности',aliases:[],price_summary_text:'1000 ₽',offer_groups:[],
 price:{presentation:'detail',rows:[{offer_id:'offer',service_name:'Консультация'}]},details:{offer:{parts:[]}}};
const fixture={client_id:'demo_medical',catalog_version:'v',show_sections:true,sections:[{section_id:'section',title:'ЛОР',subtitle:'Описание'}],services:[service]};
const calls=[];globalThis.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>fixture};};
const root=new Element('div'),asked=[],applied=[];
const catalog=mountCatalog(root,{apiBase:'',clientId:'demo_medical',onAsk:name=>asked.push(name),onApply:(selection,mount)=>applied.push({selection,mount})});
const walk=n=>[n,...n.children.flatMap(walk)];
const find=(text)=>{const result=walk(root).find(n=>n.tagName==='button'&&n.textContent===text);assert(result,'missing '+text);return result;};
await catalog.load();find('ЛОРОписание').click();find(service.name+'1000 ₽Подробности').click();
panel.scrollTop=146;const nodes=[...root.children];
find('Задать вопрос об услуге').click();assert.deepEqual(asked,[service.name]);
assert.deepEqual(root.children,nodes);assert.equal(panel.scrollTop,146);
await catalog.load();assert.deepEqual(root.children,nodes);assert.equal(calls.length,1);
find('Оставить заявку').click();assert.equal(applied.length,1);
assert.deepEqual(applied[0].selection,{service_id:'service',offer_id:'offer',catalog_version:'v'});
assert(!walk(root).some(n=>n.textContent==='Задать вопрос об услуге'));
assert(!walk(root).some(n=>n.textContent==='Оставить заявку'));
assert.equal(calls.length,1); // No ask/lead/model request on contextual navigation.

// Execute the actual composer callback and existing tab switch in their UI scope.
const widget=fs.readFileSync('static/widget/widget.js','utf8');
const callback=widget.slice(widget.indexOf("  let preparedCatalogQuestion='';"),widget.indexOf('  const catalog=mountCatalog'));
const switcher=widget.slice(widget.indexOf("  let activeTab='assistant';"),widget.indexOf('  for(const [index,button]of [...root.querySelectorAll'));
const buttons=['assistant','catalog','booking'].map(name=>({dataset:{clinicTab:name},setAttribute(){}}));
const feed={scrollTop:12},catalogPanel={scrollTop:246},bookingPanel={scrollTop:0},input={value:'',style:{},focus(){this.focused=true;},setSelectionRange(a,b){this.selection=[a,b];}};
const ctx={root:{querySelectorAll:()=>buttons},feed,catalogPanel,bookingPanel,input,composerForm:{},bookingRoot:{},catalog,booking:{render(){throw Error('unexpected form');}},
 autoResizeTextarea:()=>{},syncSendState:()=>{},};
vm.createContext(ctx);vm.runInContext(callback+switcher+';this.openQuestion=openCatalogQuestion;this.go=switchTab;',ctx);
ctx.go('catalog');catalogPanel.scrollTop=246;ctx.openQuestion(service.name);
assert.equal(input.value,`По услуге «${service.name}»: `);assert(input.focused);assert.equal(input.selection[0],input.value.length);
ctx.go('catalog');assert.equal(catalogPanel.scrollTop,246);assert.deepEqual(root.children,nodes.filter(n=>n.className!=='clinic-catalog__apply'&&n.className!=='clinic-catalog__ask'));
ctx.openQuestion('Другая услуга');assert.equal(input.value,'По услуге «Другая услуга»: ');
input.value+='Сколько длится?';const draft=input.value;ctx.go('catalog');ctx.openQuestion('Третья услуга');assert.equal(input.value,draft);
input.value='Мой несохранённый вопрос';ctx.openQuestion('Услуга');assert.equal(input.value,'Мой несохранённый вопрос');
input.value='';ctx.openQuestion('Новая услуга');assert.equal(input.value,'По услуге «Новая услуга»: ');
assert.equal(calls.length,1);
console.log('Catalog → composer, draft, scroll, form link hiding: PASS');
