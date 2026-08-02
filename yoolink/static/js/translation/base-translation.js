// static/js/base-translation.js

$(document).ready(function () {
  function setupLanguageDropdown(buttonId, menuId, flagId, textId) {
    // Dropdown anzeigen/verstecken
    $(`#${buttonId}`).on("click", function () {
      $(`#${menuId}`).toggleClass("hidden");
    });

    // Sprache ändern (NEUE LOGIK mit URL-Prefix + django_language-Cookie)
    $(`#${menuId} .language-option`).on("click", function () {
      var selectedLang = $(this).attr("data-lang");
      var selectedFlag = $(this).attr("data-flag");
      var selectedText = $(this).attr("data-text");

      // Flagge und Text im Button aktualisieren (direktes Feedback)
      $(`#${flagId}`).attr("class", `fi fi-${selectedFlag} mr-2`);
      $(`#${textId}`).text(selectedText);

      // Django-Sprachcookie setzen (30 Tage)
      document.cookie = `django_language=${selectedLang}; path=/; max-age=${60 * 60 * 24 * 30}`;

      // Aktuellen Pfad holen
      var currentPath = window.location.pathname;

      var strippedPath = currentPath.replace(/^\/en(\/|$)/, "/");

      var targetPath;
      if (selectedLang === "de") {
        // Keine Sprach-Prefix – Root ist DE
        targetPath = strippedPath || "/";
      } else {
        targetPath = `/` + selectedLang + strippedPath;
      }

      // Auf neue Sprach-URL weiterleiten
      window.location.href = targetPath;
    });

    // Dropdown schließen, wenn außerhalb geklickt wird
    $(document).on("click", function (event) {
      if (!$(event.target).closest(`#${buttonId}, #${menuId}`).length) {
        $(`#${menuId}`).addClass("hidden");
      }
    });
  }

  // Öffentliche Seite: Desktop
  setupLanguageDropdown(
    "languageDropdownButtonDesktop",
    "languageDropdownMenuDesktop",
    "selectedLangFlagDesktop",
    "selectedLangTextDesktop"
  );

  // Öffentliche Seite: Mobile
  setupLanguageDropdown(
    "languageDropdownButtonMobile",
    "languageDropdownMenuMobile",
    "selectedLangFlagMobile",
    "selectedLangTextMobile"
  );
});
