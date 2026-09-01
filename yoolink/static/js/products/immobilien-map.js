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
  // Startansicht: weit genug heraus, dass die Objekte im Ort verortet sind.
  var INITIAL_ZOOM = 14;
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

  function popupHtml(group) {
    var first = group.entries[0];
    var html = '<div style="min-width:13rem">'
      + '<strong>' + escapeHtml(first.address) + '</strong>';

    if (group.entries.length > 1) {
      html += '<br><span>' + group.entries.length + ' Objekte an dieser Adresse</span>';
    }

    html += '<ul style="margin:0.4rem 0 0;padding-left:1.1rem">';
    group.entries.forEach(function (entry) {
      html += '<li><a href="' + escapeHtml(entry.url) + '">' + escapeHtml(entry.title) + '</a></li>';
    });
    html += '</ul>';

    if (first.maps_url) {
      html += '<a href="' + escapeHtml(first.maps_url) + '" target="_blank" rel="noopener">Route</a>';
    }
    return html + "</div>";
  }

  function hasCoordinates(entry) {
    return typeof entry.lat === "number" && typeof entry.lng === "number";
  }

  /**
   * Objekte mit derselben Anschrift zu einem Marker zusammenfassen.
   *
   * Mehrere Wohnungen in einem Haus tragen dieselbe Adresse und damit dieselben
   * Koordinaten. Ohne Gruppierung liegen ihre Marker exakt uebereinander - auf der
   * Karte ist dann nur einer zu sehen und die anderen Objekte wirken, als fehlten
   * sie. Ein Marker je Anschrift mit der Anzahl darin zeigt stattdessen, was dort
   * steht.
   *
   * Gruppiert wird ausschliesslich ueber die Anschrift, nicht ueber die Koordinaten:
   * zwei Nachbarhaeuser liegen wenige Meter auseinander und wuerden sonst in einem
   * Marker verschwinden, obwohl es zwei verschiedene Objekte an zwei Adressen sind.
   */
  function groupByAddress(entries) {
    var groups = [];
    var byKey = {};

    entries.forEach(function (entry) {
      var key = (entry.address || "").trim().replace(/\s+/g, " ").toLowerCase();
      if (!byKey[key]) {
        byKey[key] = { lat: entry.lat, lng: entry.lng, entries: [] };
        groups.push(byKey[key]);
      }
      byKey[key].entries.push(entry);
    });

    return groups;
  }

  function groupTitle(group) {
    if (group.entries.length === 1) {
      return group.entries[0].title;
    }
    return group.entries[0].address + " (" + group.entries.length + " Objekte)";
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
      var groups = groupByAddress(entries);
      var markers = {};
      var groupsByEntry = {};

      groups.forEach(function (group) {
        var position = { lat: group.lat, lng: group.lng };
        var options = { map: map, position: position, title: groupTitle(group) };

        if (group.entries.length > 1) {
          options.label = { text: String(group.entries.length), color: "#ffffff", fontWeight: "700" };
        }

        var marker = new maps.Marker(options);
        marker.addListener("click", function () {
          infoWindow.setContent(popupHtml(group));
          infoWindow.open({ anchor: marker, map: map });
        });

        // Jeder Listeneintrag zeigt auf den Marker seines Ortes - auch die
        // Nachbarwohnungen, die sich denselben Marker teilen.
        group.entries.forEach(function (entry) {
          markers[entry.id] = marker;
          groupsByEntry[entry.id] = group;
        });

        bounds.extend(position);
      });

      if (groups.length === 1) {
        map.setCenter({ lat: groups[0].lat, lng: groups[0].lng });
        map.setZoom(INITIAL_ZOOM);
      } else {
        map.fitBounds(bounds, 80);
        // fitBounds legt die Karte eng um die Marker. Liegen die Objekte dicht
        // beieinander, steht man mitten in einer Strasse ohne zu sehen, wo in
        // Plattling das ist. Der Deckel holt die Umgebung zurueck ins Bild -
        // nur fuer die Startansicht, hineinzoomen bleibt moeglich.
        maps.event.addListenerOnce(map, "idle", function () {
          if (map.getZoom() > INITIAL_ZOOM) {
            map.setZoom(INITIAL_ZOOM);
          }
        });
      }

      connectList(root, markers, function (entryId) {
        var marker = markers[entryId];
        map.panTo(marker.getPosition());
        infoWindow.setContent(popupHtml(groupsByEntry[entryId]));
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
