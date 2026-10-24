"""Real widget options → exact detail using native offline HTTP receipts."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.d2_ci_http import http_env, send, click
from tests.test_d2_price_cards import cards
from tests.test_d2_price_cards_browser import RUNNER
from tests.test_d2_price_variants import medical, native


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Chrome/Playwright geometry proof')
@pytest.mark.parametrize('tenant,service,chosen', [
    ('demo','classic','classic.one_tooth.impro'),
    ('nikadent','removable_dentures','removable_dentures.jaw.nylon'),
    ('demo_medical','laser_hair_removal','laser_hair_removal.three_zones'),
])
def test_shared_options_and_detail_in_widget(http_env, monkeypatch, tmp_path, tenant, service, chosen):
    if tenant == 'demo_medical':
        medical(http_env, monkeypatch)
    client, _, use, _ = http_env
    wire = native(use, service)
    first = send(client, client_id=tenant, sid='browser', q='Стоимость?')
    ref = 'price_select:'+chosen
    selected = click(client, first, ref, client_id=tenant, sid='browser', request_id='click')
    assert len(wire.calls) == 1
    payloads = tmp_path/'payloads.json'
    payloads.write_text(json.dumps({'responses': {'Стоимость?':first, ref:selected},
        'expected':cards(first)[0]['price']['rows'], 'selected':cards(selected)[0]['price']['rows'][0],
        'ref':ref},ensure_ascii=False),encoding='utf-8')
    bootstrap = RUNNER.split("  await send('Классическая имплантация');",1)[0]
    bootstrap = bootstrap.replace("clientId:'demo'", "clientId:"+json.dumps(tenant))
    runner = bootstrap + r'''
  await send('Стоимость?');
  const card=page.locator('.clinic-price-card');
  await card.waitFor();
  if(await card.count()!==1)throw new Error('List duplicated');
  if(await card.locator('[aria-pressed="true"]').count())throw new Error('First row preselected');
  const rows=card.locator('.clinic-price-card__overview-row');
  if(await rows.count()!==fixtures.expected.length)throw new Error('Missing options');
  if(await card.locator('[data-price-section="includes"]').count())throw new Error('List exposes hidden details');
  for(const row of fixtures.expected){
    if(!(await card.textContent()).includes(row.price_display_text))throw new Error('Price missing');
  }
  const proof=[];
  for(const width of [320,390,1280]){
    await page.setViewportSize({width,height:900});await page.waitForTimeout(150);
    const geometry=await rows.evaluateAll(entries=>entries.map(row=>{
      const name=row.querySelector('.clinic-price-card__overview-name').getBoundingClientRect();
      const amount=row.querySelector('.clinic-price-card__amount').getBoundingClientRect();
      return {nameWidth:name.width,overlap: name.right>amount.left+1 && name.bottom>amount.top+1,
        overflow:row.scrollWidth>row.clientWidth+1};
    }));
    if(geometry.some(r=>r.nameWidth<60||r.overflow||r.overlap))throw new Error('Invalid list geometry '+JSON.stringify({width,geometry}));
    proof.push({width,geometry});
  }
  const turns=await page.locator('.clinic-turn').count(), users=await page.locator('.clinic-msg--user').count();
  const index=fixtures.expected.findIndex(row=>'price_select:'+row.offer_id===fixtures.ref);
  await rows.nth(index).click();
  await page.waitForFunction(() => !document.querySelector('.clinic-price-card__overview-row'));
  if(await card.count()!==1||await page.locator('.clinic-turn').count()!==turns||await page.locator('.clinic-msg--user').count()!==users)
    throw new Error('Selection appended a conversation turn');
  if(!(await card.textContent()).includes(fixtures.selected.price_display_text))throw new Error('Exact detail missing');
  const sections=card.locator('details');
  for(let i=0;i<await sections.count();i++){
    const section=sections.nth(i);await section.locator('summary').click();
    if(!(await section.innerText()).trim())throw new Error('Empty section');
  }
  for(const text of [...fixtures.selected.includes,...fixtures.selected.excludes,...fixtures.selected.stages]){
    const compact=text=>text.replace(/\s/g,'');
    if(!compact(await card.innerText()).includes(compact(text)))throw new Error('Authored detail lost: '+text);
  }
  for(const width of [320,390,1280]){
    await page.setViewportSize({width,height:900});await page.waitForTimeout(100);
    if(await card.evaluate(c=>c.scrollWidth>c.clientWidth+1))throw new Error('Detail overflow');
  }
  if(process.env.PRICE_LAYOUT_SCREENSHOT_DIR){fs.mkdirSync(process.env.PRICE_LAYOUT_SCREENSHOT_DIR,{recursive:true});
    await page.setViewportSize({width:390,height:900});
    await card.screenshot({path:path.join(process.env.PRICE_LAYOUT_SCREENSHOT_DIR,fixtures.selected.source_client_id+'-detail.png')});}
  if(failures.length)throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,proof,provider:0}));
}finally{await browser.close();await new Promise(r=>server.close(r));}
'''
    result = subprocess.run(['node','--input-type=module','-'], input=runner,
        cwd=Path(__file__).resolve().parents[1], env={**os.environ,'CARDS_PAYLOADS':str(payloads)},
        text=True, encoding='utf-8',capture_output=True,timeout=60,check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    assert '"passed":true' in result.stdout


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Chrome/Playwright geometry proof')
def test_unpriced_detail_and_excludes_without_includes_in_widget(http_env, monkeypatch, tmp_path):
    medical(http_env, monkeypatch)
    client, _, use, tmp = http_env
    path = tmp/'clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['package']['includes'] = []
    data['package']['excludes'] = ['Дополнительная зона']
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    wire = native(use, 'botulinum_therapy', needs_completion=True, option_id='individual')
    first = send(client,client_id='demo_medical',q='Стоимость?')
    assert len(wire.calls) == 2
    payloads = tmp_path/'unpriced.json'
    payloads.write_text(json.dumps({'responses':{'Стоимость?':first}},ensure_ascii=False),encoding='utf-8')
    bootstrap = RUNNER.split("  await send('Классическая имплантация');",1)[0].replace("clientId:'demo'","clientId:'demo_medical'")
    runner = bootstrap + r'''
  await send('Стоимость?');const card=page.locator('.clinic-price-card');await card.waitFor();
  if(await card.count()!==1)throw new Error('No-public card missing');
  if(await card.locator('.clinic-price-card__overview-row').count())throw new Error('Unexpected list');
  const section=card.locator('[data-price-section="includes"]');
  if(await section.locator('summary').innerText()!=='Оплачивается отдельно')throw new Error('Empty includes heading');
  await section.locator('summary').click();
  if(!(await section.innerText()).includes('Дополнительная зона'))throw new Error('Excludes disappeared');
  if(await card.locator('summary',{hasText:'Что входит'}).count())throw new Error('Empty section shown');
  if(!(await card.locator('.clinic-price-card__amount').innerText()).includes('Стоимость уточнит администратор'))throw new Error('Authored price absent');
  for(const width of [320,390,1280]){await page.setViewportSize({width,height:900});await page.waitForTimeout(100);
    if(await card.evaluate(c=>c.scrollWidth>c.clientWidth+1))throw new Error('No-public detail overflow');}
  if(failures.length)throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,provider:0}));
}finally{await browser.close();await new Promise(r=>server.close(r));}
'''
    result = subprocess.run(['node','--input-type=module','-'],input=runner,
        cwd=Path(__file__).resolve().parents[1],env={**os.environ,'CARDS_PAYLOADS':str(payloads)},
        text=True,encoding='utf-8',capture_output=True,timeout=60,check=False)
    assert result.returncode == 0,result.stdout+result.stderr
    assert '"passed":true' in result.stdout
