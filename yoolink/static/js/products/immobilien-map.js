/**
 * Objektkarte auf der Immobilienseite (Google Maps).
 *
 * Die Koordinaten stehen bereits im Seitenquelltext: sie werden beim Speichern
 * im CMS aus der Adresse bestimmt und am Objekt gespeichert. Hier wird deshalb
 * nichts mehr umgerechnet - die Karte setzt nur noch Marker.
 *
 * Google Maps ist ein externes Medium, die Karte laedt daher erst nach der
 * Cookie-Einwilligung. Bis dahin (und wenn das Laden scheitert) bleibt die
 * Adressliste daneben stehen.
 */
(function () {
  "use strict";

  var MAPS_CALLBACK = "yoolinkGoogleMapsReady";
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
    var html = '<div style="min-width:12rem">'
      + '<strong>' + escapeHtml(entry.title) + '</strong>'
      + '<br><span>' + escapeHtml(entry.address) + '</span>'
      + '<br><a href="' + escapeHtml(entry.url) + '">Details ansehen</a>';
    if (entry.maps_url) {
      html += ' &middot; <a href="' + escapeHtml(entry.maps_url) + '" target="_blank" rel="noopener">Route</a>';
    }
    return html + "</div>";
  }

  function hasCoordinates(entry) {
    return typeof entry.lat === "number" && typeof entry.lng === "number";
  }

  /**
   * "Auf Karte zeigen" neben jeder Adresse aktivieren.
   *
   * Der Knopf steht erst zur Verfuegung, wenn die Karte wirklich da ist - ohne
   * Einwilligung oder nach einem Ladefehler wuerde er ins Leere fuehren.
   */
  function connectList(root, markers, showEntry) {
    root.querySelectorAll("[data-map-focus]").forEach(function (button) {
      var entryId = button.dataset.mapFocus;
      if (!markers[entryId]) {
        return;
      }

      button.classList.remove("hidden");
      button.classList.add("inline-flex");
      button.addEventListener("click", function () {
        showEntry(entryId);
      });
    });
  }

  function buildMap(root, canvas, entries) {
    return loadGoogleMaps(root.dataset.mapApiKey).then(function (maps) {
      var map = new maps.Map(canvas, {
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        // Ohne "cooperative" zoomt das Mausrad die Karte statt die Seite zu scrollen.
        gestureHandling: "cooperative",
      });

      var infoWindow = new maps.InfoWindow();
      var bounds = new maps.LatLngBounds();
      var markers = {};
      var entriesById = {};

      entries.forEach(function (entry) {
        var position = { lat: entry.lat, lng: entry.lng };
        var marker = new maps.Marker({ map: map, position: position, title: entry.title });

        marker.addListener("click", function () {
          infoWindow.setContent(popupHtml(entry));
          infoWindow.open({ anchor: marker, map: map });
        });

        markers[entry.id] = marker;
        entriesById[entry.id] = entry;
        bounds.extend(position);
      });

      if (entries.length === 1) {
        map.setCenter({ lat: entries[0].lat, lng: entries[0].lng });
        map.setZoom(15);
      } else {
        map.fitBounds(bounds, 48);
      }

      connectList(root, markers, function (entryId) {
        var marker = markers[entryId];
        map.panTo(marker.getPosition());
        infoWindow.setContent(popupHtml(entriesById[entryId]));
        infoWindow.open({ anchor: marker, map: map });
        canvas.scrollIntoView({ behavior: "smooth", block: "center" });
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
