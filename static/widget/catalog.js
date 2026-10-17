import { renderPriceBody } from './price_card.js';

const element=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=text;return el;};
const button=(text,action,cls='clinic-catalog__back')=>{const el=element('button',cls,text);el.type='button';
  if(cls==='clinic-catalog__back'&&text.startsWith('← ')){el.setAttribute('aria-label',text);el.textContent=text.slice(2);el.classList.add('clinic-catalog__back--chevron');}
  el.addEventListener('click',action);return el;};
const arrow=()=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class','clinic-catalog__arrow');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');
  svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.4');svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d','M4 12h16m-6-6 6 6-6 6');svg.append(path);return svg;};

/** Read-only navigation state belongs to this widget instance, never the dialogue. */
export function mountCatalog(root,{apiBase,clientId,onApply}){
  const state={data:null,loading:null,section:null,query:'',service:null,offer:null,offerQuery:'',offerScroll:0,listScroll:0,directionScroll:0};
  const scroller=()=>root.closest('[data-clinic-catalog-panel]')||root;
  const serviceById=id=>state.data.services.find(s=>s.service_id===id);
  const sectionById=id=>state.data.sections.find(s=>s.section_id===id);
  const choices=service=>(service.price?.rows||[]).map(row=>({offer_id:row.offer_id,label:row.variant_label||row.service_name}));

  function renderDetail(){
    const service=serviceById(state.service),detail=state.offer?service.details[state.offer]:null;
    const position=Boolean(detail&&service.price.rows.length>1);
    root.replaceChildren(button('← '+(position?service.name:state.query.trim()?'Результаты поиска':sectionById(state.section)?.title||'Все услуги'),()=>{
      if(position){state.offer=null;renderDetail();scroller().scrollTop=state.offerScroll;return;}
      state.service=null;state.offer=null;renderList();scroller().scrollTop=state.listScroll;
    }));
    const price=detail?.price||service.price;
    root.append(element('h2','clinic-catalog__title',position?(price.rows[0].variant_label||service.name):service.name));
    if(!position)root.append(element('p','clinic-catalog__subtitle',service.subtitle));
    if(price){
      const cardRoot=element('div');
      const renderPositions=()=>{
        cardRoot.replaceChildren();
        const query=state.offerQuery.trim().toLocaleLowerCase('ru');
        const rows=price.presentation==='options'?price.rows.filter(row=>[row.variant_label,row.service_name,row.scope_text,...service.offer_groups.filter(group=>group.offer_ids.includes(row.offer_id)).map(group=>group.title)].filter(Boolean).join(' ').toLocaleLowerCase('ru').includes(query)):price.rows;
        if(!rows.length){cardRoot.append(element('p','clinic-catalog__empty','Нет подходящих ценовых позиций'));return;}
        const groups=service.offer_groups.length?service.offer_groups.map(group=>({...group,offer_ids:group.offer_ids.filter(id=>rows.some(row=>row.offer_id===id))})).filter(group=>group.offer_ids.length):null;
        renderPriceBody(cardRoot,{revision:state.data.catalog_version,bodyParts:[{kind:'price_card',price:{...price,rows},choices:price.presentation==='options'?choices(service):[]},...(detail?.parts||((price.presentation==='detail'?service.details[price.rows[0].offer_id]?.parts:[])||[]))]},
        {clientId,rowGroups:groups,showTitle:false,catalog:true,isDisabled:()=>false,getLatestRevision:()=>state.data.catalog_version,
          offerIdForChoice:choice=>choice.offer_id,onSelect:choice=>{
            state.offerScroll=scroller().scrollTop;
            state.offer=choice.offer_id;renderDetail();scroller().scrollTop=0;
          }});
      };
      if(price.presentation==='options'&&price.rows.length>6){
        const search=element('input','clinic-catalog__search');search.type='search';search.placeholder='Найти зону или вариант…';search.setAttribute('aria-label','Поиск по прайсу');search.value=state.offerQuery;
        search.addEventListener('input',()=>{state.offerQuery=search.value;renderPositions();});root.append(search);
      }
      renderPositions();root.append(cardRoot);
    }else{
      root.append(element('p','clinic-catalog__unpriced',state.data.unpriced_text));
    }
    const apply=button('Оставить заявку',()=>{
      const offer=state.offer||(service.price?.presentation==='detail'?service.price.rows[0].offer_id:null);
      onApply({service_id:service.service_id,offer_id:offer,catalog_version:state.data.catalog_version},formMount);
    },'clinic-catalog__apply');
    const formMount=element('div','clinic-booking-mount');formMount.dataset.catalogForm='';
    root.append(apply,formMount);
  }

  function renderList(){
    root.replaceChildren();
    if(state.section)root.append(button('← Все направления',()=>{
      state.section=null;state.query='';renderList();scroller().scrollTop=state.directionScroll;
    }));
    const heading=element('div','clinic-catalog__heading');
    const title=element('h2','clinic-catalog__title');
    heading.append(title);
    const input=element('input','clinic-catalog__search');input.type='search';input.placeholder='Найти услугу или направление…';
    input.setAttribute('aria-label','Поиск по всему каталогу');input.value=state.query;
    const list=element('div','clinic-catalog__list');
    const renderRows=()=>{
      list.replaceChildren();const query=state.query.trim().toLocaleLowerCase('ru');
      list.classList.toggle('clinic-catalog__list--services',Boolean(query||state.section||!state.data.show_sections));
      title.textContent=query?'Результаты поиска':sectionById(state.section)?.title||'Услуги и цены';
      if(!query&&!state.section&&state.data.show_sections){
        for(const section of state.data.sections){
          const row=button('',()=>{state.directionScroll=scroller().scrollTop;state.section=section.section_id;renderList();scroller().scrollTop=0;},'clinic-catalog__row');
          const copy=element('span','clinic-catalog__direction-copy');
          copy.append(element('strong',null,section.title),element('small',null,section.subtitle));
          row.append(copy,arrow());list.append(row);
        }return;
      }
      const found=state.data.services.filter(service=>{
        const section=sectionById(service.section_id);
        return query?[service.name,service.subtitle,...service.aliases,section.title,...(service.price?.rows||[]).map(r=>r.variant_label||'')].join(' ').toLocaleLowerCase('ru').includes(query):!state.section||service.section_id===state.section;
      });
      if(!found.length)list.append(element('p','clinic-catalog__empty','Ничего не найдено. Попробуйте другое название.'));
      for(const service of found){
        const row=button('',()=>{state.listScroll=scroller().scrollTop;state.service=service.service_id;state.offer=null;state.offerQuery='';state.offerScroll=0;renderDetail();scroller().scrollTop=0;},'clinic-catalog__row clinic-catalog__service');
        row.append(element('strong',null,service.name));
        if(service.price_summary_text)row.append(element('span','clinic-catalog__row-price',service.price_summary_text));
        row.append(element('small',null,service.subtitle));
        row.append(arrow());
        list.append(row);
      }
    };
    input.addEventListener('input',()=>{state.query=input.value;renderRows();});
    root.append(heading,input,list);renderRows();
  }

  async function load(){
    if(state.data)return;
    if(state.loading)return state.loading;
    root.replaceChildren(element('p',null,'Загружаем услуги…'));
    state.loading=(async()=>{
      try{
        const response=await fetch(`${apiBase.replace(/\/$/,'')}/api/widget-catalog?client_id=${encodeURIComponent(clientId)}`);
        if(!response.ok)throw new Error('catalog_load_failed');
        const data=await response.json();
        if(data.client_id!==clientId||!Array.isArray(data.services)||!Array.isArray(data.sections))throw new Error('catalog_owner_invalid');
        state.data=data;renderList();
      }catch{
        root.replaceChildren(element('p',null,'Не удалось загрузить услуги.'),button('Попробовать ещё раз',()=>{state.loading=null;void load();}));
      }
    })();
    return state.loading;
  }
  return {load,async getData(){await load();if(!state.data)throw new Error("catalog_unavailable");return state.data;},reset(){state.data=null;state.loading=null;state.section=null;state.query='';state.service=null;state.offer=null;state.offerQuery='';state.offerScroll=0;root.replaceChildren();}};
}
