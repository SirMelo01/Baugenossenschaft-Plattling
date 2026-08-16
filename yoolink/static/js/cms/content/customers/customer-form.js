// Kunden-Formular: Bild-Slots, Galerie-Auswahl, Speichern.
//
// Die Bildauswahl nutzt den zentralen Picker (js/cms/media-picker.js) - vorher lag hier
// eine eigene Variante ohne Paginierung, die immer nur die erste Seite der
// Mediathek zeigte und beim ersten Klick sofort übernommen hat.

let customerGalerieLibraryItems = [];
let activeImageTarget = null;

const IMAGE_TARGETS = ["titleImage", "bannerImage", "logoImage"];

const IMAGE_TARGET_LABELS = {
    titleImage: 'Titelbild auswählen',
    bannerImage: 'Bannerbild auswählen',
    logoImage: 'Logo auswählen'
};

$(document).ready(function () {
    const $galeryModal = $('#galeryModal');

    $('#name').on('input', function () {
        const value = $(this).val() || 'Neuer Kunde';
        $('#live-title').text(value);
        $('#live-hero-title').text(value);
        updateLivePreview();
    });

    $('#subtitle, #website_display, #logo_fallback_text').on('input', updateLivePreview);
    $('#logo_style').on('change', updateLivePreview);

    updateLivePreview();

    // ---------- IMAGE PICKER ----------
    $('.customer-image-select').click(function () {
        activeImageTarget = $(this).data('target');
        openCustomerImagePicker();
    });

    $('.customer-image-clear').click(function () {
        const target = $(this).data('target');
        clearCustomerImage(target);
    });

    // ---------- GALERY MODAL HOOKS ----------
    $('#customerSelectGalery').click(function () {
        $galeryModal.removeClass('hidden').addClass('flex');
        if (customerGalerieLibraryItems.length === 0) loadCustomerGalerien(false);
    });
    $('#customerClearGalery').click(function () {
        $('#galeryPickerBox').attr('galery-id', '-1');
        $('#galeryPickerTitle').text('Keine Galerie ausgewählt');
        $('#galeryPickerDescription').text('—');
        sendNotif('Galerie entfernt', 'success');
    });
    $('#closeGaleryModal').click(function () {
        $galeryModal.addClass('hidden').removeClass('flex');
    });
    $('#reloadGalerien').click(function () { loadCustomerGalerien(true); });
    $('#galerySearchInput').on('input', function () {
        renderCustomerGaleryLibrary(customerGalerieLibraryItems);
    });

    // Click outside-to-close (nur Galerie - der Bild-Picker regelt das selbst)
    const $galeryContainer = $galeryModal.find('.modal-container');
    $(document).mouseup(function (e) {
        if ($(e.target).closest('.swal2-container').length > 0) return;
        if (window.CmsMediaPicker && window.CmsMediaPicker.isOpen()) return;
        if ($galeryContainer.is(e.target) || $galeryContainer.has(e.target).length > 0) return;
        $galeryModal.addClass('hidden').removeClass('flex');
    });

    // ---------- SAVE ----------
    $('#customer-form').submit(function (event) {
        event.preventDefault();
        submitCustomerForm();
    });
});

function openCustomerImagePicker() {
    if (!activeImageTarget || !window.CmsMediaPicker) return;

    const $preview = $('#' + activeImageTarget + 'Preview');
    const currentId = $preview.attr('data-image-id');

    window.CmsMediaPicker.open({
        title: IMAGE_TARGET_LABELS[activeImageTarget] || 'Bild auswählen',
        subtitle: 'Bild anklicken, links prüfen und mit „Bild übernehmen“ einsetzen.',
        currentImageId: currentId && currentId !== '-1' ? currentId : null,
        currentImageSrc: $preview.attr('src') || '',
        onApply: function (image) {
            selectCustomerImage(image);
        },
        onRemove: function () {
            clearCustomerImage(activeImageTarget);
        }
    });
}

function selectCustomerImage(image) {
    if (!activeImageTarget || !image) return;
    const $preview = $('#' + activeImageTarget + 'Preview');
    const $placeholder = $('#' + activeImageTarget + 'Placeholder');

    $preview.attr('src', image.url);
    $preview.attr('data-image-id', image.id);
    $preview.removeClass('hidden');
    $placeholder.addClass('hidden');

    sendNotif('Neues Bild ausgewählt', 'success');
    updateLivePreview();
}

function clearCustomerImage(target) {
    const $preview = $('#' + target + 'Preview');
    const $placeholder = $('#' + target + 'Placeholder');
    $preview.attr('src', '').attr('data-image-id', '-1').addClass('hidden');
    $placeholder.removeClass('hidden');
    sendNotif('Bild entfernt', 'success');
    updateLivePreview();
}

function updateLivePreview() {
    const titleSrc = $('#titleImagePreview').attr('src');
    const $previewImage = $('#previewImage');
    const $previewPlaceholder = $('#previewImagePlaceholder');
    if (titleSrc) {
        $previewImage.css('background-image', "url('" + titleSrc + "')");
        $previewPlaceholder.addClass('hidden');
    } else {
        $previewImage.css('background-image', '');
        $previewPlaceholder.removeClass('hidden');
    }

    const logoSrc = $('#logoImagePreview').attr('src');
    const logoStyle = $('#logo_style').val() || 'circle';

    const name = ($('#name').val() || 'Neuer Kunde');
    const fallback = ($('#logo_fallback_text').val() || name).slice(0, 1).toUpperCase() || '?';
    const websiteDisplay = ($('#website_display').val() || '').trim();
    const subtitle = ($('#subtitle').val() || '').trim();
    const subline = websiteDisplay || subtitle || '—';

    const $standardLayout = $('#previewStandardLayout');
    const $wideLayout = $('#previewWideLayout');
    const $previewLogoBox = $('#previewLogoBox');
    const $previewFallbackBadge = $('#previewFallbackBadge');

    if (logoStyle === 'wide' && logoSrc) {
        // Show wide layout
        $standardLayout.addClass('hidden');
        $wideLayout.removeClass('hidden');
        $('#previewWideLogoImage').attr('src', logoSrc);
        $('#previewWideName').text(name);
        $('#previewWideSubline').text(subline);
    } else {
        // Show standard layout
        $wideLayout.addClass('hidden');
        $standardLayout.removeClass('hidden');

        if (logoSrc) {
            $('#previewLogoImage').attr('src', logoSrc);
            $previewLogoBox.removeClass('hidden');
            $previewFallbackBadge.addClass('hidden');
        } else {
            $previewLogoBox.addClass('hidden');
            $previewFallbackBadge.removeClass('hidden');
        }

        $('#previewFallback').text(fallback);
        $('#previewName').text(name);
        $('#previewSubline').text(subline);
    }
}

// ---------- GALLERY ----------
function loadCustomerGalerien(sendLoadMsg) {
    $.ajax({
        url: '/cms/galerien/all/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            customerGalerieLibraryItems = (response.galerien && response.galerien.length) ? response.galerien : [];
            renderCustomerGaleryLibrary(customerGalerieLibraryItems);
            if (sendLoadMsg) {
                if (customerGalerieLibraryItems.length) sendNotif('Alle Galerien wurden geladen', 'success');
                else sendNotif('Es wurden keine Galerien gefunden', 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Es kam zu einem unerwarteten Fehler, versuche es später nochmal', 'error');
        }
    });
}

function renderCustomerGaleryLibrary(items) {
    const query = ($('#galerySearchInput').val() || '').toLowerCase();
    const filtered = query
        ? items.filter(function (g) {
              return (g.title || '').toLowerCase().includes(query) || (g.description || '').toLowerCase().includes(query);
          })
        : items;

    const $container = $('#possibleGalerien');
    $container.empty();

    if (filtered.length === 0) {
        $('#galeryEmptyState').removeClass('hidden');
        return;
    }
    $('#galeryEmptyState').addClass('hidden');

    filtered.forEach(function (gallery) {
        const $div = $('<div>').addClass('flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-400 hover:shadow-md hover:cursor-pointer');
        $div.attr('galeryId', gallery.id);
        const $icon = $('<div>').addClass('mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700').html('<i class="bi bi-images text-xl"></i>');
        const $title = $('<p>').addClass('text-sm font-semibold text-slate-900 truncate').text(gallery.title || 'Galerie #' + gallery.id);
        const $description = $('<p>').addClass('mt-1 text-xs text-slate-500 line-clamp-2').text(gallery.description || '');

        $div.append($icon, $title, $description);

        $div.click(function () {
            $('#galeryPickerBox').attr('galery-id', gallery.id);
            $('#galeryPickerTitle').text(gallery.title || ('Galerie #' + gallery.id));
            $('#galeryPickerDescription').text(gallery.description || 'Galerie ausgewählt');
            $('#galeryModal').addClass('hidden').removeClass('flex');
            sendNotif('Galerie übernommen', 'success');
        });

        $container.append($div);
    });
}

// ---------- SAVE ----------
function setCustomerSaveButtonsLoading(isLoading) {
    const $buttons = $('button[type="submit"][form="customer-form"]');
    $buttons.each(function () {
        const $btn = $(this);
        if (isLoading) {
            if (!$btn.data('original-html')) {
                $btn.data('original-html', $btn.html());
            }
            $btn.prop('disabled', true).addClass('cursor-not-allowed opacity-70');
            $btn.html(
                '<svg class="h-4 w-4 animate-spin text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">' +
                '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
                '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>' +
                '</svg><span>Speichert ...</span>'
            );
        } else {
            $btn.prop('disabled', false).removeClass('cursor-not-allowed opacity-70');
            const original = $btn.data('original-html');
            if (original) $btn.html(original);
        }
    });
}

function submitCustomerForm() {
    const $form = $('#customer-form');
    const customerId = $form.data('customer-id');
    const editUrl = $form.data('edit-url');
    const createUrl = $form.data('create-url');
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    const url = customerId ? editUrl : createUrl;
    const galeryId = $('#galeryPickerBox').attr('galery-id');

    const payload = {
        name: $('#name').val(),
        subtitle: $('#subtitle').val(),
        website_url: $('#website_url').val(),
        website_display: $('#website_display').val(),
        published_date: $('#published_date').val(),
        section: $('#section').val(),
        active: $('#active').is(':checked'),
        show_detail_page: $('#show_detail_page').is(':checked'),
        logo_style: $('#logo_style').val(),
        logo_fallback_text: $('#logo_fallback_text').val(),
        short_description: $('#short_description').val(),
        description: $('#description').val(),
        services_text: $('#services_text').val(),
        testimonial: $('#testimonial').val(),
        testimonial_author: $('#testimonial_author').val(),
        title_image_id: $('#titleImagePreview').attr('data-image-id') || null,
        banner_image_id: $('#bannerImagePreview').attr('data-image-id') || null,
        logo_id: $('#logoImagePreview').attr('data-image-id') || null,
        gallery_id: galeryId || null,
    };

    setCustomerSaveButtonsLoading(true);

    $.ajax({
        url: url,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', csrfToken); },
        success: function (response) {
            sendNotif(response.success || 'Gespeichert', 'success');
            if (!customerId && response.id) {
                window.location.href = '/cms/seiten/kunden/customers/' + response.id + '/edit/';
                return;
            }
            setCustomerSaveButtonsLoading(false);
        },
        error: function (xhr) {
            const err = (xhr.responseJSON && xhr.responseJSON.error) || 'Fehler beim Speichern';
            sendNotif(err, 'error');
            setCustomerSaveButtonsLoading(false);
        }
    });
}
