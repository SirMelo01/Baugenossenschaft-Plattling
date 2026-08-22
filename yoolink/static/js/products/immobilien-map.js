(function () {
  "use strict";

  var LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
  var LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var CACHE_PREFIX = "bgp_geocode_v1:";
  var leafletPromise = null;

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

  function loadLeaflet() {
    if (window.L) {
      return Promise.resolve(window.L);
    }

    if (leafletPromise) {
      return leafletPromise;
    }

    leafletPromise = new Promise(function (resolve, reject) {
      if (!document.querySelector('link[data-map-lib="leaflet"]')) {
        var link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = LEAFLET_CSS;
        link.dataset.mapLib = "leaflet";
        document.head.appendChild(link);
      }

      var existing = document.querySelector('script[data-map-lib="leaflet"]');
      if (existing) {
        existing.addEventListener("load", function () { resolve(window.L); });
        existing.addEventListener("error", reject);
        return;
      }

      var script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.defer = true;
      script.dataset.mapLib = "leaflet";
      script.onload = function () { resolve(window.L); };
      script.onerror = reject;
      document.head.appendChild(script);
    });

    return leafletPromise;
  }

  function cacheKey(address) {
    return CACHE_PREFIX + address.trim().toLowerCase();
  }

  function readCached(address) {
    try {
      var raw = window.localStorage.getItem(cacheKey(address));
      if (!raw) {
        return null;
      }
      var parsed = JSON.parse(raw);
      if (Number.isFinite(parsed.lat) && Number.isFinite(parsed.lon)) {
        return parsed;
      }
    } catch (error) {
      return null;
    }
    return null;
  }

  function writeCached(address, coords) {
    try {
      window.localStorage.setItem(cacheKey(address), JSON.stringify(coords));
    } catch (error) {
      // Cache is optional.
    }
  }

  function geocode(location) {
    var cached = readCached(location.address);
    if (cached) {
      return Promise.resolve(Object.assign({}, location, cached));
    }

    var params = new URLSearchParams({
      format: "json",
      limit: "1",
      countrycodes: "de",
      q: location.address,
    });

    return window.fetch("https://nominatim.openstreetmap.org/search?" + params.toString(), {
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Geocoding failed");
        }
        return response.json();
      })
      .then(function (result) {
        var first = Array.isArray(result) ? result[0] : null;
        if (!first) {
          return null;
        }

        var coords = {
          lat: parseFloat(first.lat),
          lon: parseFloat(first.lon),
        };
        if (!Number.isFinite(coords.lat) || !Number.isFinite(coords.lon)) {
          return null;
        }
        writeCached(location.address, coords);
        return Object.assign({}, location, coords);
      })
      .catch(function () {
        return null;
      });
  }

  function geocodeAll(locations) {
    var chain = Promise.resolve([]);
    locations.forEach(function (location, index) {
      chain = chain.then(function (results) {
        return new Promise(function (resolve) {
          window.setTimeout(function () {
            geocode(location).then(function (entry) {
              if (entry) {
                results.push(entry);
              }
              resolve(results);
            });
          }, index === 0 ? 0 : 300);
        });
      });
    });
    return chain;
  }

  function renderMap(root, locations) {
    var canvas = root.querySelector("[data-map-canvas]");
    var placeholder = root.querySelector("[data-map-placeholder]");
    var empty = root.querySelector("[data-map-empty]");
    var error = root.querySelector("[data-map-error]");

    if (!locations.length) {
      setVisible(canvas, false);
      setVisible(placeholder, false, true);
      setVisible(error, false, true);
      setVisible(empty, true, true);
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

    if (root.dataset.mapReady === "true") {
      return;
    }

    loadLeaflet()
      .then(function (L) {
        return geocodeAll(locations).then(function (entries) {
          if (!entries.length) {
            throw new Error("No coordinates found");
          }

          var map = L.map(canvas, {
            scrollWheelZoom: false,
          });

          L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          }).addTo(map);

          var bounds = [];
          entries.forEach(function (entry) {
            var latLng = [entry.lat, entry.lon];
            bounds.push(latLng);
            var popup = ""
              + '<strong>' + escapeHtml(entry.title) + '</strong>'
              + '<br><span>' + escapeHtml(entry.address) + '</span>'
              + '<br><a href="' + escapeHtml(entry.url) + '">Details ansehen</a>';
            if (entry.maps_url) {
              popup += ' · <a href="' + escapeHtml(entry.maps_url) + '" target="_blank" rel="noopener">Route</a>';
            }
            L.marker(latLng).addTo(map).bindPopup(popup);
          });

          if (bounds.length === 1) {
            map.setView(bounds[0], 15);
          } else {
            map.fitBounds(bounds, { padding: [28, 28] });
          }

          root.dataset.mapReady = "true";
          window.setTimeout(function () {
            map.invalidateSize();
          }, 100);
        });
      })
      .catch(function () {
        setVisible(canvas, false);
        setVisible(error, true, true);
      });
  }

  function init() {
    document.querySelectorAll("[data-immobilien-map]").forEach(function (root) {
      renderMap(root, parseLocations(root));
    });
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("yoolink:consentChanged", init);
})();
