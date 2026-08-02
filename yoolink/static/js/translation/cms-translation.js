// static/js/cms-translation.js

$(document).ready(function () {

  function setupLanguageDropdown(buttonId, menuId, flagId, textId) {
    // Dropdown anzeigen/verstecken
    $(`#${buttonId}`).on("click", function () {
      $(`#${menuId}`).toggleClass("hidden");
    });

    // Sprache ändern – jetzt wieder über /cms/set-language/<lang>/
    $(`#${menuId} .language-option`).on("click", function () {
      var selectedLang = $(this).attr("data-lang");
      var selectedFlag = $(this).attr("data-flag");
      var selectedText = $(this).attr("data-text");

      // UI direkt aktualisieren
      $(`#${flagId}`).attr("class", `fi fi-${selectedFlag} sm:mr-2`);
      $(`#${textId}`).text(selectedText);

      $.ajax({
        url: `/cms/set-language/${selectedLang}/`,
        type: "GET",
        success: function (response) {
          if (response && response.language) {
            // Seite neu laden, damit request.LANGUAGE_CODE aktualisiert ist
            window.location.reload();
          }
        },
        error: function (xhr, status, error) {
          console.error("Fehler beim Ändern der Sprache im CMS:", error);
        }
      });
    });

    // Dropdown schließen, wenn außerhalb geklickt wird
    $(document).on("click", function (event) {
      if (!$(event.target).closest(`#${buttonId}, #${menuId}`).length) {
        $(`#${menuId}`).addClass("hidden");
      }
    });
  }

  // Desktop
  setupLanguageDropdown(
    "languageDropdownButtonDesktop",
    "languageDropdownMenuDesktop",
    "selectedLangFlagDesktop",
    "selectedLangTextDesktop"
  );

  // Optional Mobile für später
  setupLanguageDropdown(
    "languageDropdownButtonMobile",
    "languageDropdownMenuMobile",
    "selectedLangFlagMobile",
    "selectedLangTextMobile"
  );
});
