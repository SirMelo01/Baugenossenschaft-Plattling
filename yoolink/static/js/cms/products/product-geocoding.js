/* Address lookup in the authenticated CMS, using the existing website key. */
(function (root) {
  "use strict";
  var mapsPromise = null;
  var cache = new Map();

  function streetKey(value) {
    return String(value || "").toLowerCase().replace(/ß/g, "ss")
      .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/^dr\.?/, "doktor").replace(/strasse|str\.?/g, "str").replace(/[^a-z0-9]/g, "");
  }

  function matchingPosition(address, results) {
    var expected = address.match(/^\s*(.+?)\s+(\d+(?:\s*[a-zA-Z])?(?:\s*[-/]\s*\d+\s*[a-zA-Z]?)?)\s*(?:,|\s+(?=\d{5}\b)|$)/);
    if (!expected) return null;
    var postcode = address.match(/\b(\d{5})\b/);
    var matches = [];
    (results || []).forEach(function (result) {
      var components = {};
      (result.address_components || []).forEach(function (item) {
        (item.types || []).forEach(function (type) { components[type] = item.long_name; });
      });
      if (streetKey(components.route) !== streetKey(expected[1])
        || String(components.street_number || "").replace(/\s/g, "").toLowerCase() !== expected[2].replace(/\s/g, "").toLowerCase()
        || (postcode && components.postal_code !== postcode[1])) return;
      var geometry = result.geometry || {};
      if (!["ROOFTOP", "RANGE_INTERPOLATED"].includes(geometry.location_type)) return;
      var location = geometry.location;
      if (!location) return;
      var lat = typeof location.lat === "function" ? location.lat() : location.lat;
      var lng = typeof location.lng === "function" ? location.lng() : location.lng;
      if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180
        || (lat === 0 && lng === 0)) return;
      matches.push({ lat: lat, lng: lng, rooftop: geometry.location_type === "ROOFTOP" });
    });
    return matches.find(function (match) { return match.rooftop; }) || matches[0] || null;
  }

  function failure(code) {
    var error = new Error(code);
    error.code = code;
    return error;
  }

  function loadMaps(apiKey) {
    if (root.google && root.google.maps && root.google.maps.Geocoder) return Promise.resolve(root.google.maps);
    if (!apiKey) return Promise.reject(failure("MISSING_KEY"));
    if (mapsPromise) return mapsPromise;
    mapsPromise = new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      var timer;
      function fail(code) {
        clearTimeout(timer);
        script.remove();
        reject(failure(code));
      }
      root.yoolinkCmsGoogleMapsReady = function () {
        clearTimeout(timer);
        resolve(root.google.maps);
      };
      root.gm_authFailure = function () { fail("REQUEST_DENIED"); };
      script.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(apiKey)
        + "&language=de&region=DE&loading=async&callback=yoolinkCmsGoogleMapsReady";
      script.async = true;
      script.onerror = function () { fail("SERVICE_UNAVAILABLE"); };
      timer = setTimeout(function () { fail("SERVICE_UNAVAILABLE"); }, 15000);
      document.head.appendChild(script);
    }).catch(function (error) {
      mapsPromise = null;
      throw error;
    });
    return mapsPromise;
  }

  function query(geocoder, address) {
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () { reject(failure("SERVICE_UNAVAILABLE")); }, 12000);
      try {
        geocoder.geocode({ address: address, region: "DE", componentRestrictions: { country: "DE" } }, function (results, status) {
          clearTimeout(timer);
          if (status === "OK") resolve(matchingPosition(address, results));
          else if (status === "ZERO_RESULTS") resolve(null);
          else reject(failure(status));
        });
      } catch (error) {
        clearTimeout(timer);
        reject(failure("SERVICE_UNAVAILABLE"));
      }
    });
  }

  async function geocode(address, apiKey, refresh) {
    if (!refresh && cache.has(address)) return cache.get(address);
    var maps = await loadMaps(apiKey);
    var geocoder = new maps.Geocoder();
    var position = await query(geocoder, address);
    var simplified = address.replace(/(\b\d{5}\s+[^,\-]+)-[^,]+/, "$1");
    if (!position && simplified !== address) position = await query(geocoder, simplified);
    if (!position) throw failure("NO_MATCH");
    cache.set(address, position);
    return position;
  }

  async function prepare(formData, apiKey) {
    var address = String(formData.get("address") || "").trim();
    var positionAddress = String(formData.get("position_address") || "").trim();
    var manual = formData.get("position_manual") === "true";
    var reset = formData.get("position_reset") === "true";
    formData.set("position_geocoded", "false");
    formData.set("position_geocoding_error", "");
    if (!address || (manual && !reset && positionAddress === address)) return;
    // Old manual coordinates must never be reused after changing the address.
    formData.set("position_manual", "false");
    formData.set("position_address", address);
    try {
      var position = await geocode(address, apiKey, reset);
      formData.set("latitude", String(position.lat));
      formData.set("longitude", String(position.lng));
      formData.set("position_geocoded", "true");
    } catch (error) {
      formData.set("latitude", "");
      formData.set("longitude", "");
      formData.set("position_geocoding_error", error.code || "SERVICE_UNAVAILABLE");
    }
  }

  async function prepareAddresses(addresses, apiKey) {
    var entries = [];
    // Sequential requests avoid a burst of geocoding calls for one listing.
    for (var address of addresses) {
      var data = new FormData();
      data.set("address", address);
      await prepare(data, apiKey);
      entries.push({
        address: address, position_address: data.get("position_address"),
        latitude: data.get("latitude"), longitude: data.get("longitude"),
        position_geocoded: data.get("position_geocoded") === "true",
        position_geocoding_error: data.get("position_geocoding_error")
      });
    }
    return entries;
  }

  var api = { loadMaps: loadMaps, matchingPosition: matchingPosition, prepare: prepare, prepareAddresses: prepareAddresses };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.YooLinkProductGeocoding = api;
})(typeof window !== "undefined" ? window : globalThis);
