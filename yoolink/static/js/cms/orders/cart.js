var csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
$(document).ready(function () {
    /**
     * Verify Cart (Send Email to buyer)
     */
    $('#verifyCart').click(function () {
        enableSpinner($('#verifyCart'));
        var orderItemCount = $(".order-item").length;
        if (orderItemCount === 0) {
            disableSpinner($('#verifyCart'));
            sendNotif("Der Einkaufswagen ist leer. Bitte lade die Seite neu oder gehe zur Startseite.", "error")
            return;
        }

        if(!$('#isChecked').is(":checked")) {
            disableSpinner($('#verifyCart'));
            sendNotif("Bitte bestätige die Übergabe deiner Daten", "error")
            return;
        }

        // Check if Form is Valid
        var requiredFields = ['#buyerVorname', '#buyerName', '#buyerEmail'];
        var isValid = isFormValid(requiredFields);
        if (!isValid) {
            disableSpinner($('#verifyCart'));
            return;
        }
        if (!isValidEmail($('#buyerEmail').val())) {
            sendNotif("Bitte gebe eine gültige Email ein!", "error")
            disableSpinner($('#verifyCart'));
            return;
        }


        // Update Quantity of Products first (if there were any changes)
        // Initialize an empty array to store the cart items
        var cartItems = [];

        // Iterate through each element with the class "order-item"
        $(".order-item").each(function () {
            // Extract order item ID from the "order-item-id" attribute
            var orderItemId = $(this).attr("order-item-id");

            // Extract quantity from the input field value
            var quantity = $(this).find(".item-quantity").val();
            if(parseFloat(quantity) < 1) {
                sendNotif("Keine Ware darf eine Menge von unter 1 haben!", "error")
                disableSpinner($('#verifyCart'));
                return;
            }
            // Create an object with order item ID and quantity
            var cartItem = {
                "order_item_id": orderItemId,
                "quantity": quantity
            };

            // Push the object to the cartItems array
            cartItems.push(cartItem);
        });
        // Create a new FormData object
        var updateFormData = new FormData();
        // Append the cartItems array as a JSON string to the FormData object
        updateFormData.append("cart_items", JSON.stringify(cartItems));
        // Send to backend
        $.ajax({
            type: 'POST',
            url: '/cms/api/cart/update/',
            data: updateFormData,
            contentType: false,
            processData: false,
            dataType: "json",
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (data) {
                // Handle success, e.g., redirect or show a success message
                
                if (data.success) {
                    // Create Form Data and add data
                    var formData = new FormData();
                    formData.append('buyer_email', $('#buyerEmail').val())
                    formData.append('buyer_name', $('#buyerVorname').val() + " " + $('#buyerName').val())

                    // Verify Cart Post Request
                    $.ajax({
                        type: 'POST',
                        url: '/cms/api/cart/verify/',
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
                                    window.location.href = '/cart/success/'
                                }, 2000)
                                
                            } else {
                                sendNotif(data.error, "error")
                            }
                            
                        },
                        error: function (data) {
                            // Handle errors, e.g., display error message to the user
                            sendNotif(data.responseJSON.error, "error")
                            disableSpinner($('#verifyCart'));
                        }
                    });
                }
            },
            error: function (data) {
                // Handle errors, e.g., display error message to the user
                sendNotif(data.responseJSON.error, "error")
                disableSpinner($('#verifyCart'));
            }
        });


    });

    $('#updateCart').click(function() {
        // Update Quantity of Products first (if there were any changes)
        // Initialize an empty array to store the cart items
        var cartItems = [];

        var orderItemCount = $(".order-item").length;
        if (orderItemCount === 0) {
            disableSpinner($('#verifyCart'));
            sendNotif("Der Einkaufswagen ist leer. Bitte lade die Seite neu oder gehe zur Startseite.", "error")
            return;
        }

        // Iterate through each element with the class "order-item"
        $(".order-item").each(function () {
            // Extract order item ID from the "order-item-id" attribute
            var orderItemId = $(this).attr("order-item-id");

            // Extract quantity from the input field value
            var quantity = $(this).find(".item-quantity").val();
            if(parseFloat(quantity) < 1) {
                sendNotif("Keine Ware darf eine Menge von unter 1 haben!", "error")
                disableSpinner($('#verifyCart'));
                return;
            }
            // Create an object with order item ID and quantity
            var cartItem = {
                "order_item_id": orderItemId,
                "quantity": quantity
            };

            // Push the object to the cartItems array
            cartItems.push(cartItem);
        });
        // Create a new FormData object
        var updateFormData = new FormData();
        // Append the cartItems array as a JSON string to the FormData object
        updateFormData.append("cart_items", JSON.stringify(cartItems));
        // Send to backend
        $.ajax({
            type: 'POST',
            url: '/cms/api/cart/update/',
            data: updateFormData,
            contentType: false,
            processData: false,
            dataType: "json",
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (data) {
                // Handle success, e.g., redirect or show a success message
                if (data.success) {
                    // Create Form Data and add data

                    $("#tax").text(data.tax)
                    $("#total").text(data.total_tax_price)
                    $("#discount").text(data.total_discount)
                    $("#total_with_tax").text(data.total_price)

                    $.each(data.cart_items, function(index, item) {
                        // Accessing each item's properties
                        var orderItemId = item.order_item_id;
                        var quantity = item.quantity;
                        var subtotal = item.subtotal;
        
                        // Do something with the item data
                        const orderItemElement = $('.order-item[order-item-id="' + orderItemId + '"]');
                        orderItemElement.find('.order-item-subtotal').text(subtotal + "€")
                        orderItemElement.find('.product-amount').val(quantity)
                    });

                    sendNotif(data.success, "success")
                    
                } else {
                    sendNotif(data.error, "success")
                }
            },
            error: function (data) {
                // Handle errors, e.g., display error message to the user
                sendNotif(data.responseJSON.error, "error")
                disableSpinner($('#verifyCart'));
            }
        });
    })

    /**
     * Delete Item From Cart
     */
    $(".delete-item").each(function () {
        $(this).on("click", function () {
            // Hier können Sie den Code für die Löschfunktion einfügen
            // Verwenden Sie $(this), um auf das geklickte Element zuzugreifen
            console.log("Löschen geklickt für Element mit ID:", $(this).attr("id"));
            const $cartitem = $(this).closest('.order-item')
            const cartItemId = $cartitem.attr("order-item-id");

            // Delete Item
            $.ajax({
                type: 'DELETE',
                url: `/cms/api/cart/${cartItemId}/remove/`,
                data: {},
                contentType: false,
                processData: false,
                dataType: "json",
                beforeSend: function (xhr) {
                    // Add the CSRF token to the request headers
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                },
                success: function (data) {
                    // Handle success, e.g., redirect or show a success message
                    if (data.success) {
                        $cartitem.remove();
                        sendNotif(data.success, "success")
                        disableSpinner($('#verifyCart'));
                    } else {
                        sendNotif(data.error ? data.error : "Etwas ist schief gelaufen.", "error")
                        disableSpinner($('#verifyCart'));
                    }

                },
                error: function (data) {
                    // Handle errors, e.g., display error message to the user
                    sendNotif(data.responseJSON.error, "error")
                    disableSpinner($('#verifyCart'));
                }
            });
        });
    });

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