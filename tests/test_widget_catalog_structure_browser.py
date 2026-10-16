"""Catalog structure with canonical grouped offers, flat navigation and long price search."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.d2_ci_http import http_env
from tests.test_widget_catalog import admit_medical
from tests.test_d2_price_cards_browser import RUNNER


@pytest.mark.skipif(sys.platform!='win32',reason='Windows Chrome offline catalog proof')
@pytest.mark.parametrize('tenant,service_id',[('demo','classic'),('demo_medical','laser_hair_removal'),('nikadent','removable_dentures')])
def test_catalog_flat_grouped_search_back_and_exact_form(http_env,monkeypatch,tmp_path,tenant,service_id):
    if tenant=='demo_medical':admit_medical(http_env,monkeypatch)
    client,_,_,root=http_env
    nav_path=root/'clients'/tenant/'target_response/widget_catalog.json'
    nav=json.loads(nav_path.read_text(encoding='utf-8'));nav['show_sections']=False
    if tenant=='demo_medical':
        # A longer, still server-validated pack exercises search without a second UI data model.
        catalog_path=root/'clients'/tenant/'target_response/service_catalog.json'
        catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
        offers=root/'clients'/tenant/'target_response/pricebook/services'
        base=json.loads((offers/'laser_hair_removal.underarms.json').read_text(encoding='utf-8'))
        extra=[]
        for i in range(6):
            option_id=f'catalog_test_{i}'
            catalog[service_id]['options'].append(dict(option_id=option_id,name=f'Тестовая зона {i+1}'))
            offer=json.loads(json.dumps(base));offer['offer_id']=service_id+'.'+option_id;offer['option_id']=option_id;offer['price']['amount']=2100+i*100
            (offers/(offer['offer_id']+'.json')).write_text(json.dumps(offer),encoding='utf-8');extra.append(offer['offer_id'])
        catalog_path.write_text(json.dumps(catalog),encoding='utf-8')
        nav['offer_groups'][service_id].append(dict(title='Дополнительные зоны',offer_ids=extra))
    nav_path.write_text(json.dumps(nav),encoding='utf-8')
    response=client.get('/api/widget-catalog',query_string={'client_id':tenant})
    assert response.status_code==200
    data=dict(config=client.get('/api/widget-config',query_string={'client_id':tenant}).get_json(),
              catalog=response.get_json(),definition=client.get('/api/booking-form',query_string={'client_id':tenant}).get_json(),service_id=service_id)
    payload=tmp_path/'structure.json';payload.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    runner=RUNNER.split('  await page.evaluate(async fixtures => {',1)[0]+STRUCTURE
    result=subprocess.run(['node','--input-type=module','-'],input=runner,cwd=Path(__file__).resolve().parents[1],
        env={**os.environ,'CARDS_PAYLOADS':str(payload)},text=True,encoding='utf-8',capture_output=True,timeout=100)
    assert result.returncode==0,result.stdout+result.stderr
    assert '"passed":true' in result.stdout


STRUCTURE=r'''
  await page.evaluate(async fixtures=>{
    window.calls=[];
    window.fetch=async url=>{
      window.calls.push(String(url));
      const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
      if(String(url).includes('video-catalog'))return json({videos:{}});
      if(String(url).includes('widget-catalog'))return json(fixtures.catalog);
      if(String(url).includes('booking-form'))return json(fixtures.definition);
      throw new Error('Unexpected request '+url);
    };
    const {mountWidget}=await import('/static/widget/widget.js');mountWidget(document.querySelector('#root'),{...fixtures.config,apiBase:location.origin});
    document.querySelector('[data-clinic-dev-reset]')?.remove();document.querySelector('[data-clinic-launcher-open],[data-clinic-launcher]').click();
  },fixtures);
  await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
  const panel=page.locator('[data-clinic-catalog-panel]');await panel.locator('.clinic-catalog__service').first().waitFor();
  if(await panel.locator('.clinic-catalog__service').count()!==fixtures.catalog.services.length)throw new Error('Flat root not complete');
  for(const row of await panel.locator('.clinic-catalog__service').all()){
    const name=await row.locator('strong').innerText(),service=fixtures.catalog.services.find(s=>s.name===name);
    const summary=await row.locator('.clinic-catalog__row-price').innerText();
    if(service.price?!summary.endsWith('в прайсе'):summary!==fixtures.catalog.unpriced_text)throw new Error('Service summary invents/misses positions');
  }
  const service=fixtures.catalog.services.find(s=>s.service_id===fixtures.service_id);
  await panel.locator('.clinic-catalog__service').filter({hasText:service.name}).click();
  if(await panel.locator('.clinic-catalog__eyebrow').count())throw new Error('Repeated category above service');
  const rows=panel.locator('.clinic-price-card__overview-row');
  await page.evaluate(()=>document.fonts.ready);
  const ids=service.offer_groups.flatMap(group=>group.offer_ids);
  const actualIds=await rows.evaluateAll(rows=>rows.map(row=>row.dataset.priceOfferId));
  if(JSON.stringify(actualIds)!==JSON.stringify(ids))throw new Error('Group order changed canonical offers '+JSON.stringify({actualIds,ids}));
  if(await panel.locator('.clinic-price-card__group-title').count()!==service.offer_groups.length)throw new Error('Missing group headings');
  for(const size of ['100%','200%'])for(const width of [320,360,390,430,1280]){
    await page.evaluate(size=>document.documentElement.style.fontSize=size,size);await page.setViewportSize({width,height:900});
    const bad=await rows.evaluateAll(rows=>rows.map(row=>{
      const amount=row.querySelector('.clinic-price-card__amount').getBoundingClientRect(),arrow=row.querySelector('.clinic-price-card__row-arrow').getBoundingClientRect();
      return row.scrollWidth>row.clientWidth+1||arrow.top<amount.bottom-1||Math.abs(arrow.right-amount.right)>1;
    }).some(Boolean));
    if(bad)throw new Error('Price/arrow layout '+size+'/'+width);
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='100%');await page.setViewportSize({width:390,height:900});
  const search=panel.getByRole('searchbox',{name:'Поиск по прайсу'});
  if(service.price.rows.length>6){
    await search.fill('Дополнительные зоны');if(await rows.count()!==6)throw new Error('Group search missed published positions');
    await search.fill('ничего не найдено');if(await rows.count())throw new Error('Search did not filter');
    await search.fill('Тестовая зона 6');if(await rows.count()!==1||await panel.locator('.clinic-price-card__price-area').count())throw new Error('Search auto-selected single result');
  }
  let chosen=await rows.first().getAttribute('data-price-offer-id');await rows.first().click();
  if(await rows.count()||!await panel.locator('.clinic-price-card__price-area').count())throw new Error('Position detail not opened');
  if(await panel.locator('.clinic-price-card__tabs').count())throw new Error('Selected position still has variant tabs');
  let expected=service.price.rows.find(row=>row.offer_id===chosen);
  if(await panel.locator('.clinic-price-card__selected-variant').innerText()!==expected.variant_label)throw new Error('Selected position label lost');
  if(await panel.locator('.clinic-price-card__price-area .clinic-price-card__amount').innerText()!==expected.price_display_text)throw new Error('Selected position price changed');
  if(await page.getByRole('tab',{name:'Услуги и цены',exact:true}).getAttribute('aria-selected')!=='true')throw new Error('Unexpected tab switch');
  await panel.getByRole('button',{name:'← '+service.name,exact:true}).click();
  if(service.price.rows.length>6&&await search.inputValue()!=='Тестовая зона 6')throw new Error('Position search lost on return');
  if(await rows.first().getAttribute('data-price-offer-id')!==chosen)throw new Error('Return lost selected position list');
  if(service.price.rows.length>6)await search.fill('');
  const other=panel.locator(`.clinic-price-card__overview-row:not([data-price-offer-id="${chosen}"])`).first();
  chosen=await other.getAttribute('data-price-offer-id');expected=service.price.rows.find(row=>row.offer_id===chosen);
  await other.click();
  if(await panel.locator('.clinic-price-card__tabs').count())throw new Error('Second position restored tabs');
  if(await panel.locator('.clinic-price-card__selected-variant').innerText()!==expected.variant_label)throw new Error('Other position not selected');
  if(await panel.locator('.clinic-price-card__price-area .clinic-price-card__amount').innerText()!==expected.price_display_text)throw new Error('Other position price changed');
  await panel.getByRole('button',{name:'Оставить заявку',exact:true}).click();
  const form=panel.locator('.clinic-booking');await form.waitFor();
  if(!(await form.locator('.clinic-booking__subject').innerText()).includes(expected.variant_label))throw new Error('Exact chosen offer lost');
  if(await page.evaluate(()=>window.calls.some(url=>url.includes('/ask')||url.endsWith('/lead'))))throw new Error('Catalog called model/lead');
  if(failures.length)throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,provider:0}));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
'''
