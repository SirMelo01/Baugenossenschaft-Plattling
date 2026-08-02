// Save Text Content
$(document).ready(function () {
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    function setSaveTextLoading($btn, isLoading) {
        if (!$btn || !$btn.length) return;
        const loadingClasses = 'inline-flex items-center justify-center gap-2 whitespace-nowrap align-middle';
        if (isLoading) {
            if (!$btn.data('original-html')) $btn.data('original-html', $btn.html());
            if (!$btn.data('original-pointer')) $btn.data('original-pointer', $btn.css('pointer-events'));
            if (!$btn.data('original-width')) $btn.data('original-width', $btn.outerWidth());
            $btn
                .css({
                    'pointer-events': 'none',
                    'min-width': Math.ceil($btn.data('original-width')) + 'px',
                })
                .addClass('cursor-not-allowed opacity-70 ' + loadingClasses);
            $btn.html(
                '<span>Speichert ...</span>' +
                '<svg class="h-4 w-4 shrink-0 animate-spin text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">' +
                '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
                '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>' +
                '</svg>'
            );
        } else {
            const original = $btn.data('original-html');
            if (original) $btn.html(original);
            $btn
                .css({
                    'pointer-events': $btn.data('original-pointer') || '',
                    'min-width': '',
                })
                .removeClass('cursor-not-allowed opacity-70 ' + loadingClasses);
        }
    }

    $('#saveTextData').click(function (event) {
        event.preventDefault();
        const $btn = $(this);
        if ($btn.hasClass('opacity-70')) return; // Already saving

        const requestData = {
            name: $(this).attr('name'),
        };
        const customText = [];

        $('.text-content').each(function () {
            const $inputs = $(this).find('input, textarea');
            const key = $(this).attr("key");
            const inputList = {};

            $inputs.each(function () {
                const inputValue = $(this).val();
                const inputType = $(this).attr('inputType');
                /**
                 * Input Types:
                 * header -> Header
                 * title -> Title
                 * description -> Description
                 * buttonText -> Button Text
                 */

                if (inputType && inputType.trim() !== '' && inputValue.trim() !== '') {
                    inputList[inputType] = inputValue;
                }
            });

            if (key) {
                customText.push({
                    "key": key,
                    "inputs": inputList
                });
            }
        });

        requestData.customText = JSON.stringify(customText);

        // Check if the element with ID 'header' exists before adding it to requestData
        if ($('#header').length > 0) {
            requestData.header = $('#header').val();
        }

        // Check if the element with ID 'title' exists before adding it to requestData
        if ($('#title').length > 0) {
            requestData.title = $('#title').val();
        }

        // Check if the element with ID 'description' exists before adding it to requestData
        if ($('#description').length > 0) {
            requestData.description = $('#description').val();
        }

        // Check if the element with ID 'buttonText' exists before adding it to requestData
        if ($('#buttonText').length > 0) {
            requestData.buttonText = $('#buttonText').val();
        }

        // Check images
        const images = [];
        $('.content-image').each(function () {
            const imgId = $(this).attr('imgId');
            const key = $(this).attr('key');
            if (imgId && key && imgId !== '-1') {
                images.push({
                    "id": imgId,
                    "key": key
                });
            }
        });
        requestData.images = JSON.stringify(images);

        const galerien = [];
        $('.galery-container').each(function () {
            const galeryId = $(this).attr('galery-id');
            const key = $(this).attr('key');
            if (galeryId && key && galeryId !== "-1") {
                galerien.push({
                    "id": galeryId,
                    "key": key
                });
            }
        });
        requestData.galerien = JSON.stringify(galerien);

        /* ---------- Add all videos ---------- */
        const videos = [];
        $('.content-video').each(function () {
            const videoId = $(this).attr('videoId');
            const key = $(this).attr('key');
            if (videoId && key && videoId !== '-1') {
                videos.push({ id: videoId, key: key });
            }
        });
        requestData.videos = JSON.stringify(videos);

        /* ---------- Add all button slots (Auswahl + alle Felder) ---------- */
        const buttons = [];
        $('.content-button').each(function () {
            const $b = $(this);
            const key = $b.attr('data-key');
            if (!key) return;
            buttons.push({
                id: $b.attr('data-button-id') || '-1',
                key: key,
                text: ($b.attr('data-text') || '').trim(),
                color: $b.attr('data-color') || '',
                icon: ($b.attr('data-icon') || '').trim(),
                url: ($b.attr('data-url') || '').trim(),
                page_link_id: $b.attr('data-page-link') || '',
                target: $b.attr('data-target') || '_self'
            });
        });
        requestData.buttons = JSON.stringify(buttons);

        setSaveTextLoading($btn, true);

        $.ajax({
            type: "POST",
            url: "/cms/seiten/save/",
            data: requestData,
            beforeSend: function (xhr) {
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (response) {
                if (response.success) {
                    sendNotif(response.success, "success");
                    // Let page-level listeners (e.g. the mainsite editor) react to a successful save.
                    $(document).trigger("textContentSaved");
                } else {
                    sendNotif(response.error, "error");
                    $(document).trigger("textContentSaveError");
                }
            },
            error: function (error) {
                console.error("Error occurred: " + error.statusText);
                sendNotif("Beim Speichern ist ein Fehler aufgetreten", "error");
                $(document).trigger("textContentSaveError");
            },
            complete: function () {
                setSaveTextLoading($btn, false);
            }
        });
    });
});
