/**
 * Objektkarte auf der Immobilienseite (Google Maps).
 *
 * Die Koordinaten stehen bereits im Seitenquelltext: sie werden beim Speichern
 * im CMS aus der Adresse bestimmt (oder dort von Hand korrigiert) und am Objekt
 * gespeichert. Diese Gebaeudepositionen werden serverseitig ausgegeben.
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

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { hasCoordinates: hasCoordinates };
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
      entries.forEach(function (entry) {
        var position = { lat: entry.lat, lng: entry.lng };
        // Google's standard red pin sits directly on the building coordinate.
        // Pins may overlap when zoomed out; no offsets or connector lines.
        var marker = new maps.Marker({
          map: map, position: position, title: entry.title + " - " + entry.address,
        });
        var record = { entry: entry, marker: marker };
        marker.addListener("click", function () { openInfo(record); });
        byId[entry.id] = record;
        bounds.extend(position);
      });

      function openInfo(record) {
        infoWindow.setContent(popupHtml(record.entry));
        infoWindow.open({ anchor: record.marker, map: map });
      }

      if (entries.length === 1) {
        map.setCenter({ lat: entries[0].lat, lng: entries[0].lng });
        map.setZoom(INITIAL_ZOOM);
      } else {
        map.fitBounds(bounds, 100);
        maps.event.addListenerOnce(map, "idle", function () {
          if (map.getZoom() > INITIAL_ZOOM) map.setZoom(INITIAL_ZOOM);
        });
      }

      root.querySelectorAll("[data-map-focus]").forEach(function (button) {
        var record = byId[button.dataset.mapFocus];
        if (!record) return;
        button.classList.remove("hidden");
        button.classList.add("inline-flex");
        button.addEventListener("click", function () {
          map.setCenter({ lat: record.entry.lat, lng: record.entry.lng });
          if (map.getZoom() < FOCUS_ZOOM) map.setZoom(FOCUS_ZOOM);
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
