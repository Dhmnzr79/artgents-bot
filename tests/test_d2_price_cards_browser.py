"""Real widget DOM with real offline-produced D2 receipts; no live provider."""
import json
import os
import subprocess
from pathlib import Path

from tests.test_d2_http_contract import FakeProvider, http_env, post
from tests.test_d2_sim2_dialogues import raw, price, explanation, forbidden


RUNNER = r'''
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require(process.env.PLAYWRIGHT_MODULE ||
  'C:/Users/denis/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'); }
const root = process.cwd();
const fixtures = JSON.parse(fs.readFileSync(process.env.CARDS_PAYLOADS, 'utf8'));
const server = http.createServer((req, res) => {
  if (req.url === '/') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<link rel="stylesheet" href="/static/widget/widget.css"></head><body style="margin:0"><div id="root"></div></body></html>');
    return;
  }
  const filename = path.resolve(root, '.' + req.url);
  if (!filename.startsWith(path.join(root, 'static') + path.sep) || !fs.existsSync(filename)) {
    res.writeHead(404); res.end(); return;
  }
  res.setHeader('Content-Type', filename.endsWith('.js') ? 'text/javascript' :
    filename.endsWith('.css') ? 'text/css' : 'application/octet-stream');
  res.end(fs.readFileSync(filename));
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const browser = await playwright.chromium.launch({headless:true,
  args:[`--explicitly-allowed-ports=${server.address().port}`],
  executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try {
  const page = await browser.newPage({viewport:{width:390, height:844}});
  const failures = [];
  page.on('pageerror', e => failures.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(async fixtures => {
    const {mountWidget} = await import('/static/widget/widget.js');
    window.sent = [];
    window.failedSelectionAttempts = 2;
    window.fetch = async (url, options) => {
      if (String(url).includes('video-catalog')) return new Response('{"videos":{}}');
      if (!String(url).endsWith('/ask/stream')) throw new Error('Unexpected request: '+url);
      const body = JSON.parse(options.body);
      window.sent.push(body);
      if (body.ref && window.failedSelectionAttempts > 0) {
        window.failedSelectionAttempts--;
        throw new TypeError('Failed to fetch');
      }
      if (body.ref) await new Promise(resolve => setTimeout(resolve,
        body.ref.endsWith('.nobel') ? 4000 : 300));
      const selected = body.ref?.endsWith('.nobel') ? fixtures.nobel :
        body.ref?.endsWith('.implantium') ? fixtures.back : body.ref ? fixtures.selected : body.q === 'Отбеливание' ? fixtures.whitening :
        body.q === 'Цена без суммы' ? fixtures.noPublic : body.q === 'Обычный ответ' ? fixtures.plain : fixtures.first;
      const payload = {...selected, sid:body.sid || selected.sid, request_id:body.request_id};
      return new Response('event: ui\ndata: '+JSON.stringify(payload)+'\n\nevent: done\ndata: {}\n\n',
        {headers:{'content-type':'text/event-stream'}});
    };
    mountWidget(document.querySelector('#root'), {schemaVersion:1,apiBase:location.origin,
      clientId:'demo',botName:'Надежда',onlineLabel:'ИИ-консультант клиники',
      welcomeText:'Здравствуйте!',starterPrompts:[],launcherCtaLabel:'Посмотреть демо',
      launcherSubtitle:null,videoAspect:'horizontal',demoLauncher:true,launcherTeaser:false});
    document.querySelector('[data-clinic-launcher-open], [data-clinic-launcher]').click();
  }, fixtures);
  await page.evaluate(() => {
    window.streamedBubbles = 0;
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) {
        if (node.nodeType === 1 && (node.matches('[data-live-bubble]') || node.querySelector('[data-live-bubble]')))
          window.streamedBubbles++;
      }
    }).observe(document.querySelector('#root'), {childList:true,subtree:true});
  });
  const send = async q => {
    await page.locator('[data-clinic-input]').fill(q);
    await page.locator('[data-clinic-send]').click();
  };
  await send('Классическая имплантация');
  await page.locator('.clinic-price-card').waitFor();
  const cards = page.locator('.clinic-price-card');
  if (await cards.count() !== 1) throw new Error('Price duplicated');
  if (await cards.locator('button').count() !== 3) throw new Error('Missing brands');
  if (!(await cards.textContent()).includes('76')) throw new Error('Missing exact price');
  if ((await page.locator('.clinic-turn .clinic-msg__body').allTextContents()).some(t => t.includes('76 200')))
    throw new Error('Duplicate prose price');
  const initialSid = fixtures.first.sid;
  const initialBodies = await page.locator('.clinic-turn:not(.clinic-turn--error)').count();
  const initialUsers = await page.locator('.clinic-msg--user').count();
  const activePrice = cards.locator('.clinic-price-card__amount');
  if (await cards.locator('[aria-pressed="true"]').innerText() !== 'Implantium') throw new Error('Initial tab not opened');
  await cards.locator('button', {hasText:'Impro'}).click();
  await page.locator('[data-clinic-err]').waitFor();
  if (!(await activePrice.innerText()).includes('76')) throw new Error('Failed request changed visible price');
  if (await cards.locator('[aria-pressed="true"]').innerText() !== 'Implantium') throw new Error('Optimistic tab change');
  await page.getByRole('button', {name:'Повторить запрос',exact:true}).click();
  await page.waitForFunction(() => document.querySelector('.clinic-price-card__amount').textContent.includes('85'));
  const chosen = cards.last();
  if (!(await chosen.textContent()).includes('85')) throw new Error('Chosen offer not rendered');
  if (await cards.count() !== 1 || await page.locator('.clinic-msg--user').count() !== initialUsers
      || await page.locator('.clinic-turn:not(.clinic-turn--error)').count() !== initialBodies)
    throw new Error('Tab click appended a dialogue turn');
  if (await chosen.locator('button:enabled').count() !== 3) throw new Error('Tabs lost after selection');
  if (!(await page.locator('#root').textContent()).includes('Адрес')) throw new Error('Independent address lost');
  // Observe every animation frame, including pending and final renders. A
  // settled final position alone misses the up/down jump reported by the owner.
  await page.waitForTimeout(600);
  await page.evaluate(() => {
    const card = document.querySelector('.clinic-price-card');
    let scroller = card.parentElement;
    while (scroller && !['auto','scroll'].includes(getComputedStyle(scroller).overflowY))
      scroller = scroller.parentElement;
    if (!scroller || scroller.scrollHeight <= scroller.clientHeight + 40)
      throw new Error('Scroll fixture has no scrollable content');
    scroller.scrollTo({top:40,behavior:'instant'});
    window.cardTopBefore = card.getBoundingClientRect().top;
    window.cardTops = [];
    window.selectionWaitingIndicators = 0;
    window.observeCardScroll = true;
    const sample = () => {
      window.cardTops.push(document.querySelector('.clinic-price-card').getBoundingClientRect().top);
      if (document.querySelector('.clinic-shell__typing-wrap.is-visible'))
        window.selectionWaitingIndicators++;
      if (window.observeCardScroll) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
    [...card.querySelectorAll('button')].find(b => b.textContent.includes('Nobel')).click();
  });
  await page.waitForFunction(() => document.querySelector('.clinic-price-card__amount').textContent.includes('101'));
  await page.waitForTimeout(600);
  const scroll = await page.evaluate(() => {
    window.observeCardScroll = false;
    return {before:window.cardTopBefore,tops:window.cardTops,
      waitingIndicators:window.selectionWaitingIndicators};
  });
  if (scroll.tops.length < 10 || scroll.tops.some(top => Math.abs(top-scroll.before)>1))
    throw new Error('Brand switch moved card viewport: '+JSON.stringify(scroll));
  if (scroll.waitingIndicators)
    throw new Error('Brand switch displayed a waiting indicator');
  await chosen.locator('button', {hasText:'Implantium'}).click();
  await page.waitForFunction(() => document.querySelector('.clinic-price-card__amount').textContent.includes('76'));
  const sent = await page.evaluate(() => window.sent);
  if (sent.length !== 6 || sent[1].ref !== 'price_select:classic.one_tooth.impro'
      || sent[1].ui_revision !== fixtures.first.revision || sent[1].q !== '' || sent[1].sid !== initialSid)
    throw new Error('UI authority or session lost: '+JSON.stringify(sent));
  if (JSON.stringify(sent[1]) !== JSON.stringify(sent[2]) || JSON.stringify(sent[1]) !== JSON.stringify(sent[3]))
    throw new Error('Retry did not preserve exact request');
  if (sent[4].ui_revision !== fixtures.selected.revision || sent[5].ui_revision !== fixtures.nobel.revision
      || sent.slice(1).some(body => body.priceMessage || body.userEcho || body.sid !== initialSid || body.q !== ''))
    throw new Error('Selection binding leaked or revision did not advance');
  if (await cards.count() !== 1 || await page.locator('.clinic-msg--user').count() !== initialUsers)
    throw new Error('Repeated switching duplicated card or user bubble');
  for (const width of [390,360]) {
    await page.setViewportSize({width,height:844});
    const measurements = await chosen.evaluate(el => {
      const text = el.querySelector('.clinic-price-card__condition');
      return {body:getComputedStyle(el).fontSize,note:getComputedStyle(text).fontSize,
        overflow:el.scrollWidth>el.clientWidth+1};
    });
    if (measurements.body !== '16px' || measurements.note !== '14px' || measurements.overflow)
      throw new Error('Small font or overflow: '+JSON.stringify(measurements));
  }
  await page.setViewportSize({width:390,height:844});
  await chosen.scrollIntoViewIfNeeded();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({path:process.env.CARDS_SCREENSHOT,fullPage:true});
  await send('Отбеливание');
  await page.waitForFunction(() => document.querySelectorAll('.clinic-price-card').length === 2);
  if (await cards.first().locator('button:disabled').count() !== 3) throw new Error('Historical tabs still active');
  const whitening = cards.last();
  if (!(await whitening.textContent()).includes('от 18')) throw new Error('From qualifier missing');
  if (await whitening.locator('button').count()) throw new Error('Invented brand choice');
  await send('Цена без суммы');
  await page.waitForFunction(() => document.querySelectorAll('.clinic-price-card').length === 3);
  const noPublic = cards.last();
  if (!(await noPublic.textContent()).includes('Стоимость определяют после осмотра.')) throw new Error('Approved text lost');
  if (await noPublic.locator('.clinic-price-card__amount').evaluate(el => getComputedStyle(el).fontSize) !== '16px')
    throw new Error('Approved description has giant numeric font');
  if (await page.evaluate(() => window.streamedBubbles) !== 0)
    throw new Error('Card was preceded by transient typed prose');
  await send('Обычный ответ');
  await page.waitForFunction(() => window.streamedBubbles > 0);
  await page.waitForFunction(() => !document.querySelector('[data-live-bubble]') &&
    document.querySelector('#root').textContent.includes('Обычный текстовый ответ сохраняет постепенное появление текста.'));
  if (await cards.count() !== 3) throw new Error('Ordinary prose created a card');
  if (failures.length) throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,widths:[390,360],provider:0}));
} finally { await browser.close(); await new Promise(r=>server.close(r)); }
'''


def test_real_card_fonts_selection_and_session_in_browser(http_env, tmp_path):
    client, _, use, tmp = http_env
    fake = use(FakeProvider(raw(price("classic", "service"),
        {"kind":"contact","request_id":"r2","contact_fields":["contact_address"]})))
    first = post(client, q="Классическая имплантация").get_json()
    fake.generate = forbidden
    selected_response = post(client, request_id="selected", q="",
        ref="price_select:classic.one_tooth.impro", ui_revision=first["revision"])
    assert selected_response.status_code == 200
    nobel = post(client, request_id="nobel", q="", ref="price_select:classic.one_tooth.nobel",
                 ui_revision=selected_response.get_json()["revision"])
    assert nobel.status_code == 200
    back = post(client, request_id="back", q="", ref="price_select:classic.one_tooth.implantium",
                ui_revision=nobel.get_json()["revision"])
    assert back.status_code == 200
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = raw(price("professional_whitening", "service"))
    whitening = post(client, request_id="white", q="Отбеливание").get_json()
    filename = tmp / "clients/demo/target_response/pricebook/services/professional_whitening.default.json"
    offer = json.loads(filename.read_text(encoding="utf-8"))
    offer["price"] = {"mode":"no_public_price","approved_text":"Стоимость определяют после осмотра."}
    filename.write_text(json.dumps(offer,ensure_ascii=False),encoding="utf-8")
    no_public_response = post(client, sid="no-public-card", request_id="no-public", q="Отбеливание")
    assert no_public_response.status_code == 200
    fake.raw = raw(explanation("Обычный текстовый ответ сохраняет постепенное появление текста."))
    plain = post(client, sid="no-public-card", request_id="plain", q="Обычный ответ").get_json()
    payloads = tmp_path / "payloads.json"
    payloads.write_text(json.dumps({"first":first,"selected":selected_response.get_json(),
                                   "nobel":nobel.get_json(),"back":back.get_json(),
                                   "whitening":whitening,"noPublic":no_public_response.get_json(),
                                   "plain":plain},ensure_ascii=False),encoding="utf-8")
    screenshot = os.environ.get("D2_CARDS_SCREENSHOT", str(tmp_path / "price-cards.png"))
    env = {**os.environ, "CARDS_PAYLOADS":str(payloads), "CARDS_SCREENSHOT":screenshot}
    result = subprocess.run(["node", "--input-type=module", "-"], input=RUNNER,
        cwd=Path(__file__).resolve().parents[1], env=env, text=True,encoding="utf-8",
        capture_output=True,timeout=80,check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
    assert len(fake.inputs) == 4
