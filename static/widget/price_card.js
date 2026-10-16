import { setBotAnswerBody } from "./answer_format.js";

export function renderPriceBody(bubble, message, {clientId, isDisabled, onSelect, getLatestRevision, offerIdForChoice = choice => String(choice.reply_id || "").replace(/^price_select:/, "")}) {
  let texts = [];
  let financialCard = null;
  const sections = new Map();
  let promotionCount = 0;
  const svg = (name) => {
    const paths = {layers:'m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',
      check:'m5 12 4 4 10-10',clock:'M12 7v5l4 2',info:'M12 11v6M12 7v1',
      gift:'M3 9h18v4H3ZM5 13v8h14v-8M12 9v12M12 9C5 9 5 3 8 3c3 0 4 6 4 6s1-6 4-6c3 0 3 6-4 6Z',
      chevron:'m9 5 7 7-7 7',arrow:'M4 12h16M14 6l6 6-6 6',extent:'m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3ZM4 7.5l8 4.5 8-4.5M12 12v9'};
    const el = document.createElementNS('http://www.w3.org/2000/svg','svg');
    el.setAttribute('viewBox','0 0 24 24'); el.setAttribute('aria-hidden','true');
    el.classList.add('clinic-price-card__icon');
    if (name === 'info' || name === 'clock') {
      const circle = document.createElementNS(el.namespaceURI,'circle');
      circle.setAttribute('cx','12');circle.setAttribute('cy','12');circle.setAttribute('r','9');el.appendChild(circle);
    }
    const path = document.createElementNS(el.namespaceURI,'path');path.setAttribute('d',paths[name]);el.appendChild(path);
    return el;
  };
  const flushText = () => {
    if (!texts.length) return;
    const body = document.createElement('div');body.className='clinic-msg__body';
    setBotAnswerBody(body,texts.join('\n\n'));bubble.appendChild(body);texts=[];
  };
  const detail = (key, label, icon) => {
    if (sections.has(key)) return sections.get(key);
    const el=document.createElement('details');el.className='clinic-price-card__detail';
    el.dataset.priceSection=key;
    const summary=document.createElement('summary');summary.appendChild(svg(icon));
    const title=document.createElement('span');title.textContent=label;summary.appendChild(title);
    const arrow=svg('chevron');arrow.classList.add('clinic-price-card__chevron');summary.appendChild(arrow);
    el.appendChild(summary);financialCard.appendChild(el);sections.set(key,el);return el;
  };
  const addText = (target,text) => {
    const body=document.createElement('div');body.className='clinic-price-card__detail-body';
    setBotAnswerBody(body,text);target.appendChild(body);
  };
  const disabled = isDisabled;
  const select = (choice, revision) => onSelect(choice, revision);
  for (const part of message.bodyParts) {
    if (part.kind==='text' && part.price_owned && part.price_section && financialCard) {
      flushText();
      if (part.price_section==='promotion' && promotionCount++===0) {
        const promo=document.createElement('section');promo.className='clinic-price-card__promotion';
        promo.appendChild(svg('gift'));
        const content=document.createElement('div');addText(content,part.text);promo.appendChild(content);financialCard.appendChild(promo);
      } else {
        const payment=part.price_section==='consultation';
        addText(detail(payment?'payment':'conditions',payment?'Порядок оплаты':'Условия и преимущества',payment?'clock':'info'),part.text);
      }
      continue;
    }
    if(part.kind==='text'){texts.push(part.text);continue;}
    if(part.kind!=='price_card'||part.price?.source_client_id!==clientId)continue;
    flushText();
    const rows=part.price.rows||[];
    if(!rows.length||rows.some(row=>row.source_client_id!==clientId))continue;
    const card=document.createElement('section');card.className='clinic-price-card';
    const overview=Boolean(part.overview);
    const options=part.price.presentation==='options';
    card.setAttribute('aria-label',overview?'Услуги и цены':rows[0].service_name);
    financialCard=card;sections.clear();promotionCount=0;
    if(part.overview?.volume_choices?.length){
      message.volumeNavigation={
        revision:message.revision,
        choices:part.overview.volume_choices.map(choice=>choice.candidate),
        selectedReplyId:message.volumeNavigation?.selectedReplyId,
      };
    }
    if(overview&&message.volumeNavigation?.choices.length){
      const nav=document.createElement('div');nav.className='clinic-price-card__tabs clinic-price-card__volumes';
      nav.setAttribute('role','group');nav.setAttribute('aria-label','Объём лечения');
      for(const choice of message.volumeNavigation.choices){
        const button=document.createElement('button');button.type='button';button.className='clinic-price-card__tab';
        button.textContent=choice.label;button.disabled=disabled();
        const selected=message.volumeNavigation.selectedReplyId
          || (part.overview.applied_extent ? `volume:${part.overview.topic_id}:${part.overview.applied_extent}` : null);
        button.setAttribute('aria-pressed',String(choice.reply_id===selected));
        button.addEventListener('click',()=>select(choice,message.volumeNavigation.revision));nav.appendChild(button);
      }
      card.appendChild(nav);
      if(message.volumeNavigation.selectedReplyId===`volume:${part.overview.topic_id}:unknown`){
        const hint=document.createElement('p');
        hint.className='clinic-price-card__volume-hint';
        hint.setAttribute('role','status');
        hint.textContent='Не уверены, какой вариант подходит? На консультации врач оценит состояние зубов и предложит варианты лечения с понятной стоимостью.';
        card.appendChild(hint);
      }
    }
    const title=document.createElement('h3');title.className='clinic-price-card__title';
    title.textContent=overview?'Услуги и цены':rows[0].service_name;card.appendChild(title);
    if(!options&&(part.choices||[]).length>1){
      const tabs=document.createElement('div');tabs.className='clinic-price-card__tabs';tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Вариант');
      for(const choice of part.choices){
        const active=offerIdForChoice(choice)===rows[0].offer_id;
        const tab=document.createElement('button');tab.type='button';tab.className='clinic-price-card__tab';
        tab.textContent=choice.label;tab.setAttribute('aria-pressed',String(active));tab.disabled=disabled();
        tab.addEventListener('click',()=>{if(!active||message.revision!==getLatestRevision())select(choice,message.revision)});tabs.appendChild(tab);
      }card.appendChild(tabs);
    }
    if(!options&&(part.choices||[]).length<=1&&rows[0].variant_label){
      const label=document.createElement('p');label.className='clinic-price-card__selected-variant';
      label.textContent=rows[0].variant_label;card.appendChild(label);
    }
    const allChoices=[...(part.choices||[]),...(part.service_choices||[])];
    for(const row of rows){
      const choice=allChoices.find(choice=>offerIdForChoice(choice)===row.offer_id);
      const item=document.createElement(options&&choice?'button':'div');
      item.className=options?'clinic-price-card__overview-row':'clinic-price-card__price-area';
      if(options&&row.mode==='no_public_price')item.classList.add('clinic-price-card__overview-row--description');
      if(options&&choice){item.type='button';item.disabled=disabled();item.addEventListener('click',()=>select(choice,message.revision));}
      if(options){const name=document.createElement('span');name.className='clinic-price-card__overview-name';name.textContent=overview?row.service_name:(row.variant_label||row.service_name);item.appendChild(name);}
      const amount=document.createElement('strong');amount.className='clinic-price-card__amount';
      amount.textContent=row.price_display_text;
      if(row.mode==='no_public_price')amount.classList.add('clinic-price-card__amount--description');
      else if(!options)amount.classList.add('clinic-price-card__amount--single');item.appendChild(amount);
      if(options&&choice){const arrow=svg('arrow');arrow.classList.add('clinic-price-card__row-arrow');item.appendChild(arrow);}
      if(row.scope_text){const caption=document.createElement('p');caption.className='clinic-price-card__caption';if(!options)caption.appendChild(svg('extent'));const scope=document.createElement('span');scope.textContent=row.scope_text;caption.appendChild(scope);item.appendChild(caption);}
      // Overview is a compact preview; full authored conditions stay in detail.
      for(const term of (options ? [] : [...new Set(row.condition_texts||[])])){
        if(term===row.scope_text)continue;
        const note=document.createElement('p');note.className='clinic-price-card__condition';note.appendChild(svg('info'));
        const text=document.createElement('span');text.textContent=term.charAt(0).toUpperCase()+term.slice(1);note.appendChild(text);item.appendChild(note);
      }
      card.appendChild(item);
    }
    bubble.appendChild(card);
    if(!options&&rows.length===1){
      const row=rows[0];
      if(row.includes?.length){
        const el=detail('includes','Что входит в стоимость','layers');
        const list=document.createElement('ul');list.className='clinic-price-card__check-list';
        for(const line of row.includes){const li=document.createElement('li');li.appendChild(svg('check'));const text=document.createElement('span');text.textContent=line;li.appendChild(text);list.appendChild(li);}el.appendChild(list);
      }
      if(row.excludes?.length){const el=detail('excludes','Оплачивается отдельно','info');const exclusions=document.createElement('ul');for(const line of row.excludes){const li=document.createElement('li');li.textContent=line;exclusions.appendChild(li);}el.appendChild(exclusions);}
      if(row.stages?.length){
        const el=detail('payment','Порядок оплаты','clock');
        for(const line of row.stages){
          // Frozen stage formatter separates its heading/amount from timing with '. '.
          const separator=line.indexOf('. ');
          const body=document.createElement('div');body.className='clinic-price-card__detail-body';
          const heading=document.createElement('strong');heading.className='clinic-price-card__stage-title';
          heading.textContent=separator<0?line:line.slice(0,separator+1);body.appendChild(heading);
          if(separator>=0){const timing=document.createElement('p');timing.textContent=line.slice(separator+2);body.appendChild(timing);}
          el.appendChild(body);
        }
      }
    }
  }
  // Commercial parts may arrive after the promotion; keep the open promo last.
  for(const card of bubble.querySelectorAll('.clinic-price-card')){const promo=card.querySelector('.clinic-price-card__promotion');if(promo)card.appendChild(promo);}
  flushText();
}

export function mergePriceMessage(old, turn, selectedRef) {
  const cardIndex=old.bodyParts.findIndex(part=>part.kind==='price_card');
  const nextCardIndex=turn.bodyParts.findIndex(part=>part.kind==='price_card');
  if(cardIndex<0||nextCardIndex<0)return false;
  const nextCard=turn.bodyParts[nextCardIndex],overview=old.bodyParts[cardIndex].overview;
  if(!old.volumeNavigation&&overview?.volume_choices?.length)old.volumeNavigation={revision:old.revision,choices:overview.volume_choices.map(c=>c.candidate)};
// Replace price-owned content at its existing anchors. Independent
// text (e.g. an address between price and promotion) stays in place.
const before = turn.bodyParts.slice(0, nextCardIndex).filter(p => p.price_owned);
const after = turn.bodyParts.slice(nextCardIndex + 1).filter(p => p.price_owned);
const merged = [];
let beforeInserted = false, afterInserted = false;
old.bodyParts.forEach((part, index) => {
  if (part.price_owned) {
    if (index < cardIndex && !beforeInserted) { merged.push(...before); beforeInserted = true; }
    if (index > cardIndex && !afterInserted) { merged.push(...after); afterInserted = true; }
  } else if (index === cardIndex) {
    if (!beforeInserted) { merged.push(...before); beforeInserted = true; }
    merged.push(nextCard);
  } else merged.push(part);
});
if (!afterInserted) merged.push(...after);
Object.assign(old, turn, {bodyParts: merged});
if(String(selectedRef).startsWith("volume:")&&old.volumeNavigation)old.volumeNavigation.selectedReplyId=selectedRef;
  return true;
}
