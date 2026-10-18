"""Real widget: catalog navigation, shared private form, remount and exact chat card."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
from uuid import uuid4
import pytest

from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,click
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_d2_price_cards_browser import RUNNER
from tests.test_widget_catalog import admit_medical
from tests.test_widget_booking_form import form_payload


@pytest.mark.skipif(sys.platform!='win32',reason='Windows Chrome/Playwright offline widget proof')
@pytest.mark.parametrize('tenant,service,chosen',[
    ('demo','classic','classic.one_tooth.nobel'),
    ('nikadent','removable_dentures','removable_dentures.jaw.nylon'),
    ('demo_medical','ent_consultation','ent_consultation.repeat')])
def test_three_tabs_private_shared_form_and_page_remount(http_env,monkeypatch,tmp_path,tenant,service,chosen):
    if tenant=='demo_medical':admit_medical(http_env,monkeypatch)
    client,_,use,_=http_env;sid=uuid4().hex
    wire=Transport(message(None,price(service)),message('<NO_TEXT>'));use(D2HttpProvider(transport=wire))
    first=send(client,client_id=tenant,sid=sid,q='Стоимость?')
    catalog=client.get('/api/widget-catalog',query_string={'client_id':tenant}).get_json()
    selection=dict(service_id=service,offer_id=chosen,catalog_version=catalog['catalog_version'])
    sender=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    submitted=client.post('/lead',json=form_payload(client,tenant=tenant,sid=sid,selection=selection)).get_json()
    assert submitted['ok']
    history=client.post('/api/widget-session',json={'client_id':tenant,'sid':sid}).get_json()
    selected=click(client,first,'price_select:'+chosen,request_id='choose',client_id=tenant,sid=sid)
    assert len(wire.calls)==2
    data=dict(config=client.get('/api/widget-config',query_string={'client_id':tenant}).get_json(),
        catalog=catalog,definition=client.get('/api/booking-form',query_string={'client_id':tenant}).get_json(),
        first=first,selected=selected,history=history,submitted=submitted,service=next(s for s in catalog['services'] if s['service_id']==service),chosen=chosen)
    payloads=tmp_path/'tabs.json';payloads.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    prefix=RUNNER.split('  await page.evaluate(async fixtures => {',1)[0]
    runner=prefix+r'''
  const setup=async()=>await page.evaluate(async fixtures=>{
    const {mountWidget}=await import('/static/widget/widget.js');window.calls=[];window.formRequests=[];window.askRequests=[];
    window.fetch=async(url,options={})=>{
      const address=String(url),body=options.body?JSON.parse(options.body):null;window.calls.push({url:address,body});
      const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
      if(address.includes('video-catalog'))return json({videos:{}});
      if(address.includes('widget-catalog'))return json(fixtures.catalog);
      if(address.includes('booking-form'))return json(fixtures.definition);
      if(address.endsWith('/api/widget-session'))return json(fixtures.history);
      if(address.endsWith('/lead')){window.formRequests.push(body);if(window.failNextLead){window.failNextLead=false;throw new Error('offline response lost');}return json({...fixtures.submitted,request_id:body.request_id});}
      if(!address.endsWith('/ask/stream'))throw new Error('Unexpected fetch '+address);
      window.askRequests.push(body);const value=body.ref?fixtures.selected:fixtures.first;
      return new Response('event: ui\ndata: '+JSON.stringify({...value,request_id:body.request_id,sid:body.sid||value.sid})+'\n\nevent: done\ndata: {}\n\n',
        {headers:{'Content-Type':'text/event-stream'}});
    };
    mountWidget(document.querySelector('#root'),{...fixtures.config,apiBase:location.origin});
    document.querySelector('[data-clinic-dev-reset]')?.remove(); // Same as the real test panel: no overlapping debug control.
    document.querySelector('[data-clinic-launcher-open],[data-clinic-launcher]').click();
  },fixtures);
  await setup();
  const auditLayout=async state=>{
    await page.evaluate(()=>document.fonts.ready);
    for(const textSize of ['100%','200%']){
      await page.evaluate(size=>document.documentElement.style.fontSize=size,textSize);
      for(const width of [320,360,390,412,440,1280]){
        await page.setViewportSize({width,height:900});
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        const problems=await page.locator('[data-clinic-panel]').evaluate(panel=>{
          const bounds=panel.getBoundingClientRect(),bad=[];
          for(const el of panel.querySelectorAll('*')){
            const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
            if(!rect.width||!rect.height||style.display==='inline'||el instanceof SVGElement)continue;
            if(rect.left<bounds.left-1||rect.right>bounds.right+1)bad.push(el.className+': bounds');
            if(!el.matches('input,textarea,select')&&el.scrollWidth>el.clientWidth+2)bad.push(el.tagName+'.'+el.className+': content '+el.clientWidth+'/'+el.scrollWidth+' '+el.textContent.slice(0,80));
          }
          if(bounds.top<0||bounds.bottom>innerHeight+1)bad.push('viewport height');
          return bad;
        });
        if(problems.length)throw new Error(JSON.stringify({state,width,textSize,problems}));
      }
    }
    await page.evaluate(()=>document.documentElement.style.fontSize='100%');
    await page.setViewportSize({width:390,height:900});
  };
  await auditLayout('assistant welcome');
  await page.locator('[data-clinic-input]').fill('Стоимость?');await page.locator('[data-clinic-send]').click();
  await page.locator('[data-clinic-feed] .clinic-price-card').waitFor();
  const chatBefore=await page.locator('[data-clinic-feed]').textContent();
  const userCount=await page.locator('.clinic-msg--user').count();
  await auditLayout('chat price options and composer');
  await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
  const catalogPanel=page.locator('[data-clinic-catalog-panel]');
  await catalogPanel.locator('.clinic-catalog__row').first().waitFor();
  await auditLayout('directions');
  if((await catalogPanel.innerText()).includes('Услуг:')||(await catalogPanel.innerText()).includes('Демо-клиника'))throw new Error('Prototype presentation replaced by count/disclaimer');
  if(process.env.THREE_TABS_SCREENSHOT_DIR){fs.mkdirSync(process.env.THREE_TABS_SCREENSHOT_DIR,{recursive:true});
    for(const width of [390,1280]){await page.setViewportSize({width,height:900});await page.locator('[data-clinic-panel]').screenshot({path:path.join(process.env.THREE_TABS_SCREENSHOT_DIR,`${fixtures.config.clientId}-${width}-directions.png`)});}
    await page.setViewportSize({width:390,height:900});}
  await catalogPanel.locator('.clinic-catalog__row').first().click();
  for(const row of await catalogPanel.locator('.clinic-catalog__service').all()){
    const name=await row.locator('strong').innerText();
    const service=fixtures.catalog.services.find(service=>service.name===name);
    if(!service||await row.locator('small').innerText()!==service.subtitle)throw new Error('Authored service subtitle missing');
  }
  await auditLayout('service list');
  // Search still covers the full clinic after choosing a section.
  await catalogPanel.getByRole('searchbox').fill(fixtures.service.name);
  const result=catalogPanel.locator('.clinic-catalog__row').filter({hasText:fixtures.service.name});
  if(await result.count()!==1)throw new Error('Global search missed exact service');
  if(await result.locator('small').innerText()!==fixtures.service.subtitle)throw new Error('Search replaced authored subtitle');
  await result.click();
  const options=catalogPanel.locator('.clinic-price-card__overview-row');
  if(await options.count()!==fixtures.service.price.rows.length)throw new Error('Missing service options');
  await auditLayout('catalog price options');
  const index=fixtures.service.price.rows.findIndex(row=>row.offer_id===fixtures.chosen);
  await catalogPanel.locator(`[data-price-offer-id="${fixtures.chosen}"]`).click();
  if(await catalogPanel.locator('.clinic-price-card__overview-row').count())throw new Error('Detail did not open');
  await catalogPanel.locator('details').evaluateAll(items=>items.forEach(item=>item.open=true));
  await auditLayout('detail, variants, expanded conditions and description');
  if(process.env.THREE_TABS_SCREENSHOT_DIR)await page.locator('[data-clinic-panel]').screenshot({path:path.join(process.env.THREE_TABS_SCREENSHOT_DIR,`${fixtures.config.clientId}-390-detail.png`)});
  await catalogPanel.getByRole('button',{name:'Оставить заявку',exact:true}).click();
  await catalogPanel.getByLabel('Как к вам обращаться').fill('Анна Проверка');
  if(await catalogPanel.locator('.clinic-catalog__apply').count())throw new Error('Catalog CTA remains above open form');
  await catalogPanel.getByLabel('Телефон',{exact:true}).fill('+79991234567');
  await catalogPanel.getByRole('button',{name:'Отправить заявку',exact:true}).click();
  if(await page.evaluate(()=>window.formRequests.length)!==0)throw new Error('Unchecked form submitted');
  await auditLayout('inline form and validation error');
  await page.getByRole('tab',{name:'Запись',exact:true}).click();
  const booking=page.locator('[data-clinic-booking-panel]');
  await booking.getByLabel('Как к вам обращаться').waitFor();
  if(await booking.getByLabel('Как к вам обращаться').inputValue()!=='Анна Проверка')throw new Error('Name draft lost');
  if(await booking.getByLabel('Телефон',{exact:true}).inputValue()!=='+79991234567')throw new Error('Phone draft lost');
  if(!(await booking.locator('.clinic-booking__subject').innerText()).includes(fixtures.service.name))throw new Error('Exact service lost');
  if(await booking.locator('select').count())throw new Error('Removed service selector remains');
  const chosenLabel=fixtures.service.price.rows[index].variant_label;
  if(chosenLabel&&!(await booking.locator('.clinic-booking__subject').innerText()).includes(chosenLabel))throw new Error('Exact offer label lost');
  await booking.getByLabel('Пожелания (необязательно)').fill('Позвонить после 18:00');
  await auditLayout('extended booking form');
  await booking.getByRole('checkbox').check();
  if(await page.evaluate(()=>window.formRequests.length)!==0)throw new Error('Checkbox submitted');
  await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
  if(!await catalogPanel.getByRole('checkbox').isChecked())throw new Error('Shared consent lost');
  if(await catalogPanel.getByLabel('Как к вам обращаться').inputValue()!=='Анна Проверка')throw new Error('Inline name lost');
  await page.getByRole('tab',{name:'Запись',exact:true}).click();
  await page.evaluate(()=>{window.failNextLead=true;});
  await booking.getByRole('button',{name:'Отправить заявку',exact:true}).click();
  await booking.getByRole('button',{name:'Проверить отправку',exact:true}).waitFor();
  await auditLayout('uncertain submission and retry');
  if(!await booking.getByRole('button',{name:'Убрать',exact:true}).isDisabled())throw new Error('Uncertain request selection is mutable');
  await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
  // Open a different offer while delivery is uncertain; its CTA must not replace the frozen request.
  await catalogPanel.getByRole('button',{name:fixtures.service.name,exact:true}).click();
  await catalogPanel.locator('.clinic-price-card__overview-row').nth((index+1)%fixtures.service.price.rows.length).click();
  await catalogPanel.getByRole('button',{name:'Оставить заявку',exact:true}).click();
  if(!await catalogPanel.getByLabel('Телефон',{exact:true}).isDisabled())throw new Error('Opening another form discarded uncertain request');
  await page.getByRole('tab',{name:'Запись',exact:true}).click();
  await booking.getByRole('button',{name:'Проверить отправку',exact:true}).click();
  await booking.locator('.clinic-booking__success').waitFor();
  await auditLayout('confirmed submission');
  const formRequests=await page.evaluate(()=>window.formRequests);
  if(formRequests.length!==2||JSON.stringify(formRequests[0])!==JSON.stringify(formRequests[1])||formRequests[0].selection.offer_id!==fixtures.chosen||formRequests[0].selection.service_id!==fixtures.service.service_id)
    throw new Error('Exact selection or immutable retry lost');
  if(formRequests[0].wish!=='Позвонить после 18:00'||!formRequests[0].consent.accepted)throw new Error('Private fields lost');
  if(await booking.locator('input').count()||await booking.getByRole('button',{name:'Новая заявка'}).count())throw new Error('Success restarts form');
  await page.getByRole('tab',{name:'Помощник',exact:true}).click();
  if(await page.locator('[data-clinic-feed]').textContent()!==chatBefore||await page.locator('.clinic-msg--user').count()!==userCount)
    throw new Error('Tabs/form changed dialogue');
  if(await page.evaluate(()=>window.askRequests.length)!==1)throw new Error('Browse/form called model');
  const storage=await page.evaluate(()=>JSON.stringify({...localStorage}));
  if(storage.includes('Анна Проверка')||storage.includes('79991234567'))throw new Error('Private draft persisted in browser');
  // Full page navigation restores existing receipts rather than a second history copy.
  await page.reload();await setup();
  await page.locator('[data-clinic-feed] .clinic-price-card').waitFor();
  if(await page.locator('[data-clinic-feed]').textContent()!==chatBefore)throw new Error('Remount lost conversation');
  if(await page.evaluate(()=>window.askRequests.length)!==0)throw new Error('Restore called model');
  const chatRows=page.locator('[data-clinic-feed] .clinic-price-card__overview-row');await chatRows.nth(index).click();
  await page.waitForFunction(()=>!document.querySelector('[data-clinic-feed] .clinic-price-card__overview-row'));
  if(await page.locator('[data-clinic-feed] .clinic-price-card').count()!==1)throw new Error('Restored card choice appended card');
  if(await page.locator('.clinic-msg--user').count()!==userCount)throw new Error('Price choice appended user echo');
  await page.locator('[data-clinic-feed] .clinic-turn__btn--cta-primary').last().click();
  const inline=page.locator('[data-clinic-feed] .clinic-booking');await inline.waitFor();
  if(await page.locator('[data-clinic-feed] .clinic-turn__btn--cta-primary').count())throw new Error('Chat CTA remains above open form');
  if(!(await inline.locator('.clinic-booking__subject').innerText()).includes(chosenLabel))throw new Error('Chat CTA lost exact offer');
  await inline.getByLabel('Как к вам обращаться').fill('Мария');
  await page.getByRole('tab',{name:'Запись',exact:true}).click();
  if(await booking.getByLabel('Как к вам обращаться').inputValue()!=='Мария')throw new Error('Chat draft not shared');
  if(!(await booking.locator('.clinic-booking__subject').innerText()).includes(fixtures.service.name))throw new Error('Chat service not shared');
  if(await page.evaluate(()=>window.askRequests.length)!==1)throw new Error('Chat CTA called model');
  for(const width of [320,390,1280]){
    await page.setViewportSize({width,height:900});
    for(const tab of ['Помощник','Услуги и цены','Запись']){
      await page.getByRole('tab',{name:tab,exact:true}).click();await page.waitForTimeout(150);
      if(await page.locator('[data-clinic-panel]').evaluate(panel=>panel.scrollWidth>panel.clientWidth+1))throw new Error('Panel overflow '+tab+width);
      if(process.env.THREE_TABS_SCREENSHOT_DIR){fs.mkdirSync(process.env.THREE_TABS_SCREENSHOT_DIR,{recursive:true});
        await page.locator('[data-clinic-panel]').screenshot({path:path.join(process.env.THREE_TABS_SCREENSHOT_DIR,`${fixtures.config.clientId}-${width}-${['Помощник','Услуги и цены','Запись'].indexOf(tab)}.png`)});}
    }
  }
  if(failures.length)throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,provider:0}));
}finally{await browser.close();await new Promise(r=>server.close(r));}
'''
    result=subprocess.run(['node','--input-type=module','-'],input=runner,cwd=Path(__file__).resolve().parents[1],
        env={**os.environ,'CARDS_PAYLOADS':str(payloads)},text=True,encoding='utf-8',capture_output=True,timeout=180,check=False)
    assert result.returncode==0,result.stdout+result.stderr
    assert '"passed":true' in result.stdout
