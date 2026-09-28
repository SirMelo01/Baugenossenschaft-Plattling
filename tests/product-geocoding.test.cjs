const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../yoolink/static/js/cms/products/product-geocoding.js'), 'utf8');

function result(number = '35', latitude = 48.78, street = 'Dr.-Kiefl-Straße', postcode = '94447', precision = 'ROOFTOP') {
  return { address_components: [['route', street], ['street_number', number], ['postal_code', postcode]]
    .map(([type, value]) => ({ types: [type], long_name: value })),
    geometry: { location_type: precision, location: { lat: () => latitude, lng: () => 12.87 } } };
}

function setup(respond) {
  const requests = [];
  const window = { google: { maps: { Geocoder: class {
    geocode(request, callback) { requests.push(request); respond(request, callback); }
  } } } };
  vm.runInNewContext(source, { window, setTimeout, clearTimeout, FormData });
  return { api: window.YooLinkProductGeocoding, requests };
}

function form(address = 'Dr.-Kiefl-Straße 35, 94447 Plattling', extra = {}) {
  const data = new FormData();
  for (const [key, value] of Object.entries({ address, ...extra })) data.set(key, value);
  return data;
}

test('new addresses resolve in the browser and produce bound automatic coordinates', async () => {
  const h = setup((request, done) => done([result(request.address.includes('37') ? '37' : '35')], 'OK'));
  for (const number of ['35', '37']) {
    const data = form(`Dr.-Kiefl-Straße ${number}, 94447 Plattling`);
    await h.api.prepare(data, 'existing-website-key');
    assert.equal(data.get('position_geocoded'), 'true');
    assert.equal(data.get('position_manual'), 'false');
    assert.equal(data.get('position_address'), data.get('address'));
    assert.equal(data.get('latitude'), '48.78');
    assert.equal(data.get('longitude'), '12.87');
  }
  assert.equal(h.requests.length, 2);
});

test('awaits the Google callback before allowing the save to continue', async () => {
  let finish;
  const h = setup((request, done) => { finish = done; });
  const data = form();
  let ready = false;
  const pending = h.api.prepare(data, 'website-key').then(() => { ready = true; });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ready, false);
  finish([result()], 'OK');
  await pending;
  assert.equal(ready, true);
  assert.equal(data.get('position_geocoded'), 'true');
});

test('manual pins and empty addresses skip lookup; changed addresses invalidate old manual pins', async () => {
  const h = setup((request, done) => done([result('37')], 'OK'));
  const manual = form(undefined, { position_manual: 'true', position_address: 'Dr.-Kiefl-Straße 35, 94447 Plattling', latitude: '48.7', longitude: '12.8' });
  await h.api.prepare(manual, 'key');
  assert.equal(h.requests.length, 0);
  assert.equal(manual.get('latitude'), '48.7');
  await h.api.prepare(form(''), 'key');
  assert.equal(h.requests.length, 0);
  manual.set('address', 'Dr.-Kiefl-Straße 37, 94447 Plattling');
  await h.api.prepare(manual, 'key');
  assert.equal(h.requests.length, 1);
  assert.equal(manual.get('position_manual'), 'false');
  assert.equal(manual.get('position_geocoded'), 'true');
});

test('a reset bypasses the page cache and replaces a manual pin with an automatic one', async () => {
  const h = setup((request, done) => done([result('35', 48.78 + h.requests.length / 1000)], 'OK'));
  const first = form();
  await h.api.prepare(first, 'key');
  await h.api.prepare(form(), 'key');
  assert.equal(h.requests.length, 1);
  const reset = form(undefined, { position_manual: 'true', position_reset: 'true', position_address: first.get('address') });
  await h.api.prepare(reset, 'key');
  assert.equal(h.requests.length, 2);
  assert.notEqual(reset.get('latitude'), first.get('latitude'));
  assert.equal(reset.get('position_manual'), 'false');
});

test('wrong houses, streets, postcodes and street centres are not accepted', () => {
  const h = setup(() => {});
  const address = form().get('address');
  for (const invalid of [result('37'), result('35', 48.78, 'Andere Straße'), result('35', 48.78, 'Dr.-Kiefl-Straße', '10115'),
    result('35', 48.78, 'Dr.-Kiefl-Straße', '94447', 'GEOMETRIC_CENTER'), result('35', NaN)]) {
    assert.equal(h.api.matchingPosition(address, [invalid]), null);
  }
  assert.equal(h.api.matchingPosition(address, [result()]).lat, 48.78);
  assert.equal(h.api.matchingPosition('Andere Str. 12 a 10115 Berlin', [result('12a', 52.5, 'Andere Straße', '10115')]).lat, 52.5);
});

test('district suffix is retried, provider errors are reported without changing to server geocoding', async () => {
  const h = setup((request, done) => done(request.address.includes('Höhenrain') ? [] : [result()], request.address.includes('Höhenrain') ? 'ZERO_RESULTS' : 'OK'));
  const data = form('Dr.-Kiefl-Straße 35, 94447 Plattling-Höhenrain');
  await h.api.prepare(data, 'key');
  assert.equal(h.requests.length, 2);
  assert.equal(data.get('position_address'), data.get('address'));
  assert.equal(data.get('position_geocoded'), 'true');
  for (const status of ['REQUEST_DENIED', 'OVER_QUERY_LIMIT', 'ZERO_RESULTS']) {
    const denied = setup((request, done) => done([], status));
    const attempt = form(undefined, { latitude: '48.7', longitude: '12.8' });
    await denied.api.prepare(attempt, 'key');
    assert.equal(denied.requests.length, 1);
    assert.equal(attempt.get('position_geocoded'), 'false');
    assert.equal(attempt.get('latitude'), '');
    assert.equal(attempt.get('position_geocoding_error'), status === 'ZERO_RESULTS' ? 'NO_MATCH' : status);
  }
});

test('script loader uses the website key for the Maps JavaScript API', async () => {
  let script;
  const window = {};
  const document = { createElement: () => ({ remove() {} }), head: { appendChild: value => { script = value; } } };
  vm.runInNewContext(source, { window, document, setTimeout, clearTimeout });
  const pending = window.YooLinkProductGeocoding.loadMaps('existing-website-key');
  const url = new URL(script.src);
  assert.equal(url.origin, 'https://maps.googleapis.com');
  assert.equal(url.pathname, '/maps/api/js');
  assert.equal(url.searchParams.get('key'), 'existing-website-key');
  window.google = { maps: { Geocoder: class {} } };
  window.yoolinkCmsGoogleMapsReady();
  assert.equal(await pending, window.google.maps);
});

test('multiple addresses have independent positions and a failed lookup does not stop the others', async () => {
  const h = setup((request, done) => {
    const number = request.address.match(/ (\d+),/)[1];
    done(number === '99' ? [] : [result(number, 48.7 + Number(number) / 1000)], number === '99' ? 'ZERO_RESULTS' : 'OK');
  });
  const addresses = ['35', '99', '37'].map(number => `Dr.-Kiefl-Straße ${number}, 94447 Plattling`);
  const entries = await h.api.prepareAddresses(addresses, 'existing-website-key');
  assert.equal(h.requests.length, 3);
  assert.equal(entries.length, 3);
  assert.equal(entries[0].position_geocoded, true);
  assert.equal(entries[2].position_geocoded, true);
  assert.notEqual(entries[0].latitude, entries[2].latitude);
  assert.equal(entries[1].position_geocoded, false);
  assert.equal(entries[1].latitude, '');
  entries.forEach((entry, index) => assert.equal(entry.position_address, addresses[index]));
});
