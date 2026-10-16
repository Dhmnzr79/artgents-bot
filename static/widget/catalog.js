import { renderPriceBody } from './price_card.js';
import { setBotAnswerBody } from './answer_format.js';

const element=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=text;return el;};
const button=(text,action,cls='clinic-catalog__back')=>{const el=element('button',cls,text);el.type='button';el.addEventListener('click',action);return el;};

/** Read-only navigation state belongs to this widget instance, never the dialogue. */
export function mountCatalog(root,{apiBase,clientId,onApply}){
  const state={data:null,loading:null,section:null,query:'',service:null,offer:null,listScroll:0,directionScroll:0};
  const scroller=()=>root.closest('[data-clinic-catalog-panel]')||root;
  const serviceById=id=>state.data.services.find(s=>s.service_id===id);
  const sectionById=id=>state.data.sections.find(s=>s.section_id===id);
  const choices=service=>(service.price?.rows||[]).map(row=>({offer_id:row.offer_id,label:row.variant_label||row.service_name}));

  function renderDetail(){
    const service=serviceById(state.service),detail=state.offer?service.details[state.offer]:null;
    root.replaceChildren(button('← '+(state.query.trim()?'Результаты поиска':sectionById(state.section)?.title||'Все направления'),()=>{
      state.service=null;state.offer=null;renderList();scroller().scrollTop=state.listScroll;
    }));
    root.append(element('p','clinic-catalog__eyebrow',sectionById(service.section_id).title));
    const description=element('div','clinic-catalog__description');setBotAnswerBody(description,service.description);
    const price=detail?.price||service.price;
    if(price){
      const cardRoot=element('div');
      renderPriceBody(cardRoot,{revision:state.data.catalog_version,bodyParts:[{kind:'price_card',price,choices:choices(service)},...(detail?.parts||((price.presentation==='detail'?service.details[price.rows[0].offer_id]?.parts:[])||[]))]},
        {clientId,isDisabled:()=>false,getLatestRevision:()=>state.data.catalog_version,
          offerIdForChoice:choice=>choice.offer_id,onSelect:choice=>{
            const scroll=scroller().scrollTop;state.offer=choice.offer_id;renderDetail();scroller().scrollTop=scroll;
          }});
      root.append(cardRoot);
    }else{
      root.append(element('h2','clinic-catalog__title',service.name),element('p','clinic-catalog__unpriced',state.data.unpriced_text));
    }
    const information=element('details','clinic-price-card__detail');
    information.append(element('summary',null,'Об услуге'),description);root.append(information);
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
    const title=element('h2','clinic-catalog__title');
    const input=element('input','clinic-catalog__search');input.type='search';input.placeholder='Найти услугу или направление…';
    input.setAttribute('aria-label','Поиск по всему каталогу');input.value=state.query;
    const list=element('div','clinic-catalog__list');
    const renderRows=()=>{
      list.replaceChildren();const query=state.query.trim().toLocaleLowerCase('ru');
      title.textContent=query?'Результаты поиска':sectionById(state.section)?.title||'Услуги и цены';
      if(!query&&!state.section){
        for(const section of state.data.sections){
          const row=button('',()=>{state.directionScroll=scroller().scrollTop;state.section=section.section_id;renderList();scroller().scrollTop=0;},'clinic-catalog__row');
          row.append(element('strong',null,section.title),element('span','clinic-catalog__arrow','→'),element('small',null,`Услуг: ${section.service_ids.length}`));list.append(row);
        }return;
      }
      const found=state.data.services.filter(service=>{
        const section=sectionById(service.section_id);
        return query?[service.name,...service.aliases,section.title,...(service.price?.rows||[]).map(r=>r.variant_label||'')].join(' ').toLocaleLowerCase('ru').includes(query):service.section_id===state.section;
      });
      if(!found.length)list.append(element('p','clinic-catalog__empty','Ничего не найдено. Попробуйте другое название.'));
      for(const service of found){
        const row=button('',()=>{state.listScroll=scroller().scrollTop;state.service=service.service_id;state.offer=null;renderDetail();scroller().scrollTop=0;},'clinic-catalog__row');
        const first=service.price?.rows[0];
        row.append(element('strong',null,service.name),element('span','clinic-catalog__row-price',first?.price_display_text||state.data.unpriced_text));
        row.append(element('small',null,[query?sectionById(service.section_id).title:null,first?.variant_label,
          service.price?.rows.length>1?`Вариантов: ${service.price.rows.length}`:null].filter(Boolean).join(' · ')));
        list.append(row);
      }
    };
    input.addEventListener('input',()=>{state.query=input.value;renderRows();});
    root.append(title,input,list);renderRows();
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
  return {load,async getData(){await load();if(!state.data)throw new Error("catalog_unavailable");return state.data;},reset(){state.data=null;state.loading=null;state.section=null;state.query='';state.service=null;state.offer=null;root.replaceChildren();}};
}
