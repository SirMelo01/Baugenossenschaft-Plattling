(function () {
  "use strict";
  function root() { return document.querySelector("[data-additional-addresses]"); }
  function rows() { return Array.from(root()?.querySelectorAll("[data-address-row]") || []); }
  function primaryRow() { return root()?.querySelector("[data-primary-address-row]"); }
  function setStatus(row, text) { if (row) row.querySelector("[data-address-status]").textContent = text; }
  function addresses() { return rows().map(function (row) { return row.querySelector("input").value.trim(); }); }

  window.YooLinkProductAddresses = {
    snapshot: addresses,
    prepare: async function (formData, apiKey) {
      var snapshot = addresses();
      var primary = String(formData.get("address") || "").trim();
      var seen = new Set(primary ? [primary.toLocaleLowerCase().replace(/\s+/g, " ")] : []);
      snapshot.filter(Boolean).forEach(function (address) {
        var key = address.toLocaleLowerCase().replace(/\s+/g, " ");
        if (seen.has(key)) throw new Error("Die Adresse „" + address + "“ wurde mehrfach eingetragen.");
        seen.add(key);
      });
      if (primary) {
        setStatus(primaryRow(), formData.get("position_geocoded") === "true" ? "Position gefunden. Wird gespeichert."
          : formData.get("position_geocoding_error") ? "Position nicht gefunden. Die Adresse wird gespeichert; eine bisherige Position bleibt erhalten."
          : "Position gespeichert.");
      }
      rows().forEach(function (row) { setStatus(row, "Position wird gesucht …"); });
      var result = await window.YooLinkProductGeocoding.prepareAddresses(snapshot.filter(Boolean), apiKey);
      if (JSON.stringify(addresses()) !== JSON.stringify(snapshot)) {
        throw new Error("Die Adressen wurden während der Suche geändert. Bitte erneut speichern.");
      }
      formData.set("additional_addresses", JSON.stringify(result));
      rows().forEach(function (row, index) {
        var entry = result.find(function (item) { return item.address === snapshot[index]; });
        row.querySelector("[data-address-status]").textContent = !entry ? "Leere Zeile wird nicht gespeichert."
          : entry.position_geocoded ? "Position gefunden. Wird gespeichert."
          : "Position nicht gefunden. Die Adresse wird gespeichert; eine bisherige Position bleibt erhalten.";
      });
    },
    saved: function (locations) {
      [primaryRow()].concat(rows()).filter(Boolean).forEach(function (row) {
        var status = row.querySelector("[data-address-status]");
        var address = row.querySelector("input").value.trim();
        var location = (locations || []).find(function (item) { return item.address === address; });
        if (location) status.textContent = location.lat !== null && location.lng !== null
          ? "Position gespeichert." : "Adresse gespeichert. Noch keine Position gefunden; Anschrift prüfen und erneut speichern.";
      });
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var container = root();
    if (!container) return;
    container.addEventListener("click", function (event) {
      if (event.target.closest("[data-address-add]")) {
        var fragment = container.querySelector("template").content.cloneNode(true);
        var input = fragment.querySelector("input");
        container.querySelector("[data-address-list]").appendChild(fragment);
        input.focus();
      }
      var remove = event.target.closest("[data-address-remove]");
      if (remove) {
        remove.closest("[data-address-row]").remove();
        container.querySelector("[data-address-add]").focus();
      }
    });
    container.addEventListener("input", function (event) {
      setStatus(event.target.closest("[data-address-row], [data-primary-address-row]"), "Die Position wird beim Speichern gesucht.");
    });
  });
})();
