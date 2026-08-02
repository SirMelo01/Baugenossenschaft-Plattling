(function (window, $) {
    const state = {
        activePanel: 'markdownImageLibraryPanel',
        imageLibraryItems: [],
        imageLibraryLoaded: false,
        imageLibraryPage: 1,
        imageLibraryPagination: null,
        objectUrl: '',
        selectedFile: null,
        selectedImage: null,
        activeMediaPanel: 'markdownYoutubePanel',
        mediaVideos: [],
        mediaVideosLoaded: false,
        mediaGalleries: [],
        mediaGalleriesLoaded: false,
        mediaFiles: [],
        mediaFilesLoaded: false,
        selectedVideo: null,
        selectedGallery: null,
        selectedAnyfile: null,
        editorMode: '',
        syncing: false,
        suppressMarkdownInput: false,
    };

    function csrfToken() {
        return $('input[name="csrfmiddlewaretoken"]').val();
    }

    function notify(message, status) {
        if (typeof sendNotif === 'function') {
            sendNotif(message, status || 'notice');
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function markdownAlt(value) {
        return String(value || 'Bild').replace(/[\[\]\r\n]/g, ' ').trim() || 'Bild';
    }

    function normalizeCssSize(value) {
        const nextValue = String(value || '').trim();
        if (!nextValue) return '';
        if (/^\d+(\.\d+)?$/.test(nextValue)) return nextValue === '0' ? '0' : nextValue + 'px';
        if (/^(auto|0|\d+(\.\d+)?(px|%|rem|em|vw|vh))$/.test(nextValue)) return nextValue;
        return null;
    }

    function imageOptionsSuffix(extraOptions) {
        const width = normalizeCssSize($('#markdownImageWidth').val());
        const height = normalizeCssSize($('#markdownImageHeight').val());
        if (width === null || height === null) {
            notify('Bitte nutze für Breite und Höhe Werte wie 50%, 640px oder auto.', 'error');
            return null;
        }

        const parts = [];
        if (width) parts.push('width=' + width);
        if (height) parts.push('height=' + height);
        Object.keys(extraOptions || {}).forEach(function (key) {
            const value = extraOptions[key];
            if (value !== null && value !== undefined && value !== '') {
                parts.push(key + '=' + markdownAttrValue(value));
            }
        });
        return parts.length ? '{' + parts.join(' ') + '}' : '';
    }

    function getMarkdownTextarea() {
        return document.getElementById('blogMarkdown');
    }

    function getMarkdown() {
        const textarea = getMarkdownTextarea();
        return textarea ? textarea.value : '';
    }

    function setMarkdown(value, options) {
        const textarea = getMarkdownTextarea();
        if (!textarea) return;
        if (options && options.onlyIfEmpty && textarea.value.trim()) return;
        textarea.value = value || '';
        if (!(options && options.silent)) {
            $(textarea).trigger('input');
        }
    }

    function isMarkdownMode() {
        return $('#markdownEditorPanel').length && !$('#markdownEditorPanel').hasClass('hidden');
    }

    function showMode(mode) {
        const isMarkdown = mode === 'markdown';
        $('#builderEditorPanel').toggleClass('hidden', isMarkdown);
        $('#markdownEditorPanel').toggleClass('hidden', !isMarkdown);
        $('#buttonBar').toggleClass('hidden', isMarkdown);
        state.editorMode = mode;

        $('[data-blog-editor-mode]').each(function () {
            const $button = $(this);
            const active = $button.data('blog-editor-mode') === mode;
            $button
                .toggleClass('bg-slate-900 text-white border-slate-900', active)
                .toggleClass('bg-white text-gray-700 border-gray-200 hover:bg-gray-50', !active)
                .attr('aria-pressed', active ? 'true' : 'false');
        });

        if (isMarkdown) {
            const initial = $('#blogInitialMarkdown').val();
            if (initial) setMarkdown(initial, { onlyIfEmpty: true });
            $('#blogMarkdown').trigger('focus');
        } else if (window.YooLinkBlogBuilder && typeof YooLinkBlogBuilder.refresh === 'function') {
            window.requestAnimationFrame(function () {
                YooLinkBlogBuilder.refresh();
            });
        }
    }

    function setMode(mode, options) {
        if (state.syncing) return;
        if ((options && options.skipSync) || !state.editorMode || state.editorMode === mode) {
            showMode(mode);
            return;
        }

        state.syncing = true;
        const sync = state.editorMode === 'markdown' && mode === 'builder'
            ? syncMarkdownToBuilder()
            : syncBuilderToMarkdown();

        sync.done(function () {
            showMode(mode);
        }).fail(function (xhr) {
            const message = xhr && xhr.responseJSON && xhr.responseJSON.error
                ? xhr.responseJSON.error
                : 'Der Editor konnte nicht synchronisiert werden.';
            notify(message, 'error');
        }).always(function () {
            state.syncing = false;
        });
    }

    function syncMarkdownToBuilder() {
        const markdown = getMarkdown().trim();
        const deferred = $.Deferred();

        if (!markdown) {
            if (window.YooLinkBlogBuilder && typeof YooLinkBlogBuilder.applyCode === 'function') {
                YooLinkBlogBuilder.applyCode([]);
            }
            deferred.resolve();
            return deferred.promise();
        }

        $.ajax({
            type: 'POST',
            url: '/cms/blog/markdown/preview/',
            data: { markdown: markdown },
            dataType: 'json',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken());
            },
        }).done(function (response) {
            if (!window.YooLinkBlogBuilder || typeof YooLinkBlogBuilder.applyCode !== 'function') {
                deferred.resolve();
                return;
            }
            YooLinkBlogBuilder.applyCode(response.code || []);
            deferred.resolve();
        }).fail(function (xhr) {
            deferred.reject(xhr);
        });

        return deferred.promise();
    }

    function syncBuilderToMarkdown() {
        const deferred = $.Deferred();
        const getCode = window.YooLinkBlogBuilder && YooLinkBlogBuilder.getCode;

        if (typeof getCode !== 'function') {
            deferred.resolve();
            return deferred.promise();
        }

        $.ajax({
            type: 'POST',
            url: '/cms/blog/markdown/from-code/',
            data: { code: JSON.stringify(getCode()) },
            dataType: 'json',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken());
            },
        }).done(function (response) {
            setMarkdown(response.markdown || '', { silent: true });
            deferred.resolve();
        }).fail(function (xhr) {
            deferred.reject(xhr);
        });

        return deferred.promise();
    }

    function applyPreviewLayout($modalBody) {
        const blogLayout = $('#blogLayout').val() || 'left';
        $modalBody.removeClass('flex flex-col items-center items-end');
        if (blogLayout.includes('center')) {
            $modalBody.addClass('flex flex-col items-center');
        } else if (blogLayout.includes('right')) {
            $modalBody.addClass('flex flex-col items-end');
        }
    }

    function insertAtCursor(text) {
        const textarea = getMarkdownTextarea();
        if (!textarea) return;

        const start = textarea.selectionStart || 0;
        const end = textarea.selectionEnd || 0;
        const before = textarea.value.substring(0, start);
        const after = textarea.value.substring(end);
        textarea.value = before + text + after;
        const cursor = start + text.length;
        textarea.focus();
        textarea.selectionStart = cursor;
        textarea.selectionEnd = cursor;
        $(textarea).trigger('input');
    }

    function insertImageMarkdown(url, altText, imageData) {
        if (!url) return false;
        const extraOptions = {};
        const title = imageData && (imageData.title || imageData.alt);
        if (title) extraOptions.title = title;
        if (imageData && imageData.id) extraOptions.id = imageData.id;
        const suffix = imageOptionsSuffix(extraOptions);
        if (suffix === null) return false;

        insertAtCursor('\n\n![' + markdownAlt(altText) + '](' + url + ')' + suffix + '\n\n');
        closeImageModal();
        notify('Bild-Markdown wurde eingefügt', 'success');
        return true;
    }

    function markdownAttrValue(value) {
        const stringValue = String(value || '').trim();
        if (!stringValue) return '';
        if (/\s|[{}'"]/.test(stringValue)) {
            return '"' + stringValue.replace(/"/g, '&quot;') + '"';
        }
        return stringValue;
    }

    function shortcodeAttrs(attrs) {
        const parts = [];
        Object.keys(attrs || {}).forEach(function (key) {
            const value = attrs[key];
            if (value === true) {
                parts.push(key.replace(/_/g, '-'));
            } else if (value !== null && value !== undefined && value !== '') {
                parts.push(key.replace(/_/g, '-') + '=' + markdownAttrValue(value));
            }
        });
        return parts.length ? '{' + parts.join(' ') + '}' : '{}';
    }

    function sizeOptions(widthSelector, heightSelector) {
        const width = normalizeCssSize($(widthSelector).val());
        const height = normalizeCssSize($(heightSelector).val());
        if (width === null || height === null) {
            notify('Bitte nutze für Breite und Höhe Werte wie 50%, 640px oder auto.', 'error');
            return null;
        }
        const options = {};
        if (width) options.width = width;
        if (height) options.height = height;
        return options;
    }

    function selectedMarkdownText() {
        const textarea = getMarkdownTextarea();
        if (!textarea) return '';
        return textarea.value.substring(textarea.selectionStart || 0, textarea.selectionEnd || 0);
    }

    function setMediaPanel(panelId) {
        state.activeMediaPanel = panelId;
        $('.markdown-media-panel').addClass('hidden').removeClass('flex');
        $('#' + panelId).removeClass('hidden').addClass('flex');

        $('.markdown-media-tab')
            .removeClass('bg-blue-900 text-white shadow-sm')
            .addClass('text-slate-700 hover:bg-white hover:text-slate-950');

        $('.markdown-media-tab[data-target="' + panelId + '"]')
            .addClass('bg-blue-900 text-white shadow-sm')
            .removeClass('text-slate-700 hover:bg-white hover:text-slate-950');

        if (panelId === 'markdownVideoPanel') loadMarkdownVideos(false);
        if (panelId === 'markdownGalleryPanel') loadMarkdownGalleries(false);
        if (panelId === 'markdownFilePanel') loadMarkdownFiles(false);
    }

    function resetMediaModalState() {
        state.selectedVideo = null;
        state.selectedGallery = null;
        state.selectedAnyfile = null;
        $('#markdownYoutubeUrl, #markdownYoutubeTitle, #markdownYoutubeWidth, #markdownYoutubeHeight').val('');
        $('#markdownVideoWidth, #markdownVideoHeight, #markdownGalleryWidth, #markdownGalleryHeight, #markdownFileSearch, #markdownCodeLanguage, #markdownCodeSource').val('');
        renderMarkdownVideos(state.mediaVideos);
        renderMarkdownGalleries(state.mediaGalleries);
        renderMarkdownFiles(state.mediaFiles);
    }

    function openMediaModal() {
        resetMediaModalState();
        setMediaPanel('markdownYoutubePanel');
        $('#markdownMediaModal').removeClass('hidden').addClass('flex');
    }

    function closeMediaModal() {
        $('#markdownMediaModal').addClass('hidden').removeClass('flex');
    }

    function mediaCard(title, meta, selected) {
        const $button = $('<button type="button" class="rounded-lg border bg-white p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"></button>');
        $button.toggleClass('border-blue-500 ring-2 ring-blue-100', !!selected);
        $button.toggleClass('border-slate-200 hover:border-blue-300', !selected);
        $button.append($('<span class="block text-sm font-semibold text-slate-950"></span>').text(title || 'Ohne Titel'));
        if (meta) {
            $button.append($('<span class="mt-1 block text-xs text-slate-500"></span>').text(meta));
        }
        return $button;
    }

    function renderMarkdownVideos(items) {
        const $grid = $('#markdownVideoLibrary');
        $grid.empty();
        if (!items || !items.length) {
            $('#markdownVideoEmpty').removeClass('hidden');
            return;
        }
        $('#markdownVideoEmpty').addClass('hidden');
        items.forEach(function (video) {
            const selected = state.selectedVideo && state.selectedVideo.id === video.id;
            const $card = mediaCard(video.title || 'Video', video.alt_text || video.url, selected);
            if (video.poster) {
                $card.prepend($('<img class="mb-2 aspect-video w-full rounded-md object-cover">').attr('src', video.poster).attr('alt', video.title || 'Video'));
            }
            $card.on('click', function () {
                state.selectedVideo = video;
                renderMarkdownVideos(state.mediaVideos);
            });
            $grid.append($card);
        });
    }

    function loadMarkdownVideos(force) {
        if (state.mediaVideosLoaded && !force) {
            renderMarkdownVideos(state.mediaVideos);
            return;
        }
        $('#markdownVideoLibrary').empty();
        $('#markdownVideoEmpty').addClass('hidden');
        $.get('/cms/videos/all/', function (response) {
            state.mediaVideos = response.video_urls || [];
            state.mediaVideosLoaded = true;
            renderMarkdownVideos(state.mediaVideos);
            if (force) notify(state.mediaVideos.length ? 'Videos geladen' : 'Keine Videos gefunden', state.mediaVideos.length ? 'success' : 'error');
        }).fail(function () {
            notify('Videos konnten nicht geladen werden', 'error');
        });
    }

    function renderMarkdownGalleries(items) {
        const $grid = $('#markdownGalleryLibrary');
        $grid.empty();
        if (!items || !items.length) {
            $('#markdownGalleryEmpty').removeClass('hidden');
            return;
        }
        $('#markdownGalleryEmpty').addClass('hidden');
        items.forEach(function (gallery) {
            const images = gallery.images || [];
            const selected = state.selectedGallery && state.selectedGallery.id === gallery.id;
            const $card = mediaCard(gallery.title || 'Galerie', images.length + ' Bilder', selected);
            if (images[0] && images[0].url) {
                $card.prepend($('<img class="mb-2 aspect-video w-full rounded-md object-cover">').attr('src', images[0].url).attr('alt', gallery.title || 'Galerie'));
            }
            $card.on('click', function () {
                state.selectedGallery = gallery;
                renderMarkdownGalleries(state.mediaGalleries);
            });
            $grid.append($card);
        });
    }

    function loadMarkdownGalleries(force) {
        if (state.mediaGalleriesLoaded && !force) {
            renderMarkdownGalleries(state.mediaGalleries);
            return;
        }
        $('#markdownGalleryLibrary').empty();
        $('#markdownGalleryEmpty').addClass('hidden');
        $.get('/cms/galerien/all/', function (response) {
            state.mediaGalleries = response.galerien || [];
            state.mediaGalleriesLoaded = true;
            renderMarkdownGalleries(state.mediaGalleries);
            if (force) notify(state.mediaGalleries.length ? 'Galerien geladen' : 'Keine Galerien gefunden', state.mediaGalleries.length ? 'success' : 'error');
        }).fail(function () {
            notify('Galerien konnten nicht geladen werden', 'error');
        });
    }

    function renderMarkdownFiles(items) {
        const query = ($('#markdownFileSearch').val() || '').toLowerCase().trim();
        const filtered = (items || []).filter(function (file) {
            return !query || String(file.title || '').toLowerCase().includes(query) || String(file.ext || '').toLowerCase().includes(query);
        });
        const $grid = $('#markdownFileLibrary');
        $grid.empty();
        if (!filtered.length) {
            $('#markdownFileEmpty').removeClass('hidden');
            return;
        }
        $('#markdownFileEmpty').addClass('hidden');
        filtered.forEach(function (file) {
            const selected = state.selectedAnyfile && state.selectedAnyfile.id === file.id;
            const $card = mediaCard(file.title || 'Datei', file.ext || file.url, selected);
            $card.on('click', function () {
                state.selectedAnyfile = file;
                renderMarkdownFiles(state.mediaFiles);
            });
            $grid.append($card);
        });
    }

    function loadMarkdownFiles(force) {
        if (state.mediaFilesLoaded && !force) {
            renderMarkdownFiles(state.mediaFiles);
            return;
        }
        $('#markdownFileLibrary').empty();
        $('#markdownFileEmpty').addClass('hidden');
        $.get('/cms/anyfiles/all/', function (response) {
            state.mediaFiles = response.files || [];
            state.mediaFilesLoaded = true;
            renderMarkdownFiles(state.mediaFiles);
            if (force) notify(state.mediaFiles.length ? 'Dateien geladen' : 'Keine Dateien gefunden', state.mediaFiles.length ? 'success' : 'error');
        }).fail(function () {
            notify('Dateien konnten nicht geladen werden', 'error');
        });
    }

    function insertMarkdownMedia() {
        if (state.activeMediaPanel === 'markdownYoutubePanel') {
            const options = sizeOptions('#markdownYoutubeWidth', '#markdownYoutubeHeight');
            if (options === null) return;
            const url = $('#markdownYoutubeUrl').val().trim();
            if (!url) {
                notify('Bitte gib eine YouTube URL ein', 'error');
                return;
            }
            insertAtCursor('\n\n::youtube' + shortcodeAttrs($.extend({ url: url, title: $('#markdownYoutubeTitle').val().trim() || 'YouTube Video' }, options)) + '\n\n');
        } else if (state.activeMediaPanel === 'markdownVideoPanel') {
            const video = state.selectedVideo;
            if (!video) {
                notify('Bitte wähle ein Video aus', 'error');
                return;
            }
            const options = sizeOptions('#markdownVideoWidth', '#markdownVideoHeight');
            if (options === null) return;
            const attrs = $.extend({
                src: video.url,
                poster: video.poster || '',
                title: video.title || 'Video',
                alt: video.alt_text || '',
                description: video.description || '',
                tags: video.tags || '',
                duration: video.duration || '',
                id: video.id || '',
                preload: video.preload || 'metadata',
                controls: video.show_controls !== false,
                autoplay: !!video.autoplay,
                muted: !!video.muted,
                loop: !!video.loop,
                playsinline: !!video.playsinline,
            }, options);
            insertAtCursor('\n\n::video' + shortcodeAttrs(attrs) + '\n\n');
        } else if (state.activeMediaPanel === 'markdownGalleryPanel') {
            const gallery = state.selectedGallery;
            if (!gallery || !gallery.images || !gallery.images.length) {
                notify('Bitte wähle eine Galerie mit Bildern aus', 'error');
                return;
            }
            const options = sizeOptions('#markdownGalleryWidth', '#markdownGalleryHeight');
            if (options === null) return;
            const lines = gallery.images
                .filter(function (image) { return image && image.url; })
                .map(function (image, index) {
                    const alt = image.alt || image.title || gallery.title || 'Galeriebild ' + (index + 1);
                    const options = {};
                    if (image.title) options.title = image.title;
                    if (image.id) options.id = image.id;
                    const suffix = shortcodeAttrs(options).replace('{}', '');
                    return '![' + markdownAlt(alt) + '](' + image.url + ')' + suffix;
                });
            insertAtCursor('\n\n:::gallery' + shortcodeAttrs(options).replace('{}', '') + '\n' + lines.join('\n') + '\n:::\n\n');
        } else if (state.activeMediaPanel === 'markdownFilePanel') {
            const file = state.selectedAnyfile;
            if (!file) {
                notify('Bitte wähle eine Datei aus', 'error');
                return;
            }
            insertAtCursor('\n\n::file' + shortcodeAttrs({ href: file.url, title: file.title || 'Datei herunterladen', ext: file.ext || '', id: file.id || '' }) + '\n\n');
        } else if (state.activeMediaPanel === 'markdownCodePanel') {
            const language = $('#markdownCodeLanguage').val().trim();
            const source = $('#markdownCodeSource').val() || selectedMarkdownText() || '';
            insertAtCursor('\n\n```' + language + '\n' + source + '\n```\n\n');
        }
        closeMediaModal();
        notify('Markdown-Element wurde eingefügt', 'success');
    }

    function setImagePanel(panelId) {
        state.activePanel = panelId;
        $('.markdown-image-panel').addClass('hidden').removeClass('flex');
        $('#' + panelId).removeClass('hidden').addClass('flex');

        $('.markdown-image-tab')
            .removeClass('bg-blue-900 text-white shadow-sm')
            .addClass('text-slate-700 hover:bg-white hover:text-slate-950');

        $('.markdown-image-tab[data-target="' + panelId + '"]')
            .addClass('bg-blue-900 text-white shadow-sm')
            .removeClass('text-slate-700 hover:bg-white hover:text-slate-950');

        updateInsertState();
    }

    function resetImageModalState() {
        state.selectedImage = null;
        state.selectedFile = null;
        state.imageLibraryLoaded = false;
        state.imageLibraryPage = 1;
        state.imageLibraryPagination = null;
        if (state.objectUrl) {
            URL.revokeObjectURL(state.objectUrl);
            state.objectUrl = '';
        }
        $('#markdownImageAlt, #markdownImageWidth, #markdownImageHeight, #markdownImageSearchInput').val('');
        $('#markdownImageFile').val('');
        $('#markdownImageSelectedFileName').text('JPG, PNG, GIF oder WebP');
        refreshSelectedPreview('');
        renderImageLibrary(state.imageLibraryItems);
        renderImagePagination();
        updateInsertState();
    }

    function openImageModal() {
        resetImageModalState();
        setImagePanel('markdownImageLibraryPanel');
        $('#markdownImageModal').removeClass('hidden').addClass('flex');
        loadImageLibrary(false);
    }

    function closeImageModal() {
        $('#markdownImageModal').addClass('hidden').removeClass('flex');
    }

    function refreshSelectedPreview(src) {
        const $preview = $('#markdownImageSelectedPreview');
        if (src) {
            $preview.attr('src', src).removeClass('hidden');
            $('#markdownImageSelectedPlaceholder').addClass('hidden');
        } else {
            $preview.attr('src', '').addClass('hidden');
            $('#markdownImageSelectedPlaceholder').removeClass('hidden');
        }
    }

    function updateInsertState() {
        const canInsert = state.activePanel === 'markdownImageUploadPanel' ? !!state.selectedFile : !!state.selectedImage;
        $('#insertMarkdownImage').prop('disabled', !canInsert);
    }

    function selectLibraryImage(image) {
        state.selectedImage = image;
        state.selectedFile = null;
        $('#markdownImageFile').val('');
        $('#markdownImageSelectedFileName').text('JPG, PNG, GIF oder WebP');
        if (!$('#markdownImageAlt').val()) {
            $('#markdownImageAlt').val(image.title || 'Bild');
        }
        refreshSelectedPreview(image.preview_url || image.url);
        renderImageLibrary(state.imageLibraryItems);
        updateInsertState();
    }

    function selectUploadFile(file) {
        if (!file || !file.type || !file.type.startsWith('image/')) {
            notify('Bitte wähle eine Bilddatei aus', 'error');
            return;
        }

        state.selectedFile = file;
        state.selectedImage = null;
        if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
        state.objectUrl = URL.createObjectURL(file);
        $('#markdownImageSelectedFileName').text(file.name);
        if (!$('#markdownImageAlt').val()) {
            $('#markdownImageAlt').val(file.name.replace(/\.[^.]+$/, ''));
        }
        refreshSelectedPreview(state.objectUrl);
        renderImageLibrary(state.imageLibraryItems);
        updateInsertState();
    }

    function renderImageLibrary(items) {
        const $grid = $('#markdownImageLibrary');
        $grid.empty();

        if (!items || !items.length) {
            $('#markdownImageEmpty').removeClass('hidden');
            renderImagePagination();
            return;
        }

        $('#markdownImageEmpty').addClass('hidden');
        items.forEach(function (image) {
            const title = image.title || 'Bild';
            const selected = state.selectedImage && state.selectedImage.url === image.url;
            const $button = $('<button type="button" class="group relative overflow-hidden rounded-lg bg-white text-left shadow-sm ring-1 transition hover:-translate-y-0.5 hover:shadow-lg"></button>');
            $button.toggleClass('ring-blue-500', selected);
            $button.toggleClass('ring-slate-200 hover:ring-blue-300', !selected);
            const $img = $('<img class="h-36 w-full object-cover" loading="lazy">');
            $img.attr('src', image.preview_url || image.url);
            $img.attr('alt', title);
            const $caption = $('<span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/80 to-transparent px-3 pb-3 pt-8 text-xs font-semibold text-white opacity-0 transition group-hover:opacity-100"></span>');
            $caption.html(escapeHtml(title));
            $button.append($img).append($caption);
            $button.on('click', function () {
                selectLibraryImage(image);
            });
            $grid.append($button);
        });
        renderImagePagination();
    }

    function renderImagePagination() {
        const pagination = state.imageLibraryPagination || {};
        const page = pagination.page || state.imageLibraryPage || 1;
        const totalPages = pagination.total_pages || 1;
        $('#markdownImagePageInfo').text('Seite ' + page + ' / ' + totalPages);
        $('#markdownImagePrevPage').prop('disabled', !pagination.has_previous);
        $('#markdownImageNextPage').prop('disabled', !pagination.has_next);
    }

    function loadImageLibrary(force, page) {
        const nextPage = page || state.imageLibraryPage || 1;
        if (state.imageLibraryLoaded && !force) {
            renderImageLibrary(state.imageLibraryItems);
            return;
        }

        $('#markdownImageLibrary').empty();
        $('#markdownImageEmpty').addClass('hidden');
        $.ajax({
            url: '/cms/images/all/',
            type: 'GET',
            data: {
                page: nextPage,
                per_page: 24,
                q: ($('#markdownImageSearchInput').val() || '').trim(),
            },
            dataType: 'json',
            success: function (response) {
                state.imageLibraryItems = response.image_urls || [];
                state.imageLibraryPagination = response.pagination || null;
                state.imageLibraryPage = state.imageLibraryPagination ? state.imageLibraryPagination.page : nextPage;
                state.imageLibraryLoaded = true;
                renderImageLibrary(state.imageLibraryItems);
                if (force) {
                    notify(state.imageLibraryItems.length ? 'Alle Bilder wurden geladen' : 'Keine Bilder gefunden', state.imageLibraryItems.length ? 'success' : 'error');
                }
            },
            error: function () {
                notify('Bilder konnten nicht geladen werden', 'error');
            }
        });
    }

    function uploadSelectedImage() {
        const file = state.selectedFile;
        if (!file) {
            notify('Bitte wähle ein Bild aus', 'error');
            return;
        }

        const $button = $('#insertMarkdownImage');
        const originalText = $button.text();
        const formData = new FormData();
        formData.append('file', file);

        $button.prop('disabled', true).text('Lädt...');
        $.ajax({
            url: '/cms/upload/post',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken());
            },
            success: function (response) {
                if (!response.image || !response.image.url) {
                    notify('Bild konnte nicht verarbeitet werden', 'error');
                    return;
                }
                const altText = $('#markdownImageAlt').val() || response.image.title || file.name;
                if (insertImageMarkdown(response.image.url, altText, response.image)) {
                    state.imageLibraryLoaded = false;
                }
            },
            error: function () {
                notify('Bild konnte nicht hochgeladen werden', 'error');
            },
            complete: function () {
                $button.prop('disabled', false).text(originalText);
                updateInsertState();
            }
        });
    }

    function insertSelectedImage() {
        if (state.activePanel === 'markdownImageUploadPanel') {
            uploadSelectedImage();
            return;
        }

        if (!state.selectedImage) {
            notify('Bitte wähle ein Bild aus', 'error');
            return;
        }

        insertImageMarkdown(state.selectedImage.url, $('#markdownImageAlt').val() || state.selectedImage.title, state.selectedImage);
    }

    function previewMarkdown(title) {
        const markdown = getMarkdown().trim();
        if (!markdown) {
            notify('Bitte füge Markdown-Inhalt ein', 'error');
            return;
        }

        $.ajax({
            type: 'POST',
            url: '/cms/blog/markdown/preview/',
            data: { markdown: markdown },
            dataType: 'json',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken());
            },
            success: function (response) {
                if (response.error) {
                    notify(response.error, 'error');
                    return;
                }

                const $modalBody = $('#previewBody');
                $modalBody.empty();
                applyPreviewLayout($modalBody);
                if (title) {
                    $modalBody.append($('<h1 class="text-3xl mb-6 font-extrabold leading-tight text-gray-900 lg:text-4xl"></h1>').text(title));
                }
                $modalBody.append(response.body || '');
                if (window.openBlogPreviewModal) {
                    window.openBlogPreviewModal();
                } else {
                    $('#previewModal').removeClass('hidden').addClass('flex');
                }
                setTimeout(function () {
                    if (window.Prism) Prism.highlightAll();
                    if (typeof loadCarousels === 'function') loadCarousels();
                }, 100);
            },
            error: function (xhr) {
                const message = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Markdown-Preview konnte nicht erstellt werden';
                notify(message, 'error');
            }
        });
    }

    function appendMarkdownToFormData(formData) {
        formData.append('content_source', 'markdown');
        formData.append('markdown', getMarkdown());
    }

    function bindImageModalEvents() {
        $('#openMarkdownImageModal').on('click', openImageModal);
        $('#closeMarkdownImageModal, #cancelMarkdownImage').on('click', closeImageModal);
        $('.markdown-image-tab').on('click', function () {
            setImagePanel($(this).attr('data-target'));
        });
        $('#reloadMarkdownImages').on('click', function () {
            state.imageLibraryLoaded = false;
            loadImageLibrary(true, state.imageLibraryPage);
        });
        $('#markdownImageSearchInput').on('input', function () {
            state.imageLibraryLoaded = false;
            state.imageLibraryPage = 1;
            loadImageLibrary(false, 1);
        });
        $('#markdownImagePrevPage').on('click', function () {
            if (!state.imageLibraryPagination || !state.imageLibraryPagination.has_previous) return;
            state.imageLibraryLoaded = false;
            loadImageLibrary(false, Math.max(1, state.imageLibraryPage - 1));
        });
        $('#markdownImageNextPage').on('click', function () {
            if (!state.imageLibraryPagination || !state.imageLibraryPagination.has_next) return;
            state.imageLibraryLoaded = false;
            loadImageLibrary(false, state.imageLibraryPage + 1);
        });
        $('#insertMarkdownImage').on('click', insertSelectedImage);

        $('#markdownImageUploadDropzone').on('click', function (event) {
            if (event.target.id === 'markdownImageFile') return;
            $('#markdownImageFile')[0].click();
        });
        $('#markdownImageFile').on('click', function (event) {
            event.stopPropagation();
        });
        $('#markdownImageFile').on('change', function () {
            selectUploadFile(this.files && this.files[0]);
        });
        $('#markdownImageUploadDropzone').on('dragover', function (event) {
            event.preventDefault();
            $(this).addClass('border-blue-500 bg-blue-100');
        });
        $('#markdownImageUploadDropzone').on('dragleave drop', function () {
            $(this).removeClass('border-blue-500 bg-blue-100');
        });
        $('#markdownImageUploadDropzone').on('drop', function (event) {
            event.preventDefault();
            selectUploadFile(event.originalEvent.dataTransfer.files && event.originalEvent.dataTransfer.files[0]);
        });

        $(document).on('mouseup', function (event) {
            const $modal = $('#markdownImageModal');
            if ($modal.hasClass('hidden')) return;
            if ($(event.target).closest('.markdown-image-modal-container, #openMarkdownImageModal').length === 0) {
                closeImageModal();
            }
        });
    }

    function bindMediaModalEvents() {
        $('#openMarkdownMediaModal').on('click', openMediaModal);
        $('#closeMarkdownMediaModal, #cancelMarkdownMedia').on('click', closeMediaModal);
        $('.markdown-media-tab').on('click', function () {
            setMediaPanel($(this).attr('data-target'));
        });
        $('#reloadMarkdownVideos').on('click', function () {
            loadMarkdownVideos(true);
        });
        $('#reloadMarkdownGalleries').on('click', function () {
            loadMarkdownGalleries(true);
        });
        $('#reloadMarkdownFiles').on('click', function () {
            loadMarkdownFiles(true);
        });
        $('#markdownFileSearch').on('input', function () {
            renderMarkdownFiles(state.mediaFiles);
        });
        $('#insertMarkdownMedia').on('click', insertMarkdownMedia);

        $(document).on('mouseup', function (event) {
            const $modal = $('#markdownMediaModal');
            if ($modal.hasClass('hidden')) return;
            if ($(event.target).closest('.markdown-media-modal-container, #openMarkdownMediaModal').length === 0) {
                closeMediaModal();
            }
        });
    }

    function bindEvents() {
        $('[data-blog-editor-mode]').on('click', function () {
            setMode($(this).data('blog-editor-mode'));
        });
        $('#blogMarkdown').on('input', function () {
            if (!state.suppressMarkdownInput) {
                state.lastEdited = 'markdown';
            }
        });
        $('#blogContent').on('input change keyup paste yoolink:builder-change', function () {
            state.lastEdited = 'builder';
        });
        $('#buttonBar').on('click', 'button', function () {
            state.lastEdited = 'builder';
        });
        bindImageModalEvents();
        bindMediaModalEvents();
    }

    $(document).ready(function () {
        if (!$('#markdownEditorPanel').length) return;
        bindEvents();
        setMarkdown($('#blogInitialMarkdown').val() || '', { onlyIfEmpty: true, silent: true });
        const initialMode = new URLSearchParams(window.location.search).get('editor') === 'markdown' ? 'markdown' : 'builder';
        setMode(initialMode, { skipSync: true });
    });

    window.YooLinkBlogMarkdown = {
        appendMarkdownToFormData: appendMarkdownToFormData,
        getMarkdown: getMarkdown,
        isMarkdownMode: isMarkdownMode,
        loadImageLibrary: loadImageLibrary,
        previewMarkdown: previewMarkdown,
        setMarkdown: setMarkdown,
        setMode: setMode,
    };
})(window, jQuery);
