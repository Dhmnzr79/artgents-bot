/* Read-only D2 view. No browser persistence, receipt HTML, or executable bot actions. */
const $ = id => document.getElementById(id);
const state = {client:null,generation:0,controller:null,threadController:null,session:null,threadGeneration:0,cursors:{}};
const labels = {pending:'Ожидает результата',sent:'Отправлено',failed:'Не отправлено',unknown:'Нет подтверждения',demo_stub:'Демо · без отправки',completed:'Завершён',replayed:'Повторный просмотр результата',returned:'Ответ провайдера',provider:'Вызов модели',request:'Обращение'};
function node(tag,text,className=''){const n=document.createElement(tag);n.textContent=text??'';if(className)n.className=className;return n;}
function date(value){if(!value)return '—';const d=new Date(value);return Number.isNaN(d.getTime())?'—':d.toLocaleString('ru-RU');}
function number(value){return value==null?'Нет данных':Number(value).toLocaleString('ru-RU',{maximumFractionDigits:10});}
function empty(target,text){$(target).replaceChildren(node('p',text,'muted'));}
async function get(path,params={},signal=state.controller?.signal){
  const generation=state.generation,client=state.client;
  const query=new URLSearchParams({client_id:client,period:$('period').value,...params});
  const response=await fetch(`${path}?${query}`,{cache:'no-store',signal});
  if(!response.ok)throw new Error(response.status===503?'Хранилище диалогов недоступно или содержит несовместимые записи.':response.status===404?'Данные не найдены.':`Ошибка доступа (${response.status}).`);
  const data=await response.json();
  if(generation!==state.generation||client!==state.client)throw new DOMException('Устаревший ответ','AbortError');
  return data;
}
function table(target,headings,rows,append=false){
  if(append&&$(target).querySelector('tbody')){const body=$(target).querySelector('tbody');for(const row of rows)body.appendChild(row);return;}
  const wrap=node('div','','table-scroll'),t=node('table','','simple-table');
  const head=document.createElement('thead'),tr=document.createElement('tr');for(const h of headings)tr.appendChild(node('th',h));head.appendChild(tr);
  const body=document.createElement('tbody');for(const row of rows)body.appendChild(row);t.append(head,body);wrap.appendChild(t);$(target).replaceChildren(wrap);
}
function row(values){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.appendChild(value instanceof Node?value:node('span',value));tr.appendChild(td);}return tr;}
function cursor(key,next,button){state.cursors[key]=next;$(button).hidden=next==null;}
function clearThread(){state.threadController?.abort();state.threadGeneration++;state.session=null;$('dialogThreadViewer').hidden=true;$('dialogThreadBody').replaceChildren();$('moreTurns').hidden=true;}
function renderOverview(data){
  const fields=[['Сессии',data.sessions],['Сохранённые ходы',data.saved_turns],['Заявки',data.forms],['Отправлено',data.sent],['Демо-заявки',data.demo_stub],['Не отправлено',data.failed],['Без подтверждения',data.unknown],['Ожидают',data.pending]];
  if(data.metrics_available)fields.push(['Обращения за период',data.observed_requests],['Ошибки за период',data.observed_failures]);
  $('overview').replaceChildren(...fields.map(([label,value])=>{const n=node('div','','kpi');n.append(node('span',label,'kpi-label'),node('span',number(value),'kpi-value'));return n;}));
}
async function loadCosts(){
  const d=await get('/api/costs');
  if(!d.available){empty('costs','Метрик пока нет. Они появятся после новых обращений к боту.');return;}
  if(!d.items.length){empty('costs','За выбранный период вызовов модели не записано.');return;}
  table('costs',['Модель','Вызовы','Вход, всего','Из кэша','Без кэша','Выход','Оценка, $'],d.items.map(x=>row([x.model||'Не указана',number(x.calls),number(x.prompt_tokens),number(x.cached_prompt_tokens),number(x.uncached_prompt_tokens),number(x.completion_tokens),number(x.estimated_usd)])));
  $('costs').appendChild(node('p',`Оценка по сохранённым тарифам: ${number(d.estimated_usd)} $. Новых вызовов без расчёта: ${d.unpriced_calls}. Без разбивки кэша: ${d.unsplit_calls}.`,'muted'));
  $('costs').appendChild(node('p','Объёмы — суммы известных токенов из ответа провайдера. Для direct DeepSeek учтён UTC-график пик/непик; исключения китайских праздников не автоматизированы. Это оценка, не выписка со счёта.','muted'));
  if(d.legacy_calls)$('costs').appendChild(node('p',`Прежних вызовов: ${d.legacy_calls}. Их старая оценка ${number(d.legacy_estimated_usd)} $ показана отдельно и не включена в новую сумму.`,'muted'));
}
async function loadFunnel(){
  const d=await get('/api/funnel');
  if(!d.available||!d.items.length){empty('funnel','Событий за период пока нет. Учёт начнётся с новых открытий обновлённого виджета.');return;}
  const keys=['opened','question','form','submit','accepted','sent','demo_stub','unknown','failed','pending'];
  table('funnel',['Сайт / страница','Открыли','Вопрос','Форма','Отправка формы','Принято','Отправлено','Демо','Без подтверждения','Не отправлено','Ожидают'],
    [row(['Всего по клинике',...keys.map(k=>number(d.totals[k]))]),...d.items.map(x=>row([`${x.domain}${x.path==='(other)'?' / Другие страницы':x.path}`,...keys.map(k=>number(x[k]))]))]);
  $('funnel').appendChild(node('p','Сохраняем только домен и известные пути из настроек виджета. Остальные адреса — «Другие страницы». URL-параметры, UTM, тексты и контакты не собираются. Срок хранения событий — 30 дней. Учёт приблизительный: блокировщик или обрыв сети может пропустить действие.','muted'));
  if(d.truncated)$('funnel').appendChild(node('p','Достигнут лимит 50 000 событий для одного отчёта; показаны неполные данные. Выберите меньший период.','muted'));
}
async function loadDialogs(append=false){
  const d=await get('/api/dialogs',append?{cursor:state.cursors.dialogs}:{});
  const rows=d.items.map(x=>{const b=node('button',`Открыть ${x.session_id.slice(0,8)}`,'dialog-toggle');b.type='button';b.addEventListener('click',()=>void showThread(x.session_id));return row([b,date(x.last_activity),number(x.revision)]);});
  if(!rows.length&&!append)empty('dialogs','Сохранённых диалогов пока нет.');else table('dialogs',['Сессия','Последняя активность','Ревизия'],rows,append);
  cursor('dialogs',d.next_cursor,'moreDialogs');
}
async function showThread(session,older=false){
  if(!older){clearThread();state.session=session;$('dialogThreadViewer').hidden=false;$('dialogViewerTitle').textContent=`Диалог ${session.slice(0,8)}`;}
  state.threadController?.abort();state.threadController=new AbortController();const generation=++state.threadGeneration,client=state.client;
  try{
    const d=await get(`/api/dialogs/${session}/thread`,older?{cursor:state.cursors.turns}:{},state.threadController.signal);
    if(generation!==state.threadGeneration||client!==state.client||session!==state.session)return;
    const fragment=document.createDocumentFragment();
    for(const turn of d.items){const box=node('section','','admin-turn');box.append(node('p',`Ревизия ${turn.revision}`,'muted'),node('div',turn.patient_text||(turn.selected_action?'Выбор в виджете':'Сообщение скрыто'),'admin-turn__user'),node('div',turn.answer,'admin-turn__answer'));fragment.appendChild(box);}
    if(older)$('dialogThreadBody').prepend(fragment);else $('dialogThreadBody').replaceChildren(fragment);
    if(!d.items.length&&!older)$('dialogThreadBody').appendChild(node('p','В этой сессии нет публичных сообщений.','muted'));
    cursor('turns',d.next_cursor,'moreTurns');
  }catch(e){if(e.name!=='AbortError'&&generation===state.threadGeneration)empty('dialogThreadBody',e.message);}
}
async function loadLeads(append=false){
  const d=await get('/api/leads',append?{cursor:state.cursors.leads}:{});
  const rows=d.items.map(x=>row([date(x.accepted_at),labels[x.status]||'Неизвестный статус',x.service_id||'Уточнить услугу',x.offer_id||'—',x.request_key.slice(0,8)]));
  if(!rows.length&&!append)empty('leads','Заявок пока нет.');else table('leads',['Время','Результат','Услуга','Вариант','Заявка'],rows,append);
  cursor('leads',d.next_cursor,'moreLeads');
}
async function loadObservations(key,append=false){
  const d=await get(`/api/${key}`,append?{cursor:state.cursors[key]}:{});
  const rows=d.items.map(x=>row([date(x.observed_at),labels[x.kind]||x.kind,x.outcome==='failed'?'Ошибка':(labels[x.outcome]||x.outcome),x.model||'—',number(x.cached_prompt_tokens),number(x.uncached_prompt_tokens),number(x.completion_tokens),number(x.estimated_usd),x.pricing_basis||'—',number(x.duration_ms),x.request_hash.slice(0,8)]));
  if(!rows.length&&!append)empty(key,d.available?'За выбранный период записей нет.':'Учёт новых обращений ещё не начат.');else table(key,['Время','Тип','Результат','Модель','Кэш','Без кэша','Выход','Оценка, $','Тариф','мс','Запрос'],rows,append);
  cursor(key,d.next_cursor,key==='events'?'moreEvents':'moreProblems');
}
async function refresh(){
  state.controller?.abort();state.controller=new AbortController();clearThread();state.cursors={};
  for(const id of ['moreDialogs','moreLeads','moreProblems','moreEvents'])$(id).hidden=true;
  const generation=++state.generation;
  for(const target of ['overview','costs','funnel','dialogs','leads','problems','events'])empty(target,'Загрузка…');
  const jobs=[['overview',()=>get('/api/overview').then(renderOverview)],['costs',loadCosts],['funnel',loadFunnel],['dialogs',loadDialogs],['leads',loadLeads],['problems',()=>loadObservations('problems')]];
  if($('eventExplorer').open)jobs.push(['events',()=>loadObservations('events')]);else empty('events','Откройте раздел для загрузки метрик.');
  await Promise.all(jobs.map(async([target,fn])=>{try{await fn();}catch(e){if(e.name!=='AbortError'&&generation===state.generation)empty(target,e.message);}}));
}
function more(id,fn){$(id).addEventListener('click',async()=>{$(id).disabled=true;try{await fn();}catch(e){if(e.name!=='AbortError')$('statusBar').textContent=e.message;}finally{$(id).disabled=false;}});}
async function init(){
  try{
    const response=await fetch('/api/clients',{cache:'no-store'});if(!response.ok)throw new Error('Админка недоступна: проверьте авторизацию и адрес запуска.');
    const data=await response.json();for(const client of data.items){const option=node('option',client.label);option.value=client.client_id;$('clientId').appendChild(option);}
    if(!data.items.length)throw new Error('Нет разрешённых клиентов. Проверьте список клиентов и admin.enabled.');
    const requested=new URL(location.href).searchParams.get('client_id');
    if(requested&&!data.items.some(c=>c.client_id===requested))throw new Error('Этот клиент не разрешён в админке.');
    state.client=requested||data.items[0].client_id;$('clientId').value=state.client;
    const health=await fetch('/api/health',{cache:'no-store'});if(!health.ok)throw new Error('Хранилище диалогов недоступно.');
    $('statusBar').textContent='Только просмотр · данные не сохраняются в браузере';
    $('clientId').addEventListener('change',()=>{state.client=$('clientId').value;const url=new URL(location.href);url.searchParams.set('client_id',state.client);history.replaceState(null,'',url);void refresh();});
    $('refreshBtn').addEventListener('click',()=>void refresh());$('period').addEventListener('change',()=>void refresh());$('dialogViewerClose').addEventListener('click',clearThread);
    more('moreDialogs',()=>loadDialogs(true));more('moreLeads',()=>loadLeads(true));more('moreProblems',()=>loadObservations('problems',true));more('moreEvents',()=>loadObservations('events',true));more('moreTurns',()=>showThread(state.session,true));
    $('eventExplorer').addEventListener('toggle',()=>{if($('eventExplorer').open)void loadObservations('events').catch(e=>{if(e.name!=='AbortError')empty('events',e.message);});});
    await refresh();
  }catch(e){$('statusBar').textContent=e.message;}
}
window.addEventListener('pagehide',()=>{state.controller?.abort();clearThread();for(const id of ['overview','costs','funnel','dialogs','leads','events','problems'])$(id).replaceChildren();});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
void init();
