const filesConfig = document.getElementById("productFormConfig");
const anyFilesUrl = filesConfig?.dataset.anyfilesUrl;

const selectedProductFiles = new Map();

function getSelectedProductFileIds() {
  return Array.from(selectedProductFiles.keys());
}

window.getSelectedProductFileIds = getSelectedProductFileIds;

$(document).ready(function () {
  const $anyFileModal = $("#anyFileModal");
  const $modalContainer = $anyFileModal.find(".modal-container");
  const $possibleAnyFiles = $("#possibleAnyFiles");
  const $selectedProductFiles = $("#selectedProductFiles");
  const $searchInput = $("#anyFileSearch");
  const $selectedAnyFilesCount = $("#selectedAnyFilesCount");
  const $selectedAnyFilesSummary = $("#selectedAnyFilesSummary");
  const $anyFileEmptyState = $("#anyFileEmptyState");

  function openAnyFileModal() {
    $anyFileModal.removeClass("hidden").addClass("flex");
  }

  function closeAnyFileModal() {
    $anyFileModal.addClass("hidden").removeClass("flex");
  }

  initSelectedFilesFromDom();
  renderSelectedFiles();

  $(".edit-files").on("click", function () {
    openAnyFileModal();
    loadAnyFiles();
  });

  $("#closeAnyFileModal").on("click", function () {
    closeAnyFileModal();
  });

  $("#confirmAnyFiles").on("click", function () {
    closeAnyFileModal();
    renderSelectedFiles();
  });

  $("#reloadAnyFiles").on("click", function () {
    loadAnyFiles(true);
  });

  $(document).mouseup(function (e) {
    if (
      !$modalContainer.is(e.target) &&
      $modalContainer.has(e.target).length === 0
    ) {
      closeAnyFileModal();
    }
  });

  $searchInput.on("input", function () {
    filterAnyFiles($(this).val().trim().toLowerCase());
  });

  $selectedProductFiles.on("click", ".remove-product-file", function () {
    const fileId = String($(this).closest(".selected-product-file").data("file-id"));
    selectedProductFiles.delete(fileId);
    renderSelectedFiles();
  });

  function initSelectedFilesFromDom() {
    $(".selected-product-file").each(function () {
      const $item = $(this);
      const fileId = String($item.data("file-id"));

      selectedProductFiles.set(fileId, {
        id: fileId,
        url: $item.data("file-url") || "",
        title: $item.data("file-title") || "Datei",
        ext: $item.data("file-ext") || "",
      });
    });
  }

  function loadAnyFiles(showMessage = false) {
    if (!anyFilesUrl) {
      sendNotif("Die Datei URL fehlt. Bitte lade die Seite neu.", "error");
      return;
    }

    $.ajax({
      url: anyFilesUrl,
      type: "GET",
      dataType: "json",
      success: function (response) {
        renderAnyFiles(response.files || []);

        if (showMessage) {
          sendNotif("Dateien wurden geladen.", "success");
        }
      },
      error: function (xhr) {
        console.error(xhr);
        sendNotif("Dateien konnten nicht geladen werden.", "error");
      }
    });
  }

  function renderAnyFiles(files) {
    $possibleAnyFiles.empty();
    $anyFileEmptyState.toggleClass("hidden", files.length !== 0);

    files.forEach(function (file) {
      const fileId = String(file.id);
      const fileUrl = escapeHtml(file.url || "#");
      const isSelected = selectedProductFiles.has(fileId);
      const cardClass = isSelected
        ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200"
        : "border-slate-200 bg-white hover:border-blue-200";
      const iconClass = isSelected
        ? "bg-blue-600 text-white"
        : "bg-slate-100 text-slate-500";
      const buttonClass = isSelected
        ? "bg-red-50 text-red-700 hover:bg-red-100"
        : "bg-blue-50 text-blue-700 hover:bg-blue-100";

      const card = $(`
        <div class="anyfile-option cursor-pointer rounded-lg border p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${cardClass}" data-file-id="${fileId}">
          <div class="mb-4 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-slate-950">${escapeHtml(file.title || "Datei")}</p>
              <p class="mt-1 truncate text-xs text-slate-500">${escapeHtml(file.ext || "Datei")}</p>
            </div>
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${iconClass}">
              <i class="bi ${isSelected ? "bi-check2" : "bi-file-earmark"}"></i>
            </span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <a href="${fileUrl}" target="_blank" class="truncate text-sm font-medium text-blue-600 hover:underline">Datei öffnen</a>
            <button type="button" class="toggle-anyfile rounded-md px-3 py-1.5 text-xs font-semibold transition ${buttonClass}">
              ${isSelected ? "Entfernen" : "Hinzufügen"}
            </button>
          </div>
        </div>
      `);

      card.on("click", function (event) {
        if ($(event.target).closest("a, button").length) {
          return;
        }
        toggleFile(file);
      });

      card.find(".toggle-anyfile").on("click", function (event) {
        event.stopPropagation();
        toggleFile(file);
      });

      $possibleAnyFiles.append(card);
    });

    filterAnyFiles($searchInput.val().trim().toLowerCase());
  }

  function toggleFile(file) {
    const fileId = String(file.id);

    if (selectedProductFiles.has(fileId)) {
      selectedProductFiles.delete(fileId);
    } else {
      selectedProductFiles.set(fileId, {
        id: fileId,
        url: file.url || "",
        title: file.title || "Datei",
        ext: file.ext || "",
      });
    }

    renderSelectedFiles();
    loadAnyFiles();
  }

  function renderSelectedFiles() {
    $selectedProductFiles.empty();
    renderModalSelectionSummary();

    if (!selectedProductFiles.size) {
      $selectedProductFiles.append(
        '<div class="rounded-xl border border-dashed border-gray-300 p-4 text-sm text-gray-500">Noch keine Dateien zugeordnet</div>'
      );
      return;
    }

    selectedProductFiles.forEach(function (file) {
      const item = $(`
        <div
          class="selected-product-file flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-4 py-3"
          data-file-id="${file.id}"
          data-file-url="${escapeHtml(file.url)}"
          data-file-title="${escapeHtml(file.title)}"
          data-file-ext="${escapeHtml(file.ext)}"
        >
          <div class="min-w-0">
            <p class="truncate font-medium text-gray-900">${escapeHtml(file.title)}</p>
            <p class="text-sm text-gray-500">${escapeHtml(file.ext)}</p>
          </div>
          <button
            type="button"
            class="remove-product-file rounded-lg px-3 py-1 text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            Entfernen
          </button>
        </div>
      `);

      $selectedProductFiles.append(item);
    });
  }

  function renderModalSelectionSummary() {
    const count = selectedProductFiles.size;

    $selectedAnyFilesCount.text(count === 1 ? "1 Datei ausgewählt" : `${count} Dateien ausgewählt`);
    $selectedAnyFilesSummary.empty();

    if (!count) {
      $selectedAnyFilesSummary.append('<p class="text-center text-slate-400">Noch keine Dateien ausgewählt</p>');
      return;
    }

    selectedProductFiles.forEach(function (file) {
      $selectedAnyFilesSummary.append(`
        <div class="rounded-md bg-white px-3 py-2 shadow-sm">
          <p class="truncate font-medium text-slate-800">${escapeHtml(file.title)}</p>
          <p class="truncate text-xs text-slate-500">${escapeHtml(file.ext)}</p>
        </div>
      `);
    });
  }

  function filterAnyFiles(query) {
    let visibleCount = 0;

    $("#possibleAnyFiles .anyfile-option").each(function () {
      const isVisible = $(this).text().toLowerCase().includes(query);
      $(this).toggle(isVisible);

      if (isVisible) {
        visibleCount += 1;
      }
    });

    $anyFileEmptyState.toggleClass("hidden", visibleCount !== 0);
  }

  function escapeHtml(value) {
    return $("<div>").text(value || "").html();
  }
});
