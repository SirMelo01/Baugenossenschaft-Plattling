const $productGalery = $("#productGalery");

const galleryConfig = document.getElementById("productFormConfig");
const galleriesUrl = galleryConfig?.dataset.galleriesUrl;
const galleryImagesUrl = galleryConfig?.dataset.galleryImagesUrl;

$(document).ready(function () {
  const $galeryModal = $("#galeryModal");
  const $galeryModalContainer = $galeryModal.find(".modal-container");

  function openGaleryModal() {
    $galeryModal.removeClass("hidden").addClass("flex");
  }

  function closeGaleryModal() {
    $galeryModal.addClass("hidden").removeClass("flex");
  }

  $("#reloadGalerien").on("click", function () {
    loadGalerien(true);
  });

  $("#closeGaleryModal").on("click", function () {
    closeGaleryModal();
  });

  $(".edit-galery").on("click", function () {
    openGaleryModal();
  });

  $(document).mouseup(function (e) {
    if (
      !$galeryModalContainer.is(e.target) &&
      $galeryModalContainer.has(e.target).length === 0
    ) {
      closeGaleryModal();
    }
  });
});

function loadGalerien(sendLoadMsg) {
  if (!galleriesUrl) {
    sendNotif("Die Galerie URL fehlt. Bitte lade die Seite neu.", "error");
    return;
  }

  $.ajax({
    url: galleriesUrl,
    type: "GET",
    dataType: "json",
    success: function (response) {
      if (response.galerien && response.galerien.length !== 0) {
        $("#possibleGalerien").empty();

        response.galerien.forEach(function (gallery) {
          const $galleryItem = addTitleAndDescription(gallery.title, gallery.description, gallery.id);

          $galleryItem.on("click", function () {
            const galeryId = $(this).attr("galeryId");
            sendNotif("Diese Galerie wird geladen...", "notice");
            selectGalery(galeryId);
          });

          $("#possibleGalerien").append($galleryItem);
        });

        if (sendLoadMsg) {
          sendNotif("Alle Galerien wurden geladen.", "success");
        }
      } else if (sendLoadMsg) {
        sendNotif("Es wurden keine Galerien gefunden.", "error");
      }
    },
    error: function () {
      if (sendLoadMsg) {
        sendNotif("Es kam zu einem unerwarteten Fehler. Versuche es später nochmal.", "error");
      }
    }
  });
}

function addTitleAndDescription(title, description, id) {
  const $div = $("<div>").addClass(
    "border border-gray-200 shadow-xl rounded-2xl h-full w-full p-4 hover:cursor-pointer hover:shadow-blue-300"
  );
  $div.attr("galeryId", id);

  const $title = $("<h1>").addClass("text-xl font-semibold mb-2").text(title);
  const $description = $("<p>").addClass("max-h-[8rem] overflow-auto").text(description);

  $div.append($title);
  $div.append($description);

  return $div;
}

function selectGalery(id) {
  if (!galleryImagesUrl) {
    sendNotif("Die Galerie Bild URL fehlt. Bitte lade die Seite neu.", "error");
    return;
  }

  $.ajax({
    url: galleryImagesUrl,
    type: "GET",
    data: { galeryId: id },
    dataType: "json",
    success: function (data) {
      if (data.images.length > 0) {
        const existingSlides = $productGalery.find(".slick-slide:not(.slick-cloned)");

        for (let i = existingSlides.length - 1; i >= 0; i--) {
          $productGalery.slick("slickRemove", i);
        }

        data.images.forEach(function (image) {
          const img = `<img src="${image.upload_url}" class="w-full rounded-xl" style="height: 16rem;">`;
          $productGalery.slick("slickAdd", `<div>${img}</div>`);
        });

        $productGalery.attr("galery-id", id);
        $("#galeryModal").addClass("hidden").removeClass("flex");
        sendNotif("Galerie wurde erfolgreich geladen.", "success");
      } else {
        sendNotif("Diese Galerie ist leer. Bitte befülle sie erst!", "error");
      }
    },
    error: function (xhr, status, error) {
      console.error("Error:", error);
      sendNotif("Etwas hat nicht funktioniert. Versuche es später erneut.", "error");
    }
  });
}
