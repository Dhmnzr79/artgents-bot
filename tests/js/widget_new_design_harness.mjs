// Appended to the existing isolated static-server test runner. All fetches are fixtures.
  for (const fixture of fixtures) {
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.evaluate(async fixture => {
      const {mountWidget}=await import('/static/widget/widget.js');
      window.formRequests=[];window.fetches=[];window.askRequests=[];window.failLead=true;
      window.fetch=async (url,options={})=>{
        const address=String(url);window.fetches.push(address);
        const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
        if(address.includes('/api/widget-catalog'))return json(fixture.catalog);
        if(address.includes('/api/booking-form'))return json(fixture.definition);
        if(address.includes('video-catalog'))return json({videos:{}});
        if(address.endsWith('/api/widget-session'))return json({messages:[]});
        if(address.endsWith('/ask/stream')&&fixture.dialogue){
          const body=JSON.parse(options.body);window.askRequests.push(body);
          const value=fixture.dialogue[body.ref||'initial'];
          if(!value)throw Error('Unpublished mock ref '+body.ref);
          return new Response('event: ui\ndata: '+JSON.stringify({...value,sid:body.sid,request_id:body.request_id})+'\n\nevent: done\ndata: {}\n\n',{headers:{'Content-Type':'text/event-stream'}});
        }
        if(address.endsWith('/lead')){
          window.formRequests.push(JSON.parse(options.body));
          if(window.failLead){window.failLead=false;throw Error('offline response lost');}
          return json({ok:true,message:'Заявка принята — подтверждённый ответ API'});
        }
        throw Error('Unexpected network call: '+address);
      };
      localStorage.clear();
      mountWidget(document.querySelector('#root'),{...fixture.config,apiBase:location.origin});
      document.querySelector('[data-clinic-dev-reset]')?.remove();
      document.querySelector('[data-clinic-launcher-open],[data-clinic-launcher]').click();
    },fixture);
    await page.evaluate(()=>document.fonts.ready);
    const shell=page.locator('[data-clinic-root]');
    if(await page.locator('[data-clinic-send] path').first().getAttribute('d')!=='m21 3-7.1 18-3.8-7.1L3 10.1 21 3Z')throw Error('Composer send is not a paper plane');
    if(await shell.getAttribute('data-design')!==fixture.config.design)throw Error('Wrong tenant theme');
    if(await page.locator('.clinic-shell__welcome-actions .clinic-msg__link').count()!==3)throw Error('Expected three start actions');
    if(await page.locator('.clinic-shell__welcome-actions .clinic-msg__link-icon').count()!==3)throw Error('Missing authored icons');
    const header=await page.locator('.clinic-shell__header').innerText();
    if(!header.includes('Помощник клиники')||!header.includes(fixture.config.botName+' сейчас онлайн'))throw Error('Header content');
    const typography=await page.locator('.clinic-shell__welcome-text').evaluate(el=>{const s=getComputedStyle(el);return [s.fontSize,s.lineHeight,s.fontWeight,s.fontFamily];});
    if(typography[0]!=='15.5px'||typography[1]!=='23.25px'||typography[2]!=='400'||!typography[3].includes('Inter'))throw Error('Dialogue typography '+typography);
    const layout=async state=>{
      for(const width of [320,360,390,412,440,1280]){
        await page.setViewportSize({width,height:844});
        const errors=await page.locator('[data-clinic-panel]').evaluate(panel=>{
          const bounds=panel.getBoundingClientRect(),errors=[];
          if(bounds.top<0||bounds.bottom>innerHeight+1)errors.push('vertical panel overflow');
          for(const el of panel.querySelectorAll('*')){
            const r=el.getBoundingClientRect(),s=getComputedStyle(el);
            if(!r.width||!r.height||s.display==='inline'||el instanceof SVGElement)continue;
            if(r.left<bounds.left-1||r.right>bounds.right+1)errors.push(el.className+' bounds');
            if(!el.matches('input,textarea,select')&&el.scrollWidth>el.clientWidth+2)errors.push(el.className+' text overflow');
          }
          for(const tab of panel.querySelectorAll('[role=tab]'))if(tab.clientHeight>44)errors.push('tabs wrapped');
          return errors;
        });
        if(errors.length)throw Error(JSON.stringify({tenant:fixture.config.clientId,state,width,errors}));
      }
      await page.setViewportSize({width:390,height:844});
      if(process.env.WIDGET_DESIGN_SCREENSHOT_DIR){
        fs.mkdirSync(process.env.WIDGET_DESIGN_SCREENSHOT_DIR,{recursive:true});
        await page.locator('[data-clinic-panel]').screenshot({path:path.join(process.env.WIDGET_DESIGN_SCREENSHOT_DIR,`${fixture.config.clientId}-${state.replaceAll(' ','-')}.png`)});
      }
    };
    await layout('welcome');
    await page.getByRole('tab',{name:'Услуги и цены',exact:true}).click();
    const catalog=page.locator('[data-clinic-catalog-panel]');
    await catalog.locator('.clinic-catalog__row').first().waitFor();
    if(await catalog.locator('.clinic-catalog__heading').isVisible())throw Error('Duplicate root heading');
    const service=fixture.catalog.services.find(item=>item.price?.rows.length>1);
    if(!service)throw Error('Fixture lacks variants');
    await catalog.getByRole('searchbox').fill(service.name);
    const row=catalog.locator('.clinic-catalog__service').filter({hasText:service.name});
    if(await row.count()!==1)throw Error('Search service mismatch');
    const positions=await row.evaluate(el=>{
      const name=el.querySelector('strong').getBoundingClientRect(),subtitle=el.querySelector('small').getBoundingClientRect(),amount=el.querySelector('.clinic-catalog__row-price')?.getBoundingClientRect();
      return {name:name.bottom,subtitle:subtitle.top,subtitleBottom:subtitle.bottom,amount:amount?.top};
    });
    if(positions.subtitle<positions.name||positions.amount<positions.subtitleBottom)throw Error('Price not below description');
    await layout('service list');await row.click();await layout('options');
    await catalog.locator('.clinic-price-card__overview-row').first().click();
    await catalog.locator('.clinic-price-card__summary').waitFor();
    await catalog.locator('details').evaluateAll(items=>items.forEach(item=>item.open=true));
    if(await catalog.locator('.clinic-price-card__price-area .clinic-price-card__caption').count()>1)throw Error('Multiple price notes');
    await layout('detail');
    const paths=await catalog.locator('.clinic-catalog__back-icon path').getAttribute('d');
    if(paths!=='M5 12h14m-5-5 5 5-5 5')throw Error('Back arrow mismatch');
    await catalog.getByRole('button',{name:'Оставить заявку',exact:true}).click();
    await page.getByRole('tab',{name:'Запись',exact:true}).click();
    const booking=page.locator('[data-clinic-booking-panel]');
    await booking.getByLabel('Как к вам обращаться').fill('Анна');
    await booking.getByLabel('Телефон',{exact:true}).fill('+79991234567');
    await booking.getByLabel('Пожелания (необязательно)').fill('После 18:00');
    await booking.getByRole('checkbox').check();
    if(await booking.locator('select').count())throw Error('Native service picker remains');
    if(await booking.locator('h2').count())throw Error('Duplicate booking heading');
    await booking.getByRole('button',{name:'Убрать',exact:true}).click();
    await booking.locator('.clinic-booking__subject').waitFor({state:'detached'});
    if(await booking.getByLabel('Как к вам обращаться').inputValue()!=='Анна'||await booking.getByLabel('Телефон',{exact:true}).inputValue()!=='+79991234567'||await booking.getByLabel('Пожелания (необязательно)').inputValue()!=='После 18:00'||!await booking.getByRole('checkbox').isChecked())throw Error('Clear selection lost draft');
    if(await catalog.locator('.clinic-booking__subject').count())throw Error('Clear did not sync inline form');
    await layout('booking');
    await booking.getByRole('button',{name:'Отправить заявку',exact:true}).click();
    await booking.getByRole('button',{name:'Проверить отправку',exact:true}).waitFor();
    if(!await booking.getByLabel('Телефон',{exact:true}).isDisabled())throw Error('Retry body mutable');
    if(await booking.locator('.clinic-booking__success').count())throw Error('False success');
    await booking.getByRole('button',{name:'Проверить отправку',exact:true}).click();
    await booking.locator('.clinic-booking__success').waitFor();
    const requests=await page.evaluate(()=>window.formRequests);
    if(requests.length!==2||JSON.stringify(requests[0])!==JSON.stringify(requests[1]))throw Error('Retry changed payload');
    if(requests[0].selection!==null||requests[0].name!=='Анна'||requests[0].wish!=='После 18:00'||!requests[0].consent.accepted)throw Error('Cleared context/private fields not delivered');
    if(await page.evaluate(()=>window.fetches.some(url=>url.endsWith('/ask')||url.endsWith('/ask/stream'))))throw Error('Browsing/form called model');
    if(await page.evaluate(()=>JSON.stringify({...localStorage}).includes('Анна')))throw Error('Contact persisted');
    await page.getByRole('tab',{name:'Помощник',exact:true}).click();
    if(await page.locator('.clinic-shell__welcome-screen').count()!==1)throw Error('Switch changed dialogue');
    if(fixture.dialogue){
      await page.getByRole('textbox',{name:'Введите сообщение',exact:true}).fill('Сколько стоит лечение?');
      await page.getByRole('button',{name:'Отправить сообщение',exact:true}).click();
      const card=page.locator('[data-clinic-feed] .clinic-price-card');
      await card.locator('.clinic-price-card__volumes button').first().waitFor();
      await page.waitForFunction(()=>!document.querySelector('[data-clinic-feed] .clinic-price-card__volumes button').disabled);
      await layout('dialogue-overview');
      for(const [index,extent] of ['one_tooth','full_arch','unknown'].entries()){
        await card.locator('.clinic-price-card__volumes button').nth(index).click();
        await page.waitForFunction(()=>!document.querySelector('[data-clinic-feed] .clinic-price-card__volumes button').disabled);
        const ref=Object.keys(fixture.dialogue).find(key=>key.endsWith(':'+extent));
        const expected=fixture.dialogue[ref].ui.body_parts.find(part=>part.kind==='price_card');
        const amounts=await card.locator('.clinic-price-card__amount').allTextContents();
        if(JSON.stringify(amounts)!==JSON.stringify(expected.price.rows.map(row=>row.price_display_text)))throw Error('Volume prices changed '+extent);
        if(await card.count()!==1||await card.locator('.clinic-price-card__volumes button').count()!==3)throw Error('Volume appended/removed navigation');
        if(await page.locator('.clinic-msg--user').count()!==1)throw Error('Volume added user echo');
        await layout('dialogue-'+extent);
      }
      const asks=await page.evaluate(()=>window.askRequests);
      const expectedRevisions=[fixture.dialogue.initial.revision,...['one_tooth','full_arch'].map(extent=>fixture.dialogue[Object.keys(fixture.dialogue).find(key=>key.endsWith(':'+extent))].revision)];
      if(asks.length!==4||asks.slice(1).some((body,index)=>body.ui_revision!==expectedRevisions[index]))throw Error('Published volume revision lost: '+JSON.stringify(asks));
    }
  }
  if(failures.length)throw Error(failures.join('\n'));
  console.log(JSON.stringify({tenants:3,provider:0}));
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
