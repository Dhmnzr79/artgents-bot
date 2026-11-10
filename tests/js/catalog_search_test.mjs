import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../../static/widget/catalog_search.js', import.meta.url), 'utf8');
const { matchesCatalogSearch: match } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
for (const query of ['имплан', 'имплонтация', 'имплатнация', 'имплантаци', 'импланттация', '  ИМПЛАНТАЦИЯ  ']) {
  assert.equal(match(['Классическая имплантация'], query), true, query);
}
assert.equal(match(['Элайнеры', 'прозрачные капы'], 'прозрачные капы'), true);
assert.equal(match(['Съёмное протезирование'], 'съемное протезирвоание'), true);
assert.equal(match(['Лечение кариеса'], 'лечение кареиса'), true);
assert.equal(match(['Имплантация All-on-4'], 'имплонтация all on 4'), true);
for (const query of ['имплонтация all on 6', 'отбеливание', 'zzzzzz', '!!!']) {
  assert.equal(match(['Имплантация All-on-4'], query), false, query);
}
assert.equal(match(['КТ'], 'КП'), false);
assert.equal(match(['Лечение кариеса'], 'лечение кариеса неизвестное'), false);
assert.equal(match(['Лечение кариеса'], ''), true);
console.log('Catalog search: all cases passed');
