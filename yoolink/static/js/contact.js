
$(document).ready(function() {
    function updateSubmitState() {
        const consent = window.YooLinkConsent && window.YooLinkConsent.categories();
        const hasExternalConsent = Boolean(consent && consent.external);
        const captchaReady = $('[data-recaptcha-container]').attr('data-rendered') === 'true';
        $('#contactSubmit').prop('disabled', !(hasExternalConsent && captchaReady));
    }

    document.addEventListener("yoolink:consentChanged", updateSubmitState);
    document.addEventListener("yoolink:recaptcha-ready", updateSubmitState);
    document.addEventListener("yoolink:recaptcha-reset", updateSubmitState);
    updateSubmitState();

    $('#emailForm').submit(function (event) {
        event.preventDefault(); // Prevent the default form submission
        updateSubmitState();
        if ($('#contactSubmit').prop('disabled')) {
          sendNotif("Bitte stimmen Sie reCAPTCHA in den Cookie-Einstellungen zu.", "error");
          return;
        }
        // Send form data to the server using AJAX
        $.ajax({
          type: 'POST',
          url: '/cms/email/request/',
          data: $("#emailForm").serialize(),
          success: function (response) {
            // Handle successful response here
            if (response.success) {
              sendNotif("Ihre Nachricht wurde erfolgreich gesendet", "success")
            }
            $('#emailForm')[0].reset();
          },
          error: function (xhr, status, error) {
            // Handle error response here
            console.error('Form submission failed');
            sendNotif("Etwas ist schief gelaufen. Versuchen Sie es bitte später nochmal.", "error")
          }
        });
      });
})
