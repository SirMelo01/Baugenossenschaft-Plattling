/**
 * UnsavedGuard
 * ============
 * Zentraler Schutz vor Datenverlust: erkennt ungespeicherte Änderungen auf einer
 * CMS-Editor-Seite, zeigt das deutlich an (Badge) und warnt sauber, bevor man
 * weg navigiert (interne Links, Navbar, Tab schließen, Zurück, Neu laden).
 *
 * Wiederverwendbar für Seiten, Blogs, Produkte, Galerien, ...
 *
 *   UnsavedGuard.init({
 *     name: "blog",
 *     watch: "main",                     // Scope für input/change/select (Default: main)
 *     watchMutations: ["#blogContent"],  // Container, deren DOM-Änderungen "dirty" bedeuten
 *     dirtyEvents: ["yoolink:builder-change"], // zusätzliche Events, die "dirty" auslösen
 *     attributeWatch: [                  // Attribut-Swaps (Bild/Galerie/Video) = dirty
 *       { selector: ".content-image", attributes: ["imgid", "src"] }
 *     ],
 *     saveTrigger: "#updateBlog",        // Klick hierauf = Speichern
 *     savedEvent: "blogSaved",           // document-Event bei Erfolg
 *     errorEvent: "blogSaveError"        // document-Event bei Fehler
 *   });
 *
 * Öffentliche API: UnsavedGuard.markDirty(), .markClean(), .isDirty()
 */
(function (window, $) {
    "use strict";

    var guard = {
        _initialized: false,
        _dirty: false,
        _bypass: false,
        _armed: true,   // solange false werden Änderungen ignoriert (z.B. initiales Laden)
        _config: null
    };

    /* ----------------------------------------------------------------- *
     * Dirty-State
     * ----------------------------------------------------------------- */
    function markDirty() {
        // Während des initialen (programmatischen) Aufbaus einer Seite noch nicht
        // scharf -> verhindert ein "Nicht gespeichert" direkt nach dem Laden.
        if (!guard._armed) return;
        if (guard._dirty) return;
        guard._dirty = true;
        toggleBadge(true);
    }

    function arm() {
        guard._armed = true;
    }

    function markClean() {
        guard._dirty = false;
        toggleBadge(false);
    }

    function toggleBadge(show) {
        var $badge = $("[data-unsaved-badge]");
        if (!$badge.length) return;
        $badge.toggleClass("hidden", !show).toggleClass("inline-flex", show);
    }

    /* ----------------------------------------------------------------- *
     * Badge – wird vor dem Speichern-Button eingefügt, falls keiner da ist
     * ----------------------------------------------------------------- */
    function ensureBadge(cfg) {
        if ($("[data-unsaved-badge]").length) return;       // Seite stellt eigenes Badge
        if (!cfg.saveTrigger) return;
        var $save = $(cfg.saveTrigger).first();
        if (!$save.length) return;
        var $badge = $(
            '<span data-unsaved-badge class="hidden items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">' +
            '<span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500"></span>' +
            'Nicht gespeichert' +
            '</span>'
        );
        // Badge + Speichern-Button gemeinsam in eine Flex-Zeile packen, damit das Badge
        // sauber neben dem Button liegt (mit Abstand) – egal wie der Button-Container
        // aufgebaut ist. Verhindert das "klebt drüber / macht Leiste höher"-Problem.
        var $group = $('<div class="flex flex-wrap items-center justify-end gap-2"></div>');
        $save.before($group);
        $group.append($badge).append($save);
    }

    /* ----------------------------------------------------------------- *
     * Bestätigungs-Modal (im CMS-Stil, nicht das laute Swal)
     * ----------------------------------------------------------------- */
    function ensureModal() {
        if (document.getElementById("unsavedGuardModal")) return;
        var hasSave = guard._config && guard._config.saveTrigger;
        var saveBtn = hasSave
            ? '<button type="button" data-guard-action="save" class="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700">' +
              '<i class="bi bi-check2"></i> Speichern &amp; fortfahren</button>'
            : "";
        var html =
            '<div id="unsavedGuardModal" class="fixed inset-0 z-[200] hidden items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">' +
              '<div data-guard-card class="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">' +
                '<div class="flex items-start gap-4 p-6">' +
                  '<span class="grid h-11 w-11 flex-shrink-0 place-items-center rounded-full bg-amber-100 text-amber-600"><i class="bi bi-exclamation-triangle text-xl"></i></span>' +
                  '<div class="min-w-0">' +
                    '<h3 class="text-lg font-semibold text-slate-900">Ungespeicherte Änderungen</h3>' +
                    '<p class="mt-1 text-sm leading-relaxed text-slate-500">Du hast Änderungen, die noch nicht gespeichert sind. Wenn du die Seite verlässt, gehen sie verloren.</p>' +
                  '</div>' +
                '</div>' +
                '<div class="flex flex-col gap-2 border-t border-slate-100 bg-slate-50 px-6 py-4">' +
                  saveBtn +
                  '<div class="flex gap-2">' +
                    '<button type="button" data-guard-action="discard" class="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-rose-200 bg-white px-4 py-2.5 text-sm font-semibold text-rose-600 transition hover:bg-rose-50"><i class="bi bi-trash"></i> Verwerfen</button>' +
                    '<button type="button" data-guard-action="cancel" class="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100">Abbrechen</button>' +
                  '</div>' +
                  '<a data-guard-action="newtab" href="#" class="mt-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium text-blue-600 transition hover:text-blue-800"><i class="bi bi-box-arrow-up-right"></i> Stattdessen in neuem Tab öffnen (Änderungen behalten)</a>' +
                '</div>' +
              '</div>' +
            '</div>';
        $("body").append(html);

        var $modal = $("#unsavedGuardModal");
        $modal.on("click", function (e) {
            if (e.target === this) closeModal();           // Klick auf Overlay
        });
        $modal.on("click", "[data-guard-action]", function (e) {
            e.preventDefault();
            var action = $(this).attr("data-guard-action");
            var url = $modal.data("targetUrl");
            if (action === "save") { closeModal(); saveThenNavigate(url); }
            else if (action === "discard") { closeModal(); navigateTo(url); }
            else if (action === "newtab") { closeModal(); window.open(url, "_blank", "noopener"); }
            else { closeModal(); }                          // cancel
        });
        $(document).on("keydown.unsavedGuard", function (e) {
            if (e.key === "Escape" && $modal.is(":visible")) closeModal();
        });
    }

    function openModal(url) {
        ensureModal();
        var $modal = $("#unsavedGuardModal");
        $modal.data("targetUrl", url).removeClass("hidden").addClass("flex");
    }

    function closeModal() {
        $("#unsavedGuardModal").addClass("hidden").removeClass("flex");
    }

    /* ----------------------------------------------------------------- *
     * Navigation
     * ----------------------------------------------------------------- */
    function navigateTo(url) {
        guard._bypass = true;
        markClean();
        if (url) window.location.href = url;
    }

    function saveThenNavigate(url) {
        var cfg = guard._config;
        if (!cfg || !cfg.saveTrigger) { navigateTo(url); return; }
        var ns = "unsavedGuardSave";
        var timer;
        function cleanup() {
            window.clearTimeout(timer);
            $(document).off("." + ns);
        }
        function onSaved() { cleanup(); navigateTo(url); }
        function onError() { cleanup(); }
        // .one mit Namespace, damit wir nur diese temporären Listener wieder lösen.
        $(document).one(cfg.savedEvent + "." + ns, onSaved);
        if (cfg.errorEvent) $(document).one(cfg.errorEvent + "." + ns, onError);
        // Safety-Net: bricht das Speichern still ab (z.B. Validierung), lösen wir
        // die temporären Listener nach kurzer Zeit wieder, statt sie zu behalten.
        timer = window.setTimeout(cleanup, 12000);
        $(cfg.saveTrigger).first().trigger("click");
    }

    /* ----------------------------------------------------------------- *
     * Link-Interception
     * ----------------------------------------------------------------- */
    function shouldGuardLink($a, anchor) {
        var href = $a.attr("href");
        if (!href || href === "#" || href.charAt(0) === "#") return false;
        if (/^(javascript:|mailto:|tel:)/i.test(href)) return false;
        if ($a.attr("target") === "_blank") return false;
        if ($a.is("[download]")) return false;
        if (anchor.dataset && anchor.dataset.guardIgnore !== undefined) return false;
        if ($a.closest("#unsavedGuardModal").length) return false;
        // Reiner Hash-Sprung auf derselben Seite -> kein echtes Verlassen
        if (anchor.pathname === window.location.pathname &&
            anchor.search === window.location.search &&
            anchor.hash) return false;
        return true;
    }

    function bindLinkInterception() {
        document.addEventListener("click", function (e) {
            if (!guard._dirty) return;
            var anchor = e.target.closest ? e.target.closest("a[href]") : null;
            if (!anchor) return;
            var $a = $(anchor);
            if (!shouldGuardLink($a, anchor)) return;
            e.preventDefault();
            e.stopPropagation();
            openModal(anchor.href);
        }, true); // Capture-Phase: vor anderen Handlern
    }

    /* ----------------------------------------------------------------- *
     * Init
     * ----------------------------------------------------------------- */
    function init(cfg) {
        if (guard._initialized) return;
        guard._initialized = true;
        guard._config = cfg = cfg || {};

        // Seiten, die ihren Inhalt erst per JS aufbauen (z.B. Blog-Editor), erst
        // scharf schalten, wenn der Aufbau fertig ist – manuell via UnsavedGuard.arm()
        // und als Sicherheitsnetz nach armDelay ms automatisch.
        if (cfg.armManually) {
            guard._armed = false;
            window.setTimeout(arm, cfg.armDelay || 4000);
        }

        var scope = cfg.watch || "main";
        var $scope = $(scope);
        if (!$scope.length) $scope = $("body");

        ensureBadge(cfg);

        // 1) Eingaben markieren als "dirty".
        $scope.on("input.unsavedGuard change.unsavedGuard", "input, textarea, select", function () {
            if (this.closest("#unsavedGuardModal")) return;
            if (this.closest("[data-guard-ignore]")) return;
            markDirty();
        });

        // 2) Zusätzliche Custom-Events (z.B. Builder-Änderungen).
        (cfg.dirtyEvents || []).forEach(function (ev) {
            $(document).on(ev, markDirty);
        });

        // 3) DOM-Änderungen in Containern (z.B. Blog-Builder) -> dirty.
        if (window.MutationObserver) {
            (cfg.watchMutations || []).forEach(function (sel) {
                $(sel).each(function () {
                    new MutationObserver(markDirty).observe(this, {
                        childList: true, subtree: true
                    });
                });
            });
            // 4) Attribut-Swaps (Bild/Galerie/Video-Auswahl per Modal).
            (cfg.attributeWatch || []).forEach(function (rule) {
                $scope.find(rule.selector).each(function () {
                    new MutationObserver(function (mutations) {
                        for (var i = 0; i < mutations.length; i++) {
                            if (mutations[i].type === "attributes") { markDirty(); return; }
                        }
                    }).observe(this, { attributes: true, attributeFilter: rule.attributes });
                });
            });
        }

        // 5) Erfolgreiches Speichern räumt den Dirty-State ab.
        if (cfg.savedEvent) $(document).on(cfg.savedEvent, markClean);

        // 6) Link-Interception + Browser-Safety-Net.
        bindLinkInterception();
        window.addEventListener("beforeunload", function (e) {
            if (guard._dirty && !guard._bypass) {
                e.preventDefault();
                e.returnValue = "";
                return "";
            }
        });
    }

    /* ----------------------------------------------------------------- *
     * Auto-Presets: erkennt bekannte Editor-Seiten anhand des Save-Buttons.
     * ----------------------------------------------------------------- */
    function autoInit() {
        if (guard._initialized) return;

        var seitenAttr = [
            { selector: ".content-image", attributes: ["imgid", "src"] },
            { selector: ".galery-container", attributes: ["galery-id"] },
            { selector: ".content-video", attributes: ["videoid", "src"] }
        ];

        if (document.getElementById("saveTextData")) {
            init({
                name: "seiten",
                watch: "main",
                saveTrigger: "#saveTextData",
                savedEvent: "textContentSaved",
                errorEvent: "textContentSaveError",
                attributeWatch: seitenAttr
            });
        } else if (document.getElementById("updateBlog")) {
            init({
                name: "blog-edit",
                watch: "main",
                saveTrigger: "#updateBlog",
                savedEvent: "blogSaved",
                errorEvent: "blogSaveError",
                watchMutations: ["#blogContent"],
                dirtyEvents: ["yoolink:builder-change"],
                // Blog-Editor baut den vorhandenen Inhalt erst per JS auf.
                armManually: true,
                armDelay: 5000
            });
        } else if (document.getElementById("createBlog")) {
            init({
                name: "blog-create",
                watch: "main",
                saveTrigger: "#createBlog",
                savedEvent: "blogSaved",
                errorEvent: "blogSaveError",
                watchMutations: ["#blogContent"],
                dirtyEvents: ["yoolink:builder-change"],
                // Falls beim Laden ein Standard-Block eingefügt wird: kurz warten.
                armManually: true,
                armDelay: 1500
            });
        } else if (document.getElementById("savePrivacyPolicy")) {
            init({
                name: "datenschutz",
                watch: "main",
                saveTrigger: "#savePrivacyPolicy",
                savedEvent: "textContentSaved",
                errorEvent: "textContentSaveError"
            });
        } else if (document.getElementById("saveImpressum")) {
            init({
                name: "impressum",
                watch: "main",
                saveTrigger: "#saveImpressum",
                savedEvent: "textContentSaved",
                errorEvent: "textContentSaveError",
                watchMutations: ["#impressumBlocks"]
            });
        }
    }

    window.UnsavedGuard = {
        init: init,
        arm: arm,
        markDirty: markDirty,
        markClean: markClean,
        isDirty: function () { return guard._dirty; }
    };

    $(autoInit);
})(window, jQuery);
