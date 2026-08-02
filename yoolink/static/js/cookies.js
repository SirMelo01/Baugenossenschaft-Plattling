(function () {
  "use strict";

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback);
    } else {
      callback();
    }
  }

  ready(function () {
    const form = document.querySelector("[data-cookie-settings-form]");
    if (!form || !window.YooLinkConsent) return;

    const status = document.querySelector("[data-cookie-settings-status]");
    const toggles = form.querySelectorAll("[data-consent-toggle]");
    let reloadTimer = null;

    function sync() {
      const categories = window.YooLinkConsent.categories();
      toggles.forEach((toggle) => {
        toggle.checked = Boolean(categories[toggle.dataset.consentToggle]);
      });
    }

    function showStatus(message) {
      if (!status) return;
      status.textContent = message;
      status.classList.remove("hidden");
    }

    function saveAndReload(saveCallback, message) {
      saveCallback();
      showStatus(message);

      if (reloadTimer) window.clearTimeout(reloadTimer);
      reloadTimer = window.setTimeout(() => {
        window.location.reload();
      }, 200);
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const next = {};
      toggles.forEach((toggle) => {
        next[toggle.dataset.consentToggle] = toggle.checked;
      });
      saveAndReload(
        () => window.YooLinkConsent.save(next),
        "Ihre Cookie-Auswahl wurde gespeichert. Die Seite wird neu geladen, damit die Einstellungen aktiv werden."
      );
    });

    document.querySelectorAll("[data-cookie-settings-action]").forEach((button) => {
      button.addEventListener("click", function () {
        const action = button.dataset.cookieSettingsAction;
        if (action === "accept-all") {
          saveAndReload(
            () => {
              window.YooLinkConsent.acceptAll();
              sync();
            },
            "Alle optionalen Dienste wurden akzeptiert. Die Seite wird neu geladen."
          );
        } else if (action === "reject-all") {
          saveAndReload(
            () => {
              window.YooLinkConsent.rejectAll();
              sync();
            },
            "Alle optionalen Dienste wurden abgelehnt. Die Seite wird neu geladen."
          );
        }
      });
    });

    document.addEventListener("yoolink:consentChanged", sync);
    sync();
  });
})();
