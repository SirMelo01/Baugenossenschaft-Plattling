// Customer create/edit form -- handles image select modal, gallery select modal, save

let customerImageLibraryItems = [];
let customerGalerieLibraryItems = [];
let activeImageTarget = null;
let customerImageSearchTimeout = null;

const IMAGE_TARGETS = ["titleImage", "bannerImage", "logoImage"];

$(document).ready(function () {
    const $imageModal = $('#imageModal');
    const $galeryModal = $('#galeryModal');
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    $('#name').on('input', function () {
        const value = $(this).val() || 'Neuer Kunde';
        $('#live-title').text(value);
        $('#live-hero-title').text(value);
        updateLivePreview();
    });

    $('#subtitle, #website_display, #logo_fallback_text').on('input', updateLivePreview);
    $('#logo_style').on('change', updateLivePreview);

    updateLivePreview();

    // ---------- IMAGE MODAL HOOKS ----------
    $('.customer-image-select').click(function () {
        activeImageTarget = $(this).data('target');
        openCustomerImageModal();
    });

    $('.customer-image-clear').click(function () {
        const target = $(this).data('target');
        clearCustomerImage(target);
    });

    $('#closeImageModal').click(closeCustomerImageModal);
    $('#reloadImages').click(function () { loadCustomerImages(true); });
    $('#imageSearchInput').on('input', function () {
        window.clearTimeout(customerImageSearchTimeout);
        customerImageSearchTimeout = window.setTimeout(function () {
            loadCustomerImages(false);
        }, 250);
    });

    $('.image-modal-tab').click(function () {
        setCustomerImageModalTab($(this).attr('data-target'));
    });

    $('#imageUploadDropzone').click(function (event) {
        if (event.target.id === 'imageUploadInput') return;
        $('#imageUploadInput')[0].click();
    });
    $('#imageUploadInput').click(function (event) { event.stopPropagation(); });
    $('#imageUploadInput').on('change', function () {
        uploadCustomerImageFiles(this.files, csrfToken);
        this.value = '';
    });
    $('#imageUploadDropzone').on('dragover', function (event) {
        event.preventDefault();
        $(this).addClass('border-blue-500 bg-blue-100');
    });
    $('#imageUploadDropzone').on('dragleave drop', function () {
        $(this).removeClass('border-blue-500 bg-blue-100');
    });
    $('#imageUploadDropzone').on('drop', function (event) {
        event.preventDefault();
        uploadCustomerImageFiles(event.originalEvent.dataTransfer.files, csrfToken);
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

    // Click outside-to-close
    const $modals = [$imageModal, $galeryModal];
    const $modalContainers = $modals.map(function ($m) { return $m.find('.modal-container'); });
    $(document).mouseup(function (e) {
        if ($(e.target).closest('.swal2-container').length > 0) return;
        let clickedOutsideAll = true;
        for (const $container of $modalContainers) {
            if ($container.is(e.target) || $container.has(e.target).length > 0) {
                clickedOutsideAll = false;
                break;
            }
        }
        if (clickedOutsideAll) {
            closeCustomerImageModal();
            $galeryModal.addClass('hidden').removeClass('flex');
        }
    });

    // ---------- SAVE ----------
    $('#customer-form').submit(function (event) {
        event.preventDefault();
        submitCustomerForm();
    });

    loadCustomerImages(false);
});

function openCustomerImageModal() {
    refreshCustomerSelectedImagePreview();
    setCustomerImageModalTab('imageLibraryPanel');
    $('#imageModal').removeClass('hidden').addClass('flex');
}

function closeCustomerImageModal() {
    $('#imageModal').addClass('hidden').removeClass('flex');
}

function setCustomerImageModalTab(panelId) {
    $('.image-modal-panel').addClass('hidden').removeClass('flex');
    $('#' + panelId).removeClass('hidden').addClass('flex');

    $('.image-modal-tab')
        .removeClass('bg-blue-900 text-white shadow-sm')
        .addClass('text-slate-700 hover:bg-white hover:text-slate-950');

    $('.image-modal-tab[data-target="' + panelId + '"]')
        .addClass('bg-blue-900 text-white shadow-sm')
        .removeClass('text-slate-700 hover:bg-white hover:text-slate-950');
}

function refreshCustomerSelectedImagePreview() {
    if (!activeImageTarget) {
        $('#selectedImagePreview').attr('src', '').addClass('hidden');
        $('#selectedImagePlaceholder').removeClass('hidden');
        return;
    }
    const $preview = $('#' + activeImageTarget + 'Preview');
    const src = $preview.attr('src');
    if (src) {
        $('#selectedImagePreview').attr('src', src).removeClass('hidden');
        $('#selectedImagePlaceholder').addClass('hidden');
    } else {
        $('#selectedImagePreview').attr('src', '').addClass('hidden');
        $('#selectedImagePlaceholder').removeClass('hidden');
    }
}

function selectCustomerImage($image) {
    if (!activeImageTarget) return;
    const $preview = $('#' + activeImageTarget + 'Preview');
    const $placeholder = $('#' + activeImageTarget + 'Placeholder');

    $preview.attr('src', $image.attr('data-full-url') || $image.attr('src'));
    $preview.attr('data-image-id', $image.attr('imgId'));
    $preview.removeClass('hidden');
    $placeholder.addClass('hidden');

    closeCustomerImageModal();
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

function renderCustomerImageLibrary(images) {
    const $container = $('#possibleImages');
    $container.empty();

    images.forEach(function (image) {
        const title = customerEscapeHtml(image.title || 'Bild');
        const previewUrl = customerEscapeHtml(image.preview_url || image.mobile_url || image.url || '');
        const $button = $(`
            <button type="button" class="group relative overflow-hidden rounded-lg bg-white text-left shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-lg hover:ring-blue-300">
                <img src="${previewUrl}" imgId="${image.id}" data-full-url="${customerEscapeHtml(image.url || '')}" alt="${title}" loading="lazy" decoding="async" class="h-24 w-full object-cover sm:h-28">
                <span class="image-delete-button absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/95 text-xs font-semibold text-red-700 opacity-0 shadow-sm ring-1 ring-red-100 transition hover:bg-red-50 group-hover:opacity-100" data-image-id="${image.id}">
                    <i class="bi bi-trash"></i>
                </span>
                <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/80 to-transparent px-3 pb-3 pt-8 text-xs font-semibold text-white opacity-0 transition group-hover:opacity-100">${title}</span>
            </button>
        `);
        $button.click(function () {
            selectCustomerImage($(this).find('img'));
        });
        $button.find('.image-delete-button').click(function (event) {
            event.preventDefault();
            event.stopPropagation();
            confirmDeleteCustomerImage(image.id, title);
        });
        $container.append($button);
    });

    $('#imageEmptyState').toggleClass('hidden', images.length > 0);
}

function confirmDeleteCustomerImage(imageId, title) {
    const confirmText = 'Dieses Bild wird dauerhaft gelöscht.';
    const confirmAction = function () { deleteCustomerImage(imageId); };

    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: 'Bild löschen?',
            text: confirmText,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor: '#64748b',
            confirmButtonText: 'Ja, löschen',
            cancelButtonText: 'Abbrechen',
            reverseButtons: true,
        }).then(function (result) { if (result.isConfirmed) confirmAction(); });
        return;
    }

    if (window.confirm(title + ' löschen?\n\n' + confirmText)) confirmAction();
}

function deleteCustomerImage(imageId) {
    $.ajax({
        url: '/cms/images/delete/' + imageId + '/',
        type: 'POST',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', $('input[name="csrfmiddlewaretoken"]').val());
        },
        success: function (response) {
            customerImageLibraryItems = customerImageLibraryItems.filter(function (image) {
                return String(image.id) !== String(imageId);
            });
            renderCustomerImageLibrary(customerImageLibraryItems);

            IMAGE_TARGETS.forEach(function (target) {
                const $preview = $('#' + target + 'Preview');
                if (String($preview.attr('data-image-id')) === String(imageId)) {
                    clearCustomerImage(target);
                }
            });

            sendNotif(response.success || 'Bild wurde gelöscht', 'success');
        },
        error: function () { sendNotif('Bild konnte nicht gelöscht werden', 'error'); }
    });
}

function uploadCustomerImageFiles(fileList, csrfToken) {
    const files = Array.from(fileList || []).filter(function (file) {
        return file.type && file.type.startsWith('image/');
    });

    if (!files.length) {
        sendNotif('Bitte wähle eine Bilddatei aus', 'error');
        return;
    }

    $('#imageUploadQueue').removeClass('hidden');

    files.forEach(function (file) {
        const itemId = 'upload-' + Date.now() + '-' + Math.random().toString(16).slice(2);
        addCustomerUploadItem(itemId, file.name);

        const formData = new FormData();
        formData.append('file', file);

        $.ajax({
            url: '/cms/upload/post',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', csrfToken); },
            success: function (response) {
                setCustomerUploadItemStatus(itemId, 'Fertig', 'text-green-700', customerUploadOptimizationText(response.image));
                if (response.image) {
                    customerImageLibraryItems.unshift(response.image);
                    renderCustomerImageLibrary(customerImageLibraryItems);
                    setCustomerImageModalTab('imageLibraryPanel');
                } else {
                    loadCustomerImages(false);
                }
                sendNotif('Bild wurde hochgeladen', 'success');
            },
            error: function () {
                setCustomerUploadItemStatus(itemId, 'Fehlgeschlagen', 'text-red-700');
                sendNotif('Bild konnte nicht hochgeladen werden', 'error');
            }
        });
    });
}

function addCustomerUploadItem(id, name) {
    $('#imageUploadItems').prepend(`
        <div id="${id}" class="rounded-md bg-slate-50 px-3 py-2 text-sm">
            <div class="flex items-center justify-between gap-3">
                <span class="truncate text-slate-700">${customerEscapeHtml(name)}</span>
                <span class="upload-status shrink-0 text-slate-500">Lädt...</span>
            </div>
            <p class="upload-detail mt-1 hidden text-xs leading-snug text-slate-500"></p>
        </div>
    `);
    $('#' + id).children('.upload-status').remove();
}

function setCustomerUploadItemStatus(id, text, className, detail) {
    const $item = $('#' + id);
    $item.children('.upload-status').remove();
    $item.find('.upload-status')
        .removeClass('text-slate-500 text-green-700 text-red-700')
        .addClass(className)
        .text(text);

    if (detail) {
        $item.find('.upload-detail').text(detail).removeClass('hidden');
    }
}

function customerUploadOptimizationText(image) {
    if (!image || !image.optimization) return '';
    const optimization = image.optimization;
    const desktop = optimization.desktop || {};
    const mobile = optimization.mobile || {};
    const desktopSaved = optimization.desktop_saved_percent > 0 ? ` / -${optimization.desktop_saved_percent}%` : '';
    const mobileSaved = optimization.mobile_saved_percent > 0 ? ` / -${optimization.mobile_saved_percent}%` : '';
    return `Original ${optimization.original_size_kb || 0} KB | Desktop ${desktop.size_kb || 0} KB${desktopSaved} | Mobil ${mobile.size_kb || 0} KB${mobileSaved}`;
}

function customerEscapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function loadCustomerImages(sendLoadMsg) {
    $.ajax({
        url: '/cms/images/all/',
        type: 'GET',
        data: {
            page: 1,
            per_page: 12,
            q: $('#imageSearchInput').val() || '',
        },
        dataType: 'json',
        success: function (response) {
            customerImageLibraryItems = response.image_urls || [];
            renderCustomerImageLibrary(customerImageLibraryItems);
            if (sendLoadMsg) {
                const message = customerImageLibraryItems.length ? 'Alle Bilder wurden geladen' : 'Keine Bilder wurden gefunden';
                sendNotif(message, customerImageLibraryItems.length ? 'success' : 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Es kam zu einem unerwarteten Fehler, versuche es später nochmal', 'error');
        }
    });
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
