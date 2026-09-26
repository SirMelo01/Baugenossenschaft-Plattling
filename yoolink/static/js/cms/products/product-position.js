/**
 * Position der Immobilie auf der Objektkarte pruefen und von Hand korrigieren.
 *
 * Beim Speichern bestimmt der Server die Koordinaten aus der Adresse. Der
 * Geocoder trifft dabei das Gebaeude, aber nicht immer den Eingang - bei einem
 * Block mit mehreren Hausnummern landet der Punkt etwa in dessen Mitte. Hier
 * laesst sich der Pin an die richtige Stelle ziehen. Die Werte stehen in
 * versteckten Feldern des Formulars und gehen mit "Speichern" zum Server.
 *
 * Google Maps laedt erst auf Knopfdruck, damit das Formular ohne Karte schnell
 * bleibt und keine Kartenaufrufe fuer Seiten entstehen, auf denen niemand den
 * Pin anschaut.
 */
(function ($) {
  "use strict";

  var MAPS_CALLBACK = "yoolinkCmsGoogleMapsReady";
  var PLATTLING = { lat: 48.7766, lng: 12.8707 };
  var mapsPromise = null;

  function loadGoogleMaps(apiKey) {
    if (window.google && window.google.maps) {
      return Promise.resolve(window.google.maps);
    }
    if (mapsPromise) {
      return mapsPromise;
    }

    mapsPromise = new Promise(function (resolve, reject) {
      window[MAPS_CALLBACK] = function () {
        resolve(window.google.maps);
      };
      window.gm_authFailure = function () {
        reject(new Error("Google Maps hat den API-Key abgelehnt."));
      };

      var script = document.createElement("script");
      script.src = "https://maps.googleapis.com/maps/api/js"
        + "?key=" + encodeURIComponent(apiKey)
        + "&language=de&region=DE&loading=async&callback=" + MAPS_CALLBACK;
      script.async = true;
      script.onerror = function () {
        mapsPromise = null;
        reject(new Error("Google Maps konnte nicht geladen werden."));
      };
      document.head.appendChild(script);
    });

    return mapsPromise;
  }

  function notify(message, type) {
    if (typeof window.sendNotif === "function") {
      window.sendNotif(message, type);
    }
  }

  $(function () {
    var $root = $("#productPosition");
    if (!$root.length) {
      return;
    }

    var $lat = $root.find("[data-position-lat]");
    var $lng = $root.find("[data-position-lng]");
    var $manual = $root.find("[data-position-manual]");
    var $reset = $root.find("[data-position-reset]");
    var $status = $root.find("[data-position-status]");
    var $load = $root.find("[data-position-load]");
    var $auto = $root.find("[data-position-auto]");
    var $canvas = $root.find("[data-position-map]");
    var $hint = $root.find("[data-position-hint]");
    var $address = $("#address");
    var savedAddress = ($address.val() || "").trim();

    var map = null;
    var marker = null;

    function currentPosition() {
      var lat = parseFloat($lat.val());
      var lng = parseFloat($lng.val());
      if (isNaN(lat) || isNaN(lng)) {
        return null;
      }
      return { lat: lat, lng: lng };
    }

    function isManual() {
      return $manual.val() === "true";
    }

    function setAutoVisible(visible) {
      $auto.toggleClass("hidden", !visible).toggleClass("inline-flex", visible);
    }

    function renderStatus() {
      var addressChanged = ($address.val() || "").trim() !== savedAddress;

      if ($reset.val() === "true") {
        $status.text("Wird beim Speichern neu aus der Adresse bestimmt.");
      } else if (addressChanged && !isManual()) {
        $status.text("Adresse geändert - die Position wird beim Speichern neu bestimmt.");
      } else if (!currentPosition()) {
        $status.text("Noch keine Position - wird beim Speichern aus der Adresse bestimmt.");
      } else if (isManual()) {
        $status.text("Von Hand gesetzt. Bleibt erhalten, solange die Adresse gleich bleibt.");
      } else {
        $status.text("Automatisch aus der Adresse bestimmt.");
      }

      setAutoVisible(isManual() && $reset.val() !== "true");
    }

    function placeManually(latLng) {
      $lat.val(latLng.lat().toFixed(7));
      $lng.val(latLng.lng().toFixed(7));
      $manual.val("true");
      $reset.val("false");
      renderStatus();
    }

    function showMarker(maps) {
      var position = currentPosition();

      if (!marker) {
        marker = new maps.Marker({ map: map, draggable: true, title: "Zum Verschieben ziehen" });
        marker.addListener("dragend", function (event) {
          placeManually(event.latLng);
        });
      }

      if (position) {
        marker.setPosition(position);
        marker.setMap(map);
        map.setCenter(position);
        map.setZoom(19);
      } else {
        marker.setMap(null);
        map.setCenter(PLATTLING);
        map.setZoom(14);
      }
    }

    $load.on("click", function () {
      var apiKey = $root.data("apiKey");
      if (!apiKey) {
        notify("Für die Karte ist kein Google-Maps-Schlüssel hinterlegt.", "error");
        return;
      }

      $load.prop("disabled", true);
      loadGoogleMaps(apiKey)
        .then(function (maps) {
          $canvas.removeClass("hidden");
          $hint.removeClass("hidden");
          $load.addClass("hidden");

          if (!map) {
            map = new maps.Map($canvas[0], {
              mapTypeId: "hybrid",
              mapTypeControl: true,
              streetViewControl: false,
              fullscreenControl: true,
              tilt: 0,
            });
            // Ein Klick setzt den Pin dorthin - bequemer als Ziehen, wenn die
            // Stelle ausserhalb des sichtbaren Ausschnitts lag.
            map.addListener("click", function (event) {
              placeManually(event.latLng);
              marker.setPosition(event.latLng);
              marker.setMap(map);
            });
          }
          showMarker(maps);
        })
        .catch(function (error) {
          $load.prop("disabled", false);
          notify(error.message || "Die Karte konnte nicht geladen werden.", "error");
        });
    });

    $auto.on("click", function () {
      $manual.val("false");
      $reset.val("true");
      renderStatus();
    });

    $address.on("input", function () {
      // Neue Adresse, neuer Ort: eine alte Korrektur gehoert nicht mehr dazu.
      // Wer den Pin danach wieder zieht, setzt sie fuer die neue Adresse neu.
      if (($address.val() || "").trim() !== savedAddress) {
        $manual.val("false");
      }
      renderStatus();
    });

    // product-detail.js meldet ein erfolgreiches Speichern mit der Antwort des
    // Servers - dort steht die jetzt gueltige Position.
    $(document).on("cms:productSaved", function (event, response) {
      savedAddress = ($address.val() || "").trim();
      $lat.val(response.latitude == null ? "" : response.latitude);
      $lng.val(response.longitude == null ? "" : response.longitude);
      $manual.val(response.positionManual ? "true" : "false");
      $reset.val("false");
      renderStatus();

      if (map && window.google && window.google.maps) {
        showMarker(window.google.maps);
      }
    });

    renderStatus();
  });
})(window.jQuery);
