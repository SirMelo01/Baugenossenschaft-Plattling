/**
 * Objektkarte auf der Immobilienseite (Google Maps).
 *
 * Die Koordinaten stehen bereits im Seitenquelltext: sie werden beim Speichern
 * im CMS aus der Adresse bestimmt (oder dort von Hand korrigiert) und am Objekt
 * gespeichert. Gepruefte Gebaeudepositionen werden serverseitig ausgegeben.
 * Der Browser verwendet ausschliesslich die Maps JavaScript API.
 *
 * Google Maps ist ein externes Medium, die Karte laedt daher erst nach der
 * Cookie-Einwilligung. Bis dahin (und wenn das Laden scheitert) bleibt die
 * Adressliste daneben stehen.
 */
(function () {
  "use strict";

  var MAPS_CALLBACK = "yoolinkGoogleMapsReady";
  var INITIAL_ZOOM = 16;
  var FOCUS_ZOOM = 19;
  var BRAND_NAVY = "#2E434C";
  var mapsPromise = null;

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function externalConsentAllowed() {
    if (!window.YooLinkConsent || typeof window.YooLinkConsent.categories !== "function") {
      return false;
    }
    return Boolean(window.YooLinkConsent.categories().external);
  }

  function parseLocations(root) {
    var scriptId = root.dataset.locationsScript;
    var script = scriptId ? document.getElementById(scriptId) : null;
    if (!script) {
      return [];
    }

    try {
      var parsed = JSON.parse(script.textContent || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function setVisible(node, visible, flex) {
    if (!node) {
      return;
    }
    node.classList.toggle("hidden", !visible);
    if (flex) {
      node.classList.toggle("flex", visible);
    }
  }

  function loadGoogleMaps(apiKey) {
    if (window.google && window.google.maps) {
      return Promise.resolve(window.google.maps);
    }

    if (mapsPromise) {
      return mapsPromise;
    }

    mapsPromise = new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[data-map-lib="google-maps"]');
      if (existing) {
        existing.addEventListener("error", reject);
        return;
      }

      window[MAPS_CALLBACK] = function () {
        resolve(window.google.maps);
      };

      var script = document.createElement("script");
      script.src = "https://maps.googleapis.com/maps/api/js"
        + "?key=" + encodeURIComponent(apiKey)
        + "&language=de&region=DE&loading=async&callback=" + MAPS_CALLBACK;
      script.async = true;
      script.dataset.mapLib = "google-maps";
      script.onerror = reject;
      document.head.appendChild(script);
    });

    return mapsPromise;
  }

  function popupHtml(entry) {
    return '<div style="min-width:13rem;max-width:20rem">'
      + '<strong>' + escapeHtml(entry.address) + '</strong><br>'
      + '<a href="' + escapeHtml(entry.url) + '">' + escapeHtml(entry.title) + '</a>'
      + (entry.maps_url ? '<br><a href="' + escapeHtml(entry.maps_url)
        + '" target="_blank" rel="noopener">Route</a>' : '') + '</div>';
  }

  function hasCoordinates(entry) {
    return Number.isFinite(entry.lat) && Number.isFinite(entry.lng)
      && Math.abs(entry.lat) <= 85.05112878 && Math.abs(entry.lng) <= 180;
  }

  function worldPixel(position, zoom) {
    var scale = 256 * Math.pow(2, zoom);
    var sin = Math.sin(position.lat * Math.PI / 180);
    return {
      x: (position.lng + 180) / 360 * scale,
      y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale,
    };
  }

  function fromWorldPixel(point, zoom) {
    var scale = 256 * Math.pow(2, zoom);
    return {
      lat: Math.atan(Math.sinh(Math.PI * (1 - 2 * point.y / scale))) * 180 / Math.PI,
      lng: point.x / scale * 360 - 180,
    };
  }

  // Fixed 40 x 32 px labels, with an 8 px gap. Coordinates remain immutable;
  // only the label moves, with a leader line back to the building position.
  function layoutMarkers(entries, zoom) {
    var placed = [];
    return entries.map(function (entry) {
      var origin = worldPixel(entry, zoom);
      var point = { x: origin.x, y: origin.y };
      function overlaps(candidate) {
        return placed.some(function (other) {
          return Math.abs(candidate.x - other.x) < 48
            && Math.abs(candidate.y - other.y) < 40;
        });
      }
      // Expand a rectangular ring until a free label position exists. There is
      // no fallback that piles remaining markers onto an occupied position.
      for (var ring = 1; overlaps(point); ring++) {
        var candidates = [];
        for (var offset = -ring; offset <= ring; offset++) {
          candidates.push({ x: origin.x + offset * 48, y: origin.y - ring * 40 });
          candidates.push({ x: origin.x + offset * 48, y: origin.y + ring * 40 });
          if (Math.abs(offset) !== ring) {
            candidates.push({ x: origin.x - ring * 48, y: origin.y + offset * 40 });
            candidates.push({ x: origin.x + ring * 48, y: origin.y + offset * 40 });
          }
        }
        candidates.sort(function (a, b) {
          return Math.hypot(a.x - origin.x, a.y - origin.y)
            - Math.hypot(b.x - origin.x, b.y - origin.y);
        });
        var free = candidates.find(function (candidate) { return !overlaps(candidate); });
        if (free) point = free;
      }
      placed.push(point);
      return { position: fromWorldPixel(point, zoom), pixel: point,
        displaced: point.x !== origin.x || point.y !== origin.y };
    });
  }

  function markerLabel(entry, index) {
    var match = String(entry.address || "").split(",")[0].match(/(\d+[a-zA-Z]?)\s*$/);
    return match && match[1].length <= 4 ? match[1].toLowerCase() : String(index + 1);
  }

  // These pure functions can be checked without an API key or browser.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { layoutMarkers: layoutMarkers, worldPixel: worldPixel,
      fromWorldPixel: fromWorldPixel, hasCoordinates: hasCoordinates, markerLabel: markerLabel };
    return;
  }

  function buildMap(root, canvas, entries) {
    return loadGoogleMaps(root.dataset.mapApiKey).then(function (maps) {
      var map = new maps.Map(canvas, {
        mapTypeControl: false, streetViewControl: false, fullscreenControl: true,
        gestureHandling: "cooperative", heading: 0, tilt: 0,
      });
      var infoWindow = new maps.InfoWindow();
      var bounds = new maps.LatLngBounds();
      var byId = {};
      // Stable ordering keeps displacement predictable when the list is sorted.
      entries = entries.slice().sort(function (a, b) {
        return String(a.id).localeCompare(String(b.id), "en", { numeric: true });
      });
      var records = entries.map(function (entry, index) {
        var position = { lat: entry.lat, lng: entry.lng };
        var marker = new maps.Marker({
          map: map, position: position, title: entry.title + " - " + entry.address,
          optimized: false,
          label: { text: markerLabel(entry, index), color: "#ffffff", fontWeight: "700", fontSize: "12px" },
          icon: {
            url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(
              '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="32" viewBox="0 0 40 32">'
              + '<rect x="1" y="1" width="38" height="30" rx="10" fill="'
              + BRAND_NAVY + '" stroke="white" stroke-width="2"/></svg>'),
            scaledSize: new maps.Size(40, 32), anchor: new maps.Point(20, 16),
            labelOrigin: new maps.Point(20, 16),
          },
          zIndex: 100 + index,
        });
        var line = new maps.Polyline({ map: map, clickable: false,
          strokeColor: BRAND_NAVY, strokeOpacity: 0.85, strokeWeight: 2, zIndex: 1 });
        var anchor = new maps.Marker({ map: map, position: position, clickable: false,
          visible: false, zIndex: 2,
          icon: { path: maps.SymbolPath.CIRCLE, scale: 4, fillColor: BRAND_NAVY,
            fillOpacity: 1, strokeColor: "#ffffff", strokeWeight: 1 } });
        var record = { entry: entry, marker: marker, line: line, anchor: anchor };
        marker.addListener("click", function () { openInfo(record); });
        byId[entry.id] = record;
        bounds.extend(position);
        return record;
      });

      function openInfo(record) {
        infoWindow.setContent(popupHtml(record.entry));
        infoWindow.open({ anchor: record.marker, map: map });
      }

      function arrange() {
        var zoom = map.getZoom();
        if (!Number.isFinite(zoom)) return;
        layoutMarkers(entries, zoom).forEach(function (layout, index) {
          var record = records[index];
          record.marker.setPosition(layout.position);
          record.line.setPath(layout.displaced ? [
            { lat: record.entry.lat, lng: record.entry.lng }, layout.position,
          ] : []);
          record.anchor.setVisible(layout.displaced);
        });
      }
      map.addListener("zoom_changed", arrange);
      if (entries.length === 1) {
        map.setCenter({ lat: entries[0].lat, lng: entries[0].lng });
        map.setZoom(INITIAL_ZOOM);
      } else {
        map.fitBounds(bounds, 100);
        maps.event.addListenerOnce(map, "idle", function () {
          if (map.getZoom() > INITIAL_ZOOM) map.setZoom(INITIAL_ZOOM);
          arrange();
        });
      }
      arrange();

      root.querySelectorAll("[data-map-focus]").forEach(function (button) {
        var record = byId[button.dataset.mapFocus];
        if (!record) return;
        button.classList.remove("hidden");
        button.classList.add("inline-flex");
        button.addEventListener("click", function () {
          map.setCenter({ lat: record.entry.lat, lng: record.entry.lng });
          if (map.getZoom() < FOCUS_ZOOM) map.setZoom(FOCUS_ZOOM);
          arrange();
          openInfo(record);
          canvas.scrollIntoView({ behavior: "smooth", block: "center" });
        });
      });
      root.dataset.mapReady = "true";
    });
  }

  function renderMap(root, locations) {
    var canvas = root.querySelector("[data-map-canvas]");
    var placeholder = root.querySelector("[data-map-placeholder]");
    var empty = root.querySelector("[data-map-empty]");
    var error = root.querySelector("[data-map-error]");
    var entries = locations.filter(hasCoordinates);

    if (!locations.length) {
      setVisible(canvas, false);
      setVisible(placeholder, false, true);
      setVisible(error, false, true);
      setVisible(empty, true, true);
      return;
    }

    // Ohne API-Key oder ohne eine einzige gefundene Adresse gibt es nichts zu
    // zeigen - die Liste daneben bleibt aber vollstaendig.
    if (!root.dataset.mapApiKey || !entries.length) {
      setVisible(canvas, false);
      setVisible(placeholder, false, true);
      setVisible(empty, false, true);
      setVisible(error, true, true);
      return;
    }

    if (!externalConsentAllowed()) {
      setVisible(canvas, false);
      setVisible(empty, false, true);
      setVisible(error, false, true);
      setVisible(placeholder, true, true);
      return;
    }

    setVisible(placeholder, false, true);
    setVisible(empty, false, true);
    setVisible(error, false, true);
    setVisible(canvas, true);

    // "loading" verhindert, dass eine zweite Einwilligungsmeldung waehrend des
    // Ladens eine zweite Karte in dieselbe Flaeche baut.
    if (root.dataset.mapReady) {
      return;
    }
    root.dataset.mapReady = "loading";

    buildMap(root, canvas, entries).catch(function () {
      root.dataset.mapReady = "";
      setVisible(canvas, false);
      setVisible(error, true, true);
    });
  }

  function init() {
    document.querySelectorAll("[data-immobilien-map]").forEach(function (root) {
      renderMap(root, parseLocations(root));
    });
  }

  /**
   * Einen abgelehnten API-Key meldet Google nicht ueber das Skript, sondern nur
   * ueber diesen globalen Rueckruf. Ohne ihn bliebe eine graue Flaeche stehen -
   * so tritt stattdessen der Hinweis mit der Adressliste an ihre Stelle.
   */
  window.gm_authFailure = function () {
    document.querySelectorAll("[data-immobilien-map]").forEach(function (root) {
      root.dataset.mapReady = "";
      setVisible(root.querySelector("[data-map-canvas]"), false);
      setVisible(root.querySelector("[data-map-error]"), true, true);
    });
  };

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("yoolink:consentChanged", init);
})();
