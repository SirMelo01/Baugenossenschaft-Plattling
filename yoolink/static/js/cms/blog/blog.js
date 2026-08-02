// Text-Editoren laufen jetzt über Quill (siehe BlogRichText / blog-richtext.js).
var imageData = null;
// Editable Fields
var $editSlider = null;
var $editImg = null;
var $editYoutube = null;
// Wenn gesetzt, fügt der Bild-Dialog das gewählte Bild in den Quill-Editor ein
// (statt ein Block-Bild zu bearbeiten): { quill, range }.
var blogEditorImageTarget = null;
var selectedVideoData = null;
let selectedVideoElement = null;
let selectedAnyfile = null; // {id,url,title,ext}
let blogImageLibraryItems = [];
let blogVideoLibraryItems = [];
let selectedGalleryId = null;
let selectedGalleryTitle = '';

function blogCsrfToken() {
    return $('input[name="csrfmiddlewaretoken"]').val();
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function normalizeBlogTextHtml(value) {
    const $wrapper = $('<div>').html(value || '');
    $wrapper.find('h4,h5,h6').each(function () {
        $(this).replaceWith($('<p>').html($(this).html()));
    });
    return $wrapper.html();
}

function setBlogImagePanel(panelId) {
    $('.blog-image-panel').addClass('hidden').removeClass('flex');
    $('#' + panelId).removeClass('hidden').addClass('flex');
    $('.blog-image-tab')
        .removeClass('bg-blue-900 text-white shadow-sm')
        .addClass('text-slate-700 hover:bg-white hover:text-slate-950');
    $('.blog-image-tab[data-target="' + panelId + '"]')
        .addClass('bg-blue-900 text-white shadow-sm')
        .removeClass('text-slate-700 hover:bg-white hover:text-slate-950');
}

function openBlogPreviewModal() {
    $('#previewModal').removeClass('hidden').addClass('flex');
}

function closeBlogPreviewModal() {
    $('#previewModal').addClass('hidden').removeClass('flex');
}

window.openBlogPreviewModal = openBlogPreviewModal;
window.closeBlogPreviewModal = closeBlogPreviewModal;

function refreshBlogImagePreview() {
    const src = (blogEditorImageTarget && blogEditorImageTarget.src)
        ? blogEditorImageTarget.src
        : ($editImg ? $editImg.attr('src') : '');
    if (src) {
        $('#blogImageSelectedPreview').attr('src', src).removeClass('hidden');
        $('#blogImageSelectedPlaceholder').addClass('hidden');
    } else {
        $('#blogImageSelectedPreview').attr('src', '').addClass('hidden');
        $('#blogImageSelectedPlaceholder').removeClass('hidden');
    }
}

function currentCssSize($element, key, fallback) {
    if (!$element || !$element.length) return fallback || '';
    const inlineValue = $element[0].style && $element[0].style[key] ? $element[0].style[key] : '';
    return inlineValue || fallback || '';
}

function openBlogImageModal($image) {
    blogEditorImageTarget = null;   // Block-Bild bearbeiten, kein Editor-Einfügen
    $editImg = $image;
    const height = currentCssSize($editImg, 'height', $editImg.height() ? $editImg.height() + 'px' : 'auto');
    let width = currentCssSize($editImg, 'width', $editImg.width() ? $editImg.width() + 'px' : '100%');
    if (width === '0px' || width === '0') width = '100%';

    $('#imgHeight').val(height);
    $('#imgWidth').val(width);
    $('#imgText').val($editImg.attr('title') || '');
    $('#imgAlt').val($editImg.attr('alt') || $editImg.attr('title') || '');
    $('#imgURL').val($editImg.attr('src') || '');
    $('#imgLazy').prop('checked', ($editImg.attr('loading') || 'lazy') === 'lazy');
    $('#imgAsync').prop('checked', ($editImg.attr('decoding') || 'async') === 'async');
    refreshBlogImagePreview();
    setBlogImagePanel('blogImageLibraryPanel');
    $('#imageModal').removeClass('hidden').addClass('flex');
    loadBlogImageLibrary(false);
}

function closeBlogImageModal() {
    $('#imageModal').addClass('hidden').removeClass('flex');
    blogEditorImageTarget = null;
}

/**
 * Öffnet den normalen CMS-Bild-Dialog (Mediathek + Upload), um ein Bild in einen
 * Quill-Text-Editor einzufügen – wie beim Bild-Element, nur dass das Ergebnis
 * inline in den Editor kommt statt als eigenes Block-Bild.
 */
function openBlogEditorImagePicker(quill) {
    if (!quill) return;
    $editImg = null;
    blogEditorImageTarget = {
        quill: quill,
        range: quill.getSelection(true) || { index: quill.getLength() },
        src: ''
    };
    // Eigenschaften für ein frisches Bild zurücksetzen.
    $('#imgURL').val('');
    $('#imgAlt').val('');
    $('#imgText').val('');
    $('#imgWidth').val('');
    $('#imgHeight').val('');
    $('#imgLazy').prop('checked', true);
    $('#imgAsync').prop('checked', true);
    refreshBlogImagePreview();
    $('#imageModal').removeClass('hidden').addClass('flex');
    setBlogImagePanel('blogImageLibraryPanel');
    loadBlogImageLibrary(false);
}
window.openBlogEditorImagePicker = openBlogEditorImagePicker;

function selectBlogImage(image) {
    // Einfüge-Modus (Editor): Bild nur auswählen – Titel/Alt/Größe lassen sich danach
    // setzen, eingefügt wird per "Übernehmen" (wie beim Block-Bild).
    if (blogEditorImageTarget && blogEditorImageTarget.quill && image && image.url) {
        blogEditorImageTarget.src = image.url;
        if (image.id) blogEditorImageTarget.imgId = image.id;
        if (!$('#imgAlt').val()) $('#imgAlt').val(image.title || 'Bild');
        if (!$('#imgText').val()) $('#imgText').val(image.title || '');
        refreshBlogImagePreview();
        sendNotif('Bild gewählt – mit „Übernehmen" einfügen', 'notice');
        return;
    }
    if (!$editImg || !image || !image.url) return;
    $editImg.attr('src', image.url);
    if (image.id) $editImg.attr('imgId', image.id);
    if (!$('#imgAlt').val()) $('#imgAlt').val(image.title || 'Bild');
    if (!$('#imgText').val()) $('#imgText').val(image.title || '');
    refreshBlogImagePreview();
    sendNotif('Neues Bild ausgewählt', 'success');
}

function renderBlogImageLibrary(images) {
    const search = ($('#imageSearchInput').val() || '').toLowerCase().trim();
    const filteredImages = (images || []).filter(function (image) {
        return !search || String(image.title || '').toLowerCase().includes(search);
    });
    const $container = $('#possibleImages');
    $container.empty();

    filteredImages.forEach(function (image) {
        const title = escapeHtml(image.title || 'Bild');
        const selected = $editImg && $editImg.attr('src') === image.url;
        const $button = $(`
            <button type="button" class="group relative overflow-hidden rounded-lg bg-white text-left shadow-sm ring-1 transition hover:-translate-y-0.5 hover:shadow-lg">
                <img src="${image.url}" imgId="${image.id || ''}" alt="${title}" class="h-36 w-full object-cover">
                <span class="absolute left-2 top-2 rounded-md bg-white/90 px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200">
                    ${escapeHtml(image.format || 'IMG')}${image.has_mobile ? ' + Mobil' : ''}
                </span>
                <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/80 to-transparent px-3 pb-3 pt-8 text-xs font-semibold text-white opacity-0 transition group-hover:opacity-100">${title}</span>
            </button>
        `);
        $button.toggleClass('ring-blue-500', !!selected);
        $button.toggleClass('ring-slate-200 hover:ring-blue-300', !selected);
        $button.on('click', function () {
            selectBlogImage(image);
            renderBlogImageLibrary(blogImageLibraryItems);
        });
        $container.append($button);
    });

    $('#imageEmptyState').toggleClass('hidden', filteredImages.length > 0);
}

function loadBlogImageLibrary(sendLoadMsg) {
    $.ajax({
        url: '/cms/images/all/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            blogImageLibraryItems = response.image_urls || [];
            renderBlogImageLibrary(blogImageLibraryItems);
            if (sendLoadMsg) {
                sendNotif(blogImageLibraryItems.length ? 'Alle Bilder wurden geladen' : 'Keine Bilder wurden gefunden', blogImageLibraryItems.length ? 'success' : 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Bilder konnten nicht geladen werden', 'error');
        }
    });
}

function uploadBlogImage(file) {
    if (!file || !file.type || !file.type.startsWith('image/')) {
        sendNotif('Bitte wähle eine Bilddatei aus', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    $('#blogImageUploadFileName').text(file.name);
    $('#blogImageUploadQueue').removeClass('hidden').text('Upload läuft...');

    $.ajax({
        url: '/cms/upload/post',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', blogCsrfToken());
        },
        success: function (response) {
            if (response.image) {
                blogImageLibraryItems.unshift(response.image);
                selectBlogImage(response.image);
                renderBlogImageLibrary(blogImageLibraryItems);
                setBlogImagePanel('blogImageLibraryPanel');
                $('#blogImageUploadQueue').text(response.image.note || 'Bild wurde hochgeladen.');
                sendNotif('Bild wurde hochgeladen', 'success');
            } else {
                loadBlogImageLibrary(false);
            }
        },
        error: function () {
            $('#blogImageUploadQueue').text('Upload fehlgeschlagen.');
            sendNotif('Bild konnte nicht hochgeladen werden', 'error');
        }
    });
}

function openBlogGalleryModal($carousel) {
    $editSlider = $carousel;
    selectedGalleryId = null;
    selectedGalleryTitle = '';
    $('#selectedGalleryLabel').text($editSlider.closest('.relative').attr('galery-id') ? 'Aktuelle Builder-Galerie' : 'Keine neue Galerie gewählt');

    const $firstImg = $editSlider.find('img').first();
    const height = $firstImg.length ? currentCssSize($firstImg, 'height', $firstImg.height() ? $firstImg.height() + 'px' : 'auto') : 'auto';
    let width = $firstImg.length ? currentCssSize($firstImg, 'width', $firstImg.width() ? $firstImg.width() + 'px' : '100%') : '100%';
    if (width === '0px' || width === '0') width = '100%';

    $('#galeryHeight').val(height);
    $('#galeryWidth').val(width);
    $('#galeryAltPrefix').val('Galeriebild');
    $('#galeryAutoplay').prop('checked', ($editSlider.attr('data-autoplay') || 'true') !== 'false');
    $('#galerySpeed').val($editSlider.attr('data-autoplay-speed') || '3000');
    $('#galleryModal').removeClass('hidden').addClass('flex');
    loadBlogGalleries(false);
}

function selectedGalleryCard($card) {
    $('#possibleGalerien .pGalery').removeClass('border-blue-500 ring-2 ring-blue-100');
    $card.addClass('border-blue-500 ring-2 ring-blue-100');
    selectedGalleryId = $card.attr('galeryId');
    selectedGalleryTitle = $card.data('title') || $card.find('.gallery-title').text() || 'Galerie';
    $('#selectedGalleryLabel').text(selectedGalleryTitle);
}

function rebuildSlickGallery(images, galleryId) {
    if (!$editSlider || !images || !images.length) return;

    if ($editSlider.hasClass('slick-initialized')) {
        $editSlider.slick('unslick');
    }

    const height = $('#galeryHeight').val() || 'auto';
    const width = $('#galeryWidth').val() || '100%';
    const altPrefix = $('#galeryAltPrefix').val() || 'Galeriebild';
    $editSlider.empty();
    images.forEach(function (image, index) {
        const imageUrl = image.upload_url || image.url;
        const altText = image.alt || image.title || altPrefix + ' ' + (index + 1);
        const $slide = $('<div>');
        $('<img>', {
            src: imageUrl,
            alt: altText,
            title: image.title || altText,
            class: 'w-full rounded-xl',
            loading: 'lazy',
            decoding: 'async',
        }).attr('data-media-id', image.id || '').css('height', height).css('width', width).appendTo($slide);
        $editSlider.append($slide);
    });

    const $galleryContainer = $editSlider.closest('.relative');
    $galleryContainer.attr('galery-id', galleryId || $galleryContainer.attr('galery-id') || '0');
    $galleryContainer.css('height', height).css('width', width);
    $editSlider.attr('data-autoplay', $('#galeryAutoplay').is(':checked') ? 'true' : 'false');
    $editSlider.attr('data-autoplay-speed', $('#galerySpeed').val() || '3000');
    initBlogCarousels($galleryContainer);
    refreshVisibleBlogCarousels($galleryContainer);
}

function applyGalleryPropertiesToCurrent() {
    if (!$editSlider || !$editSlider.length) return;
    const height = $('#galeryHeight').val() || 'auto';
    const width = $('#galeryWidth').val() || '100%';
    const $galleryContainer = $editSlider.closest('.relative');

    if ($editSlider.hasClass('slick-initialized')) {
        $editSlider.slick('unslick');
    }

    $galleryContainer.css('height', height).css('width', width);
    $editSlider.find('img').each(function (index) {
        const fallbackAlt = ($('#galeryAltPrefix').val() || 'Galeriebild') + ' ' + (index + 1);
        $(this).css('height', height).css('width', width);
        if (!$(this).attr('alt')) $(this).attr('alt', fallbackAlt);
        $(this).attr('loading', 'lazy').attr('decoding', 'async');
    });
    $editSlider.attr('data-autoplay', $('#galeryAutoplay').is(':checked') ? 'true' : 'false');
    $editSlider.attr('data-autoplay-speed', $('#galerySpeed').val() || '3000');
    initBlogCarousels($galleryContainer);
    refreshVisibleBlogCarousels($galleryContainer);
}

function galleryCardMarkup(gallery) {
    const title = escapeHtml(gallery.title || 'Galerie');
    const description = escapeHtml(gallery.description || 'Keine Beschreibung hinterlegt.');
    return $(`
        <button type="button" galeryId="${gallery.id}" data-title="${title}"
            class="pGalery rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md">
            <span class="gallery-title block text-base font-semibold text-slate-950">${title}</span>
            <span class="mt-2 block max-h-20 overflow-hidden text-sm text-slate-500">${description}</span>
        </button>
    `);
}

function filterBlogGalleryCards() {
    const search = ($('#galerySearchInput').val() || '').toLowerCase().trim();
    let visibleCount = 0;
    $('#possibleGalerien .pGalery').each(function () {
        const visible = !search || $(this).text().toLowerCase().includes(search);
        $(this).toggleClass('hidden', !visible);
        if (visible) visibleCount += 1;
    });
    $('#galeryEmptyState').toggleClass('hidden', visibleCount > 0);
}

function loadBlogGalleries(sendLoadMsg) {
    if (sendLoadMsg) sendNotif('Alle Galerien werden geladen...', 'notice');
    $.ajax({
        url: '/cms/galerien/all/',
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            const galleries = response.galerien || [];
            const $container = $('#possibleGalerien');
            $container.empty();
            galleries.forEach(function (gallery) {
                $container.append(galleryCardMarkup(gallery));
            });
            filterBlogGalleryCards();
            if (sendLoadMsg) {
                sendNotif(galleries.length ? 'Alle Galerien wurden geladen' : 'Es wurden keine Galerien gefunden', galleries.length ? 'success' : 'error');
            }
        },
        error: function () {
            if (sendLoadMsg) sendNotif('Es kam zu einem unerwarteten Fehler, versuche es später nochmal', 'error');
        }
    });
}

function openBlogVideoModal($targetContainer) {
    const $video = $targetContainer.find('video').first();
    $('#videoModal').data('target', $targetContainer).removeClass('hidden').addClass('flex');
    selectedVideoData = null;
    selectedVideoElement = null;

    const currentTitle = $video.attr('title') || '';
    $('#selectedVideoId').val($video.data('video_id') || '');
    $('#selectedVideoLabel').text(currentTitle || 'Aktuelles Builder-Video');
    $('#videoTitle').val(currentTitle);
    $('#videoAlt').val($video.data('alt_text') || '');
    $('#videoDescription').val($video.data('description') || '');
    $('#videoTags').val($video.data('tags') || '');
    $('#videoDuration').val($video.data('duration') || '');
    $('#videoControls').prop('checked', $video.prop('controls') || $video.attr('controls') === 'controls');
    $('#videoAutoplay').prop('checked', $video.prop('autoplay') || $video.attr('autoplay') === 'autoplay');
    $('#videoMuted').prop('checked', $video.prop('muted') || $video.attr('muted') === 'muted');
    $('#videoLoop').prop('checked', $video.prop('loop') || $video.attr('loop') === 'loop');
    $('#videoPlaysinline').prop('checked', $video.prop('playsinline') || $video.attr('playsinline') === 'playsinline');
    $('#videoPreload').val($video.attr('preload') || 'metadata');
    $('#videoWidth').val(currentCssSize($video, 'width', $video.attr('width') || '100%'));
    $('#videoHeight').val(currentCssSize($video, 'height', $video.attr('height') || 'auto'));
    loadBlogCMSVideos($video.data('video_id') || null);
}

function closeBlogVideoModal() {
    $('#videoModal').addClass('hidden').removeClass('flex');
}

function renderBlogCMSVideos(videos, preselectId) {
    const $container = $('#availableVideos');
    $container.empty();
    (videos || []).forEach(function (video) {
        const title = escapeHtml(video.title || 'Video');
        const meta = escapeHtml(video.description || video.tags || '');
        const $preview = $(`
            <button type="button" class="cms-video-preview group overflow-hidden rounded-lg border border-slate-200 bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md" data-video-id="${video.id}">
                <video src="${video.url}" poster="${video.poster || ''}" preload="metadata" muted class="h-36 w-full bg-slate-900 object-cover"></video>
                <span class="block px-3 pb-1 pt-3 text-sm font-semibold text-slate-950">${title}</span>
                <span class="block px-3 pb-3 text-xs text-slate-500">${meta}</span>
            </button>
        `);
        if (preselectId && String(video.id) === String(preselectId)) {
            $preview.addClass('border-blue-500 ring-2 ring-blue-100');
            selectVideoData(video);
        }
        $container.append($preview);
    });
    $('#videoEmptyState').toggleClass('hidden', (videos || []).length > 0);
}

function loadBlogCMSVideos(preselectId) {
    const $container = $('#availableVideos');
    $container.empty();
    $.get('/cms/videos/all/', function (response) {
        blogVideoLibraryItems = response.video_urls || [];
        renderBlogCMSVideos(blogVideoLibraryItems, preselectId);
    }).fail(function () {
        $('#videoEmptyState').removeClass('hidden').text('Videos konnten nicht geladen werden.');
    });
}

function selectVideoData(video) {
    selectedVideoData = video;
    $('#selectedVideoId').val(video.id || '');
    $('#selectedVideoLabel').text(video.title || 'Video');
    $('#videoTitle').val(video.title || '');
    $('#videoAlt').val(video.alt_text || '');
    $('#videoDescription').val(video.description || '');
    $('#videoTags').val(video.tags || '');
    $('#videoDuration').val(video.duration || '');
    $('#videoControls').prop('checked', video.show_controls !== false);
    $('#videoAutoplay').prop('checked', !!video.autoplay);
    $('#videoMuted').prop('checked', !!video.muted);
    $('#videoLoop').prop('checked', !!video.loop);
    $('#videoPlaysinline').prop('checked', !!video.playsinline);
    $('#videoPreload').val(video.preload || 'metadata');
}

function applyBooleanVideoAttr($video, attr, enabled) {
    $video.prop(attr, !!enabled);
    if (enabled) $video.attr(attr, attr);
    else $video.removeAttr(attr);
}

function applyBlogVideoProperties() {
    const $target = $('#videoModal').data('target');
    if (!$target) return false;
    const $video = $target.find('video').first();
    if (!$video.length) return false;

    if (selectedVideoData) {
        $video.attr('src', selectedVideoData.url || '');
        $video.attr('poster', selectedVideoData.poster || '');
        $video.data('video_id', selectedVideoData.id || '');
        $video.attr('data-video_id', selectedVideoData.id || '');
    }

    const dataMap = {
        alt_text: $('#videoAlt').val() || '',
        description: $('#videoDescription').val() || '',
        tags: $('#videoTags').val() || '',
        duration: $('#videoDuration').val() || '',
    };
    $video.attr('title', $('#videoTitle').val() || '');
    Object.keys(dataMap).forEach(function (key) {
        $video.data(key, dataMap[key]);
        $video.attr('data-' + key, dataMap[key]);
    });
    applyBooleanVideoAttr($video, 'controls', $('#videoControls').is(':checked'));
    applyBooleanVideoAttr($video, 'autoplay', $('#videoAutoplay').is(':checked'));
    applyBooleanVideoAttr($video, 'muted', $('#videoMuted').is(':checked'));
    applyBooleanVideoAttr($video, 'loop', $('#videoLoop').is(':checked'));
    applyBooleanVideoAttr($video, 'playsinline', $('#videoPlaysinline').is(':checked'));
    $video.attr('preload', $('#videoPreload').val() || 'metadata');

    const widthVal = $('#videoWidth').val();
    const heightVal = $('#videoHeight').val();
    if (widthVal) $video.css('width', widthVal).attr('width', widthVal);
    if (heightVal) $video.css('height', heightVal).attr('height', heightVal);
    return true;
}

const BLOG_CAROUSEL_OPTIONS = {
        dots: true,  // Display navigation dots
        arrows: true,  // Display navigation arrows
        infinite: true,  // Enable infinite looping
        slidesToShow: 1,  // Number of slides to show at once
        slidesToScroll: 1,  // Number of slides to scroll at a time
        autoplay: true,
        autoplaySpeed: 3000,
        // Add any other configuration options as needed
};

function collectCarousels($scope) {
    const $root = $scope && $scope.length ? $scope : $(document);
    return $root.is && $root.is('.carousel') ? $root : $root.find('.carousel');
}

function initBlogCarousels($scope) {
    if (!$.fn.slick) return;

    collectCarousels($scope).each(function () {
        const $carousel = $(this);
        if (!$carousel.children().length || !$carousel.is(':visible')) return;

        if ($carousel.hasClass('slick-initialized')) {
            $carousel.slick('setPosition');
            return;
        }

        const options = $.extend({}, BLOG_CAROUSEL_OPTIONS, {
            autoplay: ($carousel.attr('data-autoplay') || 'true') !== 'false',
            autoplaySpeed: parseInt($carousel.attr('data-autoplay-speed') || BLOG_CAROUSEL_OPTIONS.autoplaySpeed, 10) || BLOG_CAROUSEL_OPTIONS.autoplaySpeed,
        });
        $carousel.slick(options);
    });
}

function refreshVisibleBlogCarousels($scope) {
    if (!$.fn.slick) return;

    collectCarousels($scope).each(function () {
        const $carousel = $(this);
        if ($carousel.hasClass('slick-initialized')) {
            $carousel.slick('setPosition');
        }
    });
}

function loadSlick() {
    initBlogCarousels($(document));

    // Bind Next function to the Next button
    // Bind Next function to the Next button of each carousel
    $('.next-button').off('click.blogCarousel').on('click.blogCarousel', function () {
        var carousel = $(this).closest('.carousel-container').find('.carousel');
        carousel.slick('slickNext');
    });

    // Bind Previous function to the Previous button of each carousel
    $('.prev-button').off('click.blogCarousel').on('click.blogCarousel', function () {
        var carousel = $(this).closest('.carousel-container').find('.carousel');
        carousel.slick('slickPrev');
    });
}

function loadNicEditors() {
    // Mountet alle noch nicht initialisierten Text-Blöcke als Quill-Editoren.
    if (window.BlogRichText) BlogRichText.mountAll();
}

function isBlogBuilderVisible() {
    const $panel = $('#builderEditorPanel')
    return $panel.length && !$panel.hasClass('hidden') && $panel.width() > 0
}

function refreshBlogBuilderPresentation() {
    if (!isBlogBuilderVisible()) {
        $('#blogContent').data('needs-nic-refresh', true)
        return
    }

    loadNicEditors()
    try {
        initBlogCarousels($('#blogContent'))
        window.requestAnimationFrame(function () {
            refreshVisibleBlogCarousels($('#blogContent'))
        })
        setTimeout(function () {
            initBlogCarousels($('#blogContent'))
            refreshVisibleBlogCarousels($('#blogContent'))
        }, 120)
    } catch (error) { console.warn(error) }
    $('#blogContent').removeData('needs-nic-refresh')
}

function bindBlogBuilderDelete($container) {
    $container.find('.del-elem').click(function () {
        $(this).parent().remove()
        $('#blogContent').trigger('yoolink:builder-change')
    });
}

function blogBuilderControls() {
    return {
        delSpan: $('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'),
        moveHandle: $('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'),
    }
}

function applyBlogCodeToBuilder(code) {
    const $blogContent = $('#blogContent')
    const controls = blogBuilderControls()
    const stamp = Date.now()

    $blogContent.empty()

    $.each(code || [], function (index, element) {
        const $container = $('<div class="relative">')
        const elementName = element.name === 'title-3' ? 'textArea' : element.name
        switch (elementName) {
            case 'title-1':
            case 'title-2': {
                const classMap = {
                    'title-1': 'title-1 my-3 text-2xl font-bold text-gray-900 w-full px-4 py-2 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative',
                    'title-2': 'title-2 text-xl font-semibold w-full px-4 py-2 my-3 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative',
                }
                const placeholderMap = {
                    'title-1': 'Titel 1',
                    'title-2': 'Titel 2',
                }
                $container.attr('element-type', element.name)
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                $('<input/>', {
                    type: "text",
                    class: classMap[element.name],
                    placeholder: placeholderMap[element.name],
                    value: element.value || '',
                }).appendTo($container)
                bindBlogBuilderDelete($container)
                $blogContent.append($container)
                break;
            }
            case 'textArea': {
                const textAreaId = 'textAreaSync' + stamp + '-' + index
                $container.attr('element-type', 'textArea')
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                // Quill-Editor mit dem gespeicherten HTML als Start-Inhalt; das
                // eigentliche Mounten erledigt refreshBlogBuilderPresentation()/loadNicEditors().
                BlogRichText.create(textAreaId, element.value || '').appendTo($container)
                bindBlogBuilderDelete($container)
                $blogContent.append($container)
                break;
            }
            case 'image': {
                const attrs = element.attributes || {}
                const css = element.css || {}
                $container.attr('element-type', 'image').addClass("w-fit my-3")
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-img"><i class="bi bi-pencil-square"></i></span>'))
                $('<img>', {
                    title: attrs.title || attrs.alt || 'Bild',
                    alt: attrs.alt || attrs.title || '',
                    class: "rounded-2xl w-auto h-80",
                    src: attrs.src || "https://placehold.co/600x400",
                }).css('width', css.width || '100%').css('height', css.height || 'auto').appendTo($container)
                bindBlogBuilderDelete($container)
                $container.find('.edit-img').click(function () {
                    openBlogImageModal($(this).siblings('img'));
                });
                $blogContent.append($container)
                break;
            }
            case 'galery': {
                const css = element.css || {}
                const attrs = element.attributes || {}
                $container.attr('element-type', 'galery').addClass("w-full my-4")
                if (attrs.id) $container.attr('galery-id', attrs.id)
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-slider"><i class="bi bi-pencil-square"></i></span>'))
                const $carouselContainer = $('<div class="carousel rounded-lg">')
                if (attrs['data-autoplay']) $carouselContainer.attr('data-autoplay', attrs['data-autoplay'])
                if (attrs['data-autoplay-speed']) $carouselContainer.attr('data-autoplay-speed', attrs['data-autoplay-speed'])
                $container.css("height", css.height || 'auto').css("width", css.width || '100%')
                const imageAlts = element.imageAlts || []
                $(element.images || []).each(function (imageIndex, imageUrl) {
                    const $divContainer = $('<div>')
                    $('<img>', {
                        src: imageUrl,
                        alt: imageAlts[imageIndex] || 'Galeriebild',
                        class: element.imageClass || "w-full rounded-xl",
                    }).css("height", css.height || 'auto').css("width", css.width || '100%').appendTo($divContainer)
                    $carouselContainer.append($divContainer)
                })
                $container.append($carouselContainer)
                bindBlogBuilderDelete($container)
                $container.find('.edit-slider').click(function () {
                    openBlogGalleryModal($(this).siblings('.carousel'));
                });
                $blogContent.append($container)
                break;
            }
            case 'code': {
                const className = (element.attributes && element.attributes.class) || ''
                const language = className.split(/\s+/).find(function (part) { return part.indexOf('language-') === 0 }) || ''
                $container.attr('element-type', 'code').addClass('my-3')
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                const $codeContainer = $('<div class="code border-2 border-dotted border-gray-600 rounded-xl p-2 mb-3">')
                $('<input/>', {
                    type: "text",
                    class: "code-language title-3 text-lg w-full px-4 py-2 my-3 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
                    placeholder: "Sprache (z.B. python)",
                    value: language.replace('language-', ''),
                }).appendTo($codeContainer)
                $('<textarea/>', {
                    rows: "4",
                    class: "code-source w-full text-black px-4 py-2 my-3 rounded-2xl border border-gray-300 focus:outline-none focus:border-blue-500 min-h-[5rem]",
                    placeholder: "Deinen Source-Code hier rein kopieren",
                }).text(element.value || '').appendTo($codeContainer)
                $container.append($codeContainer)
                bindBlogBuilderDelete($container)
                $blogContent.append($container)
                break;
            }
            case 'yt-video': {
                const attrs = element.attributes || {}
                const css = element.css || {}
                $container.attr('element-type', 'yt-video').addClass("w-fit py-4 my-3")
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-youtube"><i class="bi bi-pencil-square"></i></span>'))
                $('<iframe/>', {
                    title: attrs.title || "YouTube video player",
                    frameborder: attrs.frameborder || "0",
                    src: attrs.src || "",
                    allow: attrs.allow || "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share",
                    class: attrs.class || "my-8 rounded-2xl",
                    width: attrs.width || css.width || "560",
                    height: attrs.height || css.height || "315",
                    allowfullscreen: attrs.allowfullscreen || "True",
                    loading: attrs.loading || "lazy",
                }).css('width', css.width || '').css('height', css.height || '').appendTo($container)
                bindBlogBuilderDelete($container)
                $container.find('.edit-youtube').click(function () {
                    $editYoutube = $(this).siblings('iframe');
                    const height = $editYoutube[0].style.height ? $editYoutube[0].style.height : $editYoutube.height();
                    const width = $editYoutube[0].style.width ? $editYoutube[0].style.width : $editYoutube.width();
                    $('#youtubeHeight').val(height)
                    $('#youtubeWidth').val(width)
                    $('#youtubeURL').val($editYoutube.attr('src'))
                    $('#youtubeText').val($editYoutube.attr('title'))
                    $('#youtubeModal').toggleClass("hidden");
                });
                $blogContent.append($container)
                break;
            }
            case 'video': {
                const attrs = element.attributes || {}
                const css = element.css || {}
                $container.attr('element-type', 'video').addClass("py-4 my-3")
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-cmsvideo"><i class="bi bi-pencil-square"></i></span>'))
                const $videoEl = $('<video>');
                $.each(attrs, function (key, value) {
                    if (['autoplay', 'muted', 'loop', 'playsinline', 'controls'].includes(key)) {
                        $videoEl.prop(key, true).attr(key, key);
                    } else if (value !== null && value !== false) {
                        $videoEl.attr(key, value);
                    }
                });
                if (css.width) $videoEl.css('width', css.width);
                if (css.height) $videoEl.css('height', css.height);
                $container.append($videoEl)
                bindBlogBuilderDelete($container)
                $container.find('.edit-cmsvideo').click(function () {
                    openBlogVideoModal($(this).parent());
                });
                $blogContent.append($container)
                break;
            }
            case 'file': {
                const attrs = element.attributes || {}
                $container.attr('element-type', 'file').addClass('my-3')
                $container.append(controls.delSpan.clone()).append(controls.moveHandle.clone())
                const ext = attrs['data-ext'] || ''
                const iconCls = fileIconForExt(ext)
                const $a = $('<a>');
                $.each(attrs, function (key, value) {
                    if (key === 'class') $a.addClass(value)
                    else $a.attr(key, value)
                });
                $a.addClass('file-attachment')
                $a.prepend($('<i>').addClass('bi ' + iconCls + ' text-xl mr-2'))
                $a.append($('<span class="file-title truncate">').text(element.value || attrs.title || 'Datei'))
                $container.append($a)
                bindBlogBuilderDelete($container)
                $blogContent.append($container)
                break;
            }
            default:
                $blogContent.append(getWebElement(element).wrap('<div class="relative" element-type="textArea"></div>').parent())
                break;
        }
    })

    refreshBlogBuilderPresentation()
    $blogContent.trigger('yoolink:builder-synced')
}

function getBlogBuilderCode() {
    return receiveContent($('#blogContent'))
}

function fileIconForExt(ext) {
    switch (ext) {
        case '.jpg': case '.jpeg': case '.png': case '.gif': case '.webp':
            return 'bi-card-image text-yellow-600';
        case '.pdf': return 'bi-file-earmark-pdf-fill text-red-600';
        case '.zip': case '.rar': return 'bi-file-earmark-zip-fill text-gray-600';
        case '.doc': case '.docx': return 'bi-file-earmark-word-fill text-blue-700';
        case '.xls': case '.xlsx': return 'bi-file-earmark-excel-fill text-green-600';
        case '.mp4': case '.mov': case '.webm': return 'bi-file-earmark-play-fill text-purple-600';
        case '.txt': return 'bi-file-earmark-text-fill text-gray-600';
        default: return 'bi-file-earmark-fill text-gray-500';
    }
}

$(document).ready(function () {

    loadSlick();
    loadNicEditors();   // mountet vorhandene Text-Blöcke als Quill-Editoren
    loadImages();

    function initializeSimpleSortable() {
        new Sortable(document.getElementById('blogContent'), {
            handle: '.handle', // handle's class
            animation: 150,
            forceFallback: true
        })
    }


    // Initialize sortable for existing elements
    initializeSimpleSortable();

    // Handle the keydown event on the textarea
    $('textarea').on('keydown', function (event) {
        // Check if the pressed key is Tab (key code 9)
        if (event.keyCode === 9) {
            event.preventDefault(); // Prevent the default behavior (jumping to the next element)
            // Insert a tab character at the current cursor position
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;
            this.value = value.substring(0, start) + '\t' + value.substring(end);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    });

    $('.del-elem').click(function () {
        $(this).parent().remove()
    })

    // scroll bottom
    function scrollToBottom() {
        // Scroll to the bottom of the page
        $('html, body').animate({
            scrollTop: $(document).height() - $(window).height()
        }, 800); // 800 milliseconds for animation duration
    }

    /**
     * Add H2 heading to Blog
     */
    $('#addTitle').click(function () {
        // Create Container
        const $container = $('<div class="relative" element-type="title-1">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        $('<input/>', {
            type: "text",
            class: "title-1 my-3 text-2xl font-bold text-gray-900 w-full px-4 py-2 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
            placeholder: "Titel 1"
        }).appendTo($container)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        sendNotif("Titel 1 wurde hinzugefuegt", "success")
        scrollToBottom()
    });

    /**
      * Add H3 heading to Blog
      */
    $('#addTitle2').click(function () {
        // Create Container
        const $container = $('<div class="relative" element-type="title-2">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        $('<input/>', {
            type: "text",
            class: "title-2 text-xl font-semibold w-full px-4 py-2 my-3 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
            placeholder: "Titel 2"
        }).appendTo($container)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        sendNotif("Titel 2 wurde hinzugefuegt", "success")
        scrollToBottom()
    });

    /**
      * Add Text to Blog
      */
    $('#addText').click(function () {
        // Create Container
        const $container = $('<div class="relative my-2" element-type="textArea">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        const textAreaId = "textArea" + Date.now();
        BlogRichText.create(textAreaId, '').appendTo($container)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        BlogRichText.mount(document.getElementById(textAreaId), '')
        sendNotif("Eine Text-Box wurde hinzugefügt", "success")
        scrollToBottom()
    });

    /**
      * Add Image to Blog
      */
    $('#addImage').click(function () {
        // Create Container
        const $container = $('<div class="relative w-fit my-3" element-type="image">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-img"><i class="bi bi-pencil-square"></i></span>'))

        $('<img>', {
            title: "Bildtitel",
            src: "https://placehold.co/600x400",
            class: "rounded-2xl w-auto h-129",
        }).appendTo($container)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        $container.find('.edit-img').click(function () {
            openBlogImageModal($(this).siblings('img'));
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        sendNotif("Ein Bild wurde hinzugefügt. Bitte konfigurieren.", "success")
        scrollToBottom()
        $container.find('.edit-img').click()
    });

    /**
      * Add Image to Blog
      */
    $('#addVideo').click(function () {
        // Create Container
        const $container = $('<div class="relative w-fit py-4 my-3" element-type="yt-video">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-youtube"><i class="bi bi-pencil-square"></i></span>'))

        $('<iframe/>', {
            title: "YouTube video player",
            frameborder: "0",
            src: "https://www.youtube.com/embed/eEzD-Y97ges",
            allow: "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share",
            class: "rounded-2xl",
            width: "560",
            height: "315",
            allowfullscreen: "True"
        }).appendTo($container)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        $container.find('.edit-youtube').click(function () {
            $editYoutube = $(this).siblings('iframe');

            height = $editYoutube[0].style.height ? $editYoutube[0].style.height : $editYoutube.height();
            width = $editYoutube[0].style.width ? $editYoutube[0].style.width : $editYoutube.width();

            $('#youtubeHeight').val(height)
            $('#youtubeWidth').val(width)

            $('#youtubeURL').val($editYoutube.attr('src'))
            $('#youtubeText').val($editYoutube.attr('title'))
            $('#youtubeModal').toggleClass("hidden");
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        sendNotif("Ein Youtube Video wurde hinzugefügt. Bitte konfigurieren.", "success")
        scrollToBottom()
        $container.find('.edit-youtube').click()
    });

    /**
     * Add Real Video
     */
    $('#addVideoCMS').click(function () {
        $.get("/cms/videos/all/", function (response) {
            if (!response.video_urls || response.video_urls.length === 0) {
                sendNotif("Keine Videos verfügbar", "error");
                return;
            }

            const video = response.video_urls[0]; // z.B. erstes Video einfügen
            const $container = $('<div class="relative py-4 my-3" element-type="video">');
            $container.append($('<span class="absolute top-0 right-0 px-2 py-1 text-sm text-white bg-red-500 rounded-full z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'));
            $container.append($('<span class="absolute top-0 right-1/2 px-2 py-1 text-sm text-white bg-blue-500 rounded-full z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'));
            $container.append($('<span class="absolute top-0 left-0 px-2 py-1 text-sm font-semibold text-white bg-orange-500 rounded-full z-40 hover:cursor-pointer edit-cmsvideo"><i class="bi bi-pencil-square"></i></span>'));

            const $videoElem = $('<video>', {
                title: video.title,
                src: video.url,
                poster: video.poster,
                class: "rounded-2xl",
                width: 560,
                height: 315,
                autoplay: video.autoplay,
                muted: video.muted,
                loop: video.loop,
                playsinline: video.playsinline,
                controls: video.show_controls,
                preload: video.preload
            });

            // SEO relevante Daten als Data-Attributes
            $videoElem.data({
                video_id: video.id,
                description: video.description,
                alt_text: video.alt_text,
                tags: video.tags,
                duration: video.duration
            });
            $videoElem.attr('data-video_id', video.id || '');
            $videoElem.attr('data-description', video.description || '');
            $videoElem.attr('data-alt_text', video.alt_text || '');
            $videoElem.attr('data-tags', video.tags || '');
            $videoElem.attr('data-duration', video.duration || '');

            $container.append($videoElem);

            $container.find('.del-elem').click(function () {
                $(this).parent().remove();
            });

            // Edit-Handler
            $container.find('.edit-cmsvideo').click(function () {
                openBlogVideoModal($(this).parent());
            });

            $("#blogContent").append($container);
            sendNotif("Ein Video wurde eingefügt", "success");
            scrollToBottom();
            $container.find('.edit-cmsvideo').click();
        });
    });

    // Open File modal
    $('#addFile').click(function () {
        $('#anyfileModal').removeClass('hidden');
        selectedAnyfile = null;
        $('#selectAnyfile').prop('disabled', true);
        loadAnyfiles();
    });

    /**
     * Add Galerie to Blog
     */
    $('#addGalerie').click(function () {
        // Create Container
        const $container = $('<div class="relative w-full my-4" element-type="galery" galery-id="0">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))
        $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-slider"><i class="bi bi-pencil-square"></i></span>'))

        const $carousel = $('<div class="carousel rounded-lg">')
        for (let i = 0; i < 2; i++) {
            const $cDiv = $('<div>')
            $('<img>', {
                title: "Carousel Placeholder",
                src: "https://placehold.co/800x400",
                class: "w-full rounded-xl h-96",
            }).appendTo($cDiv)
            $carousel.append($cDiv)
        }
        $carousel.slick({
            dots: true,  // Display navigation dots
            arrows: true,  // Display navigation arrows
            infinite: true,  // Enable infinite looping
            slidesToShow: 1,  // Number of slides to show at once
            slidesToScroll: 1,  // Number of slides to scroll at a time
            autoplay: true,
            autoplaySpeed: 3000,
            // Add any other configuration options as needed
        });
        $container.append($carousel)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        $container.find('.edit-slider').click(function () {
            openBlogGalleryModal($(this).siblings('.carousel'));
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);

        sendNotif("Eine Galerie wurde hinzugefügt. Bitte konfigurieren.", "success")
        scrollToBottom()
        $container.find('.edit-slider').click()

    });

    /**
      * Add Text to Blog
      */
    $('#addCode').click(function () {
        // Create Container
        const $container = $('<div class="relative my-3" element-type="code">')
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'))
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'))

        const $codeContainer = $('<div class="code border-2 border-dotted border-gray-600 rounded-xl p-2 mb-3">')

        $('<input/>', {
            type: "text",
            class: "code-language title-3 text-lg w-full px-4 py-2 my-3 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
            placeholder: "Sprache (z.B. python)"
        }).appendTo($codeContainer)
        $('<textarea/>', {
            rows: "4",
            class: "code-source w-full text-black px-4 py-2 my-3 rounded-2xl border border-gray-300 focus:outline-none focus:border-blue-500 min-h-[5rem]",
            placeholder: "Deinen Source-Code hier rein kopieren"
        }).appendTo($codeContainer)
        $container.append($codeContainer)
        // Click event handler for the span with class del-elem
        $container.find('.del-elem').click(function () {
            $(this).parent().remove()
        });
        // Append Container to Blog Builder
        $("#blogContent").append($container);
        sendNotif("Ein Code-Editor wurde hinzugefügt", "success")
        scrollToBottom()
    });



    /****************** Titelbild *******************/

    $('#titleImgUpload').change(function () {
        // Get the uploaded file
        var file = this.files[0];

        // Check if a file is selected
        if (file) {
            // Create a FileReader
            var reader = new FileReader();

            // Set up the FileReader onload event
            reader.onload = function (e) {
                // Set the source of the preview image to the FileReader result
                $('#fileUpload').css('background-image', "url('" + e.target.result + "')");
                // Show the preview image
                imageData = e.target.result
            };

            // Read the uploaded file as a data URL
            reader.readAsDataURL(file);
        } else {
            // Hide the preview image if no file is selected
            $('#fileUpload').css('background-image', "none");

        }
    });

    /****************** Blog Action Logic *******************/
    $('#closeModal').click(function () {
        closeBlogPreviewModal()
    });
    $('#closeGaleryModal').click(function () {
        $('#galleryModal').addClass('hidden').removeClass('flex')
    });
    $('#closeImageModal').click(function () {
        closeBlogImageModal()
    })
    $('#closeYoutubeModal').click(function () {
        $('#youtubeModal').toggleClass("hidden")
    })
    $('#closeAnyfileModal').click(function () {
        $('#anyfileModal').addClass('hidden');
    });

    /****************** AnyFile Logic *******************/
    $('#reloadAnyfiles').click(function () {
        loadAnyfiles($('#anyfileSearch').val().trim());
    });
    // Live-Filter (client-seitig)
    $('#anyfileSearch').on('input', function () {
        const q = $(this).val().toLowerCase();
        $('#availableAnyfiles .anyfile-tile').each(function () {
            const hay = ($(this).data('title') + ' ' + $(this).data('ext')).toLowerCase();
            $(this).toggle(hay.includes(q));
        });
    });
    // Laden
    function loadAnyfiles() {
        const $grid = $('#availableAnyfiles');
        const $empty = $('#anyfileEmpty');
        $grid.empty(); $empty.addClass('hidden');

        $.get('/cms/anyfiles/all/', function (resp) {
            if (!resp.files || resp.files.length === 0) {
                $empty.removeClass('hidden'); return;
            }
            resp.files.forEach(f => {
                const $tile = $(`
            <div class="anyfile-tile border rounded p-3 hover:shadow cursor-pointer transition group"
                data-id="${f.id}" data-url="${f.url}" data-title="${$('<div>').text(f.title).html()}" data-ext="${f.ext}">
            <div class="flex items-center gap-2">
                <i class="bi ${fileIconForExt(f.ext)} text-xl"></i>
                <div class="truncate">
                <div class="font-medium truncate" title="${f.title}">${f.title}</div>
                <div class="text-xs text-gray-500">${f.ext}</div>
                </div>
            </div>
            </div>
        `);
                $tile.on('click', function () {
                    $('#availableAnyfiles .anyfile-tile').removeClass('border-2 border-blue-500');
                    $(this).addClass('border-2 border-blue-500');
                    selectedAnyfile = {
                        id: $(this).data('id'),
                        url: $(this).data('url'),
                        title: $(this).data('title'),
                        ext: $(this).data('ext'),
                    };
                    $('#selectAnyfile').prop('disabled', false);
                });
                $grid.append($tile);
            });
        });
    }
    // UI-Block erzeugen
    function addAnyfileToContent(file) {
        const $container = $('<div class="relative my-3" element-type="file">');
        $container.append($('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>'));
        $container.append($('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>'));

        const icon = fileIconForExt(file.ext);
        const $a = $(`
    <a class="file-attachment flex items-center gap-2 p-3 border rounded hover:bg-gray-50"
       href="${file.url}" target="_blank" rel="noopener"
       data-id="${file.id}" data-ext="${file.ext}" title="${file.title}">
      <i class="bi ${icon} text-xl"></i>
      <span class="file-title truncate">${file.title}</span>
    </a>
  `);

        $container.append($a);

        // delete des Blocks
        $container.find('.del-elem').click(function () {
            $(this).parent().remove();
        });

        $('#blogContent').append($container);
    }

    $('#selectAnyfile').click(function () {
        if (!selectedAnyfile) return;
        addAnyfileToContent(selectedAnyfile);
        $('#anyfileModal').addClass('hidden');
        sendNotif('Datei hinzugefügt', 'success');
        // Scroll nach unten (du hast schon scrollToBottom())
        if (typeof scrollToBottom === 'function') scrollToBottom();
    });

    // Save Blog
    $('#createBlog').click(function () {
        enableSpinner($(this))
        // Get the CSRF token from the hidden input field

        // Check for errors
        const title = $('#blogTitle').val()
        const description = ($('#blogDescription').val() || '').trim()
        var files = $('#titleImgUpload').prop("files");

        if (title === "" || title === undefined) {
            sendNotif("Bitte gebe einen Titel für den Blog (rechts) ein.", "error")
            disableSpinner($(this))
            return;
        }

        if (description === "") {
            sendNotif("Bitte gebe eine Beschreibung für den Blog ein.", "error")
            disableSpinner($(this))
            return;
        }

        var csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

        if (window.YooLinkBlogMarkdown && YooLinkBlogMarkdown.isMarkdownMode()) {
            if (YooLinkBlogMarkdown.getMarkdown().trim() === "") {
                sendNotif("Bitte füge Markdown-Inhalt ein.", "error")
                disableSpinner($(this))
                return;
            }

            var markdownFormData = new FormData();
            markdownFormData.append('title', $('#blogTitle').val());
            markdownFormData.append('active', $('#activeSwitch').is(':checked'));
            markdownFormData.append('description', description);
            markdownFormData.append('title_image_alt', $('#titleImageAlt').val() || '');
            markdownFormData.append('title_image_title', $('#titleImageTitle').val() || '');
            markdownFormData.append('title_image_caption', $('#titleImageCaption').val() || '');
            YooLinkBlogMarkdown.appendMarkdownToFormData(markdownFormData);
            if (files.length > 0) markdownFormData.append('title_image', files[0]);

            $.ajax({
                type: "POST",
                url: "/cms/blog/create/",
                data: markdownFormData,
                processData: false,
                contentType: false,
                dataType: "json",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                },
                success: function (response) {
                    if (response.error) {
                        sendNotif(response.error, "error")
                        $(document).trigger("blogSaveError")
                        return;
                    }
                    if (window.UnsavedGuard) UnsavedGuard.markClean();
                    window.location.href = '/cms/blog/' + response.blogId + "/";
                },
                error: function (xhr, status, error) {
                    console.error("Request failed:", error);
                    const message = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Es kam zu einem unerwarteten Fehler. Versuche es später nochmal";
                    sendNotif(message, "error")
                    $('#createBlog').prop("disabled", false);
                    $(document).trigger("blogSaveError")
                },
                complete: function () {
                    disableSpinner($('#createBlog'))
                }
            });
            return;
        }

        // Get Code
        const $blockContent = $('#blogContent')
        // Select the first element with attr("element-type") = 'textArea' within elements with class 'relative' in 'blockContent'
        var $firstTextArea = $blockContent.children('.relative').find('.textArea').first();
        if ($firstTextArea.length == 0) {
            sendNotif("Es muss mindestens ein gefüllter Text hinzugefügt werden!", "error")
            disableSpinner($(this))
            return;
        }
        var firstTextAreaId = $firstTextArea.attr('id')
        var firstRt = BlogRichText.instanceById(firstTextAreaId)
        var firstTextAreaContent = firstRt ? firstRt.getContent() : ''
        var tempDiv = document.createElement("div");
        tempDiv.innerHTML = firstTextAreaContent;
        var plainText = tempDiv.textContent || tempDiv.innerText || ""
        // Überprüfen, ob ein Element gefunden wurde
        if (plainText.trim() === '') {
            // Ein Element wurde gefunden
            // Du kannst hier weiter mit 'firstTextArea' arbeiten
            sendNotif("Es muss mindestens ein gefüllter Text hinzugefügt werden!", "error")
            disableSpinner($(this))
            return;
        }
        const content = receiveContent($blockContent)
        // Load to previewBody
        const $directCodeContainer = $('<div>')
        const $modalBody = $('<div class"space-y-6">')
        const blogLayout = $('#blogLayout').val()
        if (blogLayout.includes('center')) {
            $modalBody.addClass('flex flex-col items-center')
        } else if (blogLayout.includes('right')) {
            $modalBody.removeClass('items-center').addClass('flex flex-col items-end')
        } else {
            $modalBody.removeClass('flex flex-col items-center items-end')
        }
        //$modalBody.append($copy)
        content.forEach(function (element) {
            // Führe eine Aktion für jedes Element aus
            const $elem = (element.name !== "galery") ? getWebElement(element) : getGaleryElement(element)
            $modalBody.append($elem);
        });
        $directCodeContainer.append($modalBody)

        // Create a new FormData object
        var formData = new FormData();
        formData.append('title', $('#blogTitle').val());
        formData.append('body', $directCodeContainer.html());
        formData.append('code', JSON.stringify(content));
        formData.append('active', $('#activeSwitch').is(':checked'));
        if (files.length > 0) formData.append('title_image', files[0]);
        formData.append('description', description);
        formData.append('title_image_alt', $('#titleImageAlt').val() || '');
        formData.append('title_image_title', $('#titleImageTitle').val() || '');
        formData.append('title_image_caption', $('#titleImageCaption').val() || '');

        // Send the Ajax POST request //
        $.ajax({
            type: "POST",
            url: "/cms/blog/create/",
            data: formData,
            processData: false, // Prevent jQuery from processing the data
            contentType: false, // Prevent jQuery from setting the content type
            dataType: "json",
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (response) {
                // Handle the success response here
                if (response.error) {
                    sendNotif(response.error, "error")
                    $(document).trigger("blogSaveError")
                    return;
                }
                if (window.UnsavedGuard) UnsavedGuard.markClean();
                window.location.href = '/cms/blog/' + response.blogId + "/";
            },
            error: function (xhr, status, error) {
                // Handle the error response here
                console.error("Request failed:", error);
                sendNotif("Es kam zu einem unerwarteten Fehler. Versuche es später nochmal")
                $('#createBlog').prop("disabled", false);
                $(this).find('svg').addClass('hidden');
                $(document).trigger("blogSaveError")
            },
            complete: function (result, status) {
                disableSpinner($('#createBlog'))
            }
        });
    })


    // Click on preview Button (Test)
    $('#preview').click(function () {
        if (window.YooLinkBlogMarkdown && YooLinkBlogMarkdown.isMarkdownMode()) {
            YooLinkBlogMarkdown.previewMarkdown($('#blogTitle').val());
            return;
        }

        // receive block content
        const $blockContent = $('#blogContent')
        const content = receiveContent($blockContent)

        const $modalBody = $('#previewBody')

        const blogLayout = $('#blogLayout').val()

        if (blogLayout.includes('center')) {
            $modalBody.addClass('flex flex-col items-center')
        } else if (blogLayout.includes('right')) {
            $modalBody.removeClass('items-center').addClass('flex flex-col items-end')
        } else {
            $modalBody.removeClass('flex flex-col items-center items-end')
        }

        //const $copy = $modalBody.find('address').clone()
        $modalBody.empty()
        // Add Title
        $modalBody.append($('<h1 class="text-3xl mb-6 font-extrabold leading-tight text-gray-900 lg:text-4xl">').text($('#blogTitle').val()))
        //$modalBody.append($copy)
        content.forEach(function (element) {
            // Führe eine Aktion für jedes Element aus
            const $elem = (element.name !== "galery") ? getWebElement(element) : getGaleryElement(element)
            $modalBody.append($elem);
        });

        openBlogPreviewModal()

        // Load Carousels
        setTimeout(function () {
            Prism.highlightAll();
            loadCarousels()
        }, 1000)


    });

    // Open Image Modal
    $('.edit-img').click(function () {
        openBlogImageModal($(this).siblings('img'));
    });

    /** -------- BEGIN - Youtube-Video -------- */

    // Open Youtube Modal
    $('.edit-youtube').click(function () {

        $editYoutube = $(this).siblings('iframe');

        height = $editYoutube[0].style.height ? $editYoutube[0].style.height : $editYoutube.height();
        width = $editYoutube[0].style.width ? $editYoutube[0].style.width : $editYoutube.width();

        $('#youtubeHeight').val(height)
        $('#youtubeWidth').val(width)

        $('#youtubeURL').val($editYoutube.attr('src'))
        $('#youtubeText').val($editYoutube.attr('title'))
        $('#youtubeModal').toggleClass("hidden");

    });

    // Use external image
    $('#useYoutubeURL').click(function () {
        if ($editYoutube && $('#youtubeURL').val()) {
            // Extrahiere den Code hinter "v="
            const vidTitle = $('#youtubeURL').val()
            const videoCode = vidTitle.split("v=")[1];

            // Erstelle den eingebetteten Link
            const embeddedLink = vidTitle.includes('embed') ? vidTitle : `https://www.youtube.com/embed/${videoCode}`;
            $editYoutube.attr('src', embeddedLink);
            sendNotif('Youtube Video ausgewählt', 'success')
        }
    })

    // Resize Youtube Iframe (click on "Übernehmen")
    $('#selectYoutube').click(function () {
        var imgHeight = $('#youtubeHeight').val();
        var imgWidth = $('#youtubeWidth').val();
        const $imgDiv = $editYoutube.closest('.relative')
        // Set height of edited image and parent container
        $editYoutube.css("height", imgHeight)
        $imgDiv.css("height", parseInt(imgHeight) + 20)
        // Set width of edited image and parent container
        $editYoutube.css("width", imgWidth)
        $imgDiv.css("width", imgWidth)
        // Set title of edited image
        $editYoutube.attr('title', $('#youtubeText').val())

        sendNotif('Youtube Video wurde erfolgreich angepasst', 'success')
    })

    /** -------- END - Youtube-Video -------- */

    // Open gallery Modal
    $('.edit-slider').click(function () {
        openBlogGalleryModal($(this).siblings('.carousel'));

    })

    // Reload Images
    $('#reloadImages').click(function () {
        loadBlogImageLibrary(true);
    })
    $('#imageSearchInput').on('input', function () {
        renderBlogImageLibrary(blogImageLibraryItems);
    });
    $('.blog-image-tab').on('click', function () {
        setBlogImagePanel($(this).attr('data-target'));
    });
    $('#blogImageUploadDropzone').on('click', function (event) {
        if (event.target.id === 'blogImageUploadInput') return;
        $('#blogImageUploadInput')[0].click();
    });
    $('#blogImageUploadInput').on('click', function (event) {
        event.stopPropagation();
    });
    $('#blogImageUploadInput').on('change', function () {
        uploadBlogImage(this.files && this.files[0]);
        this.value = '';
    });
    $('#blogImageUploadDropzone').on('dragover', function (event) {
        event.preventDefault();
        $(this).addClass('border-blue-500 bg-blue-100');
    });
    $('#blogImageUploadDropzone').on('dragleave drop', function () {
        $(this).removeClass('border-blue-500 bg-blue-100');
    });
    $('#blogImageUploadDropzone').on('drop', function (event) {
        event.preventDefault();
        uploadBlogImage(event.originalEvent.dataTransfer.files && event.originalEvent.dataTransfer.files[0]);
    });

    // Reload Galerien
    $('#reloadGalerien').click(function () {
        loadBlogGalleries(true);
    })
    $('#galerySearchInput').on('input', filterBlogGalleryCards);
    $('#possibleGalerien').on('click', '.pGalery', function () {
        selectedGalleryCard($(this));
    });

    // Text Field - Editor sicherstellen (Quill mountet sonst automatisch)
    $('.toggle-text-editor').click(function () {
        const sibling = $(this).siblings(".textArea")[0]
        if (sibling && window.BlogRichText) BlogRichText.mount(sibling)
    })

    /*---- IMAGES SECTION -----*/

    // Select new image
    $('#possibleImages img').click(function () {
        if ($editImg) {
            $editImg.attr('src', $(this).attr('src'));
            //$editImg.attr('imgId', )
            //$('#imageModal').toggleClass("hidden");
            sendNotif('Neues Bild ausgewählt', 'success')
        }
    });

    // Modal schließen
    $('#closeVideoModal').click(function () {
        closeBlogVideoModal();
    });

    // Modal öffnen und Videos laden
    function openVideoModal(targetElement) {
        openBlogVideoModal(targetElement);
    }

    // Modal-Videos neu laden
    $('#reloadCMSVideos').click(function () {
        loadBlogCMSVideos($('#selectedVideoId').val() || null);
    });
    $('#availableVideos').on('click', '.cms-video-preview', function () {
        const videoId = $(this).data('video-id');
        const video = blogVideoLibraryItems.find(function (item) {
            return String(item.id) === String(videoId);
        });
        $('.cms-video-preview').removeClass('border-blue-500 ring-2 ring-blue-100');
        $(this).addClass('border-blue-500 ring-2 ring-blue-100');
        selectedVideoElement = $(this);
        if (video) selectVideoData(video);
        else selectVideoAndLoadProps(videoId);
    });


    function loadCMSVideos(preselectId = null) {
        loadBlogCMSVideos(preselectId);
    }

    function selectVideoAndLoadProps(videoId) {
        $.get(`/cms/videos/get/${videoId}/`, function (data) {
            selectVideoData(data);
        });
    }

    $('#selectVideo').click(function () {
        if (!applyBlogVideoProperties()) return;
        closeBlogVideoModal();
        sendNotif("Video übernommen", "success");
    });

    function updateBlogVideoFromCMS(videoId, $targetContainer) {
        $.get(`/cms/videos/get/${videoId}/`, function (data) {
            const $video = $targetContainer.find('video');

            $video.attr('src', data.url);
            $video.attr('poster', data.poster);
            $video.attr('title', data.title || '');

            // Optional: Optionen setzen
            $video.prop('autoplay', data.autoplay);
            $video.prop('muted', data.muted);
            $video.prop('loop', data.loop);
            $video.prop('playsinline', data.playsinline);
            $video.prop('controls', data.show_controls);
            $video.attr('preload', data.preload);
            $video.data('video_id', data.id || '');
            $video.attr('data-video_id', data.id || '');
            $video.data('alt_text', data.alt_text || '');
            $video.attr('data-alt_text', data.alt_text || '');
            $video.data('description', data.description || '');
            $video.attr('data-description', data.description || '');
            $video.data('tags', data.tags || '');
            $video.attr('data-tags', data.tags || '');
            $video.data('duration', data.duration || '');
            $video.attr('data-duration', data.duration || '');

            sendNotif("Video aktualisiert", "success");
        });
    }

    function selectGalery(id) {
        if (!id) return;
        sendNotif("Diese Galerie wird geladen...", "notice")
        $.ajax({
            url: "/cms/galery/getImages/", // Replace this with your API endpoint
            type: "GET",
            data: { "galeryId": id },
            dataType: "json", // The data type you expect to receive from the server
            success: function (data) {
                // This function will be executed if the request is successful
                if (data.images.length > 0) {
                    rebuildSlickGallery(data.images, id)
                    $('#galleryModal').addClass('hidden').removeClass('flex')
                    sendNotif("Galerie wurde erfolgreich geladen", "success")
                } else {
                    sendNotif("Diese Galerie ist leer. Bitte befülle sie erst!", "error")
                }

                // You can now process the received data
            },
            error: function (xhr, status, error) {
                // This function will be executed if the request fails
                console.error("Error:", error);
                sendNotif("Etwas hat nicht funktioniert. Versuche es später erneut", "error")
            }
        });
    }

    // Use external image
    $('#useExternImageURL').click(function () {
        const url = $('#imgURL').val();
        if (!url) return;
        if (blogEditorImageTarget && blogEditorImageTarget.quill) {
            blogEditorImageTarget.src = url;
            refreshBlogImagePreview();
            sendNotif('Externes Bild gewählt – mit „Übernehmen" einfügen', 'notice');
            return;
        }
        if ($editImg) {
            $editImg.attr('src', url);
            refreshBlogImagePreview();
            sendNotif('Externes Bild ausgewählt', 'success')
        }
    })

    // Resize Image (click on "Übernehmen")
    $('#selectImg').click(function () {
        // Editor-Einfügemodus: Bild mit Titel/Alt/Größe in den Quill-Editor einfügen.
        if (blogEditorImageTarget && blogEditorImageTarget.quill) {
            const src = blogEditorImageTarget.src || $('#imgURL').val();
            if (!src) { sendNotif('Bitte zuerst ein Bild auswählen', 'error'); return; }
            const altText = $('#imgAlt').val() || $('#imgText').val() || '';
            const titleText = $('#imgText').val() || '';
            const w = ($('#imgWidth').val() || '').trim();
            const h = ($('#imgHeight').val() || '').trim();
            const esc = function (v) { return String(v).replace(/"/g, '&quot;'); };
            let imgHtml = '<img src="' + esc(src) + '"';
            if (altText) imgHtml += ' alt="' + esc(altText) + '"';
            if (titleText) imgHtml += ' title="' + esc(titleText) + '"';
            if (w) imgHtml += ' width="' + esc(w) + '"';
            if (h) imgHtml += ' height="' + esc(h) + '"';
            imgHtml += '>';
            const quill = blogEditorImageTarget.quill;
            const range = blogEditorImageTarget.range;
            const idx = (range && range.index != null) ? range.index : quill.getLength();
            quill.clipboard.dangerouslyPasteHTML(idx, imgHtml, 'user');
            quill.setSelection(idx + 1, 0, 'user');
            closeBlogImageModal();
            sendNotif('Bild eingefügt', 'success');
            return;
        }
        var imgHeight = $('#imgHeight').val();
        var imgWidth = $('#imgWidth').val();
        const $imgDiv = $editImg.closest('.relative')
        // Set height of edited image and parent container
        $editImg.css("height", imgHeight)
        $imgDiv.css("height", imgHeight)
        // Set width of edited image and parent container
        $editImg.css("width", imgWidth)
        $imgDiv.css("width", imgWidth)
        // Set title of edited image
        $editImg.attr('title', $('#imgText').val())
        $editImg.attr('alt', $('#imgAlt').val() || $('#imgText').val())
        if ($('#imgLazy').is(':checked')) $editImg.attr('loading', 'lazy'); else $editImg.removeAttr('loading');
        if ($('#imgAsync').is(':checked')) $editImg.attr('decoding', 'async'); else $editImg.removeAttr('decoding');

        sendNotif('Bild wurde erfolgreich angepasst', 'success')
        closeBlogImageModal()
    })

    // Resize Galery (click on "Übernehmen")
    $('#selectGalery').click(function () {
        if (selectedGalleryId) {
            selectGalery(selectedGalleryId);
            return;
        }
        applyGalleryPropertiesToCurrent();
        $('#galleryModal').addClass('hidden').removeClass('flex')
        sendNotif('Galerie wurde erfolgreich angepasst', 'success')
    })

    // Load images from backend
    function loadImages() {
        loadBlogImageLibrary(true);
    }

    // For loadGalerien()
    function addTitleAndDescription(title, description, id) {
        return galleryCardMarkup({ title: title, description: description, id: id });
    }

    // Load galerien from backend
    function loadGalerien() {
        loadBlogGalleries(true);
    }

    $('.pgallery').click(function () {
        // TODO: Select new gallery
        // ...
    })

    $('.modal').each(function () {
        const modal = $(this);
        const modalContainer = modal.find('.modal-container');

        // Close the modal when clicking outside of it (by targeting the parent modal)
        $(document).mouseup(function (e) {
            if (!modalContainer.is(e.target) && modalContainer.has(e.target).length === 0) {
                modal.addClass('hidden').removeClass('flex');
            }
        });
    });

});

/**
 * Receive content from blog edit div
 * @param {*} blockContent 
 * @returns 
 */
function receiveContent(blockContent) {
    // Loop through all divs
    var content = []
    blockContent.children('.relative').each(function () {
        // Check for type of div
        const elementType = $(this).attr("element-type");

        switch (elementType) {
            case "title-1":
                const title1Input = $(this).find('.title-1').val()
                content.push({
                    "name": "title-1",
                    "type": "h2",
                    "attributes": {
                        "class": "text-2xl mb-6 font-bold text-gray-900 lg:text-3xl",
                    },
                    "value": title1Input
                })
                break;
            case "title-2":
                const title2Input = $(this).find('.title-2').val()
                content.push({
                    "name": "title-2",
                    "type": "h3",
                    "attributes": {
                        "class": "text-xl font-semibold my-4 lg:text-2xl",
                    },
                    "value": title2Input
                })
                break;
            case "title-3":
                const title3Input = $(this).find('.title-3').val()
                content.push({
                    "name": "textArea",
                    "type": "p",
                    "attributes": {
                        "class": "text-base my-4",
                    },
                    "value": escapeHtml(title3Input)
                })
                break;
            case "textArea":
                const $textArea = $(this).find('.textArea')
                textId = $textArea.attr('id')
                const rtInstance = textId ? BlogRichText.instanceById(textId) : null
                if (rtInstance) {
                    content.push({
                        "name": "textArea",
                        // div statt p: Quill liefert Block-HTML (<p>/<ul>/…), das sauber
                        // in einem <div> sitzt (verschachtelte <p> wären ungültig).
                        "type": "div",
                        "attributes": {
                            // rich-text: rendert Quill-Ausrichtung/Einzug/Listen/Überschriften
                            // (rich-text.css) auf der öffentlichen Seite und in der Vorschau.
                            "class": "text-base my-4 rich-text",
                        },
                        "value": normalizeBlogTextHtml(rtInstance.getContent())
                    })
                }
                break;
            case "image":
                const $img = $(this).find('img')
                cssHeight = $img.css('height');
                cssWidth = $img.css('width');

                height = typeof $img[0].style !== 'undefined' && $img[0].style.height ? $img[0].style.height : cssHeight;
                width = typeof $img[0].style !== 'undefined' && $img[0].style.width ? $img[0].style.width : cssWidth;

                content.push({
                    "name": "image",
                    "type": "img",
                    "attributes": {
                        "src": $img.attr('src'),
                        "title": $img.attr('title'),
                        "alt": $img.attr('alt') || $img.attr('title'),
                        "class": "rounded-2xl my-4",
                        "loading": $img.attr('loading') || "",
                        "decoding": $img.attr('decoding') || "",
                    },
                    "css": {
                        "height": height,
                        "width": width
                    }
                });
                break;
            case "code":
                const lang = "language-" + $(this).find('.code-language').val()
                const $code = $(this).find('.code')
                if (lang) {
                    content.push({
                        "name": "code",
                        "type": "code",
                        "attributes": {
                            "class": "rounded-2xl my-4 " + lang,
                            "data-prismjs-copy": "Copy"
                        },
                        "value": $(this).find('.code-source').val(),
                        "css": {
                            "height": $code.css('height'),
                            "width": $code.css('width')
                        }

                    })
                }
                break;
            case "yt-video":
                const $video = $(this).find('iframe')
                cssHeight = $video.css('height');
                cssWidth = $video.css('width');

                height = typeof $video[0].style !== 'undefined' && $video[0].style.height ? $video[0].style.height : cssHeight;
                width = typeof $video[0].style !== 'undefined' && $video[0].style.width ? $video[0].style.width : cssWidth;
                content.push({
                    "name": "yt-video",
                    "type": "iframe",
                    "attributes": {
                        "width": width,
                        "height": height,
                        "src": $video.attr('src'),
                        "title": $video.attr('title'),
                        "frameborder": "0",
                        "allow": "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share",
                        "allowfullscreen": "True",
                        "class": "my-8 rounded-2xl"

                    },

                })
                break;
            case "galery":
                $carousel = $(this).find('.carousel');
                cssHeight = $carousel.css('height');
                cssWidth = $carousel.css('width');

                //height = $carousel[0].style.height ? $carousel[0].style.height : cssHeight;
                //width = $carousel[0].style.width ? $carousel[0].style.width : cssWidth;
                var urlList = []
                var altList = []
                var titleList = []
                var idList = []

                var height;
                var width;

                $carousel.find('img').each(function () {
                    var imageUrl = $(this).attr('src');
                    var imageAlt = $(this).attr('alt') || '';
                    var imageTitle = $(this).attr('title') || imageAlt;
                    var imageId = $(this).attr('data-media-id') || '';

                    if (typeof height === 'undefined' || typeof width === 'undefined') {
                        height = typeof $(this).style !== 'undefined' && $(this).style.height ? $(this).style.height : $(this).css("height");
                        width = typeof $(this).style !== 'undefined' && $(this).style.width ? $(this).style.width : $(this).css("width");
                    }

                    if (!urlList.includes(imageUrl)) {
                        urlList.push(imageUrl);
                        altList.push(imageAlt);
                        titleList.push(imageTitle);
                        idList.push(imageId);
                    }
                });
                content.push({
                    "name": "galery",
                    "type": "div",
                    "attributes": {
                        "id": $(this).attr("galery-id"),
                        "class": "carousel rounded-lg !w-full",
                        "data-autoplay": $carousel.attr("data-autoplay") || "true",
                        "data-autoplay-speed": $carousel.attr("data-autoplay-speed") || "3000",
                    },
                    "css": {
                        "height": height,
                        "width": width
                    },
                    "images": urlList,
                    "imageAlts": altList,
                    "imageTitles": titleList,
                    "imageIds": idList,
                    "imageClass": "w-full rounded-xl",
                })
                break;
            case "video":
                // 1) Bevorzugt echtes <video>
                const $videoEl = $(this).find('video');
                if ($videoEl.length) {
                    // Größen ermitteln
                    const cssH = $videoEl.css('height');
                    const cssW = $videoEl.css('width');
                    const height = ($videoEl[0].style && $videoEl[0].style.height) ? $videoEl[0].style.height : cssH;
                    const width = ($videoEl[0].style && $videoEl[0].style.width) ? $videoEl[0].style.width : cssW;
                    // Attribute/Props einsammeln
                    const src = $videoEl.attr('src') || '';
                    const poster = $videoEl.attr('poster') || '';
                    const title = $videoEl.attr('title') || '';
                    const preload = $videoEl.attr('preload') || 'metadata';
                    const autoplay = !!$videoEl.prop('autoplay');
                    const muted = !!$videoEl.prop('muted');
                    const loop = !!$videoEl.prop('loop');
                    const playsinline = !!$videoEl.prop('playsinline');
                    const controls = !!$videoEl.prop('controls');
                    // SEO/Model Felder (data-Attribute)
                    const dataAlt = $videoEl.data('alt_text') || '';
                    const dataDesc = $videoEl.data('description') || '';
                    const dataTags = $videoEl.data('tags') || '';
                    const dataDuration = $videoEl.data('duration') || '';
                    const dataVideoId = $videoEl.data('video_id') || '';
                    // Klassen zusammenführen
                    const klass = ($videoEl.attr('class') || '').trim();
                    const mergedClass = (klass ? klass + " " : "") + "my-8 rounded-2xl";
                    // Attribute setzen (Booleans nur wenn true)
                    const attrs = {
                        "src": src,
                        "poster": poster,
                        "title": title,
                        "preload": preload,
                        "class": mergedClass,
                        "data-alt_text": dataAlt,
                        "data-description": dataDesc,
                        "data-tags": dataTags,
                        "data-duration": dataDuration,
                        "data-video_id": dataVideoId,
                    };
                    if (autoplay) attrs.autoplay = "autoplay";
                    if (muted) attrs.muted = "muted";
                    if (loop) attrs.loop = "loop";
                    if (playsinline) attrs.playsinline = "playsinline";
                    if (controls) attrs.controls = "controls";
                    content.push({
                        "name": "video",
                        "type": "video",
                        "attributes": attrs,
                        "css": {
                            "height": height,
                            "width": width
                        }
                    });
                }
                break;
            case "file":
                const $a = $(this).find('a.file-attachment');
                content.push({
                    "name": "file",
                    "type": "a",
                    "attributes": {
                        "href": $a.attr('href'),
                        "target": "_blank",
                        "rel": "noopener",
                        "title": $a.attr('title') || $a.find('.file-title').text(),
                        "data-id": $a.data('id'),
                        "data-ext": $a.data('ext'),
                        "class": "file-attachment flex items-center gap-2 p-3 border rounded my-3"
                    },
                    // Text im Anchor (nutzen wir als sichtbaren Titel)
                    "value": $a.find('.file-title').text()
                });
                break;

        }
    });
    return content;
}


function getGaleryElement(gallery) {
    var elem = $('<' + gallery.type + ">");
    // Füge die Attribute dem Element hinzu
    $.each(gallery.attributes, function (key, value) {
        elem.attr(key, value);
    });

    $.each(gallery.css, function (key, value) {
        elem.css(key, value);
    });

    const imageAlts = gallery.imageAlts || [];
    const imageTitles = gallery.imageTitles || [];
    const imageIds = gallery.imageIds || [];
    gallery.images.forEach(function (url, index) {
        const $div = $('<div>')
        const $img = $('<img>');
        $img.addClass(gallery.imageClass);
        $img.attr('src', url);
        $img.attr('alt', imageAlts[index] || 'Galeriebild');
        if (imageTitles[index]) $img.attr('title', imageTitles[index]);
        if (imageIds[index]) $img.attr('data-media-id', imageIds[index]);
        $.each(gallery.css, function (key, value) {
            $img.css(key, value);
        });
        $div.append($img);
        elem.append($div);
    })
    return elem;
}

function loadCarousels() {
    initBlogCarousels($(document));
    refreshVisibleBlogCarousels($(document));
}

function replaceLinks(text) {
    const linkRegex = /link\("([^"]+)", "([^"]+)"\)/g;
    let replacedText = text;

    let match;
    while ((match = linkRegex.exec(text)) !== null) {
        const link = `<a class="text-blue-500 hover:text-blue-600" href="${match[2]}">${match[1]}</a>`;
        replacedText = replacedText.replace(match[0], link);
    }

    return replacedText;
}

/**
 * Baut aus einem JSON-Baustein ein DOM-Element.
 * Unterstützt speziell: <video> (Boolean-Props, CSS width/height)
 * und "code" (in <pre> wrap).
 *
 * @param {*} jsonElem
 * @returns jQuery-Element
 */
function getWebElement(jsonElem) {
    const type = jsonElem.type || 'div';
    let elem;

    // 1) Spezialfall: echtes Video
    if (jsonElem.name === 'video' && type === 'video') {
        elem = $('<video>');

        // Attribute setzen (string-Attribute)
        if (jsonElem.attributes) {
            // zuerst Standard-String-Attribute
            const strAttrs = ['src', 'poster', 'title', 'preload', 'class', 'id'];
            strAttrs.forEach(k => {
                if (jsonElem.attributes[k] != null && jsonElem.attributes[k] !== false) {
                    elem.attr(k, jsonElem.attributes[k]);
                }
            });

            // SEO/Model-Daten als data-*
            Object.keys(jsonElem.attributes).forEach(k => {
                if (k.startsWith('data-')) {
                    elem.attr(k, jsonElem.attributes[k]);
                }
            });

            // Boolean-Props korrekt anwenden
            const boolMap = ['autoplay', 'muted', 'loop', 'playsinline', 'controls'];
            boolMap.forEach(k => {
                // im JSON steht meist "autoplay": "autoplay" (oder true)
                const v = jsonElem.attributes[k];
                if (v === true || v === 'true' || v === k || v === '1' || v === 'autoplay' || v === 'muted' || v === 'loop' || v === 'playsinline' || v === 'controls') {
                    elem.prop(k, true).attr(k, k); // prop + Präsenz-Attribut
                }
            });
        }

        // Größe immer per CSS setzen (unterstützt px/%)
        if (jsonElem.css) {
            if (jsonElem.css.width) elem.css('width', jsonElem.css.width);
            if (jsonElem.css.height) elem.css('height', jsonElem.css.height);
            // weitere CSS übernehmen
            Object.keys(jsonElem.css).forEach(k => {
                if (k !== 'width' && k !== 'height') elem.css(k, jsonElem.css[k]);
            });
        }

        return elem;
    }

    // Spezialfall: Datei-Link mit Icon
    if (jsonElem.name === 'file' && (jsonElem.type === 'a' || !jsonElem.type)) {
        const ext = (jsonElem.attributes && (jsonElem.attributes['data-ext'] || jsonElem.attributes['data- ext'])) || '';
        const iconCls = fileIconForExt(ext);
        const $wrap = $('<div class="my-3">');
        const $a = $('<a>');
        if (jsonElem.attributes) {
            Object.keys(jsonElem.attributes).forEach(k => $a.attr(k, jsonElem.attributes[k]));
        }
        $a.addClass('file-attachment');
        if (jsonElem.value) $a.append($('<span class="file-title truncate">').text(jsonElem.value));
        // Icon vorn einsetzen
        $a.prepend($('<i>').addClass('bi ' + iconCls + ' text-xl mr-2'));
        return $wrap.append($a);
    }

    // 2) Standard-Rendering (inkl. iframe, img, h*, p*, etc.)
    elem = $('<' + type + '>');
    if (jsonElem.value) {
        if (jsonElem.name === 'code') {
            elem.text(jsonElem.value);
        } else {
            elem.html(replaceLinks(jsonElem.value));
        }
    }

    // Attribute setzen
    if (jsonElem.attributes) {
        $.each(jsonElem.attributes, function (key, value) {
            // Für iframes darf alles wie gehabt als Attribut bleiben
            elem.attr(key, value);
        });
    }

    // CSS anwenden
    if (jsonElem.css) {
        $.each(jsonElem.css, function (key, value) {
            elem.css(key, value);
        });
    }

    // Code in <pre> wrappen
    if (jsonElem.name === 'code') {
        elem = $('<pre>').append(elem);
    }

    return elem;
}

/**
 * Disable Button Spinner
 * @param {*} $elem 
 */
function disableSpinner($elem) {
    $elem.prop("disabled", false);
    $elem.find('svg').addClass('hidden');
    $elem.find('.bi').removeClass('hidden');
}

/**
 * Enable Button Spinner
 * @param {*} $elem 
 */
function enableSpinner($elem) {
    $elem.prop("disabled", true);
    $elem.find('svg').removeClass('hidden');
    $elem.find('.bi').addClass('hidden');
}

window.YooLinkBlogBuilder = {
    applyCode: applyBlogCodeToBuilder,
    getCode: getBlogBuilderCode,
    refresh: refreshBlogBuilderPresentation,
};
