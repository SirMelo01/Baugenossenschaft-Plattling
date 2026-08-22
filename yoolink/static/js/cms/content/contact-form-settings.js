/**
 * Vorlagen-Auswahl der drei Kontaktformulare (Seiten -> Kontakt).
 *
 * Verbindet die Karten mit dem zentralen Datei-Dialog. Gespeichert wird hier
 * nichts: die Karten tragen ihren Stand in data-Attributen, und der eine
 * "Speichern"-Knopf oben schickt sie zusammen mit allen Textbausteinen mit
 * (siehe save-text.js). Genauso arbeiten auch die Bild- und Button-Slots.
 */
$(document).ready(function () {
    var ICONS = {
        '.pdf': { icon: 'bi-file-earmark-pdf-fill', bg: 'bg-rose-50', tone: 'text-rose-600' },
        '.doc': { icon: 'bi-file-earmark-word-fill', bg: 'bg-blue-50', tone: 'text-blue-600' },
        '.docx': { icon: 'bi-file-earmark-word-fill', bg: 'bg-blue-50', tone: 'text-blue-600' },
        '.xls': { icon: 'bi-file-earmark-excel-fill', bg: 'bg-emerald-50', tone: 'text-emerald-600' },
        '.xlsx': { icon: 'bi-file-earmark-excel-fill', bg: 'bg-emerald-50', tone: 'text-emerald-600' },
        '.zip': { icon: 'bi-file-earmark-zip-fill', bg: 'bg-amber-50', tone: 'text-amber-600' }
    };

    function iconFor(ext) {
        return ICONS[(ext || '').toLowerCase()] ||
            { icon: 'bi-file-earmark-fill', bg: 'bg-slate-100', tone: 'text-slate-500' };
    }

    function applyDocument($card, file) {
        var $box = $card.find('[data-document-card]');
        var $pick = $card.find('[data-document-pick]');

        if (!file) {
            $card.attr('data-document-id', '');
            $box.addClass('hidden');
            $pick.removeClass('hidden');
            return;
        }

        var meta = iconFor(file.ext);
        $card.attr('data-document-id', file.id);
        $box.find('span').first()
            .attr('class', 'grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg text-lg ' + meta.bg + ' ' + meta.tone)
            .html('<i class="bi ' + meta.icon + '" aria-hidden="true"></i>');
        $box.find('[data-document-name]').text(file.display_name || file.title || file.filename || 'Datei');
        $box.find('[data-document-link]').attr('href', file.url || '#');
        $box.removeClass('hidden');
        $pick.addClass('hidden');
    }

    function openPicker($card) {
        if (!window.CmsDocumentPicker) {
            if (typeof window.sendNotif === 'function') {
                window.sendNotif('Der Datei-Dialog konnte nicht geladen werden', 'error');
            }
            return;
        }

        var current = $card.attr('data-document-id') || null;
        window.CmsDocumentPicker.open({
            title: 'Vorlage wählen',
            subtitle: 'Die Vorlage können Besucher im Formular herunterladen.',
            applyLabel: 'Als Vorlage übernehmen',
            currentId: current || null,
            onApply: function (file) { applyDocument($card, file); },
            onRemove: current ? function () { applyDocument($card, null); } : null
        });
    }

    $('.content-formsettings')
        .on('click', '[data-document-pick], [data-document-change]', function () {
            openPicker($(this).closest('.content-formsettings'));
        })
        .on('click', '[data-document-clear]', function () {
            applyDocument($(this).closest('.content-formsettings'), null);
        });
});
