/**
 * Button-Designer (Erstellen & Bearbeiten) mit Live-Vorschau.
 *
 * Das Farb-Mapping spiegelt die Frontend-Komponente
 * yoolink/templates/pages/components/button.html — bei Änderungen beide Stellen anpassen.
 */
const BUTTON_BASE_CLASSES = 'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-center text-sm font-bold transition';
const BUTTON_LINK_CLASSES = 'inline-flex items-center text-sm font-medium text-blue-900 transition hover:text-blue-950';
const BUTTON_COLOR_CLASSES = {
    blue: 'bg-blue-600 text-white hover:bg-blue-700',
    navy: 'bg-blue-900 text-white hover:bg-blue-800',
    dark: 'bg-slate-900 text-white hover:bg-slate-700',
    emerald: 'bg-emerald-600 text-white hover:bg-emerald-700',
    white: 'bg-white text-blue-900 shadow-sm ring-1 ring-gray-200 hover:bg-blue-50',
    outline: 'border border-blue-900 bg-transparent text-blue-900 hover:bg-blue-50',
    link: 'text-blue-900 hover:text-blue-950',
};

const SWATCH_ACTIVE_CLASSES = 'border-blue-500 ring-2 ring-blue-100';
const LINK_TYPE_ACTIVE_CLASSES = 'border-blue-500 bg-blue-50 text-blue-700';

function escapeButtonHtml(value) {
    return $('<div>').text(value || '').html();
}

function getSelectedLinkType() {
    return $('#linkTypeToggle .link-type-btn.is-active').data('link-type') || 'internal';
}

function getButtonHref() {
    if (getSelectedLinkType() === 'internal') {
        return $('#page_link_id option:selected').data('url') || '';
    }
    return ($('#url').val() || '').trim();
}

function updateButtonPreview() {
    const text = $('#text').val() || 'Button';
    const color = $('#color').val() || 'blue';
    const icon = ($('#icon').val() || '').trim();
    const href = getButtonHref();
    const newTab = $('#targetSwitch').is(':checked');

    let html = '';
    let previewClasses;
    if (color === 'link') {
        // Textlink: Icon hinter dem Text, keine Fläche/Polsterung
        previewClasses = `pointer-events-none ${BUTTON_LINK_CLASSES}`;
        html = escapeButtonHtml(text);
        if (icon) {
            html += ` <i class="${escapeButtonHtml(icon)} ml-1"></i>`;
        }
    } else {
        const colorClasses = BUTTON_COLOR_CLASSES[color] || BUTTON_COLOR_CLASSES.blue;
        previewClasses = `pointer-events-none ${BUTTON_BASE_CLASSES} ${colorClasses}`;
        if (icon) {
            html += `<i class="${escapeButtonHtml(icon)}"></i>`;
        }
        html += escapeButtonHtml(text);
    }

    $('#buttonPreviewLight, #buttonPreviewDark')
        .attr('class', previewClasses)
        .html(html);

    $('#previewHref').text(href || '–');
    $('#previewTarget').text(newTab ? 'in neuem Tab' : 'im gleichen Tab');
    $('#liveButtonTitle').text($('#text').val() || 'Erstellen');
}

function setActiveSwatch(color) {
    $('#color').val(color);
    $('#colorSwatches .color-swatch').each(function () {
        const active = $(this).data('color') === color;
        $(this).toggleClass(SWATCH_ACTIVE_CLASSES, active);
    });
    updateButtonPreview();
}

function setLinkType(linkType) {
    $('#linkTypeToggle .link-type-btn').each(function () {
        const active = $(this).data('link-type') === linkType;
        $(this).toggleClass(`is-active ${LINK_TYPE_ACTIVE_CLASSES}`, active);
    });
    $('#internalLinkBox').toggleClass('hidden', linkType !== 'internal');
    $('#externalLinkBox').toggleClass('hidden', linkType !== 'external');
    updateButtonPreview();
}

function getDesignerPayload() {
    const internal = getSelectedLinkType() === 'internal';
    return {
        text: ($('#text').val() || '').trim(),
        hover_text: $('#hover_text').val() || '',
        color: $('#color').val() || 'blue',
        page_link_id: internal ? ($('#page_link_id').val() || null) : null,
        url: internal ? '' : ($('#url').val() || '').trim(),
        target: $('#targetSwitch').is(':checked') ? '_blank' : '_self',
        icon: ($('#icon').val() || '').trim(),
        order: parseInt($('#order').val(), 10) || 0,
    };
}

$(function () {
    const $form = $('#buttonDesignerForm');
    if (!$form.length) {
        return;
    }

    // Initialzustand aus den gerenderten Feldwerten ableiten
    setActiveSwatch($('#color').val() || 'blue');
    const initialType = !$('#page_link_id').val() && ($('#url').val() || '').trim() ? 'external' : 'internal';
    setLinkType(initialType);

    $('#colorSwatches').on('click', '.color-swatch', function () {
        setActiveSwatch($(this).data('color'));
    });

    $('#linkTypeToggle').on('click', '.link-type-btn', function () {
        setLinkType($(this).data('link-type'));
    });

    $form.on('input change', 'input, select', updateButtonPreview);

    $form.on('submit', function (e) {
        e.preventDefault();

        $.ajax({
            url: $form.data('endpoint'),
            method: 'POST',
            headers: { 'X-CSRFToken': $form.find('input[name=csrfmiddlewaretoken]').val() },
            contentType: 'application/json',
            data: JSON.stringify(getDesignerPayload()),
            success: function () {
                if ($form.data('mode') === 'create') {
                    window.location.href = $form.data('redirect');
                } else {
                    sendNotif('Der Button wurde gespeichert', 'success');
                }
            },
            error: function (xhr) {
                const message = (xhr.responseJSON && xhr.responseJSON.error) || 'Speichern fehlgeschlagen';
                sendNotif(message, 'error');
            },
        });
    });
});
