/** Execute the real panel module with DOM/transport doubles; no browser/network. */
import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
const source = fs.readFileSync(new URL("../../static/widget-test-panel.js", import.meta.url), "utf8");
for (const id of ["demo", "nikadent"]) {
  const elements = new Map();
  function element(key) {
    if (!elements.has(key)) elements.set(key, {textContent:key === "test-questions" ? "[]" : "", value:"", dataset:{},
      listeners:{}, addEventListener(name, fn) {this.listeners[name] = fn;},
      appendChild() {}, querySelectorAll() {return [];}, querySelector(name) {return element(name);}});
    return elements.get(key);
  }
  const mounted = [], requests = [], navigation = [];
  const context = vm.createContext({URL, AbortController, setTimeout:()=>0, clearTimeout:()=>{},
    location:{href:`http://127.0.0.1:9001/static/widget-test.html?client=${id}`,host:"127.0.0.1:9001",assign:url=>navigation.push(url)},
    window:{addEventListener() {}}, document:{getElementById:element,createElement:element,body:element("body"),
      querySelector:element,querySelectorAll:()=>[]},
    fetch:async url=>{requests.push(url);return {ok:true,json:async()=>url==="/health/live"
      ? {ok:true,status:"live"} : {clientId:id,demoLauncher:id==="demo"}};},
  });
  const entry = new vm.SourceTextModule(source,{context});
  await entry.link(()=>new vm.SyntheticModule(["mountWidget"],function(){
    this.setExport("mountWidget",(_root,config)=>{mounted.push(config);return {resetSession(){}};});
  },{context}));
  await entry.evaluate();
  assert.equal(mounted.length,1);
  assert.equal(mounted[0].clientId,id);
  assert.ok(requests.includes(`/api/widget-config?client_id=${id}`));
  assert.equal(element("client-select").value,id);
  assert.ok(element("client-new-tab").href.endsWith(`client=${id}`));
  const other=id==="demo" ? "nikadent" : "demo";
  element("client-select").value=other;
  element("client-select").listeners.change();
  assert.ok(navigation[0].endsWith(`client=${other}`));
}
console.log("Panel config/switching: PASS");
