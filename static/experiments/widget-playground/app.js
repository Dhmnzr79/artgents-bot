(() => {
  'use strict';
  const $=selector=>document.querySelector(selector);
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const paths={arrow:'M4 12h16M14 6l6 6-6 6',layers:'m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',info:'M12 11v6M12 7v1',gift:'M3 9h18v4H3ZM5 13v8h14v-8M12 9v12M12 9C5 9 5 3 8 3c3 0 4 6 4 6s1-6 4-6c3 0 3 6-4 6Z',clock:'M12 7v5l4 2',chevron:'m9 5 7 7-7 7',extent:'m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3ZM4 7.5l8 4.5 8-4.5M12 12v9'};
  const icon=(name,cls='')=>`<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${['info','clock'].includes(name)?'<circle cx="12" cy="12" r="9"/>':''}<path d="${paths[name]}"/></svg>`;
  const primary=label=>`<button type="button" class="primary" data-apply>${label}${icon('arrow')}</button>`;
  const {directions,services}=window.WidgetPlaygroundData;
  const byId=id=>services.find(service=>service.id===id);
  const offerPrice=offer=>offer.price_text;
  const summaryPrice=service=>service.summary_text;
  const rowMarkup=(name,subtitle,price,attrs)=>`<button class="service-row" ${attrs}><strong>${esc(name)}</strong>${price?`<span class="row-price">${esc(price)}</span>`:''}<small>${esc(subtitle)}</small>${icon('arrow')}</button>`;
  function priceMarkup(offer,context='catalog'){
    const mount=document.createElement('div');
    window.WidgetPlaygroundRenderer.renderPriceBody(mount,
      {revision:'prototype',bodyParts:[{kind:'price_card',price:offer.detail.price,choices:[]},...offer.detail.parts]},
      {clientId:offer.client_id,showTitle:context==='chat',catalog:context!=='chat',
       isDisabled:()=>false,onSelect:()=>{},getLatestRevision:()=> 'prototype'});
    return mount.innerHTML;
  }
  const navigation={direction:null,service:null,offer:null,query:'',offerQuery:''};
  const booking=window.WidgetPlaygroundRenderer.createBookingForm({apiBase:'',clientId:'demo',
    getSid:()=> 'standalone',getCatalog:async()=>({catalog_version:'prototype',services:services.map(service=>({
      service_id:service.id,name:service.name,price:{rows:service.offers.map(offer=>({offer_id:offer.id,variant_label:service.offers.length>1?offer.name:''}))}
    }))})});
  function switchTab(name){
    document.querySelectorAll('[data-tab]').forEach(button=>{const active=button.dataset.tab===name;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;});
    document.querySelectorAll('[role=tabpanel]').forEach(panel=>panel.hidden=panel.id!=='panel-'+name);
    if(name==='booking')renderForms();
  }
  document.querySelectorAll('[data-tab]').forEach(button=>{
    button.onclick=()=>switchTab(button.dataset.tab);
    button.onkeydown=event=>{const buttons=[...document.querySelectorAll('[data-tab]')],index=buttons.indexOf(button);let next;if(event.key==='ArrowRight')next=(index+1)%3;if(event.key==='ArrowLeft')next=(index+2)%3;if(event.key==='Home')next=0;if(event.key==='End')next=2;if(next!==undefined){event.preventDefault();buttons[next].click();buttons[next].focus();}};
  });
  function openService(id,offer=null){navigation.service=id;navigation.offer=offer;navigation.offerQuery='';renderCatalog();$('#panel-catalog').scrollTop=0;}
  function applySelection(service,offer,mount){
    mount.classList.add('form-mount','clinic-booking-mount');
    booking.open({service_id:service.id,offer_id:offer?.id||null,catalog_version:'prototype'},mount);
    mount.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function renderCatalog(){
    const root=$('#catalog'),service=byId(navigation.service);
    if(service){
      const offer=navigation.offer?service.offers.find(item=>item.id===navigation.offer):(service.offers.length===1?service.offers[0]:null);
      const selectedVariant=offer&&service.offers.length>1;
      root.innerHTML=`<button class="back" data-back>← ${esc(selectedVariant?service.name:directions.find(item=>item.id===service.direction).name)}</button><h2>${esc(selectedVariant?offer.name:service.name)}</h2>${!selectedVariant?`<p class="subtitle">${esc(service.subtitle)}</p>`:''}${offer?priceMarkup(offer):`${service.offers.length>6?'<input type="search" class="search" aria-label="Поиск по прайсу" placeholder="Найти зону или вариант…">':''}<div id="positions"></div>`}${primary('Оставить заявку')}<div id="inline-form"></div>`;
      root.querySelector('[data-back]').onclick=()=>{if(selectedVariant){navigation.offer=null;}else{navigation.service=null;navigation.direction=service.direction;}renderCatalog();};
      root.querySelector('[data-apply]').onclick=()=>applySelection(service,offer,$('#inline-form'));
      if(!offer){
        const renderPositions=()=>{let group='';const query=navigation.offerQuery.toLocaleLowerCase('ru');$('#positions').innerHTML=service.offers.filter(item=>[item.name,item.subtitle,item.group].join(' ').toLocaleLowerCase('ru').includes(query)).map(item=>{const heading=item.group&&item.group!==group?`<h3 class="group-title">${esc(item.group)}</h3>`:'';group=item.group;return heading+rowMarkup(item.name,item.subtitle||item.scope||'',offerPrice(item),`data-offer="${item.id}"`);}).join('')||'<p class="empty">Ничего не найдено</p>';root.querySelectorAll('[data-offer]').forEach(button=>button.onclick=()=>{navigation.offer=button.dataset.offer;renderCatalog();$('#panel-catalog').scrollTop=0;});};
        const search=root.querySelector('.search');if(search){search.value=navigation.offerQuery;search.oninput=()=>{navigation.offerQuery=search.value;renderPositions();};}renderPositions();
      }
      return;
    }
    const direction=directions.find(item=>item.id===navigation.direction);
    root.innerHTML=`${direction?'<button class="back" data-root>← Все направления</button>':''}<h2>${esc(direction?.name||'Услуги и цены')}</h2><input type="search" class="search" aria-label="Поиск по каталогу" placeholder="Найти услугу или направление…" value="${esc(navigation.query)}"><div id="catalog-list"></div>`;
    root.querySelector('[data-root]')?.addEventListener('click',()=>{Object.assign(navigation,{direction:null,query:''});renderCatalog();});
    const list=$('#catalog-list');
    const renderRows=()=>{const query=navigation.query.trim().toLocaleLowerCase('ru');if(!direction&&!query){list.className='directions';list.innerHTML=directions.map(item=>`<button class="direction" data-direction="${item.id}"><span><strong>${esc(item.name)}</strong><small>${esc(item.subtitle)}</small></span>${icon('arrow')}</button>`).join('');list.querySelectorAll('[data-direction]').forEach(button=>button.onclick=()=>{navigation.direction=button.dataset.direction;renderCatalog();$('#panel-catalog').scrollTop=0;});}else{list.className='';list.innerHTML=services.filter(item=>query?[item.name,item.subtitle,...item.offers.map(offer=>offer.name)].join(' ').toLocaleLowerCase('ru').includes(query):item.direction===direction.id).map(item=>rowMarkup(item.name,item.subtitle,summaryPrice(item),`data-service="${item.id}"`)).join('')||'<p class="empty">Ничего не найдено</p>';list.querySelectorAll('[data-service]').forEach(button=>button.onclick=()=>openService(button.dataset.service));}};
    root.querySelector('.search').oninput=event=>{navigation.query=event.target.value;renderRows();};renderRows();
  }
  function renderForms(){document.querySelectorAll('.form-mount').forEach(mount=>void booking.render(mount,{extended:mount.id==='booking-form'}));}
  function appendMessage(html,user=false){const message=document.createElement('div');message.className='message'+(user?' user':'');message.innerHTML=html;$('#feed').append(message);return message;}
  function chatPrice(service){const message=appendMessage(`<p>Вот варианты ${esc(service.name.toLowerCase())}. Выберите подходящую позицию, чтобы посмотреть состав и условия.</p><div class="chat-price">${service.offers.map(offer=>rowMarkup(offer.name,offer.subtitle||offer.scope||'',offerPrice(offer),`data-chat-offer="${offer.id}"`)).join('')}</div>`);message.querySelectorAll('[data-chat-offer]').forEach(button=>button.onclick=()=>{const offer=service.offers.find(item=>item.id===button.dataset.chatOffer);message.innerHTML=`${priceMarkup(offer,'chat')}${primary('Оставить заявку')}<div class="chat-form-slot"></div>`;message.querySelector('[data-apply]').onclick=()=>applySelection(service,offer,message.querySelector('.chat-form-slot'));});}
  function chatActions(message){message.querySelectorAll('[data-chat-action]').forEach(button=>{const label=button.textContent;if(button.dataset.chatAction==='form')button.classList.add('primary');button.innerHTML=`<span>${esc(label)}</span>${icon('arrow')}`;});message.querySelectorAll('[data-chat-action]').forEach(button=>button.onclick=()=>{const action=button.dataset.chatAction;appendMessage(esc(button.textContent),true);if(action==='prices')chatPrice(byId('implant'));if(action==='includes'){const card=appendMessage(priceMarkup(byId('implant').offers[0],'catalog'));const section=card.querySelector('[data-price-section=includes]');if(section)section.open=true;}if(action==='form'){const message=appendMessage('<div class="form-mount clinic-booking-mount"></div>');renderForms();message.scrollIntoView({block:'nearest'});}$('#feed').scrollTop=$('#feed').scrollHeight;});}
  function seedChat(){const feed=$('#feed');feed.replaceChildren();const hello=appendMessage('<p>Здравствуйте! Я Надежда, помощник клиники. Расскажу об услугах, стоимости и подготовке к приёму.</p><p>Что вас интересует?</p><div class="followups"><button data-chat-action="prices">Цены на имплантацию</button><button data-chat-action="includes">Что входит в стоимость</button><button data-chat-action="form">Оставить заявку</button></div>');chatActions(hello);appendMessage('Сколько стоит восстановить один зуб?',true);chatPrice(byId('implant'));feed.scrollTop=0;}
  $('#composer').onsubmit=event=>{event.preventDefault();const input=$('#question'),text=input.value.trim();if(!text)return;appendMessage(esc(text),true);input.value='';input.style.height='';const reply=appendMessage('<p>Помогу разобраться в услугах и стоимости. Можно сравнить предложения, посмотреть состав или оставить контакты администратору.</p><div class="followups"><button data-chat-action="prices">Показать варианты и цены</button><button data-chat-action="includes">Что входит</button><button data-chat-action="form">Оставить заявку</button></div>');chatActions(reply);$('#feed').scrollTop=$('#feed').scrollHeight;};
  $('#question').oninput=event=>{event.target.style.height='auto';event.target.style.height=Math.min(event.target.scrollHeight,120)+'px';};
  $('#question').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('#composer').requestSubmit();}};
  $('#collapse-widget').onclick=()=>{$('.widget').hidden=true;$('#reopen-widget').hidden=false;};$('#reopen-widget').onclick=()=>{$('.widget').hidden=false;$('#reopen-widget').hidden=true;};
  document.querySelectorAll('[data-font]').forEach(button=>button.onclick=()=>{
    document.documentElement.style.setProperty('--clinic-font',`"${button.dataset.font}", sans-serif`);
    document.querySelectorAll('[data-font]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
  });
  renderCatalog();renderForms();seedChat();
})();
