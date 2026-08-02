$(document).ready(function () {
  const csrftoken = $('input[name="csrfmiddlewaretoken"]').val();

  $(document).on("click", ".delete-btn", function () {
    const id = $(this).data("id");
    const card = $(this).closest(".blog-card");

    Swal.fire({
      title: "Blog wirklich löschen?",
      text: "Es wird der originale Blog und alle Varianten gelöscht! \nDiese Aktion kann nicht rückgängig gemacht werden!",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#e3342f", // rot
      cancelButtonColor: "#6c757d",  // grau
      confirmButtonText: "Ja, löschen!",
      cancelButtonText: "Abbrechen",
    }).then((result) => {
      if (result.isConfirmed) {
        sendNotif("Blog wird gelöscht...Bitte warten", "notice");

        $.ajax({
          url: `${id}/delete/`,
          type: "POST",
          data: { csrfmiddlewaretoken: csrftoken },
          dataType: "json",
          success: function (response) {
            if (response.success) {
              card.remove();
              Swal.fire({
                title: "Gelöscht!",
                text: "Der Blog wurde erfolgreich entfernt.",
                icon: "success",
                timer: 1500,
                showConfirmButton: false,
              });
            }
          },
          error: function () {
            Swal.fire({
              title: "Fehler",
              text: "Beim Löschen ist ein Fehler aufgetreten.",
              icon: "error",
            });
          },
        });
      }
    });
  });
});
