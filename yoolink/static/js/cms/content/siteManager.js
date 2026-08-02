// Load images from backend
$editImg = null;
$editSlider = null;
$editVideo = null;
let imageLibraryItems = [];
let galeryLibraryItems = [];
let imageLibraryPagination = {
    page: 1,
    perPage: 12,
    total: 0,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
};
let selectedLibraryImage = null;
let imageSearchTimeout = null;
let imageRequestSequence = 0;

$(document).ready(function () {
    const $imageModal = $('#imageModal');
    const $galeryModal = $('#galeryModal');
    const $videoModal = $('#videoModal');
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    $('.edit-img').click(function () {
        $editImg = $(this).siblings('img');
        openImageModal();
    });

    $('#closeImageModal').click(function () {
        closeImageModal();
    });

    $('#reloadImages').click(function () {
        imageLibraryPagination.page = 1;
        loadImages(true);
    });

    $('#imageSearchInput').on('input', function () {
        window.clearTimeout(imageSearchTimeout);
        imageSearchTimeout = window.setTimeout(function () {
            imageLibraryPagination.page = 1;
            loadImages(false);
        }, 250);
    });

    $('#imagePrevPage').click(function () {
        if (!imageLibraryPagination.hasPrevious) return;
        imageLibraryPagination.page -= 1;
        loadImages(false);
    });

    $('#imageNextPage').click(function () {
        if (!imageLibraryPagination.hasNext) return;
        imageLibraryPagination.page += 1;
        loadImages(false);
    });

    $('#selectedImageApply').click(function () {
        applySelectedLibraryImage();
    });

    $('#selectedImageTitleSave').click(function () {
        saveSelectedImageTitle(csrfToken);
    });

    $('#convertImagesToWebp').click(function () {
        convertImagesToWebp($(this), csrfToken);
    });

    $('.image-modal-tab').click(function () {
        setImageModalTab($(this).attr('data-target'));
    });

    $('#imageUploadDropzone').click(function (event) {
        if (event.target.id === 'imageUploadInput') return;
        $('#imageUploadInput')[0].click();
    });

    $('#imageUploadInput').click(function (event) {
        event.stopPropagation();
    });

    $('#imageUploadInput').on('change', function () {
        uploadImageFiles(this.files, csrfToken);
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
        uploadImageFiles(event.originalEvent.dataTransfer.files, csrfToken);
    });

    $('#reloadGalerien').click(function () {
        loadGalerien(true);
    });

    $('#galerySearchInput').on('input', function () {
        renderGaleryLibrary(galeryLibraryItems);
    });

    $('#closeGaleryModal').click(function () {
        $galeryModal.addClass("hidden");
    });

    $('.edit-galery').click(function () {
        $editSlider = $(this).siblings('.carousel');
        $galeryModal.removeClass("hidden");
        if (galeryLibraryItems.length === 0) loadGalerien(false);
    });

    const $modals = [$imageModal, $galeryModal, $videoModal];
    const $modalContainers = $modals.map($m => $m.find('.modal-container'));

    function insideAnyContainer(target) {
        for (const $container of $modalContainers) {
            if ($container.is(target) || $container.has(target).length > 0) {
                return true;
            }
        }
        return false;
    }

    // Merkt sich, wo der Mausdruck begann. So schließt sich das Modal nicht,
    // wenn man Text im Input markiert (Maus gedrückt) und dabei aus dem Modal rauszieht.
    let mousedownInsideContainer = false;
    $(document).mousedown(function (e) {
        mousedownInsideContainer = insideAnyContainer(e.target);
    });

    $(document).mouseup(function (e) {
        if ($(e.target).closest('.swal2-container').length > 0) return;

        // Nur schließen, wenn die Geste komplett außerhalb begann UND endete.
        const clickedOutsideAll = !mousedownInsideContainer && !insideAnyContainer(e.target);

        if (clickedOutsideAll) {
            closeImageModal();
            $galeryModal.addClass('hidden');
            $videoModal.addClass('hidden');
        }
    });

    $('.edit-video').click(function () {
        $editVideo = $(this).siblings('video');
        $videoModal.removeClass('hidden');
    });

    $('#closeVideoModal').click(function () {
        $videoModal.addClass('hidden');
    });

    $('#reloadVideos').click(function () {
        loadVideos(true);
    });
});

function openImageModal() {
    selectedLibraryImage = null;
    refreshSelectedImagePreview();
    resetSelectedImageDetails();
    imageLibraryPagination.page = 1;
    setImageModalTab('imageLibraryPanel');
    $('#imageModal').removeClass("hidden").addClass("flex");
    loadImages(false);
    preselectCurrentImage();
}

// Lädt beim Öffnen das bereits gesetzte Bild der Stelle inkl. (übersetztem) Bildtitel,
// damit man den Titel direkt bearbeiten kann (z.B. englische Version), ohne erst zu suchen.
function preselectCurrentImage() {
    const currentId = $editImg ? ($editImg.attr('imgId') || '') : '';
    if (!currentId || currentId === '-1') return;
    $.ajax({
        url: '/cms/images/' + currentId + '/info/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            if (response && response.image) {
                selectLibraryImage(response.image);
            }
        }
    });
}

function closeImageModal() {
    $('#imageModal').addClass("hidden").removeClass("flex");
}

function setImageModalTab(panelId) {
    $('.image-modal-panel').addClass('hidden').removeClass('flex');
    $('#' + panelId).removeClass('hidden').addClass('flex');

    $('.image-modal-tab')
        .removeClass('bg-blue-900 text-white shadow-sm')
        .addClass('text-slate-700 hover:bg-white hover:text-slate-950');

    $('.image-modal-tab[data-target="' + panelId + '"]')
        .addClass('bg-blue-900 text-white shadow-sm')
        .removeClass('text-slate-700 hover:bg-white hover:text-slate-950');
}

function refreshSelectedImagePreview() {
    const src = $editImg ? $editImg.attr('src') : '';
    if (src) {
        $('#selectedImagePreview').attr('src', src).removeClass('hidden');
        $('#selectedImagePlaceholder').addClass('hidden');
    } else {
        $('#selectedImagePreview').attr('src', '').addClass('hidden');
        $('#selectedImagePlaceholder').removeClass('hidden');
    }
}

function resetSelectedImageDetails() {
    $('#selectedImageTitleInput').val('').prop('disabled', true);
    $('#selectedImageTitleSave').prop('disabled', true);
    $('#selectedImageApply').prop('disabled', true);
    $('#selectedImageMeta').text('Wähle ein Bild aus der Mediathek, um Details zu sehen.');
}

function selectLibraryImage(image) {
    selectedLibraryImage = image;

    const previewUrl = image.preview_url || image.mobile_url || image.url || '';
    if (previewUrl) {
        $('#selectedImagePreview').attr('src', previewUrl).removeClass('hidden');
        $('#selectedImagePlaceholder').addClass('hidden');
    }

    $('#selectedImageTitleInput').val(image.title || '').prop('disabled', false);
    $('#selectedImageTitleSave').prop('disabled', false);
    $('#selectedImageApply').prop('disabled', !$editImg);
    renderSelectedImageMetadata(image);
    highlightSelected();
}

// Markiert nur das aktuell gewählte Bild in der Galerie (ohne komplette Neu-Rendern,
// das bei jeder Auswahl die Lazy-Images neu dekodieren ließ -> Laggen beim Scrollen).
function highlightSelected() {
    $('#possibleImages > button').each(function () {
        const $btn = $(this);
        const isSel = selectedLibraryImage && String($btn.attr('data-image-id')) === String(selectedLibraryImage.id);
        $btn.toggleClass('ring-2 ring-blue-500', !!isSel).toggleClass('ring-slate-200', !isSel);
    });
}

function applySelectedLibraryImage() {
    if (!$editImg || !selectedLibraryImage) return;

    $editImg.attr('src', selectedLibraryImage.url);
    if (selectedLibraryImage.srcset) {
        $editImg.attr('srcset', selectedLibraryImage.srcset);
    } else {
        $editImg.removeAttr('srcset');
    }
    $editImg.attr('imgId', selectedLibraryImage.id);
    closeImageModal();
    sendNotif('Neues Bild ausgewählt', 'success');
}

// Kürzt lange Dateinamen in der Mitte (z.B. "ein-sehr…name.webp"),
// damit das Meta-Feld unten links nicht zerbricht. Voller Name bleibt als title-Tooltip.
function truncateMiddle(value, max) {
    value = String(value == null ? '' : value);
    max = max || 28;
    if (value.length <= max) return value;
    const keep = max - 1;
    const front = Math.ceil(keep / 2);
    const back = Math.floor(keep / 2);
    return value.slice(0, front) + '…' + value.slice(value.length - back);
}

function renderSelectedImageMetadata(image) {
    const metadata = image.metadata || {};
    const filename = metadata.filename || 'Unbekannt';
    const rows = [
        ['Datei', truncateMiddle(filename, 28), filename],
        ['Format', image.format || 'Unbekannt'],
        ['Größe', metadata.size_kb ? metadata.size_kb + ' KB' : 'Unbekannt'],
        ['Abmessung', metadata.dimensions || 'Unbekannt'],
        ['Mobil', metadata.mobile_size_kb ? metadata.mobile_size_kb + ' KB' : (image.has_mobile ? 'Vorhanden' : 'Nein')],
        ['Upload', metadata.uploaded_at || 'Unbekannt'],
    ];

    $('#selectedImageMeta').html(rows.map(function (row) {
        const titleAttr = row[2] ? ` title="${escapeHtml(row[2])}"` : '';
        return `<div class="flex justify-between gap-3"><span class="flex-shrink-0 font-semibold text-slate-600">${escapeHtml(row[0])}</span><span class="min-w-0 truncate text-right"${titleAttr}>${escapeHtml(row[1])}</span></div>`;
    }).join(''));
}

function saveSelectedImageTitle(csrfToken) {
    if (!selectedLibraryImage) return;

    const title = ($('#selectedImageTitleInput').val() || '').trim();
    if (!title) {
        sendNotif('Bitte gib einen Bildtitel ein', 'error');
        return;
    }

    $.ajax({
        url: '/cms/images/update/' + selectedLibraryImage.id + '/',
        type: 'POST',
        data: { title: title },
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        },
        success: function (response) {
            selectedLibraryImage.title = title;
            imageLibraryItems = imageLibraryItems.map(function (image) {
                if (String(image.id) === String(selectedLibraryImage.id)) {
                    return Object.assign({}, image, { title: title });
                }
                return image;
            });
            // Nur die betroffene Kachel aktualisieren statt komplett neu zu rendern.
            const $tile = $('#possibleImages > button[data-image-id="' + selectedLibraryImage.id + '"]');
            $tile.find('img').attr('alt', title);
            $tile.find('span.truncate').attr('title', title).text(title);
            renderSelectedImageMetadata(selectedLibraryImage);
            $('#selectedImageTitleInput').val(title);
            sendNotif(response.success || 'Bildtitel wurde gespeichert', 'success');
        },
        error: function () {
            sendNotif('Bildtitel konnte nicht gespeichert werden', 'error');
        }
    });
}

function updateWebpConversionButton(hasNonWebp, count) {
    const $button = $('#convertImagesToWebp');
    if (!$button.length) return;

    $button.toggleClass('hidden', !hasNonWebp);
    $button.attr('data-count', count || 0);
    $button.text(count ? `WebP (${count})` : 'WebP');
}

function convertImagesToWebp($button, csrfToken) {
    if ($button.prop('disabled')) return;

    const originalText = $button.text();
    $button.prop('disabled', true).text('Konvertiere...');

    $.ajax({
        url: '/cms/images/convert-webp/',
        type: 'POST',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        },
        success: function (response) {
            updateWebpConversionButton(response.has_non_webp, response.remaining);
            imageLibraryPagination.page = 1;
            loadImages(false);
            const converted = response.converted_images || 0;
            const skipped = response.skipped_variants || 0;
            const suffix = skipped ? ` (${skipped} Varianten übersprungen)` : '';
            sendNotif(`${converted} Bilder zu WebP konvertiert${suffix}`, 'success');
        },
        error: function () {
            $button.text(originalText);
            sendNotif('WebP-Konvertierung konnte nicht abgeschlossen werden', 'error');
        },
        complete: function () {
            $button.prop('disabled', false);
        }
    });
}

function selectImage($image) {
    if (!$editImg) return;

    $editImg.attr('src', $image.attr('src'));
    $editImg.attr('imgId', $image.attr('imgId'));
    closeImageModal();
    sendNotif('Neues Bild ausgewählt', 'success');
}

function renderImageLibrary(images) {
    const $container = $('#possibleImages');
    $container.empty();

    images.forEach(function (image) {
        const title = escapeHtml(image.title || 'Bild');
        const previewUrl = escapeHtml(image.preview_url || image.mobile_url || image.url || '');
        const isSelected = selectedLibraryImage && String(selectedLibraryImage.id) === String(image.id);
        const selectedRing = isSelected ? 'ring-2 ring-blue-500' : 'ring-slate-200';
        const $button = $(`
            <button type="button" data-image-id="${image.id}" class="group relative overflow-hidden rounded-lg bg-white text-left shadow-sm ring-1 ${selectedRing} transition hover:-translate-y-0.5 hover:shadow-lg hover:ring-blue-300">
                <img src="${previewUrl}" imgId="${image.id}" alt="${title}" loading="lazy" decoding="async" class="h-24 w-full object-cover sm:h-28">
                <span class="absolute right-2 top-2 rounded-md bg-white/90 px-2 py-1 text-xs font-semibold text-red-700 opacity-0 shadow-sm ring-1 ring-red-100 transition hover:bg-red-50 group-hover:opacity-100 image-delete-button" data-image-id="${image.id}">
                    <i class="bi bi-trash"></i>
                </span>
                <span class="absolute inset-x-0 bottom-0 block truncate bg-gradient-to-t from-slate-950/80 to-transparent px-3 pb-3 pt-8 text-xs font-semibold text-white opacity-0 transition group-hover:opacity-100" title="${title}">${title}</span>
            </button>
        `);
        $button.click(function () {
            selectLibraryImage(image);
        });
        $button.find('.image-delete-button').click(function (event) {
            event.preventDefault();
            event.stopPropagation();
            confirmDeleteImage(image.id, title);
        });
        $container.append($button);
    });

    $('#imageEmptyState').toggleClass('hidden', images.length > 0);
    updateImagePaginationControls();
}

function updateImagePaginationControls() {
    const totalPages = imageLibraryPagination.totalPages || 1;
    const page = imageLibraryPagination.page || 1;
    const total = imageLibraryPagination.total || 0;
    $('#imagePaginationInfo').text(`Seite ${page} von ${totalPages} · ${total} Bilder`);
    $('#imagePrevPage').prop('disabled', !imageLibraryPagination.hasPrevious);
    $('#imageNextPage').prop('disabled', !imageLibraryPagination.hasNext);
}

function confirmDeleteImage(imageId, title) {
    const confirmText = 'Dieses Bild wird dauerhaft gelöscht.';
    const confirmAction = function () {
        deleteImage(imageId);
    };

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
        }).then(function (result) {
            if (result.isConfirmed) confirmAction();
        });
        return;
    }

    if (window.confirm(title + ' löschen?\n\n' + confirmText)) {
        confirmAction();
    }
}

function deleteImage(imageId) {
    $.ajax({
        url: '/cms/images/delete/' + imageId + '/',
        type: 'POST',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', $('input[name="csrfmiddlewaretoken"]').val());
        },
        success: function (response) {
            if (selectedLibraryImage && String(selectedLibraryImage.id) === String(imageId)) {
                selectedLibraryImage = null;
                refreshSelectedImagePreview();
                resetSelectedImageDetails();
            }

            imageLibraryItems = imageLibraryItems.filter(function (image) {
                return String(image.id) !== String(imageId);
            });
            renderImageLibrary(imageLibraryItems);
            if (imageLibraryItems.length === 0 && imageLibraryPagination.page > 1) {
                imageLibraryPagination.page -= 1;
            }
            loadImages(false);

            if ($editImg && String($editImg.attr('imgId')) === String(imageId)) {
                $editImg.attr('imgId', '-1');
                refreshSelectedImagePreview();
            }

            sendNotif(response.success || 'Bild wurde gelöscht', 'success');
        },
        error: function () {
            sendNotif('Bild konnte nicht gelöscht werden', 'error');
        }
    });
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function uploadImageFiles(fileList, csrfToken) {
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
        addUploadItem(itemId, file.name);

        const formData = new FormData();
        formData.append('file', file);

        $.ajax({
            url: '/cms/upload/post',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            },
            success: function (response) {
                setUploadItemStatus(itemId, 'Fertig', 'text-green-700', uploadOptimizationText(response.image));
                if (response.image) {
                    $('#imageSearchInput').val('');
                    imageLibraryPagination.page = 1;
                    selectedLibraryImage = response.image;
                    setImageModalTab('imageLibraryPanel');
                    loadImages(false);
                    selectLibraryImage(response.image);
                } else {
                    loadImages(false);
                }
                sendNotif('Bild wurde hochgeladen', 'success');
            },
            error: function () {
                setUploadItemStatus(itemId, 'Fehlgeschlagen', 'text-red-700');
                sendNotif('Bild konnte nicht hochgeladen werden', 'error');
            }
        });
    });
}

function addUploadItem(id, name) {
    $('#imageUploadItems').prepend(`
        <div id="${id}" class="rounded-md bg-slate-50 px-3 py-2 text-sm">
            <div class="flex items-center justify-between gap-3">
                <span class="truncate text-slate-700">${escapeHtml(name)}</span>
                <span class="upload-status shrink-0 text-slate-500">Lädt...</span>
            </div>
            <p class="upload-detail mt-1 hidden text-xs leading-snug text-slate-500"></p>
        </div>
    `);
    $('#' + id).children('.upload-status').remove();
}

function setUploadItemStatus(id, text, className, detail) {
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

function uploadOptimizationText(image) {
    if (!image || !image.optimization) return '';
    const optimization = image.optimization;
    const desktop = optimization.desktop || {};
    const mobile = optimization.mobile || {};
    const desktopSaved = optimization.desktop_saved_percent > 0 ? ` / -${optimization.desktop_saved_percent}%` : '';
    const mobileSaved = optimization.mobile_saved_percent > 0 ? ` / -${optimization.mobile_saved_percent}%` : '';
    return `Original ${optimization.original_size_kb || 0} KB | Desktop ${desktop.size_kb || 0} KB${desktopSaved} | Mobil ${mobile.size_kb || 0} KB${mobileSaved}`;
}

function loadImages(sendLoadMsg) {
    const requestId = ++imageRequestSequence;
    $.ajax({
        url: '/cms/images/all/',
        type: 'GET',
        data: {
            page: imageLibraryPagination.page,
            per_page: imageLibraryPagination.perPage,
            q: $('#imageSearchInput').val() || '',
        },
        dataType: 'json',
        success: function (response) {
            if (requestId !== imageRequestSequence) return;
            imageLibraryItems = response.image_urls || [];
            const pagination = response.pagination || {};
            imageLibraryPagination = {
                page: pagination.page || 1,
                perPage: pagination.per_page || imageLibraryPagination.perPage,
                total: pagination.total || 0,
                totalPages: pagination.total_pages || 1,
                hasPrevious: Boolean(pagination.has_previous),
                hasNext: Boolean(pagination.has_next),
            };
            updateWebpConversionButton(Boolean(response.has_non_webp), response.non_webp_count || 0);
            renderImageLibrary(imageLibraryItems);
            if (sendLoadMsg) {
                const message = imageLibraryItems.length ? 'Bilder wurden geladen' : 'Keine Bilder wurden gefunden';
                sendNotif(message, imageLibraryItems.length ? 'success' : 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Es kam zu einem unerwarteten Fehler, versuche es später nochmal', 'error');
        }
    });
}

function loadGalerien(sendLoadMsg) {
    $.ajax({
        url: '/cms/galerien/all/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            galeryLibraryItems = (response.galerien && response.galerien.length) ? response.galerien : [];
            renderGaleryLibrary(galeryLibraryItems);
            if (sendLoadMsg) {
                if (galeryLibraryItems.length) sendNotif("Alle Galerien wurden geladen", "success");
                else sendNotif("Es wurden keine Galerien gefunden", "error");
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif("Es kam zu einem unerwarteten Fehler, versuche es später nochmal", "error");
        }
    });
}

function renderGaleryLibrary(items) {
    const query = ($('#galerySearchInput').val() || '').toLowerCase();
    const filtered = query ? items.filter(g => (g.title || '').toLowerCase().includes(query) || (g.description || '').toLowerCase().includes(query)) : items;
    const $container = $('#possibleGalerien');
    $container.empty();
    if (filtered.length === 0) {
        $('#galeryEmptyState').removeClass('hidden');
        return;
    }
    $('#galeryEmptyState').addClass('hidden');
    filtered.forEach(function (gallery) {
        const $item = addTitleAndDescription(gallery.title, gallery.description, gallery.id);
        $item.click(function () {
            const galeryId = $(this).attr("galeryId");
            $('#selectedGaleryName').text(gallery.title || 'Galerie #' + galeryId).removeClass('text-slate-400').addClass('text-slate-900 font-semibold');
            sendNotif("Diese Galerie wird geladen...", "notice");
            selectGalery(galeryId);
        });
        $container.append($item);
    });
}

function loadVideos(sendLoadMsg) {
    $.ajax({
        url: '/cms/videos/all/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            if (response.video_urls && response.video_urls.length !== 0) {
                $('#possibleVideos').empty();
                response.video_urls.forEach(function (v) {
                    const $elem = $(`
                        <video
                            src="${v.url}"
                            poster="${v.poster}"
                            videoId="${v.id}"
                            class="h-40 w-full rounded-xl hover:shadow-2xl hover:cursor-pointer hover:scale-105"
                            preload="metadata">
                        </video>`
                    );

                    $elem.click(function () {
                        if ($editVideo) {
                            $editVideo.attr('src', $(this).attr('src'));
                            $editVideo.attr('poster', $(this).attr('poster'));
                            $editVideo.attr('videoId', $(this).attr('videoId'));
                            $('#videoModal').addClass('hidden');
                            sendNotif('Neues Video ausgewählt', 'success');
                        }
                    });

                    $('#possibleVideos').append($elem);
                });
                if (sendLoadMsg) sendNotif('Alle Videos wurden geladen', 'success');
            } else {
                if (sendLoadMsg) sendNotif('Keine Videos gefunden', 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Unerwarteter Fehler beim Laden der Videos', 'error');
        }
    });
}

function addTitleAndDescription(title, description, id) {
    const $div = $('<div>').addClass('flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-400 hover:shadow-md hover:cursor-pointer');
    $div.attr('galeryId', id);
    const $icon = $('<div>').addClass('mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700').html('<i class="bi bi-images text-xl"></i>');
    const $title = $('<p>').addClass('text-sm font-semibold text-slate-900 truncate').text(title || 'Galerie #' + id);
    const $description = $('<p>').addClass('mt-1 text-xs text-slate-500 line-clamp-2').text(description || '');

    $div.append($icon);
    $div.append($title);
    $div.append($description);

    return $div;
}

function selectGalery(id) {
    $.ajax({
        url: "/cms/galery/getImages/",
        type: "GET",
        data: { "galeryId": id },
        dataType: "json",
        success: function (data) {
            if (data.images.length > 0) {
                const c = $editSlider.find('.slick-slide:not(.slick-cloned)');
                for (let i = c.length - 1; i >= 0; i--) {
                    $editSlider.slick("slickRemove", i);
                }
                const height = $('#galeryHeight').val();
                const width = $('#galeryWidth').val();
                data.images.forEach(function (image) {
                    const img = '<img src="' + image.upload_url + '" class="w-full rounded-xl" style="height: ' + height + '; width: ' + width + '">';
                    $editSlider.slick('slickAdd', '<div>' + img + '</div>');
                });
                $editSlider.closest(".relative").attr('galery-id', id);
                $('#galeryModal').addClass("hidden");
                sendNotif("Galerie wurde erfolgreich geladen", "success");
            } else {
                sendNotif("Diese Galerie ist leer. Bitte befülle sie erst!", "error");
            }
        },
        error: function (xhr, status, error) {
            console.error("Error:", error);
            sendNotif("Etwas hat nicht funktioniert. Versuche es später erneut", "error");
        }
    });
}
