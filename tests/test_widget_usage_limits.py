"""Execute actual widget API: stable tenant visitor bucket and both transports."""
from pathlib import Path
import subprocess


def test_api_identity_survives_module_reload_page_and_new_sid():
    script = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const storage=new Map();
globalThis.localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)};
const source=fs.readFileSync('static/widget/api.js','utf8');
const url='data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const first=await import(url+'#page1');
const id=first.visitorIdForClient('nikadent');
assert.equal(first.visitorIdForClient('nikadent'),id);
const second=await import(url+'#page2');
assert.equal(second.visitorIdForClient('nikadent'),id);
assert.notEqual(second.visitorIdForClient('demo'),id);
const sent=[];
globalThis.fetch=async(_url,options)=>{
 sent.push(JSON.parse(options.body));
 return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({
  answer:'Ответ',ui:{},revision:1,request_id:sent.at(-1).request_id,
  client_id:'nikadent',sid:sent.at(-1).sid})};
};
await first.postAsk('',{client_id:'nikadent',sid:'old',request_id:'r1',q:'Вопрос'});
await second.streamAsk('',{client_id:'nikadent',sid:'new',request_id:'r2',q:'Вопрос'});
assert.deepEqual(sent.map(b=>b.visitor_id),[id,id]);
assert.equal(second.friendlyErrorMessage('visitor_rate_limit').includes('минуту'),true);
Object.defineProperty(globalThis,'localStorage',{get(){throw Error('denied')},configurable:true});
assert.equal(second.visitorIdForClient('nikadent'),id);
console.log('PASS');
'''
    result=subprocess.run(["node","--input-type=module","-"],input=script,text=True,
        encoding="utf-8",capture_output=True,cwd=Path(__file__).resolve().parents[1],timeout=20)
    assert result.returncode == 0,result.stdout+result.stderr
