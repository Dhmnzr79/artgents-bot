"""Real widget rendering of mixed numeric/unpriced overview, offline API only."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.d2_ci_http import http_env
from tests.test_d2_http_contract import post
from tests.test_d2_price_cards_browser import RUNNER
from tests.test_nikadent_price_authority_offline import native, request


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Chrome/Playwright geometry proof")
def test_mixed_overview_descriptions_do_not_squeeze_titles_in_browser(http_env, tmp_path):
    client, _, use, _ = http_env
    wire = native(use, request("prosthetics", topic=True))
    initial = post(client, client_id="nikadent", sid="price-layout", q="Обзор").get_json()
    def choose(extent, previous, rid):
        response = post(client, client_id="nikadent", sid="price-layout", request_id=rid,
            q="", ref="volume:prosthetics:"+extent, ui_revision=previous["revision"])
        assert response.status_code == 200
        return response.get_json()
    full = choose("full_arch", initial, "full")
    one = choose("one_tooth", full, "one")
    assert len(wire.calls) == 2
    payloads = tmp_path / "no-public-payloads.json"
    payloads.write_text(json.dumps({"responses": {
        "Обзор": initial, "volume:prosthetics:full_arch": full,
        "volume:prosthetics:one_tooth": one}}, ensure_ascii=False), encoding="utf-8")
    bootstrap = RUNNER.split("  await send('Классическая имплантация');", 1)[0]
    bootstrap = bootstrap.replace("clientId:'demo'", "clientId:'nikadent'")
    runner = bootstrap + r'''
  await send('Обзор');
  await page.locator('.clinic-price-card').waitFor();
  await page.locator('.clinic-price-card__volumes button', {hasText:'Вся челюсть'}).click();
  await page.waitForFunction(() => document.querySelector('.clinic-price-card')?.textContent.includes('40'));
  const proof = [];
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({width,height:900});
    await page.waitForTimeout(150);
    const measurement = await page.locator('.clinic-price-card').evaluate(card => {
      const entries = [...card.querySelectorAll('.clinic-price-card__overview-row')];
      const captionStyle = getComputedStyle(card.querySelector('.clinic-price-card__caption'));
      return entries.map(row => {
        const name = row.querySelector('.clinic-price-card__overview-name');
        const value = row.querySelector('.clinic-price-card__amount');
        const r=row.getBoundingClientRect(), n=name.getBoundingClientRect(), a=value.getBoundingClientRect();
        const style = getComputedStyle(value);
        return {name:name.textContent, text:value.textContent, description:value.classList.contains('clinic-price-card__amount--description'),
          matchesCaption: ['fontFamily','fontSize','fontWeight','lineHeight','color'].every(key=>style[key]===captionStyle[key]),
          rowWidth:r.width, nameWidth:n.width, nameHeight:n.height, nameBottom:n.bottom,
          valueWidth:a.width,valueTop:a.top,overflow:row.scrollWidth>row.clientWidth+1};
      });
    });
    if (measurement.length!==3) throw new Error('Expected mixed3rows: '+JSON.stringify(measurement));
    const numeric = measurement.filter(r=>!r.description);
    if (numeric.length!==1 || !numeric[0].text.includes('40')) throw new Error('Numeric price changed');
    for (const row of measurement.filter(r=>r.description)) {
      if (!row.matchesCaption) throw new Error('Description typography differs from billing caption: '+JSON.stringify(row));
      if (row.nameWidth<row.rowWidth*0.75 || row.nameHeight>60 || row.valueWidth<row.rowWidth*0.75
          || row.valueTop<row.nameBottom-1 || row.overflow)
        throw new Error('Unpriced row squeezes/overlaps: '+JSON.stringify({width,...row}));
      if (row.text.includes(row.name)) throw new Error('Service name duplicated in description');
      if (!row.text.includes('после диагностики')) throw new Error('Authored description lost');
    }
    proof.push({width,measurement});
    if (process.env.PRICE_LAYOUT_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.PRICE_LAYOUT_SCREENSHOT_DIR,{recursive:true});
      await page.locator('.clinic-price-card').screenshot({path:path.join(process.env.PRICE_LAYOUT_SCREENSHOT_DIR,`price-layout-${width}.png`)});
    }
  }
  await page.locator('.clinic-price-card__volumes button', {hasText:'Один зуб'}).click();
  await page.waitForFunction(() => !document.querySelector('.clinic-price-card')?.textContent.includes('All-on-4'));
  if ((await page.locator('.clinic-price-card').count())!==1) throw new Error('Volume switch duplicated card');
  if (!(await page.locator('.clinic-price-card').textContent()).includes('22')) throw new Error('Numeric volume choices lost');
  if (failures.length) throw new Error(failures.join('\n'));
  console.log(JSON.stringify({passed:true,proof,provider:0}));
} finally { await browser.close(); await new Promise(r=>server.close(r)); }
'''
    result = subprocess.run(["node", "--input-type=module", "-"], input=runner,
        cwd=Path(__file__).resolve().parents[1], env={**os.environ,"CARDS_PAYLOADS":str(payloads)},
        text=True,encoding="utf-8",capture_output=True,timeout=60,check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    assert '\"passed\":true' in result.stdout
