// Seiten-Builder: Bild-, Galerie- und Video-Auswahl.
//
// Die komplette Bild-Mediathek (Laden, Paginierung, Suche, Upload, Löschen,
// Titel) liegt nicht mehr hier, sondern zentral in js/cms/media-library.js und
// js/cms/media-picker.js. Diese Datei sagt nur noch "öffne den Picker für
// dieses <img>" und schreibt das Ergebnis zurück ins DOM.
$editImg = null;
$editSlider = null;
$editVideo = null;
let galeryLibraryItems = [];

$(document).ready(function () {
    const $galeryModal = $('#galeryModal');
    const $videoModal = $('#videoModal');

    // Delegiert, damit auch nachträglich eingefügte Bild-Slots funktionieren.
    $(document).on('click', '.edit-img', function () {
        $editImg = $(this).siblings('img');
        openImagePicker();
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

    // Klick-außerhalb nur noch für Galerie/Video - der Bild-Picker bringt das
    // (inklusive Textmarkierung über den Rand hinaus) selbst mit.
    const $modalContainers = [$galeryModal, $videoModal].map($m => $m.find('.modal-container'));

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
        if (window.CmsMediaPicker && window.CmsMediaPicker.isOpen()) return;

        // Nur schließen, wenn die Geste komplett außerhalb begann UND endete.
        if (!mousedownInsideContainer && !insideAnyContainer(e.target)) {
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

// --------------------------------------------------------------- [Bildauswahl]

function openImagePicker() {
    if (!window.CmsMediaPicker) return;

    const currentId = $editImg ? ($editImg.attr('imgId') || '') : '';

    window.CmsMediaPicker.open({
        title: 'Bild auswählen',
        subtitle: 'Bild anklicken, links prüfen und mit „Bild übernehmen“ einsetzen.',
        currentImageId: currentId && currentId !== '-1' ? currentId : null,
        currentImageSrc: $editImg ? ($editImg.attr('src') || '') : '',
        onApply: applyImageToSlot
    });
}

function applyImageToSlot(image) {
    if (!$editImg || !image) return;

    $editImg.attr('src', image.url);
    if (image.srcset) {
        $editImg.attr('srcset', image.srcset);
    } else {
        $editImg.removeAttr('srcset');
    }
    $editImg.attr('imgId', image.id);
    sendNotif('Neues Bild ausgewählt', 'success');
}

// ---------------------------------------------------------------- [Galerien]

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
