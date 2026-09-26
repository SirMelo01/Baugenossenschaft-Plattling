/**
 * Objektkarte auf der Immobilienseite (Google Maps).
 *
 * Die Koordinaten stehen bereits im Seitenquelltext: sie werden beim Speichern
 * im CMS aus der Adresse bestimmt (oder dort von Hand korrigiert) und am Objekt
 * gespeichert. Bei verschiedenen Anschriften mit praktisch identischen
 * automatischen Koordinaten wird der genaue Hausnummer-Treffer geprueft.
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
  // Marker, die naeher als so viele Bildschirmpixel beieinander liegen, werden zu
  // einem Buendel mit Anzahl zusammengefasst (der Pin-Kopf ist etwa 27 px breit).
  var CLUSTER_RADIUS_PX = 34;
  // Ab dieser Zoomstufe zoomt ein Klick auf ein Buendel nicht weiter hinein,
  // sondern listet die Objekte - weiter aufloesen laesst sich dann nichts mehr.
  var MAX_CLUSTER_ZOOM = 19;
  // "Auf Karte zeigen" zoomt so nah heran, dass Nachbarhaeuser getrennt stehen.
  var FOCUS_ZOOM = 18;
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

  function groupPopupSection(group) {
    var first = group.entries[0];
    var html = '<strong>' + escapeHtml(first.address) + '</strong>';

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
    return html;
  }

  function popupHtml(groups) {
    return '<div style="min-width:13rem;max-height:18rem;overflow-y:auto">'
      + groups.map(groupPopupSection).join('<hr style="margin:0.6rem 0;border:0;border-top:1px solid #e5e7eb">')
      + "</div>";
  }

  function hasCoordinates(entry) {
    return typeof entry.lat === "number" && typeof entry.lng === "number";
  }

  function streetKey(value) {
    return String(value || "").toLowerCase().replace(/ß/g, "ss")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/^dr\.?/, "doktor")
      .replace(/stra(?:sse|ße)|str\.?/g, "str")
      .replace(/[^a-z0-9]/g, "");
  }

  function exactAddressResult(address, result) {
    var expected = address.match(/^\s*(.+?)\s+(\d+[a-zA-Z]?)\s*,/);
    if (!expected || !result || result.partial_match) return false;
    var components = {};
    (result.address_components || []).forEach(function (component) {
      (component.types || []).forEach(function (type) {
        components[type] = component.long_name;
      });
    });
    return streetKey(components.route) === streetKey(expected[1])
      && String(components.street_number || "").replace(/\s/g, "").toLowerCase() === expected[2].toLowerCase();
  }

  function sameArea(a, b) {
    var north = (a.lat - b.lat) * 111320;
    var east = (a.lng - b.lng) * 111320 * Math.cos(a.lat * Math.PI / 180);
    return north * north + east * east < 20 * 20;
  }

  function verifyCollidingAddresses(entries, maps) {
    var suspects = entries.filter(function (entry) {
      return !entry.manual && hasCoordinates(entry) && entries.some(function (other) {
        return other !== entry && hasCoordinates(other)
          && other.address.trim().toLowerCase() !== entry.address.trim().toLowerCase()
          && sameArea(entry, other);
      });
    });
    if (!suspects.length) return Promise.resolve();

    var geocoder = new maps.Geocoder();
    var checked = {};
    var chain = Promise.resolve();
    suspects.forEach(function (entry) {
      var key = entry.address.trim().toLowerCase();
      if (checked[key]) return;
      checked[key] = true;
      chain = chain.then(function () {
        var simple = entry.address.replace(/(\b\d{5}\s+[^,\-]+)-[^,]+/, "$1");
        var queries = simple === entry.address ? [entry.address] : [entry.address, simple];
        function lookup(index) {
          if (index >= queries.length) return Promise.resolve(null);
          return new Promise(function (resolve) {
            geocoder.geocode({ address: queries[index], componentRestrictions: { country: "DE" } }, function (results, status) {
              var exact = status === "OK" && (results || []).find(function (result) {
                return exactAddressResult(entry.address, result);
              });
              resolve(exact || null);
            });
          }).then(function (result) {
            return result || lookup(index + 1);
          });
        }
        return lookup(0).then(function (result) {
          suspects.forEach(function (candidate) {
            if (candidate.address.trim().toLowerCase() !== key) return;
            candidate.lat = result ? result.geometry.location.lat() : null;
            candidate.lng = result ? result.geometry.location.lng() : null;
          });
        });
      });
    });
    return chain;
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
        byKey[key] = { lat: entry.lat, lng: entry.lng, entries: [], marker: null };
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

  function countEntries(groups) {
    return groups.reduce(function (sum, group) {
      return sum + group.entries.length;
    }, 0);
  }

  /**
   * Position eines Punktes in Weltpixeln der Zoomstufe (Web-Mercator).
   *
   * Der Bildschirmabstand zweier Marker haengt nur von der Zoomstufe ab, nicht
   * vom Kartenausschnitt - deshalb reicht diese Rechnung, und die Karte muss
   * dafuer nicht erst fertig gezeichnet sein.
   */
  function worldPixel(lat, lng, zoom) {
    var scale = 256 * Math.pow(2, zoom);
    var sin = Math.min(Math.max(Math.sin(lat * Math.PI / 180), -0.9999), 0.9999);
    return {
      x: (lng + 180) / 360 * scale,
      y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale,
    };
  }

  /**
   * Anschriften, deren Marker sich auf dem Bildschirm ueberdecken, zu Buendeln
   * zusammenfassen.
   *
   * Nachbarhaeuser liegen oft nur 15-30 m auseinander. In der Startansicht sind
   * das zwei, drei Pixel: die Pins liegen deckungsgleich uebereinander und es
   * sieht aus, als stuende dort nur ein Objekt. Ein Buendel zeigt stattdessen die
   * Anzahl und zoomt beim Anklicken hinein, bis die Haeuser getrennt stehen.
   */
  function clusterGroups(groups, zoom) {
    var clusters = [];
    var radiusSquared = CLUSTER_RADIUS_PX * CLUSTER_RADIUS_PX;

    groups.forEach(function (group) {
      var point = worldPixel(group.lat, group.lng, zoom);
      var target = null;

      for (var i = 0; i < clusters.length; i++) {
        var dx = clusters[i].x - point.x;
        var dy = clusters[i].y - point.y;
        if (dx * dx + dy * dy <= radiusSquared) {
          target = clusters[i];
          break;
        }
      }

      if (!target) {
        clusters.push({ x: point.x, y: point.y, groups: [group] });
        return;
      }

      // Mittelpunkt mitfuehren, damit das Buendel zwischen seinen Haeusern sitzt.
      var size = target.groups.length;
      target.x = (target.x * size + point.x) / (size + 1);
      target.y = (target.y * size + point.y) / (size + 1);
      target.groups.push(group);
    });

    return clusters;
  }

  function clusterCenter(groups) {
    var lat = 0;
    var lng = 0;
    groups.forEach(function (group) {
      lat += group.lat;
      lng += group.lng;
    });
    return { lat: lat / groups.length, lng: lng / groups.length };
  }

  /**
   * "Auf Karte zeigen" neben jeder Adresse aktivieren.
   *
   * Der Knopf steht erst zur Verfuegung, wenn die Karte wirklich da ist - ohne
   * Einwilligung oder nach einem Ladefehler wuerde er ins Leere fuehren.
   */
  function connectList(root, groupsByEntry, showEntry) {
    root.querySelectorAll("[data-map-focus]").forEach(function (button) {
      var entryId = button.dataset.mapFocus;
      if (!groupsByEntry[entryId]) {
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
      return verifyCollidingAddresses(entries, maps).then(function () {
      entries = entries.filter(hasCoordinates);
      if (!entries.length) throw new Error("Keine exakt verortete Adresse gefunden.");
      var map = new maps.Map(canvas, {
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        // Ohne "cooperative" zoomt das Mausrad die Karte statt die Seite zu scrollen.
        gestureHandling: "cooperative",
      });

      var infoWindow = new maps.InfoWindow();
      var infoAnchor = null;
      var bounds = new maps.LatLngBounds();
      var groups = groupByAddress(entries);
      var groupsByEntry = {};
      var clusterMarkers = [];

      function openInfo(anchor, popupGroups) {
        infoAnchor = anchor;
        infoWindow.setContent(popupHtml(popupGroups));
        infoWindow.open({ anchor: anchor, map: map });
      }

      groups.forEach(function (group) {
        var position = { lat: group.lat, lng: group.lng };
        var options = { position: position, title: groupTitle(group) };

        if (group.entries.length > 1) {
          options.label = { text: String(group.entries.length), color: "#ffffff", fontWeight: "700" };
        }

        group.marker = new maps.Marker(options);
        group.marker.addListener("click", function () {
          openInfo(group.marker, [group]);
        });

        // Jeder Listeneintrag zeigt auf den Marker seines Ortes - auch die
        // Nachbarwohnungen, die sich denselben Marker teilen.
        group.entries.forEach(function (entry) {
          groupsByEntry[entry.id] = group;
        });

        bounds.extend(position);
      });

      function buildClusterMarker(cluster) {
        var total = countEntries(cluster.groups);
        var marker = new maps.Marker({
          map: map,
          position: clusterCenter(cluster.groups),
          title: total + " Objekte an " + cluster.groups.length + " Adressen - zum Vergrößern anklicken",
          label: { text: String(total), color: "#ffffff", fontWeight: "700", fontSize: "13px" },
          icon: {
            path: maps.SymbolPath.CIRCLE,
            scale: total > 9 ? 19 : 16,
            fillColor: BRAND_NAVY,
            fillOpacity: 0.95,
            strokeColor: "#ffffff",
            strokeWeight: 3,
          },
          zIndex: 1000 + total,
        });

        marker.addListener("click", function () {
          if (map.getZoom() >= MAX_CLUSTER_ZOOM) {
            openInfo(marker, cluster.groups);
            return;
          }

          var clusterBounds = new maps.LatLngBounds();
          cluster.groups.forEach(function (group) {
            clusterBounds.extend({ lat: group.lat, lng: group.lng });
          });
          map.fitBounds(clusterBounds, 80);
          // Liegen zwei Adressen (fast) auf demselben Punkt, wuerde fitBounds bis
          // zum Anschlag hineinzoomen - dort sieht man nur noch ein Hausdach.
          maps.event.addListenerOnce(map, "idle", function () {
            if (map.getZoom() > MAX_CLUSTER_ZOOM) {
              map.setZoom(MAX_CLUSTER_ZOOM);
            }
          });
        });

        cluster.marker = marker;
        return marker;
      }

      var clusters = [];

      function recluster() {
        var zoom = map.getZoom();
        if (typeof zoom !== "number") {
          return;
        }

        clusterMarkers.forEach(function (marker) {
          marker.setMap(null);
        });
        clusterMarkers = [];
        clusters = clusterGroups(groups, zoom);

        clusters.forEach(function (cluster) {
          if (cluster.groups.length === 1) {
            if (cluster.groups[0].marker.getMap() !== map) {
              cluster.groups[0].marker.setMap(map);
            }
            return;
          }

          cluster.groups.forEach(function (group) {
            group.marker.setMap(null);
          });
          clusterMarkers.push(buildClusterMarker(cluster));
        });

        // Ein Info-Fenster an einem Marker, der gerade in einem Buendel aufgegangen
        // ist, haengt sonst an einer Stelle, an der nichts mehr zu sehen ist.
        if (infoAnchor && !infoAnchor.getMap()) {
          infoWindow.close();
          infoAnchor = null;
        }
      }

      function clusterOf(group) {
        return clusters.filter(function (cluster) {
          return cluster.groups.indexOf(group) !== -1;
        })[0];
      }

      map.addListener("zoom_changed", recluster);

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
      recluster();

      connectList(root, groupsByEntry, function (entryId) {
        var group = groupsByEntry[entryId];
        map.setCenter({ lat: group.lat, lng: group.lng });
        if (map.getZoom() < FOCUS_ZOOM) {
          map.setZoom(FOCUS_ZOOM);
        }
        recluster();

        if (group.marker.getMap()) {
          openInfo(group.marker, [group]);
        } else {
          // Selbst aus der Naehe nicht zu trennen (etwa zwei Hausnummern mit
          // denselben Koordinaten) - dann das Buendel mit allen Objekten oeffnen.
          var cluster = clusterOf(group);
          if (cluster && cluster.marker) {
            openInfo(cluster.marker, cluster.groups);
          }
        }
        canvas.scrollIntoView({ behavior: "smooth", block: "center" });
      });

      root.dataset.mapReady = "true";
      });
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

    buildMap(root, canvas, entries).catch(function (failure) {
      root.dataset.mapReady = "";
      setVisible(canvas, false);
      if (failure && failure.message === "Keine exakt verortete Adresse gefunden.") {
        root.querySelector("[data-map-error-title]").textContent = "Keine genaue Position gefunden";
        root.querySelector("[data-map-error-message]").textContent =
          "Für diese Hausnummern liegt kein eindeutiger Kartentreffer vor. Die Adressen stehen weiterhin in der Liste.";
      }
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
