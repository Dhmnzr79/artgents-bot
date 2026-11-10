/* Read-only D2 view. Only theme preference persists; no dialogue persistence, receipt HTML, or executable bot actions. */
const $ = id => document.getElementById(id);
const state = {client:null,generation:0,controller:null,threadController:null,session:null,threadGeneration:0,cursors:{},dialogs:[],listGeneration:0,page:"dialogues",navigation:0};
const labels = {pending:'Ожидает результата',sent:'Отправлено',failed:'Не отправлено',unknown:'Нет подтверждения',demo_stub:'Демо · без отправки',completed:'Завершён',replayed:'Повторный просмотр результата',returned:'Ответ провайдера',provider:'Вызов модели',request:'Обращение'};
function node(tag,text,className=''){const n=document.createElement(tag);n.textContent=text??'';if(className)n.className=className;return n;}
function date(value){if(!value)return '—';const d=new Date(value);return Number.isNaN(d.getTime())?'—':d.toLocaleString('ru-RU');}
function number(value){return value==null?'Нет данных':Number(value).toLocaleString('ru-RU',{maximumFractionDigits:6});}
function empty(target,text){$(target).replaceChildren(node('p',text,'muted'));}
async function get(path,params={},signal=state.controller?.signal){
  const generation=state.generation,client=state.client;
  const query=new URLSearchParams({client_id:client,period:$('period').value,...params});
  const response=await fetch(`${path}?${query}`,{cache:'no-store',signal});
  if(!response.ok)throw new Error(response.status===503?(path==='/api/knowledge'?'Не удалось прочитать конфигурацию базы знаний.':'Хранилище диалогов недоступно или содержит несовместимые записи.'):response.status===404?'Данные не найдены.':`Ошибка доступа (${response.status}).`);
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
function clearThread(){ state.navigation++; $('threadPlaceholder').hidden=false;$('dialogWorkspace').classList.remove('has-selection');state.threadController?.abort();state.threadGeneration++;state.session=null;$('dialogThreadViewer').hidden=true;$('dialogThreadBody').replaceChildren();$('moreTurns').hidden=true;paintSelection();}
function metric(label,value,tone='blue',hint='',symbol='activity'){
  const card=node('div','',`metric metric--${tone}`);
  const top=node('div','','metric-top');top.append(node('span',label,'metric-label'),metricIcon(symbol));
  card.append(top,node('strong',value==null?'—':String(value),'metric-number'),node('span',value==null?'Нет данных за период':hint,'metric-hint'));
  return card;
}
function metricIcon(kind){
  const paths={activity:'M3 12h4l3-8 4 16 3-8h4',error:'M12 8v5m0 3h.01M10.3 3.9 2 18.2A1.2 1.2 0 0 0 3 20h18a1.2 1.2 0 0 0 1-1.8L13.7 3.9a2 2 0 0 0-3.4 0Z',clock:'M12 8v4l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',percent:'m6 18 12-12M9 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',cost:'M12 3v18m5-14H9a3 3 0 0 0 0 6h6a3 3 0 0 1 0 6H6',cache:'M4 7h16M4 12h16M4 17h16M7 4v16m10-16v16',chat:'M21 11a8 8 0 0 1-8 8H6l-4 3V11a9 9 0 0 1 19 0Z',send:'m3 11 18-8-8 18-2-8-8-2Zm8 2L21 3'};
  const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');
  for(const [key,value]of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.6','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',class:'metric-icon'}))icon.setAttribute(key,value);
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',paths[kind]||paths.activity);icon.appendChild(path);return icon;
}
function renderOverview(data){
  const requests=data.metrics_available?data.observed_requests:null,errors=data.metrics_available?data.observed_failures:null;
  $('periodOverview').replaceChildren(
    metric('Обращения',requests==null?null:number(requests),'blue','Вопросы и действия виджета'),
    metric('Неудавшиеся обращения',errors==null?null:number(errors),errors?'red':'teal',errors?'Требуют внимания':'Сбоев за период не записано','error'),
    metric('Среднее время',data.average_request_ms==null?null:`${Number(data.average_request_ms/1000).toLocaleString('ru-RU',{maximumFractionDigits:2})} с`,'violet','Выполненное обращение целиком','clock'),
    metric('Доля ошибок',requests?`${Number(errors/requests*100).toLocaleString('ru-RU',{maximumFractionDigits:2})} %`:null,errors?'red':'teal','От всех записанных обращений','percent'));
  const fields=[['Диалоги',data.sessions,'blue','chat'],['Вопросы и действия',data.saved_turns,'blue','activity'],['Заявки',data.forms,'violet','send'],['Отправлено',data.sent,'teal','send'],['Демо-заявки',data.demo_stub,'muted','chat'],['Не отправлено',data.failed,data.failed?'red':'muted','error'],['Без подтверждения',data.unknown,data.unknown?'amber':'muted','clock'],['Ожидают',data.pending,data.pending?'amber':'muted','clock']];
  $('overview').replaceChildren(...fields.map(([label,value,tone,icon])=>metric(label,number(value),tone,'За всё время',icon)));
}
async function loadKnowledge(){
  const d=await get('/api/knowledge');
  const cards=node('div','','cost-summary');
  cards.append(metric('Документы',number(d.documents),'blue',`${number(Math.round(d.md_bytes/1024*10)/10)} КиБ · MD-файлы`,'chat'),metric('Услуги',number(d.services),'violet',`${number(d.active_services)} активных`,'activity'),metric('Ценовые предложения',number(d.offers),'teal',`${number(d.active_offers)} активных`,'cost'),metric('Контекст ≈ токены',`${number(d.estimated_tokens_low)}–${number(d.estimated_tokens_high)}`,'amber','Грубая оценка, не расход API','activity'));
  $('knowledge').replaceChildren(cards);
  const detail=node('details'),summary=node('summary','Из чего складывается объём');
  const wrap=node('div','','table-scroll'),breakdown=node('table','','simple-table knowledge-table');
  const head=node('thead'),header=node('tr');
  header.append(node('th','Состав'),node('th','Объём'),node('th','Единица'));head.append(header);
  const body=node('tbody');
  body.append(
    row(['MD-корпус с шапками и границами',number(d.corpus_chars),'символов']),
    row(['Инструкции, справочники и остальные части system',number(d.other_system_chars),'символов']),
    row(['Схема ценового инструмента',number(d.tool_chars),'символов']),
    row(['Итого контекст модели',number(d.total_chars),'символов']),
    row(['Исходные MD-файлы (справочно)',number(d.md_chars),'символов']),
    row(['Пакет знаний и настроек (справочно)',number(Math.round(d.pack_bytes/1024*10)/10),'КиБ'])
  );
  breakdown.append(head,body);wrap.append(breakdown);
  detail.append(summary,wrap,node('p','Пакет знаний и настроек — без диалогов, изображений и видео. Справочные строки не прибавляются к итогу контекста.','muted'));
  $('knowledge').append(detail,node('p','Объём для обычного первого запроса: system + схема инструмента. Без истории, вопроса, служебной обёртки API и результата ценового поиска. На других этапах состав контекста отличается. Оценка токенов: 2–4 символа на токен, не точный токенизатор; фактическое значение может выходить за этот диапазон. Кэш влияет на оплату, а не на размер контекста. Пересчёт при обновлении панели, без вызова модели.','muted'));
}
async function loadCosts(){
  const d=await get('/api/costs');
  if(!d.available){empty('costs','Метрик пока нет. Они появятся после новых обращений к боту.');return;}
  table('costs',['Модель','Вызовы','Вход, всего','Из кэша','Без кэша','Выход','Оценка, $'],d.items.map(x=>row([x.model||'Не указана',number(x.calls),number(x.prompt_tokens),number(x.cached_prompt_tokens),number(x.uncached_prompt_tokens),number(x.completion_tokens),number(x.estimated_usd)])));
  const split=d.items.filter(x=>x.cached_prompt_tokens!=null&&x.uncached_prompt_tokens!=null);
  const cached=split.reduce((n,x)=>n+x.cached_prompt_tokens,0),input=split.reduce((n,x)=>n+x.cached_prompt_tokens+x.uncached_prompt_tokens,0);
  const cards=node('div','','cost-summary');
  cards.append(metric('Расход по известным тарифам',d.estimated_usd==null?null:`$ ${number(d.estimated_usd)}`,'blue',d.unpriced_calls?`Не учтены ${d.unpriced_calls} вызова без оценки`:'Оценка по сохранённым тарифам','cost'),metric('Вызовы модели',number(d.items.reduce((n,x)=>n+x.calls,0)),'violet','Один вопрос может вызвать модель дважды','activity'));
  const cacheCard=metric('Вход из кэша',input?`${Number(cached/input*100).toLocaleString('ru-RU',{maximumFractionDigits:1})} %`:null,'teal','Среди токенов с известной разбивкой','cache');
  if(input){const bar=node('progress','','cache-meter');bar.max=input;bar.value=cached;bar.setAttribute('aria-label','Доля входных токенов из кэша');cacheCard.appendChild(bar);}
  cards.appendChild(cacheCard);$('costs').prepend(cards);
  if(d.call_breakdown){
    const b=d.call_breakdown,counts=node('div','','cost-summary');
    counts.append(metric('Один вызов',number(b.one),'blue','Завершённые ответы','chat'),metric('Два вызова',number(b.two),'violet',b.two_percent==null?'Нет завершённых ответов':`${Number(b.two_percent).toLocaleString('ru-RU',{maximumFractionDigits:1})} % завершённых ответов`,'activity'),metric('Более двух',number(b.more),'amber','Зарегистрированные вызовы','activity'),metric('Без зарегистрированных вызовов',number(b.zero),'teal','Включая действия интерфейса','chat'));
    $('costs').append(counts,node('p',`Завершённых ответов и действий: ${number(b.completed)}. Неудачных попыток: ${number(b.failed_attempts)}. Повторных получений готового ответа: ${number(b.replayed)}. Ошибок вызова модели: ${number(b.failed_calls)}.`,'muted'),node('p','Разбивка по времени завершения ответа. Повторные обращения после ошибки и повторное получение готового ответа не включены в долю двойных. Назначение вызова и внутренние повторы провайдера не записаны. Это число зарегистрированных вызовов, а не доказанное число этапов. Ноль может означать действие без модели или неполные метрики; старые ответы без метрик не учитываются.','muted'));
  }
  $('costs').appendChild(node('p',`Доля кэша среди входных токенов с известной разбивкой: ${input?Number(cached/input*100).toLocaleString('ru-RU',{maximumFractionDigits:1})+' %':'Нет данных'}.`,'muted'));
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
  const stages=node('div','','journey');
  for(const [key,title]of [['opened','Открыли виджет'],['question','Задали вопрос'],['form','Открыли форму'],['submit','Отправили форму']]){const stage=node('div','','journey-stage');stage.append(node('span',title),node('strong',number(d.totals[key])));stages.appendChild(stage);}
  $('funnel').prepend(stages);
  $('funnel').appendChild(node('p','Сохраняем только домен и известные пути из настроек виджета. Остальные адреса — «Другие страницы». URL-параметры, UTM, тексты и контакты не собираются. Срок хранения событий — 30 дней. Учёт приблизительный: блокировщик или обрыв сети может пропустить действие.','muted'));
  if(d.truncated)$('funnel').appendChild(node('p','Достигнут лимит 50 000 событий для одного отчёта; показаны неполные данные. Выберите меньший период.','muted'));
}
function setPage(name){
  state.navigation++;state.page=name;
  for(const el of document.querySelectorAll('.page-panel'))el.hidden=el.id!==`page-${name}`;
  for(const el of document.querySelectorAll('[data-page]')){if(el.dataset.page===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');}
}
function paintSelection(){
  for(const el of document.querySelectorAll('.dialog-item'))el.setAttribute('aria-current',String(el.dataset.session===state.session));
  const index=state.dialogs.findIndex(x=>x.session_id===state.session);
  $('prevDialog').disabled=index<=0;$('nextDialog').disabled=index<0||index>=state.dialogs.length-1;
  $('dialogPosition').textContent=index<0?'Открыт по ссылке из другого раздела':`${index+1} из ${state.dialogs.length} загруженных · время вашего браузера`;
}
async function loadDialogs(append=false){
  const generation=++state.listGeneration;
  const params={q:$('dialogSearch').value,dialog_period:$('dialogPeriod').value,problems:$('dialogStatus').value==='problems'?'1':'0'};
  if(append)params.cursor=state.cursors.dialogs;
  const d=await get('/api/dialogs',params);
  if(generation!==state.listGeneration)return;
  if(!append){state.dialogs=[];$('dialogs').replaceChildren();}
  for(const x of d.items){
    if(state.dialogs.some(y=>y.session_id===x.session_id))continue;
    state.dialogs.push(x);
    const button=node('button','','dialog-item');button.type='button';button.dataset.session=x.session_id;
    button.append(node('strong',x.preview||`Диалог ${x.session_id.slice(0,8)}`),node('small',date(x.last_activity)),node('small',`Вопросы: ${x.questions??'—'} · действия: ${x.actions??'—'} · ${x.session_id.slice(0,8)}`));
    if(x.partial_failure||x.failed)button.append(node('span',x.partial_failure?'Часть ответа не выполнена':'Ошибка обращения','badge'));
    button.addEventListener('click',()=>void showThread(x.session_id));$('dialogs').appendChild(button);
  }
  if(!state.dialogs.length)empty('dialogs','Диалогов по этим условиям нет.');
  cursor('dialogs',d.next_cursor,'moreDialogs');paintSelection();
}
function formatted(text){
  // Only bold spans; no HTML, links, images or executable receipt actions.
  const result=node('div','','admin-turn__answer');
  String(text||'').split(/(\*\*[^*]+\*\*)/g).forEach(part=>result.appendChild(part.startsWith('**')&&part.endsWith('**')?node('strong',part.slice(2,-2)):document.createTextNode(part)));
  return result;
}
async function showThread(session,older=false,target=null){
  setPage('dialogues');
  if(!older){clearThread();state.session=session;$('dialogThreadViewer').hidden=false;$('threadPlaceholder').hidden=true;$('dialogWorkspace').classList.add('has-selection');$('dialogViewerTitle').textContent=`Диалог ${session.slice(0,8)}`;empty('dialogThreadBody','Загружаем переписку…');paintSelection();$('dialogViewerTitle').focus({preventScroll:true});}
  state.threadController?.abort();state.threadController=new AbortController();const generation=++state.threadGeneration,client=state.client;
  try{
    let next=older?state.cursors.turns:null;
    const all=[];let pages=0;
    do{
      pages++;
      const d=await get(`/api/dialogs/${session}/thread`,next?{cursor:next}:{},state.threadController.signal);
      if(generation!==state.threadGeneration||client!==state.client||session!==state.session)return;
      all.unshift(...d.items);next=d.next_cursor;
      // Explicit error deep-link: bounded history lookup, never a new bot request.
    }while(target&&next&&!all.some(t=>t.request_key===target)&&pages<10);
    const fragment=document.createDocumentFragment();
    for(const turn of all){
      const box=node('section','','admin-turn');box.dataset.request=turn.request_key;
      box.append(node('div',turn.selected_action?'Действие в виджете':'Посетитель','turn-meta'),node('div',turn.patient_text||(turn.selected_action?'Выбор в виджете':'Сообщение скрыто'),'admin-turn__user'),node('div','ИИ-помощник','turn-meta'),formatted(turn.answer));
      const usage=turn.model_usage;
      box.appendChild(node('p',usage?`Вызовы модели: ${number(usage.calls)} · время ответа: ${number(usage.duration_ms/1000)} с · оценка: ${usage.estimated_usd==null?'нет данных':number(usage.estimated_usd)+' $'}${usage.failed_attempts?' · неудачных попыток по запросу: '+number(usage.failed_attempts):''}${usage.failed_calls?' · ошибок вызовов: '+number(usage.failed_calls):''}`:'Вызовы модели: нет данных','turn-meta'));
      if(turn.failure_reasons?.length){const technical=turn.failure_reasons.includes('d2_operation_invalid');box.append(node('p',`${technical?'Часть ответа не выполнена: операция отклонена.':'Для части ответа не хватило данных.'} Сохранённая причина: ${turn.failure_reasons.join(', ')}`,technical?'failure-note':'muted'));}
      const details=node('details'),summary=node('summary','Технические сведения шага');details.append(summary,node('p',`Шаг ${turn.revision} · запрос ${turn.request_key}`));box.append(details);
      if(turn.request_key===target)box.classList.add('is-target');fragment.appendChild(box);
    }
    const scroller=$('threadScroll'),oldHeight=scroller.scrollHeight,oldTop=scroller.scrollTop;
    if(older)$('dialogThreadBody').prepend(fragment);else $('dialogThreadBody').replaceChildren(fragment);
    if(!all.length&&!older)empty('dialogThreadBody','В этой сессии нет публичных сообщений.');
    cursor('turns',next,'moreTurns');
    if(older)scroller.scrollTop=oldTop+scroller.scrollHeight-oldHeight;else scroller.scrollTop=0;
    if(target){const found=[...document.querySelectorAll('.admin-turn')].find(el=>el.dataset.request===target);if(found)found.scrollIntoView({block:'center'});else $('dialogThreadBody').prepend(node('p','Для этого запроса публичный ответ не найден в загруженной истории. Ошибка могла произойти до сохранения ответа.','failure-note'));}
  }catch(e){if(e.name!=='AbortError'&&generation===state.threadGeneration)empty('dialogThreadBody',e.message);}
}
function dialogueLink(session,request){const button=node('button','Открыть диалог');button.addEventListener('click',()=>void showThread(session,false,request));return button;}
async function loadLeads(append=false){
  const d=await get('/api/leads',append?{cursor:state.cursors.leads}:{});
  const rows=d.items.map(x=>row([date(x.accepted_at),labels[x.status]||'Неизвестный статус',x.service_id||'Уточнить услугу',x.offer_id||'—',dialogueLink(x.session_id)]));
  if(!rows.length&&!append)empty('leads','Заявок пока нет.');else table('leads',['Время','Результат','Услуга','Вариант','Диалог'],rows,append);
  cursor('leads',d.next_cursor,'moreLeads');
}
async function loadObservations(key,append=false){
  $('errorPeriod').value=$('period').value;
  const d=await get(`/api/${key}`,append?{cursor:state.cursors[key]}:{});
  const rows=d.items.map(x=>key==='problems'?row([date(x.observed_at),labels[x.kind]||x.kind,'Ошибка',x.model||'—','Причина не записана',number(x.duration_ms),dialogueLink(x.sid_hash,x.request_hash)]):row([date(x.observed_at),labels[x.kind]||x.kind,x.outcome==='failed'?'Ошибка':(labels[x.outcome]||x.outcome),x.model||'—',x.kind==='provider'?number(x.cached_prompt_tokens):'—',x.kind==='provider'?number(x.uncached_prompt_tokens):'—',x.kind==='provider'?number(x.completion_tokens):'—',x.kind==='provider'?number(x.estimated_usd):'—',number(x.duration_ms),dialogueLink(x.sid_hash,x.request_hash)]));
  if(!rows.length&&!append)empty(key,d.available?'За выбранный период записей нет.':'Учёт новых обращений ещё не начат.');else table(key,key==='problems'?['Время','Этап','Результат','Модель','Причина','мс','Диалог']:['Время','Тип','Результат','Модель','Кэш','Без кэша','Выход','Оценка, $','мс','Диалог'],rows,append);
  cursor(key,d.next_cursor,key==='events'?'moreEvents':'moreProblems');
}
async function refresh(preserve=true){
  const page=state.page;const selected=preserve?state.session:null;const scrollTop=$("threadScroll").scrollTop;
  state.controller?.abort();state.controller=new AbortController();if(!preserve){clearThread();state.dialogs=[];}state.cursors=preserve?{turns:state.cursors.turns}:{};
  const navigation=state.navigation;
  for(const id of ['moreDialogs','moreLeads','moreProblems','moreEvents'])$(id).hidden=true;
  const generation=++state.generation;
  for(const target of ['overview','periodOverview','knowledge','costs','funnel','dialogs','leads','problems','events'])empty(target,'Загрузка…');
  const jobs=[['overview',()=>get('/api/overview').then(renderOverview)],['knowledge',loadKnowledge],['costs',loadCosts],['funnel',loadFunnel],['dialogs',loadDialogs],['leads',loadLeads],['problems',()=>loadObservations('problems')]];
  if($('eventExplorer').open)jobs.push(['events',()=>loadObservations('events')]);else empty('events','Откройте раздел для загрузки метрик.');
  await Promise.all(jobs.map(async([target,fn])=>{try{await fn();}catch(e){if(e.name!=='AbortError'&&generation===state.generation)empty(target,e.message);}}));
  if(generation===state.generation&&navigation===state.navigation&&selected){
    const loading=showThread(selected);const refreshedNavigation=state.navigation;
    await loading;
    if(generation===state.generation&&refreshedNavigation===state.navigation&&state.session===selected){$('threadScroll').scrollTop=scrollTop;setPage(page);}
  }
}
function more(id,fn){$(id).addEventListener('click',async()=>{$(id).disabled=true;try{await fn();}catch(e){if(e.name!=='AbortError')$('statusBar').textContent=e.message;}finally{$(id).disabled=false;}});}
function initTheme(){
  const button=$('themeToggle');
  if(!button)return;
  const apply=theme=>{
    document.documentElement.dataset.theme=theme;
    button.textContent=theme==='dark'?'Тема: тёмная':'Тема: светлая';
    button.setAttribute('aria-pressed',String(theme==='dark'));
  };
  let theme='dark';
  try{if(localStorage.getItem('artgents-admin-theme')==='light')theme='light';}catch{}
  apply(theme);
  button.addEventListener('click',()=>{
    theme=document.documentElement.dataset.theme==='dark'?'light':'dark';apply(theme);
    try{localStorage.setItem('artgents-admin-theme',theme);}catch{}
  });
}
async function init(){
  initTheme();
  try{
    const response=await fetch('/api/clients',{cache:'no-store'});if(!response.ok)throw new Error('Админка недоступна: проверьте авторизацию и адрес запуска.');
    const data=await response.json();for(const client of data.items){const option=node('option',client.label);option.value=client.client_id;$('clientId').appendChild(option);}
    if(!data.items.length)throw new Error('Нет разрешённых клиентов. Проверьте список клиентов и admin.enabled.');
    const requested=new URL(location.href).searchParams.get('client_id');
    if(requested&&!data.items.some(c=>c.client_id===requested))throw new Error('Этот клиент не разрешён в админке.');
    state.client=requested||data.items[0].client_id;$('clientId').value=state.client;
    const health=await fetch('/api/health',{cache:'no-store'});if(!health.ok)throw new Error('Хранилище диалогов недоступно.');
    $('statusBar').textContent='Только просмотр · данные не сохраняются в браузере';
    $('clientId').addEventListener('change',()=>{state.client=$('clientId').value;const url=new URL(location.href);url.searchParams.set('client_id',state.client);history.replaceState(null,'',url);state.listGeneration++;void refresh(false);});
    for(const el of document.querySelectorAll('[data-page]'))el.addEventListener('click',()=>setPage(el.dataset.page));
    let searchTimer;
    const filter=()=>{clearTimeout(searchTimer);state.listGeneration++;clearThread();$('moreDialogs').hidden=true;empty('dialogs','Поиск…');void loadDialogs().catch(e=>{if(e.name!=='AbortError')empty('dialogs',e.message);});};
    $('dialogSearch').addEventListener('input',()=>{clearTimeout(searchTimer);state.listGeneration++;searchTimer=setTimeout(filter,250);});
    $('dialogPeriod').addEventListener('change',filter);$('dialogStatus').addEventListener('change',filter);
    $('partialDialogs').addEventListener('click',()=>{$('dialogStatus').value='problems';$('dialogPeriod').value='all';$('dialogSearch').value='';setPage('dialogues');filter();});
    for(const [id,delta]of [['prevDialog',-1],['nextDialog',1]])$(id).addEventListener('click',()=>{const i=state.dialogs.findIndex(x=>x.session_id===state.session);const next=state.dialogs[i+delta];if(next)void showThread(next.session_id);});
    $('refreshBtn').addEventListener('click',()=>void refresh());$('period').addEventListener('change',()=>void refresh());$('errorPeriod').addEventListener('change',()=>{$('period').value=$('errorPeriod').value;void refresh();});$('dialogViewerClose').addEventListener('click',clearThread);
    more('moreDialogs',()=>loadDialogs(true));more('moreLeads',()=>loadLeads(true));more('moreProblems',()=>loadObservations('problems',true));more('moreEvents',()=>loadObservations('events',true));more('moreTurns',()=>showThread(state.session,true));
    $('eventExplorer').addEventListener('toggle',()=>{if($('eventExplorer').open)void loadObservations('events').catch(e=>{if(e.name!=='AbortError')empty('events',e.message);});});
    await refresh();
  }catch(e){$('statusBar').textContent=e.message;}
}
window.addEventListener('pagehide',()=>{state.controller?.abort();clearThread();for(const id of ['overview','periodOverview','knowledge','costs','funnel','dialogs','leads','events','problems'])$(id).replaceChildren();});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
void init();
