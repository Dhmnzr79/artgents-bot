// Generated copy of the real answer formatter and price card renderer.
(() => {
/**
 * Безопасный поднабор Markdown для ответов бота. См. docs/WIDGET_ANSWER_FORMAT.md
 */

/**
 * @param {string} s
 */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * @param {string} s
 */
function formatInline(s) {
  let out = escapeHtml(s);
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  return out;
}

/**
 * @param {string} line
 */
function lineKind(line) {
  const t = line.trim();
  if (!t) return "blank";
  if (/^#{1,3}\s+/.test(t)) return "h";
  if (/^[-*]\s+/.test(t)) return "ul";
  if (/^\d+\.\s+/.test(t)) return "ol";
  return "p";
}

/**
 * @param {string} line
 */
function stripListPrefix(line) {
  const t = line.trim();
  if (/^[-*]\s+/.test(t)) return t.replace(/^[-*]\s+/, "");
  if (/^\d+\.\s+/.test(t)) return t.replace(/^\d+\.\s+/, "");
  if (/^#{1,3}\s+/.test(t)) return t.replace(/^#{1,3}\s+/, "");
  return t;
}

/**
 * @param {string[]} lines
 * @returns {{ type: string, lines: string[] }[]}
 */
function groupLines(lines) {
  /** @type {{ type: string, lines: string[] }[]} */
  const groups = [];
  /** @type {{ type: string, lines: string[] } | null} */
  let current = null;

  for (const raw of lines) {
    const kind = lineKind(raw);
    if (kind === "blank") {
      if (current) {
        groups.push(current);
        current = null;
      }
      continue;
    }
    if (!current || current.type !== kind) {
      if (current) groups.push(current);
      current = { type: kind, lines: [raw] };
    } else {
      current.lines.push(raw);
    }
  }
  if (current) groups.push(current);
  return groups;
}

/**
 * @param {{ type: string, lines: string[] }} group
 */
function renderGroup(group) {
  const { type, lines } = group;
  if (type === "ul") {
    const items = lines
      .map((ln) => `<li>${formatInline(stripListPrefix(ln))}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }
  if (type === "ol") {
    const items = lines
      .map((ln) => `<li>${formatInline(stripListPrefix(ln))}</li>`)
      .join("");
    return `<ol>${items}</ol>`;
  }
  if (type === "h") {
    return lines
      .map((ln) => `<p class="clinic-msg__lead"><strong>${formatInline(stripListPrefix(ln))}</strong></p>`)
      .join("");
  }
  return lines.map((ln) => `<p>${formatInline(ln.trim())}</p>`).join("");
}

/**
 * @param {string} text
 * @returns {string}
 */
function renderBotAnswerHtml(text) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) return "";
  const groups = groupLines(normalized.split("\n"));
  return groups.map(renderGroup).join("");
}

/**
 * @param {HTMLElement | null} el
 * @param {string} text
 */
function setBotAnswerBody(el, text) {
  if (!el) return;
  const html = renderBotAnswerHtml(text);
  if (!html) {
    el.classList.remove("clinic-msg__body--rich");
    el.textContent = "";
    return;
  }
  el.classList.add("clinic-msg__body--rich");
  el.innerHTML = html;
}



function renderPriceBody(bubble, message, {clientId, isDisabled, onSelect, getLatestRevision, rowGroups = null, showTitle = true, catalog = false, offerIdForChoice = choice => String(choice.reply_id || "").replace(/^price_select:/, "")}) {
  let texts = [];
  let financialCard = null;
  const sections = new Map();
  let promotionCount = 0;
  const svg = (name) => {
    const paths = {layers:'m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',
      clock:'M12 7v5l4 2',info:'M12 11v6M12 7v1',
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
  // The first three disclosures share one list renderer in chat and catalog.
  const addItems = (target, lines, rich = false) => {
    let list = target.querySelector('ul.clinic-price-card__list');
    if (!list) { list=document.createElement('ul');list.className='clinic-price-card__list';target.appendChild(list); }
    for (const line of lines) {
      const content=document.createElement('div');
      if (rich) setBotAnswerBody(content,line); else content.textContent=line;
      const entries=rich ? [...content.children].flatMap(block=>
        ['UL','OL'].includes(block.tagName) ? [...block.children] : [block]) : [content];
      for (const entry of entries) {
        const li=document.createElement('li');li.append(...entry.childNodes);
        if (!li.textContent.trim()) continue;
        const walker=document.createTreeWalker(li,NodeFilter.SHOW_TEXT);
        let first;
        while ((first=walker.nextNode())) {
          if (!first.nodeValue.trim()) continue;
          first.nodeValue=first.nodeValue.replace(/^(\s*)(\p{L})/u,(_,space,letter)=>space+letter.toLocaleUpperCase('ru-RU'));
          break;
        }
        // Ignore exact repeats after presentation casing; do not infer semantic equivalence.
        if (![...list.children].some(item=>item.textContent===li.textContent))list.appendChild(li);
      }
    }
    if (!list.children.length) { sections.delete(target.dataset.priceSection);target.remove(); }
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
        const section=detail(payment?'payment':'conditions',payment?'Порядок оплаты':'Условия и преимущества',payment?'clock':'info');
        if(payment)addText(section,part.text);else addItems(section,[part.text],true);
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
    if(showTitle){const title=document.createElement('h3');title.className='clinic-price-card__title';
      title.textContent=overview?'Услуги и цены':rows[0].service_name;card.appendChild(title);}
    if(!catalog&&!options&&(part.choices||[]).length>1){
      const tabs=document.createElement('div');tabs.className='clinic-price-card__tabs';tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Вариант');
      for(const choice of part.choices){
        const active=offerIdForChoice(choice)===rows[0].offer_id;
        const tab=document.createElement('button');tab.type='button';tab.className='clinic-price-card__tab';
        tab.textContent=choice.label;tab.setAttribute('aria-pressed',String(active));tab.disabled=disabled();
        tab.addEventListener('click',()=>{if(!active||message.revision!==getLatestRevision())select(choice,message.revision)});tabs.appendChild(tab);
      }card.appendChild(tabs);
    }
    if(!catalog&&!options&&(part.choices||[]).length<=1&&rows[0].variant_label){
      const label=document.createElement('p');label.className='clinic-price-card__selected-variant';
      label.textContent=rows[0].variant_label;card.appendChild(label);
    }
    const allChoices=[...(part.choices||[]),...(part.service_choices||[])];
    const displayRows=options&&rowGroups!==null?rowGroups.flatMap(group=>group.offer_ids.map((id,index)=>({row:rows.find(row=>row.offer_id===id),heading:index===0?group.title:null}))).filter(item=>item.row):rows.map(row=>({row,heading:null}));
    for(const {row,heading} of displayRows){
      if(heading){const label=document.createElement('h4');label.className='clinic-price-card__group-title';label.textContent=heading;card.appendChild(label);}
      const choice=allChoices.find(choice=>offerIdForChoice(choice)===row.offer_id);
      const item=document.createElement(options&&choice?'button':'div');
      item.className=options?'clinic-price-card__overview-row':'clinic-price-card__price-area';
      if(options)item.dataset.priceOfferId=row.offer_id;
      if(options&&row.mode==='no_public_price'&&!catalog)item.classList.add('clinic-price-card__overview-row--description');
      if(options&&choice){item.type='button';item.disabled=disabled();item.addEventListener('click',()=>select(choice,message.revision));}
      if(options){const name=document.createElement('span');name.className='clinic-price-card__overview-name';name.textContent=overview?row.service_name:(row.variant_label||row.service_name);item.appendChild(name);}
      const amount=document.createElement('strong');amount.className='clinic-price-card__amount';
      amount.textContent=row.price_display_text;
      if(row.mode==='no_public_price')amount.classList.add('clinic-price-card__amount--description');
      else if(!options)amount.classList.add('clinic-price-card__amount--single');
      if(!catalog||!options||row.mode!=='no_public_price')item.appendChild(amount);
      if(options&&choice){const arrow=svg('arrow');arrow.classList.add('clinic-price-card__row-arrow');item.appendChild(arrow);}
      if(row.scope_text){const caption=document.createElement('p');caption.className='clinic-price-card__caption';if(!options)caption.appendChild(svg('extent'));const scope=document.createElement('span');scope.textContent=row.scope_text;caption.appendChild(scope);item.appendChild(caption);}
      card.appendChild(item);
    }
    bubble.appendChild(card);
    if(!options&&rows.length===1){
      const row=rows[0];
      if(row.includes?.length)addItems(detail('includes','Что входит в стоимость','layers'),row.includes);
      if(row.excludes?.length)addItems(detail('excludes','Оплачивается отдельно','info'),row.excludes);
      const terms=[...new Set(row.condition_texts||[])].filter(term=>term!==row.scope_text&&!(row.excludes||[]).includes(term));
      if(terms.length)addItems(detail('conditions','Условия и преимущества','info'),terms);
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
  for(const card of bubble.querySelectorAll('.clinic-price-card')){
    for(const key of ['includes','excludes','conditions','payment']){const section=card.querySelector(`[data-price-section="${key}"]`);if(section)card.appendChild(section);}
    const promo=card.querySelector('.clinic-price-card__promotion');if(promo)card.appendChild(promo);
  }
  flushText();
}

function mergePriceMessage(old, turn, selectedRef) {
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

window.WidgetPlaygroundRenderer = {renderPriceBody};
})();

// Local-only booking fixture; no network transport.
(() => {


const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!=null)node.textContent=text;return node;};

/** One ephemeral draft, handler and delivery result for every form location. */
function createBookingForm({apiBase,clientId,getSid,getCatalog}){
  const draft={name:'',phone:'',consent:false,wish:'',selection:null};
  const mounts=new Map();
  let definition=null,loading=null,pending=false,result=null,body=null,error='';
  const base=apiBase.replace(/\/$/,'');
  const sync=(field,value)=>{
    draft[field]=value;if(!pending)body=null;
    for(const mount of mounts.keys())for(const input of mount.querySelectorAll(`[data-booking-field="${field}"]`)){
      if(input===document.activeElement)continue;
      if(field==='consent')input.checked=value;else input.value=value;
    }
  };
  async function load(){definition={checkbox_text:'Даю согласие на обработку имени и телефона для связи по моей заявке.'};}
  function renderAll(){for(const [mount,extended]of mounts){if(mount.isConnected)void render(mount,{extended});else mounts.delete(mount);}}
  async function render(mount,{extended=false}={}){
    mounts.set(mount,extended);
    if(result?.ok){mount.replaceChildren(el('div','clinic-booking__success',result.message));return;}
    mount.replaceChildren(el('p',null,'Открываем форму…'));
    let catalog;
    try{await load();catalog=await getCatalog();}catch{
      const retry=el('button','clinic-booking__submit','Попробовать ещё раз');retry.type='button';retry.onclick=()=>void render(mount,{extended});
      mount.replaceChildren(el('p',null,'Не удалось открыть форму.'),retry);return;
    }
    mount.replaceChildren();
    const form=el('form','clinic-booking');form.noValidate=true;
    if(!extended)form.append(el('h3',null,'Оставить заявку'),
      el('p','clinic-booking__intro','Администратор свяжется с вами и согласует время приёма.'));
    const service=draft.selection?catalog.services.find(s=>s.service_id===draft.selection.service_id):null;
    const row=service?.price?.rows.find(r=>r.offer_id===draft.selection?.offer_id);
    if(service)form.append(el('p','clinic-booking__subject',[service.name,row?.variant_label].filter(Boolean).join(' · ')));
    const field=(key,labelText,type='text')=>{
      const label=el('label','clinic-booking__field',labelText),input=el(type==='textarea'?'textarea':'input');
      if(type!=='textarea')input.type=type;
      input.dataset.bookingField=key;input.name=key;input.value=draft[key];
      input.required=key==='name'||key==='phone';input.maxLength=key==='wish'?500:key==='name'?120:40;
      if(key==='name')input.autocomplete='name';
      if(key==='phone'){input.autocomplete='tel';input.inputMode='tel';input.placeholder='+7 (999) 999-99-99';}
      if(key==='wish')input.placeholder='Например, удобно позвонить после 18:00';
      input.addEventListener('input',()=>{input.setCustomValidity('');sync(key,input.value);});
      label.append(input);form.append(label);return input;
    };
    const name=field('name','Как к вам обращаться');const phone=field('phone','Телефон','tel');
    if(extended){
      const label=el('label','clinic-booking__field','Что вас интересует · необязательно');
      const select=el('select');select.dataset.bookingService='';
      const none=el('option',null,'Помогите определиться');none.value='';select.append(none);
      for(const service of catalog.services){const option=el('option',null,service.name);option.value=service.service_id;select.append(option);}
      select.value=draft.selection?.service_id||'';
      select.onchange=()=>{draft.selection=select.value?{service_id:select.value,offer_id:null,catalog_version:catalog.catalog_version}:null;body=null;renderAll();};
      label.append(select);form.append(label);field('wish','Пожелание · необязательно','textarea');
    }
    const consentLabel=el('label','clinic-booking__consent');const consent=el('input');consent.type='checkbox';
    consent.dataset.bookingField='consent';consent.checked=draft.consent;consent.required=true;
    consent.onchange=()=>{consent.setCustomValidity('');sync('consent',consent.checked);};
    consentLabel.append(consent,el('span',null,definition.checkbox_text));form.append(consentLabel);
    const links=el('p','clinic-booking__links');
    for(const [label,url] of [['Согласие на обработку',definition.consent_url],['Политика обработки данных',definition.policy_url]]){
      if(!url)continue;let parsed;try{parsed=new URL(url);}catch{continue;}
      if(parsed.protocol!=='https:'||parsed.username||parsed.password)continue;
      const link=el('a',null,label);link.href=parsed.href;link.target='_blank';link.rel='noopener noreferrer';links.append(link);
    }
    if(links.children.length)form.append(links);
    const status=el('p','clinic-booking__error',error||(!result?.ok?result?.message||'':''));status.setAttribute('role','status');form.append(status);
    const submit=el('button','clinic-booking__submit',pending?'Отправляем…':body?'Проверить отправку':'Отправить заявку');submit.type='submit';form.append(submit);
    const terminalFailure=result&&!result.ok;
    for(const input of form.querySelectorAll('input,select,textarea'))input.disabled=pending||Boolean(body)||Boolean(terminalFailure);
    submit.disabled=pending||Boolean(terminalFailure);
    form.onsubmit=async event=>{
      event.preventDefault();if(pending||terminalFailure)return;
      if(!body){
        name.setCustomValidity(name.value.trim()?'':'Укажите имя');
        const digits=phone.value.replace(/\D/g,'');
        phone.setCustomValidity(/^(?:7|8)?\d{10}$/.test(digits)?'':'Проверьте номер телефона');
        consent.setCustomValidity(consent.checked?'':'Подтвердите согласие перед отправкой');
        if(!form.reportValidity())return;
      }
      result={ok:true,message:'Спасибо за обращение! Администратор свяжется с вами и поможет согласовать время.'};
      draft.name='';draft.phone='';draft.wish='';draft.consent=false;draft.selection=null;
      renderAll();
    };
    mount.append(form);
  }
  return {render,select(selection){if(!result&&!pending&&!body){draft.selection=selection;renderAll();}},open(selection,mount){if(selection!==undefined&&!result&&!pending&&!body){draft.selection=selection;renderAll();}void render(mount);},
    reset(){if(pending)return;Object.assign(draft,{name:'',phone:'',consent:false,wish:'',selection:null});body=null;result=null;error='';renderAll();},
    get pending(){return pending;}};
}

window.WidgetPlaygroundRenderer.createBookingForm = createBookingForm;
})();
