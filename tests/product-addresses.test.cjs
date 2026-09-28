const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../yoolink/static/js/cms/products/product-addresses.js'), 'utf8');

function harness(addresses, lookup) {
  const rows = addresses.map(value => {
    const input = { value }, status = { textContent: '' };
    return { input, status, querySelector(selector) { return selector === 'input' ? input : status; } };
  });
  const root = { querySelectorAll() { return rows; } };
  const document = { querySelector() { return root; }, addEventListener() {} };
  const window = { YooLinkProductGeocoding: { prepareAddresses: lookup } };
  vm.runInNewContext(source, { document, window });
  const data = new FormData();
  data.set('address', 'Hauptstraße 1, 94447 Plattling');
  return { api: window.YooLinkProductAddresses, rows, data };
}

test('removed and blank rows are excluded while each remaining address is submitted', async () => {
  const h = harness(['Nebenstraße 35', 'Nebenstraße 37', ''], async addresses => addresses.map(address => ({ address, position_geocoded: true })));
  h.rows.splice(0, 1);
  await h.api.prepare(h.data, 'key');
  assert.deepEqual(JSON.parse(h.data.get('additional_addresses')), [{ address: 'Nebenstraße 37', position_geocoded: true }]);
  h.api.saved([{ address: 'Nebenstraße 37', lat: 48.78, lng: 12.87 }]);
  assert.equal(h.rows[0].status.textContent, 'Position gespeichert.');
});

test('editing, adding or removing a row during geocoding prevents submission of stale coordinates', async () => {
  for (const mutate of [h => { h.rows[0].input.value = 'Andere Straße 99'; }, h => { h.rows.pop(); }, h => { h.rows.push(h.rows[0]); }]) {
    let finish;
    const h = harness(['Nebenstraße 35'], () => new Promise(resolve => { finish = resolve; }));
    const pending = h.api.prepare(h.data, 'key');
    mutate(h);
    finish([{ address: 'Nebenstraße 35', position_geocoded: true }]);
    await assert.rejects(pending, /während der Suche geändert/);
    assert.equal(h.data.has('additional_addresses'), false);
  }
});

test('duplicate addresses are rejected before another geocoding request', async () => {
  for (const addresses of [[' HAUPTSTRASSE 1, 94447 Plattling '], ['Nebenstraße 35', 'nebenstraße   35']]) {
    let calls = 0;
    const h = harness(addresses, async () => { calls++; return []; });
    // Keep the primary identical apart from whitespace/case, without assuming ß transliteration.
    h.data.set('address', 'Hauptstrasse 1, 94447 Plattling');
    await assert.rejects(h.api.prepare(h.data, 'key'), /mehrfach/);
    assert.equal(calls, 0);
  }
});
