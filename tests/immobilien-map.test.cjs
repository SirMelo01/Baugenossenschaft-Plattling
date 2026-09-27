const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const filename = path.join(__dirname, '../yoolink/static/js/products/immobilien-map.js');
const { hasCoordinates } = require(filename);

test('invalid coordinates are excluded', () => {
  assert.equal(hasCoordinates({ lat: 48.7836862, lng: 12.8686252 }), true);
  for (const lat of [null, undefined, NaN, Infinity, '48', 91]) {
    assert.equal(hasCoordinates({ lat, lng: 12 }), false);
  }
});

function harness(consent = true) {
  const markers = [], polylines = [], mapInstances = [], popups = [];
  class Events {
    constructor() { this.events = {}; }
    addListener(name, fn) { this.events[name] = fn; }
    emit(name) { this.events[name]?.(); }
  }
  class Map extends Events {
    constructor() { super(); mapInstances.push(this); }
    getZoom() { return this.zoom; }
    setZoom(zoom) { this.zoom = zoom; this.emit('zoom_changed'); }
    setCenter(center) { this.center = center; }
    fitBounds() { this.setZoom(18); }
  }
  class Marker extends Events {
    constructor(options) { super(); Object.assign(this, options); markers.push(this); }
    setPosition(position) { this.position = position; }
    setVisible(visible) { this.visible = visible; }
  }
  class Polyline {
    constructor(options) { Object.assign(this, options); polylines.push(this); }
    setPath(points) { this.path = points; }
  }
  class InfoWindow {
    constructor() { popups.push(this); }
    setContent(content) { this.content = content; }
    open(options) { this.anchor = options.anchor; }
  }
  const entries = ['31', '33', '33a', '33b', '33b'].map((number, id) => ({
    id, title: 'Objekt ' + id, address: `Dr.-Kiefl-Straße ${number}, 94447 Plattling`,
    lat: 48.7836862, lng: 12.8686252, url: '/immobilien/' + id,
  }));
  function element() {
    return { classList: { toggle() {}, remove() {}, add() {} },
      scrollIntoView() {}, addEventListener(name, fn) { this[name] = fn; } };
  }
  const buttons = entries.map(entry => ({ ...element(), dataset: { mapFocus: String(entry.id) } }));
  const nodes = {};
  const root = { dataset: { mapApiKey: 'domain-restricted-key', locationsScript: 'locations' },
    querySelector(selector) { return nodes[selector] ||= element(); },
    querySelectorAll() { return buttons; } };
  const document = { events: {}, querySelectorAll() { return [root]; },
    getElementById() { return { textContent: JSON.stringify(entries) }; },
    createElement() { return { set textContent(text) { this.innerHTML = text; } }; },
    addEventListener(name, fn) { this.events[name] = fn; } };
  // Deliberately no Geocoder: Maps JavaScript must suffice.
  const maps = { Map, Marker, Polyline, InfoWindow, SymbolPath: { CIRCLE: 0 },
    Size: class {}, Point: class {}, LatLngBounds: class { extend() {} },
    event: { addListenerOnce(map, name, fn) { map.once = fn; } } };
  const window = { google: { maps }, YooLinkConsent: { categories: () => ({ external: consent }) } };
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), { window, document });
  document.events.DOMContentLoaded();
  return { markers, polylines, mapInstances, popups, buttons, root, entries };
}

test('map renders and focuses every object without Geocoder, even at the same address', async () => {
  const h = harness();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.root.dataset.mapReady, 'true');
  const selectable = h.markers.filter(marker => marker.clickable !== false);
  assert.equal(selectable.length, 5);
  assert.equal(h.markers.length, h.entries.length);
  assert.equal(h.polylines.length, 0);
  selectable.forEach(marker => {
    assert.equal(marker.icon, undefined, 'use the standard red Google pin');
    assert.equal(marker.label, undefined);
  });
  const map = h.mapInstances[0];
  map.once();
  for (const zoom of [14, 16, 19, 21]) {
    map.setZoom(zoom);
    selectable.forEach((marker, id) => {
      assert.equal(marker.position.lat, h.entries[id].lat);
      assert.equal(marker.position.lng, h.entries[id].lng);
    });
  }
  h.buttons.forEach((button, id) => {
    button.click();
    assert.equal(h.popups[0].anchor, selectable[id]);
    assert.ok(h.popups[0].content.includes('Objekt ' + id));
    assert.equal(map.center.lat, h.entries[id].lat);
    selectable[id].emit('click');
    assert.equal(h.popups[0].anchor, selectable[id]);
  });
});

test('without consent no map is constructed', async () => {
  const h = harness(false);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.mapInstances.length, 0);
  assert.equal(h.markers.length, 0);
});
