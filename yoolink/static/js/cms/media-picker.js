/**
 * Zentraler Bild-Auswahl-Dialog (#imageModal aus components/ImageSelectModal.html).
 *
 * Vorher hatte jede Seite ihre eigene Steuerung fuer denselben Dialog - mit
 * unterschiedlichem Verhalten: im Seiten-Builder wurde erst vorgemerkt und dann
 * uebernommen, bei Team und Kunden sprang der Dialog beim ersten Klick zu, die
 * Paginierung war dort tot ("Seite 1", Weiter ohne Funktion).
 *
 * Jetzt gibt es genau einen Controller. Verwendung:
 *
 *   CmsMediaPicker.open({
 *       title: 'Titelbild wählen',
 *       currentImageId: 12,
 *       currentImageSrc: '/media/...',
 *       onApply: function (image) { ... },
 *       onRemove: function () { ... }   // optional -> zeigt "Bild entfernen"
 *   });
 *
 * Verhalten: Einfachklick markiert (Vorschau links), Doppelklick oder Enter
 * uebernimmt, Escape schliesst, der Fokus kehrt zum Ausloeser zurueck.
 */
(function (window, $) {
    'use strict';

    if (!$ || !window.CmsMedia) return;

    var CmsMedia = window.CmsMedia;
    var escapeHtml = CmsMedia.escapeHtml;

    var DEFAULTS = {
        eyebrow: 'Mediathek',
        title: 'Bild auswählen',
        subtitle: 'Bild anklicken, links prüfen und mit „Bild übernehmen“ einsetzen.',
        currentImageId: null,
        currentImageSrc: '',
        allowDelete: true,
        allowTitleEdit: true,
        applyLabel: 'Bild übernehmen',
        onApply: null,
        onRemove: null,
        onClose: null
    };

    var state = {
        ready: false,
        open: false,
        options: $.extend({}, DEFAULTS),
        grid: null,
        selected: null,
        lastFocus: null,
        mousedownInside: false,
        metaSequence: 0
    };

    var $modal, $preview, $placeholder, $titleInput, $titleSave, $apply, $remove, $meta;

    // ------------------------------------------------------------- Hilfsmittel

    function focusables() {
        return $modal.find(
            'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
            'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ).filter(':visible');
    }

    function setTab(panelId) {
        $modal.find('.media-picker-panel').addClass('hidden').removeClass('flex');
        $('#' + panelId).removeClass('hidden').addClass('flex');

        $modal.find('.media-picker-tab').each(function () {
            var active = $(this).attr('data-target') === panelId;
            $(this).toggleClass('is-active', active).attr('aria-selected', active ? 'true' : 'false');
        });
    }

    // ------------------------------------------------------------ Auswahl / Meta

    function showPreview(src) {
        if (src) {
            $preview.attr('src', src).removeClass('hidden');
            $placeholder.addClass('hidden');
        } else {
            $preview.attr('src', '').addClass('hidden');
            $placeholder.removeClass('hidden');
        }
    }

    function resetSelection() {
        state.selected = null;
        $titleInput.val('').prop('disabled', true);
        $titleSave.prop('disabled', true);
        $apply.prop('disabled', true);
        renderMeta(null);
        showPreview(state.options.currentImageSrc || '');
    }

    var META_LABELS = ['Datei', 'Format', 'Größe', 'Abmessung', 'Mobil', 'Upload'];

    /**
     * Rendert den Detail-Block - ohne Auswahl mit Platzhaltern statt mit einem
     * Hinweissatz. Grund ist die Höhe: waechst die Sidebar beim Anklicken eines
     * Bildes plötzlich um fünf Zeilen, wird der ganze Dialog höher und der
     * Bilder-Grid rechts springt mit.
     */
    function renderMeta(image) {
        var rows;

        if (!image) {
            rows = META_LABELS.map(function (label) { return [label, '—']; });
        } else {
            var metadata = image.metadata || {};
            var filename = metadata.filename || image.filename || 'Unbekannt';
            rows = [
                ['Datei', CmsMedia.truncateMiddle(filename, 26), filename],
                ['Format', image.format || 'Unbekannt'],
                ['Größe', metadata.size_kb ? metadata.size_kb + ' KB' : '…'],
                ['Abmessung', metadata.dimensions || '…'],
                ['Mobil', metadata.mobile_size_kb
                    ? metadata.mobile_size_kb + ' KB'
                    : (image.has_mobile ? 'Vorhanden' : 'Nein')],
                ['Upload', metadata.uploaded_at || image.uploaded_at || 'Unbekannt']
            ];
        }

        $meta.html(rows.map(function (row) {
            var titleAttr = row[2] ? ' title="' + escapeHtml(row[2]) + '"' : '';
            return '<div class="flex justify-between gap-3">' +
                '<span class="flex-shrink-0 font-semibold text-slate-600">' + escapeHtml(row[0]) + '</span>' +
                '<span class="min-w-0 truncate text-right"' + titleAttr + '>' + escapeHtml(row[1]) + '</span>' +
                '</div>';
        }).join(''));
    }

    /**
     * Groesse/Abmessungen stehen nicht in der Listenantwort - die muesste der
     * Server sonst fuer jedes Bild einzeln aus dem Storage lesen (der Grund fuer
     * die frueheren 2-3 Sekunden pro Seitenwechsel). Also holen wir sie erst
     * hier, fuer genau ein Bild, und cachen sie am Item.
     */
    function loadMetaDetails(image) {
        if (image.metadata) {
            renderMeta(image);
            return;
        }

        var sequence = ++state.metaSequence;
        CmsMedia.api.info(image.id)
            .done(function (response) {
                if (sequence !== state.metaSequence) return;
                if (!response || !response.image) return;
                $.extend(image, response.image);
                if (state.grid) state.grid.updateItem(image);
                if (state.selected && String(state.selected.id) === String(image.id)) renderMeta(image);
            });
    }

    function selectImage(image) {
        state.selected = image;
        showPreview(image.preview_url || image.url || '');

        $titleInput.val(image.title || '').prop('disabled', !state.options.allowTitleEdit);
        $titleSave.prop('disabled', !state.options.allowTitleEdit);
        $apply.prop('disabled', false);

        renderMeta(image);
        loadMetaDetails(image);
        if (state.grid) state.grid.setSelected(image.id);
    }

    function applySelection() {
        if (!state.selected) return;
        var image = state.selected;
        var onApply = state.options.onApply;
        close();
        if (typeof onApply === 'function') onApply(image);
    }

    // ------------------------------------------------------------------ Upload

    function uploadItemId() {
        return 'media-upload-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    }

    function addUploadItem(id, name) {
        $('#imageUploadQueue').removeClass('hidden');
        $('#imageUploadItems').prepend(
            '<div id="' + id + '" class="rounded-md bg-slate-50 px-3 py-2 text-sm">' +
                '<div class="flex items-center justify-between gap-3">' +
                    '<span class="truncate text-slate-700">' + escapeHtml(name) + '</span>' +
                    '<span class="upload-status flex-shrink-0 text-slate-500">0 %</span>' +
                '</div>' +
                '<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">' +
                    '<div class="upload-bar h-full w-0 rounded-full bg-blue-600 transition-all duration-200"></div>' +
                '</div>' +
                '<p class="upload-detail mt-1 hidden text-xs leading-snug text-slate-500"></p>' +
            '</div>'
        );
    }

    function setUploadProgress(id, percent) {
        var $item = $('#' + id);
        $item.find('.upload-bar').css('width', percent + '%');
        $item.find('.upload-status').text(percent + ' %');
    }

    function setUploadStatus(id, text, className, detail) {
        var $item = $('#' + id);
        $item.find('.upload-status')
            .removeClass('text-slate-500 text-green-700 text-red-700')
            .addClass(className)
            .text(text);
        $item.find('.upload-bar').toggleClass('bg-blue-600', className !== 'text-red-700')
            .toggleClass('bg-red-500', className === 'text-red-700')
            .css('width', '100%');
        if (detail) $item.find('.upload-detail').text(detail).removeClass('hidden');
    }

    function optimizationText(image) {
        return CmsMedia.optimizationText ? CmsMedia.optimizationText(image) : '';
    }

    function uploadFiles(fileList) {
        var files = Array.prototype.slice.call(fileList || []).filter(function (file) {
            return file.type && file.type.indexOf('image/') === 0;
        });

        if (!files.length) {
            CmsMedia.notify('Bitte wähle eine Bilddatei aus', 'error');
            return;
        }

        var skipOptimization = $('#imageUploadSkipOptimization').is(':checked');

        files.forEach(function (file) {
            var itemId = uploadItemId();
            addUploadItem(itemId, file.name);

            CmsMedia.api.upload(file, {
                skipOptimization: skipOptimization,
                onProgress: function (percent) { setUploadProgress(itemId, percent); }
            })
                .done(function (response) {
                    setUploadStatus(itemId, 'Fertig', 'text-green-700', optimizationText(response.image));
                    if (state.grid) {
                        // Der frische Upload steht auf Seite 1 - dorthin springen,
                        // egal wo man vorher geblättert oder gesucht hat.
                        state.grid.resetQuery();
                        state.grid.reload({ page: 1 });
                    }
                    if (response.image) {
                        setTab('imageLibraryPanel');
                        selectImage(response.image);
                    }
                    CmsMedia.notify('Bild wurde hochgeladen', 'success');
                })
                .fail(function () {
                    setUploadStatus(itemId, 'Fehlgeschlagen', 'text-red-700');
                    CmsMedia.notify('Bild konnte nicht hochgeladen werden', 'error');
                });
        });
    }

    // ------------------------------------------------------------------- WebP

    function updateWebpButton(hasNonWebp, count) {
        var $button = $('#convertImagesToWebp');
        if (!$button.length) return;
        $button.toggleClass('hidden', !hasNonWebp);
        $button.text(count ? 'WebP (' + count + ')' : 'WebP');
    }

    function convertToWebp() {
        var $button = $('#convertImagesToWebp');
        if ($button.prop('disabled')) return;
        var original = $button.text();
        $button.prop('disabled', true).text('Konvertiere …');

        CmsMedia.api.convertWebp()
            .done(function (response) {
                updateWebpButton(response.has_non_webp, response.remaining);
                if (state.grid) state.grid.reload();
                var skipped = response.skipped_variants ? ' (' + response.skipped_variants + ' übersprungen)' : '';
                CmsMedia.notify((response.converted_images || 0) + ' Bilder zu WebP konvertiert' + skipped, 'success');
            })
            .fail(function () {
                $button.text(original);
                CmsMedia.notify('WebP-Konvertierung konnte nicht abgeschlossen werden', 'error');
            })
            .always(function () {
                $button.prop('disabled', false);
            });
    }

    // ------------------------------------------------------------------ Titel

    function saveTitle() {
        if (!state.selected) return;
        var title = String($titleInput.val() || '').trim();
        if (!title) {
            CmsMedia.notify('Bitte gib einen Bildtitel ein', 'error');
            return;
        }

        $titleSave.prop('disabled', true);
        CmsMedia.api.updateTitle(state.selected.id, title)
            .done(function (response) {
                state.selected.title = title;
                if (state.grid) state.grid.updateItem(state.selected);
                renderMeta(state.selected);
                CmsMedia.notify((response && response.success) || 'Bildtitel wurde gespeichert', 'success');
            })
            .fail(function () {
                CmsMedia.notify('Bildtitel konnte nicht gespeichert werden', 'error');
            })
            .always(function () {
                $titleSave.prop('disabled', false);
            });
    }

    // ------------------------------------------------------------ Öffnen/Schließen

    function open(options) {
        if (!ensureReady()) {
            CmsMedia.notify('Der Bild-Dialog steht auf dieser Seite nicht zur Verfügung', 'error');
            return;
        }

        state.options = $.extend({}, DEFAULTS, options || {});
        state.lastFocus = document.activeElement;
        state.open = true;

        $('#mediaPickerEyebrow').text(state.options.eyebrow);
        $('#mediaPickerTitle').text(state.options.title);
        $('#mediaPickerSubtitle').text(state.options.subtitle);
        $apply.find('[data-media-apply-label]').text(state.options.applyLabel);
        $modal.find('[data-media-title-row]').toggleClass('hidden', !state.options.allowTitleEdit);
        $remove.toggleClass('hidden', typeof state.options.onRemove !== 'function')
               .toggleClass('flex', typeof state.options.onRemove === 'function');

        resetSelection();
        setTab('imageLibraryPanel');

        $modal.removeClass('hidden').addClass('flex').attr('aria-hidden', 'false');
        $('body').addClass('media-picker-open');

        // Jeder Aufruf startet bei Seite 1 ohne alten Suchbegriff.
        state.grid.resetQuery();
        state.grid.setSelected(state.options.currentImageId);
        state.grid.load({ page: 1 });

        // Das aktuell gesetzte Bild vorladen, damit Titel/Details sofort editierbar sind.
        if (state.options.currentImageId && String(state.options.currentImageId) !== '-1') {
            var wanted = String(state.options.currentImageId);
            CmsMedia.api.info(wanted).done(function (response) {
                if (!state.open || !response || !response.image) return;
                if (String(state.options.currentImageId) !== wanted) return;
                if (state.selected) return;      // Nutzer war schneller
                selectImage(response.image);
            });
        }

        window.setTimeout(function () {
            $('#imageSearchInput').trigger('focus');
        }, 0);
    }

    function close() {
        if (!state.open) return;
        state.open = false;
        state.metaSequence += 1;

        $modal.addClass('hidden').removeClass('flex').attr('aria-hidden', 'true');
        $('body').removeClass('media-picker-open');

        var onClose = state.options.onClose;
        if (state.lastFocus && typeof state.lastFocus.focus === 'function') {
            try { state.lastFocus.focus(); } catch (error) { /* Element ggf. entfernt */ }
        }
        state.lastFocus = null;
        if (typeof onClose === 'function') onClose();
    }

    // ------------------------------------------------------------------ Setup

    function ensureReady() {
        if (state.ready) return true;

        $modal = $('#imageModal');
        if (!$modal.length || !$modal.hasClass('media-picker')) return false;

        $preview = $('#selectedImagePreview');
        $placeholder = $('#selectedImagePlaceholder');
        $titleInput = $('#selectedImageTitleInput');
        $titleSave = $('#selectedImageTitleSave');
        $apply = $('#selectedImageApply');
        $remove = $('#selectedImageRemove');
        $meta = $('#selectedImageMeta');

        state.grid = CmsMedia.createGrid({
            grid: '#possibleImages',
            empty: '#imageEmptyState',
            search: '#imageSearchInput',
            reload: '#reloadImages',
            prev: '#imagePrevPage',
            next: '#imageNextPage',
            info: '#imagePaginationInfo',
            perPage: 12,
            allowDelete: true,
            onSelect: selectImage,
            onActivate: function (image) {
                selectImage(image);
                applySelection();
            },
            onLoaded: function (items, pagination, response) {
                updateWebpButton(Boolean(response.has_non_webp), response.non_webp_count || 0);
            },
            onDeleted: function (image) {
                if (state.selected && String(state.selected.id) === String(image.id)) resetSelection();
                // Zeigt das Ziel-Element noch auf das geloeschte Bild? Dann leeren.
                if (state.options.currentImageId && String(state.options.currentImageId) === String(image.id)) {
                    state.options.currentImageId = null;
                    state.options.currentImageSrc = '';
                }
            }
        });

        if (!state.grid) return false;   // Grid-Container fehlt -> Dialog unbrauchbar

        bindEvents();
        state.ready = true;
        return true;
    }

    function bindEvents() {
        $('#closeImageModal').on('click', close);
        $apply.on('click', applySelection);
        $titleSave.on('click', saveTitle);
        $titleInput.on('keydown', function (event) {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            saveTitle();
        });

        $remove.on('click', function () {
            var onRemove = state.options.onRemove;
            close();
            if (typeof onRemove === 'function') onRemove();
        });

        $('#convertImagesToWebp').on('click', convertToWebp);

        $modal.find('.media-picker-tab').on('click', function () {
            setTab($(this).attr('data-target'));
        });

        // ---- Upload
        var $dropzone = $('#imageUploadDropzone');
        var $input = $('#imageUploadInput');

        $dropzone.on('click', function (event) {
            if (event.target === $input[0]) return;
            $input[0].click();
        });
        $dropzone.on('keydown', function (event) {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            $input[0].click();
        });
        $input.on('click', function (event) { event.stopPropagation(); });
        $input.on('change', function () {
            uploadFiles(this.files);
            this.value = '';
        });
        $dropzone.on('dragover', function (event) {
            event.preventDefault();
            $(this).addClass('border-blue-500 bg-blue-100');
        });
        $dropzone.on('dragleave drop', function () {
            $(this).removeClass('border-blue-500 bg-blue-100');
        });
        $dropzone.on('drop', function (event) {
            event.preventDefault();
            uploadFiles(event.originalEvent.dataTransfer.files);
        });

        // ---- Klick ausserhalb: nur schliessen, wenn die Geste komplett
        //      ausserhalb begann UND endete (sonst schliesst Textmarkieren den Dialog).
        var $container = $modal.find('.media-picker-container');

        function isInside(target) {
            return $container.is(target) || $container.has(target).length > 0;
        }

        $(document).on('mousedown.mediaPicker', function (event) {
            if (!state.open) return;
            state.mousedownInside = isInside(event.target);
        });

        $(document).on('mouseup.mediaPicker', function (event) {
            if (!state.open) return;
            if ($(event.target).closest('.swal2-container').length > 0) return;
            if (!state.mousedownInside && !isInside(event.target)) close();
        });

        // ---- Tastatur: Escape schliesst, Enter uebernimmt, Tab bleibt im Dialog.
        $(document).on('keydown.mediaPicker', function (event) {
            if (!state.open) return;
            if ($(event.target).closest('.swal2-container').length > 0) return;

            if (event.key === 'Escape') {
                event.preventDefault();
                close();
                return;
            }

            if (event.key === 'Enter' && state.selected && !$(event.target).is('input, textarea, button, a')) {
                event.preventDefault();
                applySelection();
                return;
            }

            if (event.key !== 'Tab') return;
            var $focusable = focusables();
            if (!$focusable.length) return;
            var first = $focusable[0];
            var last = $focusable[$focusable.length - 1];
            if (event.shiftKey && event.target === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && event.target === last) {
                event.preventDefault();
                first.focus();
            }
        });
    }

    window.CmsMediaPicker = {
        open: open,
        close: close,
        isOpen: function () { return state.open; },
        isAvailable: function () { return $('#imageModal.media-picker').length > 0; },
        /** Erlaubt Seiten, den Grid nach externen Aenderungen zu verwerfen. */
        invalidate: function () { if (state.grid) state.grid.invalidate(); }
    };

    $(function () { ensureReady(); });
}(window, window.jQuery));
