/**
 * Zentraler Datei-Auswahl-Dialog (#documentModal aus components/DocumentSelectModal.html).
 *
 * Gegenstueck zu CmsMediaPicker, nur fuer Dokumente aus dem Modul "Dateien"
 * (AnyFile) statt fuer Bilder. Auswaehlen, suchen, umbenennen und hochladen
 * passiert im Dialog - man muss die Seite nicht verlassen, um erst eine Datei
 * in die Verwaltung zu laden.
 *
 * Verwendung:
 *
 *   CmsDocumentPicker.open({
 *       title: 'Vorlage wählen',
 *       currentId: 12,
 *       onApply: function (file) { ... },   // file = {id, title, url, ext, size, ...}
 *       onRemove: function () { ... }       // optional -> zeigt "Vorlage entfernen"
 *   });
 *
 * Einfachklick markiert, Doppelklick oder Enter uebernimmt, Escape schliesst,
 * der Fokus kehrt zum Ausloeser zurueck.
 */
(function (window, $) {
    'use strict';

    if (!$) return;

    var ENDPOINTS = {
        list: '/cms/anyfiles/all/',
        upload: '/cms/anyfiles/upload/',
        update: function (id) { return '/cms/anyfiles/update/' + id + '/'; }
    };

    var ICONS = {
        '.pdf': { icon: 'bi-file-earmark-pdf-fill', tone: 'text-rose-600' },
        '.doc': { icon: 'bi-file-earmark-word-fill', tone: 'text-blue-600' },
        '.docx': { icon: 'bi-file-earmark-word-fill', tone: 'text-blue-600' },
        '.xls': { icon: 'bi-file-earmark-excel-fill', tone: 'text-emerald-600' },
        '.xlsx': { icon: 'bi-file-earmark-excel-fill', tone: 'text-emerald-600' },
        '.ppt': { icon: 'bi-file-earmark-ppt-fill', tone: 'text-orange-600' },
        '.pptx': { icon: 'bi-file-earmark-ppt-fill', tone: 'text-orange-600' },
        '.zip': { icon: 'bi-file-earmark-zip-fill', tone: 'text-amber-600' },
        '.txt': { icon: 'bi-file-earmark-text-fill', tone: 'text-slate-600' }
    };

    var DEFAULTS = {
        eyebrow: 'Dateien',
        title: 'Datei auswählen',
        subtitle: 'Datei anklicken, links prüfen und übernehmen.',
        currentId: null,
        applyLabel: 'Datei übernehmen',
        removeLabel: 'Vorlage entfernen',
        onApply: null,
        onRemove: null,
        onClose: null
    };

    var state = {
        ready: false,
        open: false,
        options: $.extend({}, DEFAULTS),
        files: [],
        selected: null,
        query: '',
        lastFocus: null,
        uploadCounter: 0
    };

    var $modal, $grid, $empty, $apply, $remove, $titleInput, $titleSave, $preview;

    // ------------------------------------------------------------- Hilfsmittel

    function escapeHtml(value) {
        return $('<div>').text(value == null ? '' : String(value)).html();
    }

    function notify(message, type) {
        if (typeof window.sendNotif === 'function') window.sendNotif(message, type);
        else if (type === 'error') window.console && console.error(message);
    }

    function iconFor(ext) {
        return ICONS[(ext || '').toLowerCase()] || { icon: 'bi-file-earmark-fill', tone: 'text-slate-500' };
    }

    function sizeText(bytes) {
        var value = Number(bytes || 0);
        if (value >= 1048576) return (value / 1048576).toFixed(1).replace('.', ',') + ' MB';
        if (value > 0) return Math.max(1, Math.round(value / 1024)) + ' KB';
        return '';
    }

    function csrfToken() {
        return $('input[name="csrfmiddlewaretoken"]').first().val() || '';
    }

    // --------------------------------------------------------------- Darstellung

    function renderSelection() {
        var file = state.selected;
        var meta = iconFor(file && file.ext);
        var displayName = file ? (file.display_name || file.title || file.filename) : '';

        $('#documentSelectedIcon')
            .attr('class', 'grid h-11 w-11 flex-shrink-0 place-items-center rounded-lg bg-white text-xl ' + meta.tone)
            .html('<i class="bi ' + meta.icon + '" aria-hidden="true"></i>');

        $('#documentSelectedName').text(file ? displayName : 'Noch keine Datei gewählt');
        $('#documentSelectedMeta').text(
            file ? [file.ext ? file.ext.replace('.', '').toUpperCase() : '', sizeText(file.size), file.uploaded_at]
                .filter(Boolean).join(' · ') : ' '
        );

        $titleInput.val(file ? (file.title || '') : '').prop('disabled', !file);
        $titleSave.prop('disabled', !file);
        $apply.prop('disabled', !file);
        $preview.toggleClass('hidden', !file).toggleClass('flex', !!file)
                .attr('href', file ? file.url : '#');
    }

    function visibleFiles() {
        var query = state.query.trim().toLowerCase();
        if (!query) return state.files;
        return state.files.filter(function (file) {
            return ((file.display_name || '') + ' ' + (file.title || '') + ' ' + (file.filename || '')).toLowerCase().indexOf(query) !== -1;
        });
    }

    function renderGrid() {
        var files = visibleFiles();
        $empty.toggleClass('hidden', files.length > 0);

        $grid.html(files.map(function (file) {
            var meta = iconFor(file.ext);
            var active = state.selected && String(state.selected.id) === String(file.id);
            var details = [sizeText(file.size), file.uploaded_at].filter(Boolean).join(' · ');
            var displayName = file.display_name || file.title || file.filename || 'Datei';
            return '' +
                '<button type="button" data-document-id="' + escapeHtml(file.id) + '" tabindex="0"' +
                ' class="document-tile flex w-full items-center gap-3 rounded-lg border bg-white p-3 text-left transition hover:shadow-md ' +
                (active ? 'border-blue-500 ring-2 ring-blue-200' : 'border-slate-200 hover:border-blue-300') + '">' +
                '<span class="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-slate-100 text-lg ' + meta.tone + '">' +
                '<i class="bi ' + meta.icon + '" aria-hidden="true"></i></span>' +
                '<span class="min-w-0 flex-1">' +
                '<span class="block truncate text-sm font-semibold text-slate-800">' + escapeHtml(displayName) + '</span>' +
                (details ? '<span class="mt-0.5 block text-xs text-slate-500">' + escapeHtml(details) + '</span>' : '') +
                '</span>' +
                (active ? '<i class="bi bi-check-circle-fill flex-shrink-0 text-blue-600" aria-hidden="true"></i>' : '') +
                '</button>';
        }).join(''));
    }

    function selectById(id) {
        state.selected = state.files.filter(function (file) {
            return String(file.id) === String(id);
        })[0] || null;
        renderSelection();
        renderGrid();
    }

    // ------------------------------------------------------------------- Daten

    function load(selectId) {
        return $.get(ENDPOINTS.list)
            .done(function (response) {
                state.files = (response && response.files) || [];
                if (selectId != null) selectById(selectId);
                else {
                    // Auswahl nach dem Neuladen behalten, falls die Datei noch da ist.
                    var keep = state.selected && state.selected.id;
                    state.selected = null;
                    if (keep != null) selectById(keep);
                    else renderSelection();
                }
                renderGrid();
            })
            .fail(function () {
                notify('Dateien konnten nicht geladen werden', 'error');
            });
    }

    function saveTitle() {
        if (!state.selected) return;
        var file = state.selected;
        var title = ($titleInput.val() || '').trim();

        $titleSave.prop('disabled', true);
        $.ajax({
            type: 'POST',
            url: ENDPOINTS.update(file.id),
            data: { title: title },
            beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', csrfToken()); }
        })
            .done(function () {
                file.title = title;
                notify('Name wurde gespeichert', 'success');
                renderSelection();
                renderGrid();
            })
            .fail(function () { notify('Name konnte nicht gespeichert werden', 'error'); })
            .always(function () { $titleSave.prop('disabled', !state.selected); });
    }

    // ------------------------------------------------------------------ Upload

    function uploadRow(name) {
        var id = 'documentUpload' + (state.uploadCounter += 1);
        $('#documentUploadList').prepend(
            '<div id="' + id + '" class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">' +
            '<i class="bi bi-arrow-repeat animate-spin text-blue-600" aria-hidden="true"></i>' +
            '<span class="min-w-0 flex-1 truncate text-sm text-slate-700">' + escapeHtml(name) + '</span>' +
            '<span class="text-xs font-semibold text-slate-500" data-status>wird hochgeladen …</span>' +
            '</div>'
        );
        return id;
    }

    function finishRow(id, ok, text) {
        var $row = $('#' + id);
        $row.find('i').attr('class', ok
            ? 'bi bi-check-circle-fill text-emerald-600'
            : 'bi bi-exclamation-circle-fill text-rose-600');
        $row.find('[data-status]')
            .attr('class', 'text-xs font-semibold ' + (ok ? 'text-emerald-700' : 'text-rose-700'))
            .text(text);
    }

    function uploadFiles(fileList) {
        var files = Array.prototype.slice.call(fileList || []);
        if (!files.length) return;

        files.forEach(function (file) {
            var rowId = uploadRow(file.name);
            var data = new FormData();
            data.append('file', file);

            $.ajax({
                type: 'POST',
                url: ENDPOINTS.upload,
                data: data,
                processData: false,
                contentType: false,
                beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', csrfToken()); }
            })
                .done(function () {
                    finishRow(rowId, true, 'fertig');
                    // Die neue Datei ist die wahrscheinlichste Wahl - direkt markieren.
                    load().done(function () {
                        var newest = state.files[0];
                        if (newest) {
                            selectById(newest.id);
                            setTab('documentLibraryPanel');
                        }
                    });
                })
                .fail(function (xhr) {
                    var message = 'Upload fehlgeschlagen';
                    try {
                        var parsed = JSON.parse(xhr.responseText);
                        if (parsed && parsed.error) message = parsed.error;
                    } catch (error) { /* Serverantwort war kein JSON */ }
                    finishRow(rowId, false, message);
                    notify(message, 'error');
                });
        });
    }

    // -------------------------------------------------------------------- Tabs

    function setTab(panelId) {
        $modal.find('[data-document-tab]').each(function () {
            var active = $(this).data('documentTab') === panelId;
            $(this).toggleClass('is-active', active).attr('aria-selected', active ? 'true' : 'false');
        });
        $modal.find('.media-picker-panel').each(function () {
            var active = this.id === panelId;
            $(this).toggleClass('hidden', !active).toggleClass('flex', active);
        });
    }

    // --------------------------------------------------------- Öffnen/Schließen

    function ensureReady() {
        if (state.ready) return true;
        $modal = $('#documentModal');
        if (!$modal.length) return false;

        $grid = $('#documentGrid');
        $empty = $('#documentEmptyState');
        $apply = $('#documentApply');
        $remove = $('#documentRemove');
        $titleInput = $('#documentTitleInput');
        $titleSave = $('#documentTitleSave');
        $preview = $('#documentPreviewLink');

        $modal.on('click', '[data-document-tab]', function () { setTab($(this).data('documentTab')); });
        $modal.on('click', '.document-tile', function () { selectById($(this).data('documentId')); });
        $modal.on('dblclick', '.document-tile', function () {
            selectById($(this).data('documentId'));
            applySelection();
        });
        $modal.on('keydown', '.document-tile', function (event) {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            selectById($(this).data('documentId'));
            applySelection();
        });

        $('#documentSearchInput').on('input', function () {
            state.query = $(this).val() || '';
            renderGrid();
        });
        $('#documentReload').on('click', function () { load(); });
        $titleSave.on('click', saveTitle);
        $titleInput.on('keydown', function (event) {
            if (event.key === 'Enter') { event.preventDefault(); saveTitle(); }
        });

        $('#documentUploadInput').on('change', function () {
            uploadFiles(this.files);
            this.value = '';
        });
        var $dropzone = $('#documentDropzone');
        $dropzone.on('dragover dragenter', function (event) {
            event.preventDefault();
            $dropzone.addClass('border-blue-500 bg-blue-50');
        });
        $dropzone.on('dragleave drop', function () { $dropzone.removeClass('border-blue-500 bg-blue-50'); });
        $dropzone.on('drop', function (event) {
            event.preventDefault();
            uploadFiles(event.originalEvent.dataTransfer.files);
        });

        $apply.on('click', applySelection);
        $remove.on('click', function () {
            var onRemove = state.options.onRemove;
            close();
            if (typeof onRemove === 'function') onRemove();
        });
        $('#closeDocumentModal, #cancelDocumentModal').on('click', close);
        $modal.on('mousedown', function (event) { if (event.target === $modal[0]) close(); });
        $(document).on('keydown', function (event) {
            if (state.open && event.key === 'Escape') close();
        });

        state.ready = true;
        return true;
    }

    function applySelection() {
        if (!state.selected) return;
        var file = state.selected;
        var onApply = state.options.onApply;
        close();
        if (typeof onApply === 'function') onApply(file);
    }

    function open(options) {
        if (!ensureReady()) {
            notify('Der Datei-Dialog steht auf dieser Seite nicht zur Verfügung', 'error');
            return;
        }

        state.options = $.extend({}, DEFAULTS, options || {});
        state.lastFocus = document.activeElement;
        state.open = true;
        state.query = '';
        state.selected = null;

        $('#documentPickerEyebrow').text(state.options.eyebrow);
        $('#documentPickerTitle').text(state.options.title);
        $('#documentPickerSubtitle').text(state.options.subtitle);
        $apply.find('[data-document-apply-label]').text(state.options.applyLabel);
        $remove.text('').append('<i class="bi bi-x-circle" aria-hidden="true"></i> ' + state.options.removeLabel)
               .toggleClass('hidden', typeof state.options.onRemove !== 'function')
               .toggleClass('flex', typeof state.options.onRemove === 'function');

        $('#documentSearchInput').val('');
        $('#documentUploadList').empty();
        setTab('documentLibraryPanel');
        renderSelection();

        $modal.removeClass('hidden').addClass('flex').attr('aria-hidden', 'false');
        $('body').addClass('media-picker-open');

        load(state.options.currentId);

        window.setTimeout(function () { $('#documentSearchInput').trigger('focus'); }, 0);
    }

    function close() {
        if (!state.open) return;
        state.open = false;

        $modal.addClass('hidden').removeClass('flex').attr('aria-hidden', 'true');
        $('body').removeClass('media-picker-open');

        var onClose = state.options.onClose;
        if (state.lastFocus && typeof state.lastFocus.focus === 'function') {
            try { state.lastFocus.focus(); } catch (error) { /* Element ggf. entfernt */ }
        }
        state.lastFocus = null;
        if (typeof onClose === 'function') onClose();
    }

    window.CmsDocumentPicker = { open: open, close: close };
})(window, window.jQuery);
