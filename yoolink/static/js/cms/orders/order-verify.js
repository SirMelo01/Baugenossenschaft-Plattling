var csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
$(document).ready(function () {
    /**
     * Verify Cart (Send Email to buyer)
     */
    $('#verifyOrder').click(function () {
        enableSpinner($('#verifyOrder'));
        var orderItemCount = $(".order-item").length;
        if (orderItemCount === 0) {
            disableSpinner($('#verifyOrder'));
            sendNotif("Der Einkaufswagen ist leer. Bitte lade die Seite neu oder gehe zur Startseite.", "error")
            return;
        }
        // Check if Form is Valid
        var requiredFields = ['#buyerVorname', '#buyerName', '#address', '#country', '#city'];
        var isValid = isFormValid(requiredFields);
        if (!isValid) {
            disableSpinner($('#verifyOrder'));
            return;
        }

        const $shipping = $(".active")
        if($shipping.length < 1 || $shipping.length > 1) {
            disableSpinner($('#verifyOrder'));
            sendNotif("Es wurde keine Liefermethode ausgewählt", "error")
            return;
        }

        const $payment = $(".payment-active")
        if($payment.length < 1 || $payment.length > 1) {
            disableSpinner($('#verifyOrder'));
            sendNotif("Es wurde keine Bezahlmethode ausgewählt", "error")
            return;
        }

        // Create a new FormData object
        var formData = new FormData();
        formData.append('buyer_name', $('#buyerName').val());
        formData.append('buyer_prename', $('#buyerVorname').val());
        formData.append('address', $('#address').val());
        formData.append('city', $('#city').val());
        formData.append('postal_code', $('#postal_code').val());
        formData.append('country', $('#country').val());
        formData.append('token', $('#orderToken').val());
        formData.append('order_id', $('#orderId').val());
        formData.append('shipping', $shipping.attr('shipping'))


        if ($shipping.attr('shipping') == 'SHIPPING') {
            if($payment.attr('payment') == 'CASH') {
                disableSpinner($('#verifyOrder'));
                sendNotif("Bei Lieferung kann nicht in Bar bezahlt werden", "error")
                return;
            }
        }
        formData.append('payment', $payment.attr('payment'))


        // Verify Cart Post Request
        $.ajax({
            type: 'POST',
            url: '/cms/api/order/verify/',
            data: formData,
            contentType: false,
            processData: false,
            dataType: "json",
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (data) {
                // Handle success, e.g., redirect or show a success message
                if(data.success) {
                    sendNotif(data.success, "success")
                    // Redirect to success page
                    setTimeout(() => {
                        window.location.href = '/order/success/'
                    }, 2000)
                } else {
                    sendNotif(data.error, "error")
                }
                
            },
            error: function (data) {
                // Handle errors, e.g., display error message to the user
                sendNotif(data.responseJSON.error, "error")
                disableSpinner($('#verifyOrder'));
            }
        });


    });


    $('#shipping').click(function () {
        $(this).addClass('border-2 border-orange-500 active')
        $('#pickup').removeClass('border-2 border-blue-500 active')
        $('#cash').removeClass('border-2 border-blue-500 payment-active')
        $('#transfer').addClass('border-2 border-orange-500 payment-active')
        showShippingPrice()
    })

    $('#pickup').click(function () {
        $('#shipping').removeClass('border-2 border-orange-500 active')
        $(this).addClass('border-2 border-blue-500 active')
        showPickUpPrice()
    })

    $('#transfer').click(function () {
        $('#cash').removeClass('border-2 border-blue-500 payment-active')
        $(this).addClass('border-2 border-orange-500 payment-active')
    })

    $('#cash').click(function () {
        if($(".active").attr('shipping') === 'SHIPPING') {
            sendNotif("Bei Lieferung kann nicht in Bar bezahlt werden", "error")
            return;
        }
        $('#transfer').removeClass('border-2 border-orange-500 payment-active')
        $(this).addClass('border-2 border-blue-500 payment-active')
    })

    function showPickUpPrice() {
        $('.shipping-price').removeClass('flex').addClass('hidden')
        $('.pickup-price').addClass('flex').removeClass('hidden')
    }

    function showShippingPrice() {
        $('.pickup-price').removeClass('flex').addClass('hidden')
        $('.shipping-price').addClass('flex').removeClass('hidden')
    }




});

/**
 * Valid the Form
 */
function isFormValid(requiredFields) {
    var isValid = true;

    for (var i = 0; i < requiredFields.length; i++) {
        var field = $(requiredFields[i]);
        if (field.val().trim() === '') {
            sendNotif("Bitte fülle alle Pflichtfelder aus!", "error");
            isValid = false;
            break;
        }
    }
    return isValid;
}

/**
 * Check for Valid Email
 * @param {String} email 
 * @returns 
 */
function isValidEmail(email) {
    // Regular expression for validating an email address
    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
* Disable Button Spinner
* @param {*} $elem 
*/
function disableSpinner($elem) {
    $elem.prop("disabled", false);
    $elem.find('svg').addClass('hidden');
    $elem.find('.bi').removeClass('hidden');
    $elem.prop('disabled', false);
}

/**
 * Enable Button Spinner
 * @param {*} $elem 
 */
function enableSpinner($elem) {
    $elem.prop("disabled", true);
    $elem.find('svg').removeClass('hidden');
    $elem.find('.bi').addClass('hidden');
    $elem.prop('disabled', true);
}