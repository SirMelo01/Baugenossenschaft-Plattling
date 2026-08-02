$(document).ready(function () {
    const $csrf = $('input[name="csrfmiddlewaretoken"]');
    const csrfToken = $csrf.val();
    const $updateButton = $('#updateSettings');

    function getErrorMessage(xhr, fallbackMessage) {
        const response = xhr.responseJSON;

        if (response && response.error) {
            return response.error;
        }

        return fallbackMessage || 'Es kam zu einem Fehler. Versuche es erneut.';
    }

    function setButtonLoading($button, loadingText) {
        $button.data('original-text', $button.text());
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

    function getPayload() {
        return {
            company_name: $.trim($('#company_name').val()),
            owner_name: $.trim($('#owner_name').val()),
            contact_email: $.trim($('#contact_email').val()),
            tel_number: $.trim($('#tel_number').val()),
            fax_number: $.trim($('#fax_number').val()),
            mobile_number: $.trim($('#mobile_number').val()),
            website: $.trim($('#website').val()),
            address: $.trim($('#address').val()),
            social_instagram: $.trim($('#social_instagram').val()),
            social_x: $.trim($('#social_x').val()),
            social_facebook: $.trim($('#social_facebook').val()),
            social_linkedin: $.trim($('#social_linkedin').val()),
            price_range: $.trim($('#price_range').val()),
            area_served: $.trim($('#area_served').val()),
            business_description: $.trim($('#business_description').val()),
            site_meta_description: $.trim($('#site_meta_description').val()),
            site_meta_author: $.trim($('#site_meta_author').val()),
            address_region: $.trim($('#address_region').val()),
            address_country: $.trim($('#address_country').val()),
            geo_latitude: $.trim($('#geo_latitude').val()),
            geo_longitude: $.trim($('#geo_longitude').val()),
            global_font: $('#global_font').val(),
            csrfmiddlewaretoken: csrfToken
        };
    }

    $updateButton.on('click', function () {
        const url = $updateButton.data('url') || 'update/';

        setButtonLoading($updateButton, 'Speichert...');

        $.ajax({
            type: 'POST',
            url: url,
            data: getPayload(),
            success: function (response) {
                if (response.success) {
                    sendNotif(response.success, 'success');
                    return;
                }

                sendNotif(response.error || 'Es kam zu einem Fehler. Versuche es erneut.', 'error');
            },
            error: function (xhr) {
                sendNotif(getErrorMessage(xhr), 'error');
            },
            complete: function () {
                resetButton($updateButton);
            }
        });
    });
});
