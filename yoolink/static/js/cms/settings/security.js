$(document).ready(function () {
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();
    const $sendButton = $('#send2faCode');
    const $verifyButton = $('#verify2faCode');
    const $disableButton = $('#disable2fa');
    const $codeInput = $('#twoFactorCode');

    function getErrorMessage(xhr, fallbackMessage) {
        const response = xhr.responseJSON;

        if (response && response.error) {
            return response.error;
        }

        return fallbackMessage || 'Die Anfrage ist fehlgeschlagen.';
    }

    function setButtonLoading($button, loadingText) {
        $button.data('original-text', $.trim($button.text()));
        $button.prop('disabled', true).addClass('opacity-70 cursor-not-allowed');
        $button.text(loadingText);
    }

    function resetButton($button) {
        const originalText = $button.data('original-text');

        if (originalText) {
            $button.text(originalText);
        }

        $button.prop('disabled', false).removeClass('opacity-70 cursor-not-allowed');
    }

    function ajaxPost(url, data, fallbackError) {
        return $.ajax({
            type: 'POST',
            url: url,
            data: $.extend({}, data, {
                csrfmiddlewaretoken: csrfToken
            })
        }).fail(function (xhr) {
            sendNotif(getErrorMessage(xhr, fallbackError), 'error');
        });
    }

    $sendButton.on('click', function () {
        const url = $sendButton.data('url') || '/cms/settings/security/send-code/';

        setButtonLoading($sendButton, 'Sendet...');

        ajaxPost(url, {}, 'Der Code konnte nicht versendet werden.')
            .done(function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    return;
                }

                sendNotif(response.error || 'Der Code konnte nicht versendet werden.', 'error');
            })
            .always(function () {
                resetButton($sendButton);
            });
    });

    $verifyButton.on('click', function () {
        const url = $verifyButton.data('url') || '/cms/settings/security/verify-code/';
        const code = $.trim($codeInput.val());

        if (!/^\d{6}$/.test(code)) {
            sendNotif('Bitte gib einen gültigen 6-stelligen Code ein.', 'error');
            return;
        }

        setButtonLoading($verifyButton, 'Prüft...');

        ajaxPost(url, { code: code }, 'Die E-Mail-2FA konnte nicht aktiviert werden.')
            .done(function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 900);
                    return;
                }

                sendNotif(response.error || 'Die E-Mail-2FA konnte nicht aktiviert werden.', 'error');
            })
            .always(function () {
                resetButton($verifyButton);
            });
    });

    $disableButton.on('click', function () {
        const url = $disableButton.data('url') || '/cms/settings/security/disable-2fa/';

        if (!window.confirm('Möchtest du die E-Mail-2FA wirklich deaktivieren?')) {
            return;
        }

        setButtonLoading($disableButton, 'Deaktiviert...');

        ajaxPost(url, {}, 'Die E-Mail-2FA konnte nicht deaktiviert werden.')
            .done(function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 900);
                    return;
                }

                sendNotif(response.error || 'Die E-Mail-2FA konnte nicht deaktiviert werden.', 'error');
            })
            .always(function () {
                resetButton($disableButton);
            });
    });
});