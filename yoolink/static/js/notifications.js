/* =========================================================
   YooLink Toast Notifications
   Modernes, gestapeltes Benachrichtigungssystem (eigener Code, MIT).

   Öffentliche API (abwärtskompatibel zum alten System):
     sendNotif(content, status, position)
       status:   'success' | 'error' | 'warning' | 'info' | 'notice'
       position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

   Zusätzlich: window.YooToast.show(content, status, position)
               window.YooToast.dismiss(toastElement)
   ========================================================= */
(function (window, document) {
  "use strict";

  var ICONS = {
    success:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    error:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
    warning:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    info:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>'
  };

  var TITLES = {
    success: "Erfolg",
    error: "Fehler",
    warning: "Achtung",
    info: "Hinweis"
  };

  // Alias: das alte System kannte 'notice' (= info).
  var STATUS_ALIAS = {
    notice: "info",
    info: "info",
    success: "success",
    error: "error",
    warning: "warning"
  };

  var DURATIONS = {
    success: 4500,
    info: 4500,
    warning: 6000,
    error: 7000
  };

  var POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right"];
  var MAX_VISIBLE = 5;

  function getContainer(position) {
    var id = "yoo-toast-" + position;
    var container = document.getElementById(id);

    if (!container) {
      container = document.createElement("div");
      container.id = id;
      container.className = "yoo-toast-container yoo-toast-container--" + position;
      container.setAttribute("aria-live", "polite");
      container.setAttribute("aria-atomic", "false");
      document.body.appendChild(container);
    }

    return container;
  }

  function dismiss(toast) {
    if (!toast || toast._leaving) {
      return;
    }
    toast._leaving = true;
    window.clearTimeout(toast._timer);
    toast.classList.add("is-leaving");
    toast.classList.remove("is-visible");

    window.setTimeout(function () {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 320);
  }

  function show(content, status, position) {
    content = (content === undefined || content === null) ? "" : String(content);
    if (!content.trim()) {
      return null;
    }

    var statusKey = STATUS_ALIAS[status] || "info";
    var pos = POSITIONS.indexOf(position) >= 0 ? position : "bottom-right";
    var duration = DURATIONS[statusKey] || 4500;

    var container = getContainer(pos);

    // Stapel begrenzen: ältesten sichtbaren Toast entfernen.
    var visible = container.querySelectorAll(".yoo-toast:not(.is-leaving)");
    if (visible.length >= MAX_VISIBLE) {
      dismiss(visible[0]);
    }

    var toast = document.createElement("div");
    toast.className = "yoo-toast yoo-toast--" + statusKey;
    toast.setAttribute("role", statusKey === "error" ? "alert" : "status");

    toast.innerHTML =
      '<span class="yoo-toast__icon">' + ICONS[statusKey] + "</span>" +
      '<div class="yoo-toast__body">' +
        '<p class="yoo-toast__title"></p>' +
        '<p class="yoo-toast__message"></p>' +
      "</div>" +
      '<button type="button" class="yoo-toast__close" aria-label="Benachrichtigung schließen">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>' +
      "</button>" +
      '<div class="yoo-toast__progress"><span style="animation-duration:' + duration + 'ms"></span></div>';

    // Texte sicher setzen (kein HTML aus Aufrufern interpretieren).
    toast.querySelector(".yoo-toast__title").textContent = TITLES[statusKey];
    toast.querySelector(".yoo-toast__message").textContent = content;

    container.appendChild(toast);

    // Eintritts-Animation im nächsten Frame auslösen.
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        toast.classList.add("is-visible");
      });
    });

    // Auto-Dismiss mit Pause beim Hovern.
    var remaining = duration;
    var startedAt = Date.now();

    function startTimer() {
      startedAt = Date.now();
      toast._timer = window.setTimeout(function () {
        dismiss(toast);
      }, remaining);
    }

    startTimer();

    toast.addEventListener("mouseenter", function () {
      if (toast._leaving) {
        return;
      }
      window.clearTimeout(toast._timer);
      remaining -= Date.now() - startedAt;
      toast.classList.add("is-paused");
    });

    toast.addEventListener("mouseleave", function () {
      if (toast._leaving) {
        return;
      }
      toast.classList.remove("is-paused");
      startTimer();
    });

    toast.querySelector(".yoo-toast__close").addEventListener("click", function () {
      dismiss(toast);
    });

    return toast;
  }

  window.YooToast = { show: show, dismiss: dismiss };

  // Abwärtskompatible globale Funktion.
  window.sendNotif = function (content, status, position) {
    return show(content, status || "info", position || "bottom-right");
  };
})(window, document);
