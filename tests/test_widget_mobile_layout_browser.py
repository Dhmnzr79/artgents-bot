"""Embedded presentation: real Shadow bootstrap, bundled Inter and reference tokens."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.d2_ci_http import http_env
from tests.test_widget_catalog import admit_medical


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Chrome offline presentation proof')
@pytest.mark.parametrize('tenant', ['demo', 'demo_medical', 'nikadent'])
def test_embedded_fonts_reference_and_mobile_layout(http_env, monkeypatch, tmp_path, tenant):
    if tenant == 'demo_medical':
        admit_medical(http_env, monkeypatch)
    client = http_env[0]
    fixtures = {key: client.get(endpoint, query_string={'client_id': tenant}).get_json()
                for key, endpoint in [('config', '/api/widget-config'),
                                      ('catalog', '/api/widget-catalog'),
                                      ('definition', '/api/booking-form')]}
    # Capture real application CORS decisions. The Node fixture maps the allowed
    # loopback origin to its dynamically allocated host port, never inventing font permission.
    probe_origin = 'http://127.0.0.1:54321'
    fixtures['cors'] = {
        asset: client.get(asset, base_url=f'https://{tenant}.bot.artgents.ru',
                          headers={'Origin': probe_origin}).headers.get('Access-Control-Allow-Origin')
        for asset in ['/static/widget/embed.js',
                      '/static/fonts/inter-cyrillic-wght-normal.woff2',
                      '/static/fonts/inter-latin-wght-normal.woff2']}
    fixture_path = tmp_path / 'presentation.json'
    fixture_path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(['node', '--input-type=module', '-'], input=RUNNER,
                            cwd=Path(__file__).resolve().parents[1], text=True,
                            encoding='utf-8', capture_output=True, timeout=90,
                            env={**os.environ, 'LAYOUT_FIXTURES': str(fixture_path)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout


RUNNER = r'''
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/denis/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=process.cwd(),fixtures=JSON.parse(fs.readFileSync(process.env.LAYOUT_FIXTURES,'utf8'));
const tenant=fixtures.config.clientId, forbidden=[];
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://local');
  const policy=url.pathname.startsWith('/static/fonts/')?fixtures.cors[url.pathname]:fixtures.cors['/static/widget/embed.js'];
  if(req.headers.origin&&policy==='http://127.0.0.1:54321'){
    res.setHeader('Access-Control-Allow-Origin',req.headers.origin);
    res.setHeader('Access-Control-Allow-Methods','GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers','Content-Type');
  }
  if(req.method==='OPTIONS'){res.writeHead(204);return res.end();}
  const json=value=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(value));};
  if(url.pathname==='/'){
    res.setHeader('Content-Type','text/html; charset=utf-8');
    return res.end('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><body style="margin:0;min-height:2000px"><p>Host page</p></body>');
  }
  if(url.pathname==='/reference'){
    res.setHeader('Content-Type','text/html; charset=utf-8');
    return res.end(fs.readFileSync('docs/artifacts/artgents-mobile-widget.html'));
  }
  if(url.pathname==='/api/widget-config')return json(fixtures.config);
  if(url.pathname==='/api/widget-catalog')return json(fixtures.catalog);
  if(url.pathname==='/api/booking-form')return json(fixtures.definition);
  if(url.pathname==='/api/video-catalog')return json({videos:{}});
  if(url.pathname==='/api/widget-session')return json({client_id:tenant,entries:[]});
  if(req.method!=='GET'){forbidden.push(req.url);res.writeHead(400);return res.end();}
  const file=path.resolve(root,'.'+url.pathname);
  if(!file.startsWith(path.join(root,'static')+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.woff2')?'font/woff2':'application/octet-stream');
  res.end(fs.readFileSync(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
const hostServer=http.createServer((req,res)=>{
  res.setHeader('Content-Type','text/html; charset=utf-8');
  res.end('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><body style="margin:0;min-height:2000px"><p>Host page on another origin</p></body>');
});
await new Promise(resolve=>hostServer.listen(0,'127.0.0.1',resolve));
const hostOrigin=`http://127.0.0.1:${hostServer.address().port}`;
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe',args:[`--explicitly-allowed-ports=${server.address().port},${hostServer.address().port}`]});
try{
  const page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(hostOrigin);
  await page.evaluate(({tenant,origin})=>{const script=document.createElement('script');script.src=origin+'/static/widget/embed.js';script.dataset.clientId=tenant;document.body.append(script);},{tenant,origin});
  await page.locator('[data-clinic-launcher-open],[data-clinic-launcher]').first().waitFor();
  await page.evaluate(()=>scrollTo(0,240));
  await page.locator('[data-clinic-launcher-open],[data-clinic-launcher]').first().click();
  await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
  const catalog=page.locator('[data-clinic-catalog-panel]');await catalog.locator('.clinic-catalog__row').first().waitFor();
  await page.evaluate(()=>document.fonts.ready);
  const cdp=await page.context().newCDPSession(page);await cdp.send('DOM.enable');await cdp.send('CSS.enable');
  const {nodes}=await cdp.send('DOM.getFlattenedDocument',{depth:-1,pierce:true});
  const titleNode=nodes.find(node=>node.attributes?.includes('data-clinic-header-name'));
  const {fonts}=await cdp.send('CSS.getPlatformFontsForNode',{nodeId:titleNode.nodeId});
  if(!fonts.length||fonts.some(font=>!font.isCustomFont||!font.familyName.startsWith('Inter')))throw new Error('Bundled Inter not rendered: '+JSON.stringify(fonts));
  const reference=await browser.newPage({viewport:{width:390,height:900}});await reference.goto(origin+'/reference');
  // The owner explicitly requested Inter instead of the reference's Arial.
  await reference.addStyleTag({content:'@import url("/static/widget/fonts.css"); :root{font-family:Inter,sans-serif}'});
  await reference.evaluate(()=>document.fonts.ready);
  const tokens=async(p,selectors)=>p.evaluate(selectors=>selectors.map(selector=>{
    const root=document.querySelector('#clinic-widget-root')?.shadowRoot||document;
    const style=getComputedStyle(root.querySelector(selector));
    return [style.fontSize,style.lineHeight,style.backgroundColor,style.paddingTop,style.paddingRight,style.borderRadius];
  }),selectors);
  const actual=await tokens(page,['.clinic-catalog__row','.clinic-catalog__row strong','.clinic-catalog__row small','.clinic-catalog__search','.clinic-shell__tabs button']);
  const expected=await tokens(reference,['.direction-row','.direction-row strong','.direction-row small','.search','.tabs button']);
  if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error('Reference token mismatch '+JSON.stringify({actual,expected}));
  if(process.env.THREE_TABS_SCREENSHOT_DIR){
    fs.mkdirSync(process.env.THREE_TABS_SCREENSHOT_DIR,{recursive:true});
    await page.locator('[data-clinic-panel]').screenshot({path:path.join(process.env.THREE_TABS_SCREENSHOT_DIR,tenant+'-embedded-reference-width390.png')});
    await reference.locator('.widget').screenshot({path:path.join(process.env.THREE_TABS_SCREENSHOT_DIR,tenant+'-reference-inter-width390.png')});
  }
  for(const size of ['100%','200%'])for(const width of [320,360,390,430,1280]){
    await page.evaluate(size=>document.documentElement.style.fontSize=size,size);
    await page.setViewportSize({width,height:900});
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    for(const tab of ['Услуги и цены','Запись','Помощник']){
      await page.getByRole('tab',{name:tab,exact:true}).click();
      const bad=await page.locator('[data-clinic-panel]').evaluate(panel=>{
        const bounds=panel.getBoundingClientRect();
        return [...panel.querySelectorAll('button,input,textarea,.clinic-catalog__row,.clinic-booking')].filter(el=>{
          const rect=el.getBoundingClientRect();return rect.width&&rect.height&&(rect.left<bounds.left-1||rect.right>bounds.right+1);
        }).map(el=>el.className);
      });
      if(bad.length)throw new Error(JSON.stringify({size,width,tab,bad}));
    }
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='100%');
  await page.setViewportSize({width:390,height:560});
  await page.getByRole('tab',{name:'Запись',exact:true}).click();
  const phone=page.locator('[data-clinic-booking-panel]').getByLabel('Телефон',{exact:true});
  await phone.fill('+79991234567');await phone.scrollIntoViewIfNeeded();
  const visible=await phone.evaluate(el=>{const a=el.getBoundingClientRect(),b=el.closest('[role=tabpanel]').getBoundingClientRect();return a.top>=b.top&&a.bottom<=b.bottom;});
  if(!visible)throw new Error('Active field inaccessible in shorter viewport');
  await page.locator('[data-clinic-close]').click();
  if(await page.evaluate(()=>window.scrollY)!==240)throw new Error('Host scroll was not restored');
  if(errors.length||forbidden.length)throw new Error(JSON.stringify({errors,forbidden}));
  console.log(JSON.stringify({passed:true,fonts,provider:0}));
}finally{await browser.close();await Promise.all([new Promise(resolve=>server.close(resolve)),new Promise(resolve=>hostServer.close(resolve))]);}
'''
