(function () {
  "use strict";

  const CONSENT_COOKIE = "yoolink_cookie_consent";
  const CONSENT_VERSION = 1;
  const CONSENT_MAX_AGE = 60 * 60 * 24 * 180;

  const defaultPreferences = {
    necessary: true,
    analytics: false,
    external: false,
  };

  function getCookie(name) {
    const cookieArr = document.cookie ? document.cookie.split(";") : [];
    for (let i = 0; i < cookieArr.length; i += 1) {
      const cookiePair = cookieArr[i].split("=");
      if (name === cookiePair[0].trim()) {
        return decodeURIComponent(cookiePair.slice(1).join("="));
      }
    }
    return null;
  }

  function setCookie(name, value, maxAge) {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${name}=${encodeURIComponent(value)}; max-age=${maxAge}; path=/; SameSite=Lax${secure}`;
  }

  function deleteCookie(name) {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    const hostname = window.location.hostname;
    const parts = hostname.split(".").filter(Boolean);
    const domains = new Set([hostname, `.${hostname}`]);

    if (parts.length > 2) {
      domains.add(`.${parts.slice(-2).join(".")}`);
    }

    document.cookie = `${name}=; max-age=0; path=/; SameSite=Lax${secure}`;
    domains.forEach((domain) => {
      document.cookie = `${name}=; max-age=0; path=/; domain=${domain}; SameSite=Lax${secure}`;
    });
  }

  function parseConsentCookie() {
    const raw = getCookie(CONSENT_COOKIE);
    if (!raw) return null;

    try {
      const parsed = JSON.parse(raw);
      if (parsed.version !== CONSENT_VERSION || !parsed.categories) return null;
      return {
        version: CONSENT_VERSION,
        decidedAt: parsed.decidedAt || new Date().toISOString(),
        categories: Object.assign({}, defaultPreferences, parsed.categories, { necessary: true }),
      };
    } catch (error) {
      return null;
    }
  }

  function readLegacyConsent() {
    const legacyConsent = getCookie("Cookie-Consent");
    if (legacyConsent === null) return null;

    return {
      version: CONSENT_VERSION,
      decidedAt: new Date().toISOString(),
      categories: {
        necessary: true,
        analytics: getCookie("Cookie-Analytic") === "true",
        external: getCookie("Cookie-Map") === "true",
      },
    };
  }

  function getConsent() {
    return parseConsentCookie() || readLegacyConsent();
  }

  function hasDecision() {
    return getConsent() !== null;
  }

  function categories() {
    const consent = getConsent();
    return consent ? consent.categories : defaultPreferences;
  }

  function syncLegacyGlobals() {
    const consent = getConsent();
    window.cookieselect = consent ? String(Object.values(consent.categories).some(Boolean)) : null;
    window.cookieanalyticselect = String(Boolean(consent && consent.categories.analytics));
    window.cookiemapselect = String(Boolean(consent && consent.categories.external));
  }

  function syncLegacyCookies(consent) {
    const anyOptional =
      consent.categories.analytics || consent.categories.external;
    setCookie("Cookie-Consent", String(anyOptional), CONSENT_MAX_AGE);
    setCookie("Cookie-Analytic", String(consent.categories.analytics), CONSENT_MAX_AGE);
    setCookie("Cookie-Map", String(consent.categories.external), CONSENT_MAX_AGE);
  }

  function cleanupAnalyticsCookies() {
    // Matomo first-party cookies (names include site id + domain hash, so match by prefix).
    const trackingPrefixes = ["_pk_id.", "_pk_ses.", "_pk_ref.", "_pk_cvar.", "_pk_hsr.", "mtm_"];
    const cookieArr = document.cookie ? document.cookie.split(";") : [];
    cookieArr.forEach((pair) => {
      const name = pair.split("=")[0].trim();
      if (trackingPrefixes.some((prefix) => name.indexOf(prefix) === 0)) {
        deleteCookie(name);
      }
    });
  }

  function ensureAnalytics() {
    const config = window.MATOMO_CONFIG;
    // No config means this is not the hosted production site (e.g. localhost) -> never track.
    if (!config || !config.url || !config.siteId) return;
    if (document.querySelector(`script[data-cookie-service="matomo"]`)) return;

    const base = config.url.replace(/\/+$/, "") + "/";
    window._paq = window._paq || [];
    const paq = window._paq;
    paq.push(["setTrackerUrl", base + "matomo.php"]);
    paq.push(["setSiteId", String(config.siteId)]);
    paq.push(["enableLinkTracking"]);
    paq.push(["trackPageView"]);

    const script = document.createElement("script");
    script.async = true;
    script.src = base + "matomo.js";
    script.dataset.cookieService = "matomo";
    document.head.appendChild(script);
  }

  function unloadAnalytics() {
    document.querySelectorAll('script[data-cookie-service="matomo"]').forEach((node) => node.remove());
    window._paq = [];
    cleanupAnalyticsCookies();
  }

  function hydrateExternalEmbeds() {
    document.querySelectorAll("[data-cookie-src]").forEach((node) => {
      if (!node.getAttribute("src")) {
        node.setAttribute("src", node.dataset.cookieSrc);
      }
      node.classList.remove("hidden");
    });

    document.querySelectorAll("[data-cookie-placeholder]").forEach((node) => {
      node.classList.add("hidden");
    });

    renderRecaptcha();
  }

  function blockExternalEmbeds() {
    document.querySelectorAll("[data-cookie-src]").forEach((node) => {
      if (node.getAttribute("src")) {
        node.dataset.cookieSrc = node.getAttribute("src");
        node.removeAttribute("src");
      }
      node.classList.add("hidden");
    });

    document.querySelectorAll("[data-cookie-placeholder]").forEach((node) => {
      node.classList.remove("hidden");
    });

    unloadRecaptcha();
  }

  function renderRecaptcha() {
    const container = document.querySelector("[data-recaptcha-container]");
    if (!container || container.dataset.rendered === "true") return;

    const siteKey = container.dataset.sitekey;
    if (!siteKey) return;

    if (window.grecaptcha && typeof window.grecaptcha.render === "function") {
      window.grecaptcha.render(container, { sitekey: siteKey });
      container.dataset.rendered = "true";
      document.dispatchEvent(new CustomEvent("yoolink:recaptcha-ready"));
      return;
    }

    if (document.querySelector('script[data-cookie-service="recaptcha"]')) return;

    window.yoolinkOnRecaptchaLoad = function yoolinkOnRecaptchaLoad() {
      renderRecaptcha();
    };

    const script = document.createElement("script");
    script.src = "https://www.google.com/recaptcha/api.js?onload=yoolinkOnRecaptchaLoad&render=explicit";
    script.async = true;
    script.defer = true;
    script.dataset.cookieService = "recaptcha";
    document.head.appendChild(script);
  }

  function unloadRecaptcha() {
    document.querySelectorAll('script[data-cookie-service="recaptcha"]').forEach((node) => node.remove());
    document.querySelectorAll("[data-recaptcha-container]").forEach((container) => {
      container.innerHTML = "";
      delete container.dataset.rendered;
    });
    delete window.yoolinkOnRecaptchaLoad;
    window.grecaptcha = undefined;
    document.dispatchEvent(new CustomEvent("yoolink:recaptcha-reset"));
  }

  function applyConsent() {
    const selected = categories();

    if (selected.analytics) ensureAnalytics();
    else unloadAnalytics();

    if (selected.external) hydrateExternalEmbeds();
    else blockExternalEmbeds();

    syncLegacyGlobals();
  }

  function saveConsent(nextCategories) {
    const consent = {
      version: CONSENT_VERSION,
      decidedAt: new Date().toISOString(),
      categories: Object.assign({}, defaultPreferences, nextCategories, { necessary: true }),
    };

    setCookie(CONSENT_COOKIE, JSON.stringify(consent), CONSENT_MAX_AGE);
    syncLegacyCookies(consent);
    syncLegacyGlobals();
    applyConsent();
    document.dispatchEvent(new CustomEvent("yoolink:consentChanged", { detail: consent }));
    return consent;
  }

  function acceptAll() {
    return saveConsent({
      analytics: true,
      external: true,
    });
  }

  function rejectAll() {
    return saveConsent({
      analytics: false,
      external: false,
    });
  }

  function bindBanner() {
    const modal = document.getElementById("cookie-consent-modal");
    if (!modal) return;

    const details = modal.querySelector("[data-consent-details]");
    const summary = modal.querySelector("[data-consent-summary]");
    const toggles = modal.querySelectorAll("[data-consent-toggle]");
    let reloadTimer = null;

    function syncToggles() {
      const selected = categories();
      toggles.forEach((toggle) => {
        toggle.checked = Boolean(selected[toggle.dataset.consentToggle]);
      });
    }

    function showDetails() {
      details && details.classList.remove("hidden");
      summary && summary.classList.add("hidden");
      syncToggles();
    }

    function hideDetails() {
      details && details.classList.add("hidden");
      summary && summary.classList.remove("hidden");
    }

    function open(customMode) {
      modal.style.display = "";
      modal.classList.remove("hidden");
      if (customMode) showDetails();
      else hideDetails();
    }

    function close() {
      if (!hasDecision()) rejectAll();
      modal.classList.add("hidden");
    }

    function saveConsentAndReload(saveCallback) {
      saveCallback();
      // Sauber & schnell wie bei Standard-Anbietern: Auswahl speichern, Banner
      // sofort & garantiert schließen (Klasse + inline-Style gegen jeden CSS-Konflikt),
      // dann kurz darauf neu laden (kein Warten/keine Status-Box).
      modal.classList.add("hidden");
      modal.style.display = "none";
      if (reloadTimer) window.clearTimeout(reloadTimer);
      reloadTimer = window.setTimeout(() => {
        window.location.reload();
      }, 120);
    }

    window.YooLinkConsent.openSettings = function () {
      open(true);
    };

    document.addEventListener("click", (event) => {
      const actionTarget = event.target.closest("[data-consent-action]");
      if (!actionTarget) return;

      const action = actionTarget.dataset.consentAction;
      if (action === "accept-all") {
        saveConsentAndReload(acceptAll);
      } else if (action === "reject-all") {
        saveConsentAndReload(rejectAll);
      } else if (action === "customize") {
        showDetails();
      } else if (action === "save") {
        const custom = {};
        toggles.forEach((toggle) => {
          custom[toggle.dataset.consentToggle] = toggle.checked;
        });
        saveConsentAndReload(() => saveConsent(custom));
      } else if (action === "open-settings") {
        open(true);
      } else if (action === "close") {
        close();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });

    if (!hasDecision()) open(false);
    else {
      modal.classList.add("hidden");
    }
  }

  window.getCookie = getCookie;
  syncLegacyGlobals();

  window.YooLinkConsent = {
    acceptAll,
    rejectAll,
    save: saveConsent,
    get: getConsent,
    categories,
    hasDecision,
    openSettings: function () {
      const button = document.querySelector('[data-consent-action="open-settings"]');
      if (button) button.click();
    },
    renderRecaptcha,
    apply: applyConsent,
  };

  document.addEventListener("DOMContentLoaded", () => {
    syncLegacyGlobals();
    applyConsent();
    bindBanner();
  });
})();
