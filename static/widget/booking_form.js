import { visitorIdForClient } from './api.js';

const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!=null)node.textContent=text;return node;};

/** One ephemeral draft, handler and delivery result for every form location. */
export function createBookingForm({apiBase,clientId,getSid,getCatalog}){
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
  async function load(){
    if(loading)return loading;
    loading=(async()=>{const response=await fetch(`${base}/api/booking-form?client_id=${encodeURIComponent(clientId)}`);
      if(!response.ok)throw new Error('booking_config');const data=await response.json();
      if(data.client_id!==clientId)throw new Error('booking_owner');definition=data;await getCatalog();})();
    try{await loading;}catch(e){loading=null;throw e;}
  }
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
        body={client_id:clientId,sid:getSid(),request_id:crypto.randomUUID(),visitor_id:visitorIdForClient(clientId),
          name:draft.name.trim(),phone:draft.phone,wish:draft.wish,selection:draft.selection,
          consent:{accepted:draft.consent,definition_fingerprint:definition.definition_fingerprint}};
      }
      pending=true;error='';renderAll();
      try{
        const response=await fetch(`${base}/lead`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const data=await response.json();
        if(response.ok){result=data;if(data.ok){draft.name='';draft.phone='';draft.wish='';draft.consent=false;draft.selection=null;body=null;}}
        else if(response.status===400||response.status===429){
          const messages={lead_consent_required:'Подтвердите согласие перед отправкой.',lead_consent_changed:'Условия согласия обновились. Откройте форму ещё раз.',
            catalog_changed:'Предложение обновилось. Обновите страницу и выберите услугу заново.',bad_phone:'Проверьте номер телефона.',visitor_lead_limit:'Лимит заявок исчерпан. Свяжитесь с клиникой напрямую.'};
          error=messages[data.error_code]||'Проверьте заполненные поля.';body=null;
          if(data.error_code==='lead_consent_changed'){definition=null;loading=null;draft.consent=false;}
        }else error='Подтверждение пока не получено. Можно проверить отправку тем же запросом.';
      }catch{error='Не удалось получить подтверждение. Проверьте отправку тем же запросом.';}
      finally{pending=false;renderAll();}
    };
    mount.append(form);
  }
  return {render,select(selection){if(!result&&!pending&&!body){draft.selection=selection;renderAll();}},open(selection,mount){if(selection!==undefined&&!result&&!pending&&!body){draft.selection=selection;renderAll();}void render(mount);},
    reset(){if(pending)return;Object.assign(draft,{name:'',phone:'',consent:false,wish:'',selection:null});body=null;result=null;error='';renderAll();},
    get pending(){return pending;}};
}
