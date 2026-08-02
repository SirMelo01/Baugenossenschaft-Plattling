$(document).ready(function () {
    var csrfToken = $('input[name="csrfmiddlewaretoken"]').val();
    $('#savePrivacyPolicy').click(function () {
        var requestData = {
            content_html: $('#privacyContentHtml').val() || "",
        };

        $.ajax({
            type: 'POST',
            url: '/cms/seiten/datenschutz/save/',
            data: requestData,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            },
            success: function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    $(document).trigger('textContentSaved');
                } else {
                    sendNotif(response.error || 'Fehler beim Speichern', 'error');
                    $(document).trigger('textContentSaveError');
                }
            },
            error: function () {
                sendNotif('Unerwarteter Fehler beim Speichern', 'error');
                $(document).trigger('textContentSaveError');
            }
        });
    });
});
