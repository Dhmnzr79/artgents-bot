"""One detail presentation for all authored offers, in catalog and dialogue."""
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from core.d2_tenant_snapshot import load_d2_tenant_snapshot
from core.widget_catalog import build_widget_catalog
from tests.test_d2_price_cards_browser import RUNNER


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Chrome offline UI proof')
def test_all_client_price_details_share_scope_and_lists(tmp_path):
    root = Path(__file__).resolve().parents[1]
    examples = []
    for folder in sorted((root / 'clients').iterdir()):
        if not (folder / 'target_response/widget_catalog.json').exists():
            continue
        snapshot = load_d2_tenant_snapshot(folder.name, clients_root=root / 'clients')
        catalog = build_widget_catalog(snapshot, as_of=date(2026, 10, 17))
        for service in catalog['services']:
            for offer_id, detail in service['details'].items():
                examples.append(dict(client=folder.name, offer=offer_id, **detail))
    assert len(examples) == 105
    payload = tmp_path / 'all-price-details.json'
    payload.write_text(json.dumps(examples, ensure_ascii=False), encoding='utf-8')
    runner = RUNNER.split('  await page.evaluate(async fixtures => {', 1)[0] + DETAILS
    result = subprocess.run(['node', '--input-type=module', '-'], input=runner,
        cwd=root, env={**os.environ, 'CARDS_PAYLOADS': str(payload)},
        text=True, encoding='utf-8', capture_output=True, timeout=80)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"rendered":210' in result.stdout


DETAILS = r'''
  const rendered=await page.evaluate(async examples=>{
    const {renderPriceBody}=await import('/static/widget/price_card.js');
    const normalized=text=>text.replace(/\s+/g,' ').trim().toLocaleLowerCase('ru-RU');
    const richText=text=>text.replace(/\*\*/g,'');
    const readText=node=>{
      const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),chunks=[];
      let text;while((text=walker.nextNode()))chunks.push(text.nodeValue);
      return chunks.join(' ');
    };
    let count=0;
    for(const example of examples)for(const catalog of [false,true]){
      const root=document.querySelector('#root');root.replaceChildren();
      const row=example.price.rows[0];
      renderPriceBody(root,{revision:'offline',bodyParts:[
        {kind:'price_card',price:example.price,choices:[]},...example.parts
      ]},{clientId:example.client,isDisabled:()=>false,onSelect:()=>{throw Error('unexpected selection')},
        getLatestRevision:()=> 'offline',catalog});
      const card=root.querySelector('.clinic-price-card');
      if(!card)throw Error('Missing card '+example.offer);
      const area=card.querySelector('.clinic-price-card__price-area');
      if(area.querySelectorAll('.clinic-price-card__caption').length!==(row.scope_text?1:0))throw Error('Scope count '+example.offer);
      if(area.querySelector('.clinic-price-card__condition'))throw Error('Additional price note '+example.offer);
      if(row.scope_text&&area.querySelector('.clinic-price-card__caption span').textContent!==row.scope_text)throw Error('Scope changed');
      if(area.querySelector('.clinic-price-card__amount').textContent!==row.price_display_text)throw Error('Price changed');
      const contains=(section,text)=>{
        const target=card.querySelector(`[data-price-section="${section}"]`);
        if(!target||!normalized(readText(target)).includes(normalized(richText(text))))throw Error('Lost '+section+': '+example.offer+' / '+text);
      };
      for(const value of row.includes||[])contains('includes',value);
      for(const value of row.excludes||[])contains('excludes',value);
      for(const value of row.condition_texts||[])if(value!==row.scope_text)contains((row.excludes||[]).includes(value)?'excludes':'conditions',value);
      for(const value of row.stages||[])contains('payment',value);
      for(const part of example.parts)if(!normalized(readText(card)).includes(normalized(richText(part.text))))throw Error('Lost commercial text '+example.offer);
      for(const key of ['includes','excludes','conditions']){
        const section=card.querySelector(`[data-price-section="${key}"]`);if(!section)continue;
        const lists=section.querySelectorAll(':scope>ul.clinic-price-card__list');
        if(lists.length!==1||!lists[0].children.length)throw Error('Not a single populated list '+key);
        if(section.querySelector(':scope>.clinic-price-card__detail-body'))throw Error('Old paragraph layout '+key);
        for(const item of lists[0].children){
          if(item.tagName!=='LI'||item.querySelector('svg'))throw Error('Mixed list marker');
          const first=item.textContent.trim().match(/^\p{L}/u)?.[0];
          if(first&&first!==first.toLocaleUpperCase('ru-RU'))throw Error('Lowercase item '+item.textContent);
        }
        const strings=[...lists[0].children].map(item=>item.textContent);
        if(new Set(strings).size!==strings.length)throw Error('Duplicate list item');
      }
      const sections=[...card.querySelectorAll('details')].map(el=>el.dataset.priceSection);
      const ordered=['includes','excludes','conditions','payment'].filter(key=>sections.includes(key));
      if(JSON.stringify(sections)!==JSON.stringify(ordered))throw Error('Section order/count changed');
      if(card.querySelectorAll('.clinic-price-card__stage-title').length!==(row.stages||[]).length)throw Error('Payment stages changed');
      if(card.querySelector('.clinic-price-card__promotion a,.clinic-price-card__promotion button'))throw Error('Clickable promotion');
      if(card.querySelector('.clinic-price-card__check-list'))throw Error('Old checklist reachable');
      count++;
    }
    // Future arbitrary services, casing and exact duplicate conditions share the same path.
    const synthetic=structuredClone(examples[0]);const row=synthetic.price.rows[0];
    row.service_name='Произвольная услуга';row.scope_text='за один объём';
    row.includes=['пункт состава'];row.excludes=['дополнительный объём'];
    row.condition_texts=['за один объём','дополнительный объём','важное условие','Важное условие'];
    row.stages=[];
    const root=document.querySelector('#root');root.replaceChildren();
    renderPriceBody(root,{bodyParts:[{kind:'price_card',price:synthetic.price,choices:[]}]},
      {clientId:synthetic.client,catalog:false,isDisabled:()=>false,onSelect:()=>{},getLatestRevision:()=>''});
    if(root.querySelectorAll('[data-price-section=conditions] li').length!==1)throw Error('Exact duplicate condition not removed');
    if(root.querySelector('[data-price-section=payment]'))throw Error('Empty payment section');
    row.includes=[];row.excludes=[];row.condition_texts=[];root.replaceChildren();
    renderPriceBody(root,{bodyParts:[{kind:'price_card',price:synthetic.price,choices:[]},
      {kind:'text',price_owned:true,price_section:'benefits',text:'**первое условие**\n\n- второе условие\n- третье условие'}]},
      {clientId:synthetic.client,catalog:false,isDisabled:()=>false,onSelect:()=>{},getLatestRevision:()=>''});
    const list=root.querySelector('[data-price-section=conditions]>ul');
    if(JSON.stringify([...list.children].map(item=>item.textContent))!==JSON.stringify(['Первое условие','Второе условие','Третье условие']))throw Error('Authored rich blocks not uniform list items');
    if(list.querySelector('ul,ol,p')||!list.querySelector('strong'))throw Error('Nested list/paragraph layout or lost safe emphasis');
    if(root.querySelector('[data-price-section=includes],[data-price-section=excludes]'))throw Error('Empty list sections');
    row.includes=[' '];row.excludes=[''];row.condition_texts=['\n'];root.replaceChildren();
    renderPriceBody(root,{bodyParts:[{kind:'price_card',price:synthetic.price,choices:[]},
      {kind:'text',price_owned:true,price_section:'benefits',text:' '},
      {kind:'text',price_owned:true,price_section:'benefits',text:'полезное условие'}]},
      {clientId:synthetic.client,catalog:false,isDisabled:()=>false,onSelect:()=>{},getLatestRevision:()=>''});
    if(root.querySelector('[data-price-section=includes],[data-price-section=excludes]'))throw Error('Whitespace-only sections');
    if(root.querySelector('[data-price-section=conditions] li')?.textContent!=='Полезное условие')throw Error('Condition after empty block was lost');
    return count;
  },fixtures);
  if(failures.length)throw Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,rendered,provider:0}));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
'''
