'use strict';
// Standalone UX prototype. No API, model, browser storage or real lead submission.
const arrow='<svg class="arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M4 12h16m-6-6 6 6-6 6"/></svg>';
const gift='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 8h18v4H3zM5 12v9h14v-9M12 8v13M12 8H8a3 3 0 1 1 3-3l1 3Zm0 0h4a3 3 0 1 0-3-3l-1 3Z"/></svg>';
const dentalServices=[
 {id:'classic',name:'Классическая имплантация',category:'Имплантация',short:'Один зуб · имплант и постоянная коронка',description:'Восстановление отсутствующего зуба с опорой на имплант. Соседние зубы не нужно обтачивать под мост.',variants:[['Implantium','76 200 ₽'],['Impro','85 200 ₽'],['Nobel','101 200 ₽']],scope:'За один зуб · имплант + постоянная коронка',includes:['Имплант с документами','Хирургия и местная анестезия','Постоянная коронка','Контрольные осмотры и куратор'],excludes:'КТ при необходимости и временная коронка оплачиваются отдельно.',stages:['45 200 ₽ — хирургический этап','31 000 ₽ — постоянная коронка, обычно через 3–6 месяцев'],promo:'Бесплатная консультация по имплантации'},
 {id:'all4',name:'Имплантация All-on-4',category:'Имплантация',short:'Вся челюсть · несъёмный протез',description:'Восстановление зубов всей челюсти на четырёх имплантах. Временный протез помогает вернуться к улыбке и общению на период приживления.',variants:[['Implantium','318 000 ₽'],['Impro','368 000 ₽'],['Nobel','428 000 ₽']],scope:'За одну челюсть',includes:['4 импланта, хирургия и местная анестезия','Временный несъёмный протез по показаниям','Постоянный протез после приживления','Сопровождение куратора'],excludes:'КТ и костная пластика по показаниям оплачиваются отдельно.',stages:['190 800 ₽ — хирургия и временный протез','127 200 ₽ — постоянный протез после приживления'],promo:'Бесплатная консультация по имплантации'},
 {id:'crowns',name:'Циркониевые коронки',category:'Протезирование',short:'Восстановление собственного зуба',description:'Коронка восстанавливает форму и внешний вид сильно разрушенного зуба. Изготавливаем её в собственной лаборатории.',variants:[['На собственный зуб','от 25 000 ₽']],scope:'За одну коронку на собственном зубе',includes:['Изготовление циркониевой коронки','Примерка и фиксация'],excludes:'Подготовительное лечение зуба оплачивается отдельно.'},
 {id:'white',name:'Отбеливание зубов',category:'Эстетика',short:'Более светлая улыбка за один визит',description:'Профессиональное отбеливание Philips Zoom WhiteSpeed. До процедуры врач оценивает состояние зубов и обсуждает желаемый оттенок.',variants:[['Одна процедура','от 18 000 ₽']],scope:'За одну процедуру · стоимость зависит от протокола',includes:['Осмотр перед отбеливанием','Защита дёсен и кабинетное отбеливание','Рекомендации по уходу'],excludes:'Профессиональная гигиена и лечение зубов перед отбеливанием оплачиваются отдельно.'}
];

function basic(id,name,category,price,scope,description){return {id,name,category,short:scope,description,variants:[['Основной вариант',price]],scope,includes:['Приём или процедура в указанном объёме','Рекомендации специалиста'],excludes:'Дополнительные исследования и процедуры — по отдельной стоимости.'};}
dentalServices.push(
 basic('caries','Лечение кариеса','Лечение зубов','от 6 500 ₽','За один зуб','Восстановление зуба пломбой. Объём лечения врач определит после осмотра.'),
 basic('hygiene','Профессиональная гигиена','Гигиена','от 5 500 ₽','За одну процедуру','Удаление налёта и зубного камня с рекомендациями по домашнему уходу.')
);
const medicalServices=[
 basic('ent-first','Первичный приём ЛОРа','ЛОР','3 100 ₽','За один приём · взрослым и детям','Врач выслушает жалобы, проведёт осмотр ушей, носа и горла и обсудит дальнейшие действия.'),
 basic('ent-repeat','Повторный приём ЛОРа','ЛОР','2 300 ₽','За один повторный приём','Обсуждение результатов обследования и дальнейшего плана с врачом.'),
 basic('ent-wax','Удаление серной пробки','ЛОР','700 ₽','За одно ухо','Удаление серной пробки после осмотра врачом.'),
 basic('therapy','Приём терапевта','Терапия','2 800 ₽','За один первичный приём','Если непонятно, к кому обратиться, терапевт поможет определить следующий шаг.'),
 basic('therapy-repeat','Повторный приём терапевта','Терапия','2 000 ₽','За один повторный приём','Врач обсудит результаты назначенных обследований и ответит на вопросы.'),
 basic('pediatric','Приём педиатра','Педиатрия','3 000 ₽','За один первичный приём','Врач осмотрит ребёнка, обсудит самочувствие и вопросы родителей.'),
 basic('pediatric-repeat','Повторный приём педиатра','Педиатрия','2 200 ₽','За один повторный приём','Повторный осмотр и обсуждение изменений в самочувствии ребёнка.'),
 basic('gyn','Приём гинеколога','Гинекология','3 200 ₽','За один первичный приём','Консультация и осмотр с обсуждением беспокоящих вопросов.'),
 basic('gyn-repeat','Повторный приём гинеколога','Гинекология','2 400 ₽','За один повторный приём','Обсуждение результатов обследования и дальнейших рекомендаций.'),
 basic('uro','Приём уролога','Урология','3 000 ₽','За один первичный приём','Консультация специалиста и план дальнейших действий по результатам осмотра.'),
 basic('uro-repeat','Повторный приём уролога','Урология','2 200 ₽','За один повторный приём','Обсуждение результатов обследования с врачом.'),
 basic('cardio','Приём кардиолога','Кардиология','3 500 ₽','За один первичный приём','Врач обсудит жалобы и имеющиеся обследования, проведёт осмотр.'),
 basic('ecg','ЭКГ с расшифровкой','Кардиология','1 200 ₽','За одно исследование','Запись электрокардиограммы и заключение специалиста.'),
 basic('neuro','Приём невролога','Неврология','3 200 ₽','За один первичный приём','Консультация и неврологический осмотр с объяснением дальнейших действий.'),
 basic('neuro-repeat','Повторный приём невролога','Неврология','2 400 ₽','За один повторный приём','Оценка изменений и обсуждение результатов обследования.'),
 basic('us-abdomen','УЗИ брюшной полости','УЗИ','2 600 ₽','За одно исследование','Ультразвуковое исследование органов брюшной полости с заключением. Подготовку уточнят при записи.'),
 basic('us-thyroid','УЗИ щитовидной железы','УЗИ','1 800 ₽','За одно исследование','Ультразвуковое исследование щитовидной железы с заключением.'),
 basic('derma','Приём дерматолога','Дерматология','2 900 ₽','За один первичный приём','Консультация по состоянию кожи и осмотр специалистом.'),
 basic('dermoscopy','Дерматоскопия','Дерматология','1 000 ₽','За одно образование','Осмотр образования кожи с увеличением. Консультация оплачивается отдельно.'),
 basic('cosmo','Консультация косметолога','Косметология','2 500 ₽','За один приём','Обсудите задачи по уходу за кожей и возможные процедуры со специалистом.'),
 {...basic('plasma','Плазмотерапия','Косметология','6 000 ₽','За одну процедуру · выбранная зона','Процедура с использованием плазмы собственной крови. Возможность проведения определяет врач на консультации.'),variants:[['Лицо','6 000 ₽'],['Лицо и шея','9 000 ₽']],scope:'За одну процедуру · зона указана в выбранном варианте',includes:['Проведение процедуры в выбранной зоне','Рекомендации по уходу после процедуры'],excludes:'Предварительная консультация и анализы, если потребуются, оплачиваются отдельно.'}
];
const packs={
 dental:{label:'Стоматология',services:dentalServices,categories:[['Имплантация','Один зуб или вся челюсть'],['Протезирование','Коронки и восстановление зубов'],['Лечение зубов','Сохранение собственных зубов'],['Гигиена','Профессиональный уход'],['Эстетика','Более светлая улыбка']]},
 medical:{label:'Медицинский центр',services:medicalServices,categories:[['ЛОР','Уши, горло и нос · взрослым и детям'],['Терапия','Общие вопросы о здоровье'],['Педиатрия','Приём детей'],['Гинекология','Женское здоровье'],['Урология','Консультации и обследования'],['Кардиология','Сердце и сосуды'],['Неврология','Консультации невролога'],['УЗИ','Ультразвуковые исследования'],['Дерматология','Здоровье кожи'],['Косметология','Уход и эстетические процедуры']]}
};
let packKey='dental',services=packs.dental.services,activeCategory=null,categoryScroll=0;
const byId=id=>services.find(s=>s.id===id);
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let draft,submitted,activeService=null,search='',catalogScroll=0;
const selectedVariants={};
function initialDraft(){return {name:'',phone:'',consent:false,service:'',wish:''};}
function switchTab(name,focus=false){
 document.querySelectorAll('[data-tab]').forEach(b=>{const on=b.dataset.tab===name;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;if(on&&focus)b.focus();});
 document.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!==`panel-${name}`);
}
document.querySelectorAll('[data-tab]').forEach(b=>{
 b.onclick=()=>switchTab(b.dataset.tab);
 b.onkeydown=e=>{const buttons=[...document.querySelectorAll('[data-tab]')],i=buttons.indexOf(b);let n;if(e.key==='ArrowRight')n=(i+1)%3;if(e.key==='ArrowLeft')n=(i+2)%3;if(e.key==='Home')n=0;if(e.key==='End')n=2;if(n!==undefined){e.preventDefault();switchTab(buttons[n].dataset.tab,true);}};
});
function primary(label,attrs=''){return `<button class="primary" ${attrs}>${label}${arrow}</button>`;}
function scrollToEl(el){requestAnimationFrame(()=>el.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'nearest'}));}
function updateDot(){$('.draft-dot').hidden=submitted||!Object.values(draft).some(Boolean);}
function newDraft(){draft=initialDraft();submitted=false;renderForms();updateDot();}
function renderForms(){document.querySelectorAll('.form-mount').forEach(m=>renderForm(m));}
function syncDraft(key,value){draft[key]=value;document.querySelectorAll(`[data-field="${key}"]`).forEach(el=>{if(key==='consent')el.checked=value;else if(el!==document.activeElement)el.value=value;});document.querySelectorAll('.form-service').forEach(el=>el.textContent=draft.service?`Вы обращаетесь: ${byId(draft.service).name}`:'Общая заявка · услугу можно выбрать позже');updateDot();}
function renderForm(mount){
 const place=mount.dataset.place,extended=place==='booking';
 if(submitted){mount.innerHTML='<div class="success" role="status"><div class="success-icon">✓</div><strong>Всё получилось</strong><p>В рабочем виджете здесь будет подтверждение заявки. В прототипе данные никуда не отправлены.</p><button class="text-button" data-new>Новая заявка</button></div>';mount.querySelector('[data-new]').onclick=newDraft;return;}
 mount.innerHTML=`<form class="lead-card"><h3>${extended?'Ваши контакты':'Оставить заявку'}</h3><p class="lead-intro">${extended?'Поможем выбрать следующий шаг.':'Администратор свяжется с вами и согласует время.'}</p>${extended?'':'<div class="form-service"></div>'}
 <label class="form-field" for="${place}-name">Как к вам обращаться<input id="${place}-name" data-field="name" name="name" autocomplete="name" required maxlength="80" value="${esc(draft.name)}"></label>
 <label class="form-field" for="${place}-phone">Телефон<input id="${place}-phone" data-field="phone" name="phone" type="tel" autocomplete="tel" inputmode="tel" placeholder="+7 ___ ___-__-__" required maxlength="24" value="${esc(draft.phone)}"></label>
 ${extended?`<label class="form-field" for="${place}-service">Что вас интересует · необязательно<select id="${place}-service" data-field="service" name="service"><option value="">Помогите определиться</option>${services.map(s=>`<option value="${s.id}" ${draft.service===s.id?'selected':''}>${s.name}</option>`).join('')}</select></label><label class="form-field" for="${place}-wish">Пожелание · необязательно<textarea id="${place}-wish" data-field="wish" name="wish" maxlength="500" placeholder="Например, удобнее позвонить после 18:00">${esc(draft.wish)}</textarea></label>`:''}
 <label class="consent"><input type="checkbox" data-field="consent" required ${draft.consent?'checked':''}><span>Согласен на обработку персональных данных. <button type="button" data-consent-info>Подробнее</button></span></label>
 ${primary('Отправить заявку','type="submit"')}<p class="form-footnote">${extended?'':'Можно вернуться к разговору — поля сохранятся.'}</p></form>`;
 const serviceLine=mount.querySelector('.form-service');if(serviceLine)serviceLine.textContent=draft.service?`Вы обращаетесь: ${byId(draft.service).name}`:'Общая заявка · услугу можно выбрать позже';
 mount.querySelectorAll('[data-field]').forEach(el=>el.addEventListener('input',()=>{el.setCustomValidity('');syncDraft(el.dataset.field,el.type==='checkbox'?el.checked:el.value);}));
 mount.querySelector('[data-consent-info]').onclick=()=>{let p=mount.querySelector('.consent-info');if(!p){p=document.createElement('p');p.className='quiet-note consent-info';p.textContent='В рабочем виджете здесь будут условия обработки данных конкретной клиники. Этот прототип не передаёт и не сохраняет ваши контакты.';mount.querySelector('.consent').after(p);}else p.hidden=!p.hidden;};
 mount.querySelector('form').onsubmit=e=>{e.preventDefault();const phone=mount.querySelector('[data-field=phone]'),name=mount.querySelector('[data-field=name]');if(!draft.name.trim()){name.setCustomValidity('Укажите имя');name.reportValidity();return;}if(draft.phone.replace(/\D/g,'').length<10){phone.setCustomValidity('Проверьте номер: укажите не менее 10 цифр');phone.reportValidity();return;}submitted=true;draft=initialDraft();renderForms();updateDot();};
}
function showForm(place,service){
 if(service&&!submitted)syncDraft('service',service);
 let mount=document.querySelector(`.form-mount[data-place="${place}"]`);
 if(!mount){mount=document.createElement('div');mount.className='form-mount';mount.dataset.place=place;$('#feed').append(mount);}
 if(place==='chat')$('#feed').append(mount);renderForm(mount);if(place!=='booking')scrollToEl(mount);
}
function reply(text,service,links=[]){
 const el=document.createElement('section');el.className='reply';el.innerHTML=`<div class="attribution">Надежда</div>${text.split('\n\n').map(p=>`<p>${esc(p)}</p>`).join('')}`;
 const actions=document.createElement('div');actions.className='actions';links.forEach(([label,answer])=>{const b=document.createElement('button');b.className='action';b.innerHTML=`<span>${esc(label)}</span>${arrow}`;b.onclick=()=>{b.remove();ask(label,answer,service);};actions.append(b);});if(links.length)el.append(actions);
 const cta=document.createElement('div');cta.style.marginTop='15px';cta.innerHTML=primary('Оставить заявку','type="button"');cta.firstElementChild.onclick=()=>showForm('chat',service);el.append(cta);$('#feed').append(el);return el;
}
function ask(q,answer,service){
 const user=document.createElement('div');user.className='user';user.textContent=q;$('#feed').append(user);
 const el=reply(answer||'Могу помочь разобраться в услугах или оставить заявку. Откройте «Услуги и цены», чтобы выбрать направление. В этом прототипе ответы заранее подготовлены.',service,service?[['Что входит в стоимость?',byId(service).includes.join('. ')+'.'],['Что оплачивается отдельно?',byId(service).excludes]]:[]);
 scrollToEl(el);
}
function welcome(){
 $('#feed').innerHTML='<p class="welcome">Здравствуйте! Я Надежда, помощник клиники. Помогу разобраться в услугах, ценах и условиях лечения.</p><p class="section-label">С чего начнём?</p><div class="actions" id="starters"></div>';
 const starters=packKey==='medical'?[['С чего начать?','Можно начать с приёма терапевта, если вы не знаете, какой специалист нужен. Администратор поможет уточнить направление.'],['Сколько стоит приём ЛОРа?',byId('ent-first').description+' Первичный приём — 3 100 ₽.','ent-first'],['Какие есть направления?','В каталоге представлены десять направлений: от терапии и ЛОРа до УЗИ и косметологии. Выберите нужное во вкладке «Услуги и цены».'],['Хочу записаться',null]]:[['Давно не был у стоматолога','Начните с обычного осмотра. Врач выслушает, что вас беспокоит, оценит состояние зубов и дёсен и объяснит, нужен ли уход или лечение. Решение можно принять спокойно, без спешки.'],['Сколько стоит имплантация?','Классическая имплантация с постоянной коронкой — 76 200 ₽ на системе Implantium. КТ при необходимости и временная коронка оплачиваются отдельно.\n\nВ каталоге можно посмотреть состав и другие готовые варианты.','classic'],['Расскажите про коронки',byId('crowns').description+' Стоимость — от 25 000 ₽ за коронку на собственном зубе.','crowns'],['Хочу записаться',null]];
 starters.forEach(([label,a,s])=>{const b=document.createElement('button');b.className='action';b.innerHTML=`<span>${label}</span>${arrow}`;b.onclick=()=>{if(!a){const u=document.createElement('div');u.className='user';u.textContent=label;$('#feed').append(u);showForm('chat');}else ask(label,a,s);};$('#starters').append(b);});
 if(packKey==='medical')return;
 const p=document.createElement('button');p.className='promo';p.innerHTML=gift+'<span><strong>Бесплатная консультация по имплантации</strong><small>Три варианта лечения в разных бюджетах</small><span class="promo-link">Что входит →</span></span>';p.onclick=()=>ask('Что входит в консультацию?','Ведущий врач обсудит вашу задачу и предложит три варианта лечения с объяснением отличий, этапов и стоимости. КТ по показаниям оплачивается отдельно.','classic');$('#feed').append(p);
}
$('#composer').onsubmit=e=>{e.preventDefault();const input=$('#question'),q=input.value.trim();if(!q)return;input.value='';if(/запис|заявк|хочу.*при[её]м/i.test(q)){const u=document.createElement('div');u.className='user';u.textContent=q;$('#feed').append(u);showForm('chat');return;}const s=services.find(x=>q.toLowerCase().includes(x.name.toLowerCase()))||(packKey==='medical'?(/лор/i.test(q)?byId('ent-first'):null):/корон/i.test(q)?byId('crowns'):/отбел/i.test(q)?byId('white'):/all|вся челюсть/i.test(q)?byId('all4'):/имплант/i.test(q)?byId('classic'):null);ask(q,s?`${s.description}\n\n${s.variants[0][1]}. ${s.scope}. ${s.excludes}`:null,s?.id);};
function renderCatalog(){
 const root=$('#catalog');
 if(activeService){renderDetail();return;}
 root.innerHTML=`${activeCategory?'<button class="back" id="back-directions">← Все направления</button>':''}<div class="page-heading"><span class="eyebrow">${esc(packs[packKey].label)}</span><h2>${esc(activeCategory||'Услуги и цены')}</h2><p>${activeCategory?'Основные услуги и ориентиры стоимости.':'Выберите направление или найдите услугу.'}</p></div><label class="sr-only" for="service-search">Поиск по всему каталогу</label><input class="search" id="service-search" placeholder="Найти услугу или направление…"><p class="catalog-note">${packKey==='medical'?'Демонстрационные услуги и цены':'Демо-клиника · основные услуги'}</p><div id="service-list"></div>`;
 const input=$('#service-search');input.value=search;input.oninput=()=>{search=input.value;renderList();};
 if(activeCategory)$('#back-directions').onclick=()=>{activeCategory=null;search='';renderCatalog();$('#panel-catalog').scrollTop=categoryScroll;};
 renderList();
}
function renderList(){
 const list=$('#service-list'),query=search.trim().toLowerCase();list.innerHTML='';
 $('#catalog .page-heading h2').textContent=query?'Результаты поиска':activeCategory||'Услуги и цены';
 $('#catalog .page-heading p').textContent=query?'По всем направлениям клиники.':activeCategory?'Основные услуги и ориентиры стоимости.':'Выберите направление или найдите услугу.';
 if(!query&&!activeCategory){
 list.className='direction-list';packs[packKey].categories.forEach(([name,hint])=>{const b=document.createElement('button');b.className='direction-row';b.innerHTML=`<span><strong>${esc(name)}</strong><small>${esc(hint)}</small></span>${arrow}`;b.onclick=()=>{categoryScroll=$('#panel-catalog').scrollTop;activeCategory=name;renderCatalog();$('#panel-catalog').scrollTop=0;};list.append(b);});return;
 }
 list.className='service-list';
 const found=services.filter(s=>(query||s.category===activeCategory)&&`${s.name} ${s.short} ${s.category}`.toLowerCase().includes(query));
 if(!found.length){list.innerHTML='<p class="empty">Ничего не найдено. Попробуйте другое название.</p>';return;}
 found.forEach(s=>{const b=document.createElement('button');b.className='service-row';b.innerHTML=`<strong>${esc(s.name)}</strong><span class="price">${esc(s.variants[0][1])}</span><small>${query?esc(s.category)+' · ':''}${esc(s.short)}</small>${arrow}`;b.onclick=()=>{catalogScroll=$('#panel-catalog').scrollTop;activeService=s.id;renderDetail();$('#panel-catalog').scrollTop=0;};list.append(b);});
}
function renderDetail(){
 const s=byId(activeService),index=selectedVariants[s.id]||0,variant=s.variants[index],root=$('#catalog');
 root.innerHTML=`<button class="back"><span>←</span> ${search.trim()?'Результаты поиска':esc(activeCategory||'Все направления')}</button><div class="service-card"><div class="card-top"><span class="eyebrow">${s.category}</span><h2>${s.name}</h2><p>${s.description}</p>${s.variants.length>1?`<div class="choices" role="group" aria-label="Вариант услуги">${s.variants.map((v,i)=>`<button aria-pressed="${i===index}" data-variant="${i}">${v[0]}</button>`).join('')}</div>`:''}<div class="amount">${variant[1]}</div><div class="scope">${s.scope}</div></div><details><summary>Что входит в стоимость</summary><ul>${s.includes.map(x=>`<li>${x}</li>`).join('')}</ul></details><details><summary>Оплачивается отдельно</summary><p>${s.excludes}</p></details>${s.stages&&index===0?`<details><summary>Оплата по этапам</summary><ul>${s.stages.map(x=>`<li>${x}</li>`).join('')}</ul></details>`:''}${s.promo?`<div class="card-promo">${gift}<span>${s.promo}</span></div>`:''}</div><div class="catalog-actions">${primary('Оставить заявку','type="button" id="catalog-apply"')}<button class="text-button" id="ask-service">Спросить об этой услуге →</button></div><div class="form-mount" data-place="catalog" hidden></div>`;
 root.querySelector('.back').onclick=()=>{activeService=null;renderCatalog();$('#panel-catalog').scrollTop=catalogScroll;};
 root.querySelectorAll('[data-variant]').forEach(b=>b.onclick=()=>{const mount=root.querySelector('.form-mount'),wasOpen=!mount.hidden,scroll=$('#panel-catalog').scrollTop;selectedVariants[s.id]=+b.dataset.variant;renderDetail();const next=root.querySelector('.form-mount');if(wasOpen){next.hidden=false;renderForm(next);}$('#panel-catalog').scrollTop=scroll;});
 $('#catalog-apply').onclick=()=>{const m=root.querySelector('.form-mount');m.hidden=false;showForm('catalog',s.id);};
 $('#ask-service').onclick=()=>{switchTab('chat');ask(`Расскажите про услугу «${s.name}»`,`${s.description}\n\n${variant[1]}. ${s.scope}. ${s.excludes}`,s.id);};
}
function reset(){draft=initialDraft();submitted=false;activeService=null;activeCategory=null;categoryScroll=0;search='';catalogScroll=0;Object.keys(selectedVariants).forEach(k=>delete selectedVariants[k]);welcome();renderCatalog();renderForms();updateDot();switchTab('chat');$('#question').value='';$('#feed').scrollTop=0;$('#panel-booking').scrollTop=0;$('#panel-catalog').scrollTop=0;}
document.querySelectorAll('[data-pack]').forEach(b=>b.onclick=()=>{
 if(b.dataset.pack===packKey)return;
 packKey=b.dataset.pack;services=packs[packKey].services;
 document.querySelectorAll('[data-pack]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
 $('.header p').textContent=packs[packKey].label;reset();
});
$('#reset').onclick=reset;reset();
