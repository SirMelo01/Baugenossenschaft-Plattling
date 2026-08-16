/**
 * Zentrale CMS-Mediathek.
 *
 * Bis hierher hatte jede Seite (Seiten-Builder, Team, Kunden, Blog, Markdown)
 * ihre eigene Kopie von "Bilder laden + Kacheln rendern + Paginierung". Die
 * Kopien liefen auseinander: mal gab es Paginierung, mal nicht, mal wurde beim
 * Klick sofort uebernommen, mal nur vorgemerkt.
 *
 * Dieses Modul ist die einzige Stelle, die mit /cms/images/ spricht und Kacheln
 * baut. `media-picker.js` setzt darauf den gemeinsamen Dialog auf.
 *
 * Fuer gefuehlte Geschwindigkeit sorgen hier drei Dinge:
 *   1. Seiten-Cache je Suchbegriff  -> Zurueck/Weiter ist beim zweiten Mal sofort da
 *   2. Prefetch der Folgeseite      -> "Weiter" ist meistens schon geladen
 *   3. Skeleton + Busy-State        -> nie ein toter Klick ohne Rueckmeldung
 */
(function (window, $) {
    'use strict';

    if (!$) return;

    var LIST_URL = '/cms/images/all/';
    var INFO_URL = '/cms/images/{id}/info/';
    var DELETE_URL = '/cms/images/delete/{id}/';
    var UPDATE_URL = '/cms/images/update/{id}/';
    var UPLOAD_URL = '/cms/upload/post';
    var CONVERT_URL = '/cms/images/convert-webp/';

    var SEARCH_DEBOUNCE_MS = 250;
    var SKELETON_DELAY_MS = 120;   // erst ab hier Skeleton zeigen -> kein Flackern bei Cache-Treffern
    var PREFETCH_DELAY_MS = 350;
    var MAX_CACHED_PAGES = 40;

    // ---------------------------------------------------------------- Helpers

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /** Kuerzt lange Dateinamen in der Mitte, damit Meta-Zeilen nicht umbrechen. */
    function truncateMiddle(value, max) {
        value = String(value == null ? '' : value);
        max = max || 28;
        if (value.length <= max) return value;
        var keep = max - 1;
        return value.slice(0, Math.ceil(keep / 2)) + '…' + value.slice(value.length - Math.floor(keep / 2));
    }

    function csrfToken() {
        var fromInput = $('input[name="csrfmiddlewaretoken"]').first().val();
        if (fromInput) return fromInput;
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function notify(message, type) {
        if (typeof window.sendNotif === 'function') {
            window.sendNotif(message, type || 'success');
        }
    }

    function optimizationText(image) {
        if (!image || !image.optimization) return '';
        var optimization = image.optimization;
        var desktop = optimization.desktop || {};
        var mobile = optimization.mobile || {};
        var desktopSaved = optimization.desktop_saved_percent > 0 ? ' / -' + optimization.desktop_saved_percent + '%' : '';
        var mobileSaved = optimization.mobile_saved_percent > 0 ? ' / -' + optimization.mobile_saved_percent + '%' : '';
        var mobileText = optimization.skipped ? 'Keine mobile Variante' : 'Mobil ' + (mobile.size_kb || 0) + ' KB' + mobileSaved;
        return 'Original ' + (optimization.original_size_kb || 0) + ' KB | Desktop ' +
            (desktop.size_kb || 0) + ' KB' + desktopSaved + ' | ' + mobileText;
    }

    function noop() {}

    // -------------------------------------------------------------------- API

    var api = {
        list: function (params) {
            return $.ajax({
                url: LIST_URL,
                type: 'GET',
                dataType: 'json',
                data: {
                    page: params.page || 1,
                    per_page: params.perPage || 12,
                    q: params.q || ''
                }
            });
        },

        info: function (id) {
            return $.ajax({
                url: INFO_URL.replace('{id}', encodeURIComponent(id)),
                type: 'GET',
                dataType: 'json'
            });
        },

        remove: function (id) {
            return $.ajax({
                url: DELETE_URL.replace('{id}', encodeURIComponent(id)),
                type: 'POST',
                headers: { 'X-CSRFToken': csrfToken() }
            });
        },

        updateTitle: function (id, title) {
            return $.ajax({
                url: UPDATE_URL.replace('{id}', encodeURIComponent(id)),
                type: 'POST',
                data: { title: title },
                headers: { 'X-CSRFToken': csrfToken() }
            });
        },

        convertWebp: function () {
            return $.ajax({
                url: CONVERT_URL,
                type: 'POST',
                headers: { 'X-CSRFToken': csrfToken() }
            });
        },

        /** Upload mit echtem Fortschritt (XHR-Progress statt "irgendwann fertig"). */
        upload: function (file, options) {
            options = options || {};
            var formData = new FormData();
            formData.append('file', file);
            if (options.skipOptimization) formData.append('skip_optimization', '1');

            return $.ajax({
                url: UPLOAD_URL,
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                headers: { 'X-CSRFToken': csrfToken() },
                xhr: function () {
                    var xhr = $.ajaxSettings.xhr();
                    if (xhr.upload && typeof options.onProgress === 'function') {
                        xhr.upload.addEventListener('progress', function (event) {
                            if (!event.lengthComputable) return;
                            options.onProgress(Math.round((event.loaded / event.total) * 100));
                        });
                    }
                    return xhr;
                }
            });
        }
    };

    // ------------------------------------------------------------- Seiten-Cache

    function createPageStore() {
        var pages = {};
        var order = [];

        return {
            key: function (q, perPage, page) {
                return (q || '') + '|' + perPage + '|' + page;
            },
            get: function (key) {
                return pages[key];
            },
            set: function (key, value) {
                if (!pages[key]) order.push(key);
                pages[key] = value;
                while (order.length > MAX_CACHED_PAGES) {
                    delete pages[order.shift()];
                }
            },
            clear: function () {
                pages = {};
                order = [];
            }
        };
    }

    // -------------------------------------------------------------- Grid-Markup

    function tileMarkup(image, config) {
        var title = escapeHtml(image.title || 'Bild');
        var preview = escapeHtml(image.preview_url || image.mobile_url || image.url || '');
        var badge = escapeHtml(image.format || 'IMG') + (image.has_mobile ? ' · Mobil' : '');

        var deleteButton = config.allowDelete
            ? '<span class="media-tile-delete" data-media-delete="' + image.id + '" role="button" tabindex="-1" ' +
              'title="Bild löschen" aria-label="Bild löschen"><i class="bi bi-trash" aria-hidden="true"></i></span>'
            : '';

        return '' +
            '<button type="button" class="media-tile" data-media-id="' + image.id + '" ' +
            'aria-pressed="false" title="' + title + '">' +
                '<span class="media-tile-frame ' + (config.tileHeightClass || '') + '">' +
                    '<img src="' + preview + '" alt="' + title + '" loading="lazy" decoding="async">' +
                '</span>' +
                '<span class="media-tile-badge">' + badge + '</span>' +
                deleteButton +
                '<span class="media-tile-caption">' + title + '</span>' +
                '<span class="media-tile-check" aria-hidden="true"><i class="bi bi-check-lg"></i></span>' +
            '</button>';
    }

    function skeletonMarkup(count, heightClass) {
        var html = '';
        for (var i = 0; i < count; i += 1) {
            html += '<div class="media-tile-skeleton ' + (heightClass || '') + '" aria-hidden="true"></div>';
        }
        return html;
    }

    // ------------------------------------------------------------ Grid-Controller

    /**
     * Baut einen wiederverwendbaren Bild-Grid inkl. Suche, Paginierung und
     * Ladezustaenden. Alle Optionen ausser `grid` sind optional - fehlende
     * Elemente werden einfach ignoriert, damit schlankere Dialoge (Blog,
     * Markdown) dieselbe Logik nutzen koennen.
     */
    function createGrid(options) {
        var config = $.extend({
            grid: null,
            empty: null,
            status: null,
            search: null,
            reload: null,
            prev: null,
            next: null,
            info: null,
            perPage: 12,
            allowDelete: false,
            tileHeightClass: '',
            onSelect: noop,
            onActivate: null,       // Doppelklick / Enter
            onLoaded: noop,
            onDeleted: noop,
            onError: null
        }, options || {});

        var $grid = $(config.grid);
        if (!$grid.length) return null;

        var $empty = config.empty ? $(config.empty) : $();
        var $status = config.status ? $(config.status) : $();
        var $search = config.search ? $(config.search) : $();
        var $reload = config.reload ? $(config.reload) : $();
        var $prev = config.prev ? $(config.prev) : $();
        var $next = config.next ? $(config.next) : $();
        var $info = config.info ? $(config.info) : $();

        var store = createPageStore();
        var namespace = '.cmsMedia' + (createGrid.counter = (createGrid.counter || 0) + 1);

        var state = {
            page: 1,
            query: '',
            perPage: config.perPage,
            items: [],
            pagination: { page: 1, total_pages: 1, total: 0, has_previous: false, has_next: false },
            selectedId: null,
            loading: false,
            sequence: 0,
            searchTimer: null,
            skeletonTimer: null,
            prefetchTimer: null,
            destroyed: false
        };

        // ---------------------------------------------------------- Rendering

        function setBusy(isBusy) {
            state.loading = isBusy;
            $grid.attr('aria-busy', isBusy ? 'true' : 'false');
            $grid.closest('[data-media-grid-wrap]').toggleClass('is-loading', isBusy);
            if (isBusy) {
                // Doppelklicks auf "Weiter" waeren sonst ein zweiter Request.
                $prev.prop('disabled', true);
                $next.prop('disabled', true);
            } else {
                updatePagination();
            }
        }

        function showSkeleton() {
            $empty.addClass('hidden');
            $grid.html(skeletonMarkup(state.perPage, config.tileHeightClass));
        }

        function scheduleSkeleton() {
            window.clearTimeout(state.skeletonTimer);
            state.skeletonTimer = window.setTimeout(function () {
                if (state.loading) showSkeleton();
            }, SKELETON_DELAY_MS);
        }

        function cancelSkeleton() {
            window.clearTimeout(state.skeletonTimer);
        }

        function updatePagination() {
            var pagination = state.pagination || {};
            var page = pagination.page || 1;
            var totalPages = pagination.total_pages || 1;
            var total = pagination.total || 0;

            if ($info.length) {
                $info.text(total
                    ? 'Seite ' + page + ' von ' + totalPages + ' · ' + total + ' Bilder'
                    : 'Keine Bilder');
            }
            $prev.prop('disabled', state.loading || !pagination.has_previous);
            $next.prop('disabled', state.loading || !pagination.has_next);

            // Bei nur einer Seite sind die Buttons reine Deko - dann ausblenden.
            $prev.add($next).toggleClass('is-hidden', totalPages <= 1 && !state.loading);
        }

        function setStatus(text) {
            if ($status.length) $status.text(text || '');
        }

        function render() {
            cancelSkeleton();

            if (!state.items.length) {
                $grid.empty();
                $empty.removeClass('hidden');
                updatePagination();
                return;
            }

            $empty.addClass('hidden');
            var html = '';
            for (var i = 0; i < state.items.length; i += 1) {
                html += tileMarkup(state.items[i], config);
            }
            $grid.html(html);
            highlight();
            updatePagination();
        }

        /**
         * Nur Klassen umschalten statt neu zu rendern - ein kompletter Re-Render
         * laesst den Browser alle Bilder neu dekodieren, was auf schwaecheren
         * Geraeten sichtbar ruckelt.
         */
        function highlight() {
            $grid.children('.media-tile').each(function () {
                var $tile = $(this);
                var selected = state.selectedId != null &&
                    String($tile.attr('data-media-id')) === String(state.selectedId);
                $tile.toggleClass('is-selected', selected);
                $tile.attr('aria-pressed', selected ? 'true' : 'false');
            });
        }

        // ------------------------------------------------------------- Laden

        function applyResponse(response) {
            state.items = response.image_urls || [];
            state.pagination = response.pagination || {
                page: state.page, total_pages: 1, total: state.items.length,
                has_previous: false, has_next: false
            };
            state.page = state.pagination.page || state.page;
            render();
            config.onLoaded(state.items, state.pagination, response);
        }

        function prefetchNext() {
            window.clearTimeout(state.prefetchTimer);
            if (!state.pagination.has_next) return;
            var nextPage = (state.pagination.page || state.page) + 1;
            var key = store.key(state.query, state.perPage, nextPage);
            if (store.get(key)) return;

            state.prefetchTimer = window.setTimeout(function () {
                if (state.destroyed) return;
                api.list({ page: nextPage, perPage: state.perPage, q: state.query })
                    .done(function (response) { store.set(key, response); });
            }, PREFETCH_DELAY_MS);
        }

        function load(opts) {
            opts = opts || {};
            if (state.destroyed) return;

            var page = opts.page || state.page || 1;
            var force = !!opts.force;
            var key = store.key(state.query, state.perPage, page);
            var cached = force ? null : store.get(key);

            state.page = page;

            if (cached) {
                // Cache-Treffer: sofort rendern, kein Ladezustand noetig.
                setBusy(false);
                applyResponse(cached);
                prefetchNext();
                return;
            }

            var sequence = ++state.sequence;
            setBusy(true);
            setStatus('Bilder werden geladen …');
            scheduleSkeleton();

            api.list({ page: page, perPage: state.perPage, q: state.query })
                .done(function (response) {
                    if (state.destroyed || sequence !== state.sequence) return; // veraltete Antwort
                    store.set(key, response);
                    setBusy(false);
                    setStatus('');
                    applyResponse(response);
                    prefetchNext();
                    if (opts.notify) {
                        notify(state.items.length ? 'Bilder wurden geladen' : 'Keine Bilder gefunden',
                            state.items.length ? 'success' : 'error');
                    }
                })
                .fail(function (xhr) {
                    if (state.destroyed || sequence !== state.sequence) return;
                    setBusy(false);
                    cancelSkeleton();
                    $grid.empty();
                    setStatus('');
                    $empty.removeClass('hidden');
                    if (typeof config.onError === 'function') config.onError(xhr);
                    else notify('Bilder konnten nicht geladen werden', 'error');
                });
        }

        function invalidate() {
            store.clear();
        }

        function reload(opts) {
            invalidate();
            load($.extend({ force: true }, opts || {}));
        }

        // ------------------------------------------------------------ Loeschen

        function confirmDelete(image) {
            var title = image.title || 'Dieses Bild';
            var text = 'Das Bild wird dauerhaft gelöscht und aus der Mediathek entfernt.';

            if (typeof window.Swal !== 'undefined') {
                window.Swal.fire({
                    title: 'Bild löschen?',
                    text: text,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#64748b',
                    confirmButtonText: 'Ja, löschen',
                    cancelButtonText: 'Abbrechen',
                    reverseButtons: true
                }).then(function (result) {
                    if (result.isConfirmed) performDelete(image);
                });
                return;
            }

            if (window.confirm(title + ' löschen?\n\n' + text)) performDelete(image);
        }

        function performDelete(image) {
            var $tile = $grid.children('[data-media-id="' + image.id + '"]');
            $tile.addClass('is-busy');

            api.remove(image.id)
                .done(function (response) {
                    invalidate();
                    if (String(state.selectedId) === String(image.id)) state.selectedId = null;
                    config.onDeleted(image, response);
                    // Wenn die Seite dadurch leer wird, eine Seite zurueck.
                    var lastOnPage = state.items.length <= 1 && state.page > 1;
                    load({ page: lastOnPage ? state.page - 1 : state.page, force: true });
                    notify((response && response.success) || 'Bild wurde gelöscht', 'success');
                })
                .fail(function () {
                    $tile.removeClass('is-busy');
                    notify('Bild konnte nicht gelöscht werden', 'error');
                });
        }

        // -------------------------------------------------------------- Events

        function itemById(id) {
            for (var i = 0; i < state.items.length; i += 1) {
                if (String(state.items[i].id) === String(id)) return state.items[i];
            }
            return null;
        }

        $grid.on('click' + namespace, '[data-media-delete]', function (event) {
            event.preventDefault();
            event.stopPropagation();
            var image = itemById($(this).attr('data-media-delete'));
            if (image) confirmDelete(image);
        });

        $grid.on('click' + namespace, '.media-tile', function () {
            var image = itemById($(this).attr('data-media-id'));
            if (!image) return;
            state.selectedId = image.id;
            highlight();
            config.onSelect(image);
        });

        $grid.on('dblclick' + namespace, '.media-tile', function () {
            var image = itemById($(this).attr('data-media-id'));
            if (image && typeof config.onActivate === 'function') config.onActivate(image);
        });

        // Pfeiltasten bewegen den Fokus im Grid, Enter uebernimmt direkt.
        $grid.on('keydown' + namespace, '.media-tile', function (event) {
            var $tiles = $grid.children('.media-tile');
            var index = $tiles.index(this);
            var columns = Math.max(1, Math.round($grid.innerWidth() / Math.max(1, $(this).outerWidth(true))));
            var target = null;

            if (event.key === 'ArrowRight') target = index + 1;
            else if (event.key === 'ArrowLeft') target = index - 1;
            else if (event.key === 'ArrowDown') target = index + columns;
            else if (event.key === 'ArrowUp') target = index - columns;
            else if (event.key === 'Enter' && typeof config.onActivate === 'function') {
                var image = itemById($(this).attr('data-media-id'));
                if (image) {
                    event.preventDefault();
                    state.selectedId = image.id;
                    highlight();
                    config.onSelect(image);
                    config.onActivate(image);
                }
                return;
            } else {
                return;
            }

            if (target != null && target >= 0 && target < $tiles.length) {
                event.preventDefault();
                $tiles.eq(target).trigger('focus');
            }
        });

        $search.on('input' + namespace, function () {
            var value = String($(this).val() || '').trim();
            window.clearTimeout(state.searchTimer);
            state.searchTimer = window.setTimeout(function () {
                if (value === state.query) return;
                state.query = value;
                load({ page: 1 });
            }, SEARCH_DEBOUNCE_MS);
        });

        // Enter im Suchfeld soll nicht das umgebende Formular abschicken.
        $search.on('keydown' + namespace, function (event) {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            window.clearTimeout(state.searchTimer);
            state.query = String($(this).val() || '').trim();
            load({ page: 1, force: true });
        });

        $reload.on('click' + namespace, function () {
            reload({ notify: true });
        });

        $prev.on('click' + namespace, function () {
            if (state.loading || !state.pagination.has_previous) return;
            load({ page: state.page - 1 });
        });

        $next.on('click' + namespace, function () {
            if (state.loading || !state.pagination.has_next) return;
            load({ page: state.page + 1 });
        });

        // --------------------------------------------------------- Controller

        return {
            load: load,
            reload: reload,
            invalidate: invalidate,
            items: function () { return state.items; },
            pagination: function () { return state.pagination; },
            isLoading: function () { return state.loading; },
            find: itemById,
            setSelected: function (id) {
                state.selectedId = id;
                highlight();
            },
            getSelectedId: function () { return state.selectedId; },
            setQuery: function (value, options) {
                window.clearTimeout(state.searchTimer);
                state.query = String(value || '').trim();
                $search.val(state.query);
                if (!options || options.reload !== false) load({ page: 1 });
            },
            resetQuery: function () {
                // Auch den laufenden Debounce abbrechen, sonst ueberschreibt der
                // alte Suchbegriff gleich wieder das frisch geleerte Feld.
                window.clearTimeout(state.searchTimer);
                state.query = '';
                $search.val('');
            },
            focusFirst: function () {
                $grid.children('.media-tile').first().trigger('focus');
            },
            updateItem: function (image) {
                // Nur die betroffene Kachel anfassen, damit nichts neu dekodiert wird.
                var $tile = $grid.children('[data-media-id="' + image.id + '"]');
                var existing = itemById(image.id);
                if (existing) $.extend(existing, image);
                $tile.attr('title', image.title || 'Bild');
                $tile.find('img').attr('alt', image.title || 'Bild');
                $tile.find('.media-tile-caption').text(image.title || 'Bild');
            },
            destroy: function () {
                state.destroyed = true;
                window.clearTimeout(state.searchTimer);
                window.clearTimeout(state.skeletonTimer);
                window.clearTimeout(state.prefetchTimer);
                $grid.off(namespace);
                $search.off(namespace);
                $reload.off(namespace);
                $prev.off(namespace);
                $next.off(namespace);
            }
        };
    }

    window.CmsMedia = {
        api: api,
        createGrid: createGrid,
        escapeHtml: escapeHtml,
        truncateMiddle: truncateMiddle,
        optimizationText: optimizationText,
        csrfToken: csrfToken,
        notify: notify
    };
}(window, window.jQuery));
