/** Execute the real panel module with DOM/transport doubles; no browser/network. */
import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
const source = fs.readFileSync(new URL("../../static/widget-test-panel.js", import.meta.url), "utf8");
for (const [id, page] of [["demo", "/"], ["nikadent", "/all-on-4"]]) {
  const elements = new Map();
  function element(key) {
    if (!elements.has(key)) elements.set(key, {textContent:key === "test-questions" ? "[]" : "", value:"", dataset:{},
      listeners:{}, addEventListener(name, fn) {this.listeners[name] = fn;},
      appendChild() {}, querySelectorAll() {return [];}, querySelector(name) {return element(name);}});
    return elements.get(key);
  }
  const mounted = [], requests = [], navigation = [];
  const context = vm.createContext({URL, AbortController, setTimeout:()=>0, clearTimeout:()=>{},
    location:{href:`http://127.0.0.1:9001/static/widget-test.html?client=${id}&page=${encodeURIComponent(page)}`,host:"127.0.0.1:9001",assign:url=>navigation.push(url)},
    window:{addEventListener() {}}, document:{getElementById:element,createElement:element,body:element("body"),
      querySelector:element,querySelectorAll:()=>[]},
    fetch:async url=>{requests.push(url);return {ok:true,json:async()=>url==="/health/live"
      ? {ok:true,status:"live"} : {clientId:id,demoLauncher:id==="demo",
        pageMenus:id==="nikadent" ? [{paths:["/all-on-4"]}] : null}};},
  });
  const entry = new vm.SourceTextModule(source,{context});
  await entry.link(()=>new vm.SyntheticModule(["mountWidget"],function(){
    this.setExport("mountWidget",(_root,config,options)=>{mounted.push({...config,options});return {resetSession(){}};});
  },{context}));
  await entry.evaluate();
  assert.equal(mounted.length,1);
  assert.equal(mounted[0].clientId,id);
  assert.ok(requests.includes(`/api/widget-config?client_id=${id}`));
  assert.equal(element("client-select").value,id);
  assert.equal(new URL(element("client-new-tab").href).searchParams.get("client"),id);
  assert.equal(mounted[0].options.pagePath,page);
  assert.equal(element("page-select").value,page);
  element("page-select").value="/";
  element("page-select").listeners.change();
  assert.equal(new URL(navigation.pop()).searchParams.get("page"),"/");
  const other=id==="demo" ? "nikadent" : "demo";
  element("client-select").value=other;
  element("client-select").listeners.change();
  assert.ok(navigation[0].endsWith(`client=${other}`));
}
console.log("Panel config/switching: PASS");
