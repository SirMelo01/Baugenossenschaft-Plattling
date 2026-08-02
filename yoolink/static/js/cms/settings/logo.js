$(document).ready(function () {
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    const $uploadLogoButton = $('#uploadLogo');
    const $uploadFaviconButton = $('#uploadFavicon');
    const $deleteLogoButton = $('#deleteLogo');
    const $deleteFaviconButton = $('#deleteFavicon');

    function getErrorMessage(xhr, fallbackMessage) {
        const response = xhr.responseJSON;

        if (response && response.error) {
            return response.error;
        }

        return fallbackMessage || 'Es ist ein Fehler aufgetreten.';
    }

    function setButtonLoading($button, loadingText) {
        $button.data('original-html', $button.html());
        $button.prop('disabled', true).addClass('opacity-70 cursor-not-allowed');
        $button.text(loadingText);
    }

    function resetButton($button) {
        const originalHtml = $button.data('original-html');

        if (originalHtml) {
            $button.html(originalHtml);
        }

        $button.prop('disabled', false).removeClass('opacity-70 cursor-not-allowed');
    }

    function uploadFile(type, $button) {
        const input = document.getElementById(type);
        const file = input?.files?.[0];
        const url = $button.data('url') || '/cms/settings/logo/update/';

        if (!file) {
            sendNotif('Keine Datei ausgewählt.', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append(type, file);
        formData.append('csrfmiddlewaretoken', csrfToken);

        setButtonLoading($button, 'Lädt hoch...');

        $.ajax({
            url: url,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 500);
                    return;
                }

                sendNotif(response.error || 'Fehler beim Hochladen.', 'error');
                resetButton($button);
            },
            error: function (xhr) {
                sendNotif(getErrorMessage(xhr, 'Fehler beim Hochladen.'), 'error');
                resetButton($button);
            }
        });
    }

    function deleteFile(type, $button) {
        const url = $button.data('url') || '/cms/settings/logo/delete/';

        setButtonLoading($button, 'Löscht...');

        $.ajax({
            url: url,
            method: 'POST',
            data: {
                type: type,
                csrfmiddlewaretoken: csrfToken
            },
            success: function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 500);
                    return;
                }

                sendNotif(response.error || 'Fehler beim Löschen.', 'error');
                resetButton($button);
            },
            error: function (xhr) {
                sendNotif(getErrorMessage(xhr, 'Fehler beim Löschen.'), 'error');
                resetButton($button);
            }
        });
    }

    $uploadLogoButton.on('click', function () {
        uploadFile('logo', $uploadLogoButton);
    });

    $uploadFaviconButton.on('click', function () {
        uploadFile('favicon', $uploadFaviconButton);
    });

    $deleteLogoButton.on('click', function () {
        deleteFile('logo', $deleteLogoButton);
    });

    $deleteFaviconButton.on('click', function () {
        deleteFile('favicon', $deleteFaviconButton);
    });
});