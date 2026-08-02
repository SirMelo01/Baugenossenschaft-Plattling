var imageData = null;
var newImage = false;
let descriptionEditor = null;

const formConfig = document.getElementById("productFormConfig");
const productsUrl = formConfig?.dataset.productsUrl;
const createUrl = formConfig?.dataset.createUrl;
const updateUrl = formConfig?.dataset.updateUrl;
const deleteUrl = formConfig?.dataset.deleteUrl;
const descriptionImageUrl = formConfig?.dataset.descriptionImageUrl;

function normalizeBaseUrl(url) {
  if (!url) {
    return "";
  }
  return url.endsWith("/") ? url : `${url}/`;
}

function buildProductDetailUrl(productId, slug) {
  const baseUrl = normalizeBaseUrl(productsUrl);
  return `${baseUrl}${productId}/${slug}/`;
}

function getCsrfToken() {
  return $('input[name="csrfmiddlewaretoken"]').val();
}

function getAjaxErrorMessage(xhr, fallbackMessage) {
  const response = xhr.responseJSON;

  if (response) {
    if (response.error) {
      return response.error;
    }

    if (response.detail) {
      return response.detail;
    }
  }

  if (xhr.responseText) {
    try {
      const parsedResponse = JSON.parse(xhr.responseText);
      if (parsedResponse.error) {
        return parsedResponse.error;
      }
    } catch (error) {
      // Ignore non-JSON responses and use the fallback below.
    }
  }

  return fallbackMessage || "Etwas ist schief gelaufen. Versuche es erneut.";
}

function setFormDataValue(formData, key, value) {
  if (typeof formData.set === "function") {
    formData.set(key, value);
  } else {
    formData.append(key, value);
  }
}

function isFormValid(requiredFields) {
  let isValid = true;

  for (let i = 0; i < requiredFields.length; i++) {
    const field = $(requiredFields[i]);
    if (field.val().trim() === "") {
      sendNotif("Bitte fülle alle Pflichtfelder aus!", "error");
      isValid = false;
      break;
    }
  }

  return isValid;
}

function disableSpinner($elem) {
  $elem.prop("disabled", false);
  $elem.find("svg").addClass("hidden");
  $elem.find(".bi").removeClass("hidden");
}

function enableSpinner($elem) {
  $elem.prop("disabled", true);
  $elem.find("svg").removeClass("hidden");
  $elem.find(".bi").addClass("hidden");
}

function createSpecificationRow(key = "", value = "") {
  return $(`
    <div class="specification-row grid grid-cols-1 gap-3 rounded-2xl border border-gray-200 bg-gray-50 p-4 md:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
      <div>
        <label class="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-500">Bezeichnung</label>
        <input
          type="text"
          class="specification-key w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-800 focus:border-blue-500 focus:outline-none"
          placeholder="z.B. PS"
        />
      </div>

      <div>
        <label class="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-500">Wert</label>
        <input
          type="text"
          class="specification-value w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-800 focus:border-blue-500 focus:outline-none"
          placeholder="z.B. 150"
        />
      </div>

      <button
        type="button"
        class="remove-specification-row rounded-xl bg-red-50 px-4 py-3 font-semibold text-red-600 transition hover:bg-red-100 md:col-span-2 lg:col-span-1 lg:min-w-[120px]"
      >
        Entfernen
      </button>
    </div>
  `)
    .find(".specification-key").val(key).end()
    .find(".specification-value").val(value).end();
}

function toggleSpecificationPlaceholder() {
  const hasRows = $("#productSpecificationsList .specification-row").length > 0;
  $("#noSpecificationsPlaceholder").toggleClass("hidden", hasRows);
}

function collectProductSpecifications() {
  const specifications = [];
  const seenKeys = new Set();
  let hasIncompleteRow = false;
  let duplicateKey = "";

  $("#productSpecificationsList .specification-row").each(function (index) {
    const key = ($(this).find(".specification-key").val() || "").trim();
    const value = ($(this).find(".specification-value").val() || "").trim();

    if (!key && !value) {
      return;
    }

    if (!key || !value) {
      hasIncompleteRow = true;
      return false;
    }

    const normalizedKey = key.toLowerCase();
    if (seenKeys.has(normalizedKey)) {
      duplicateKey = key;
      return false;
    }

    seenKeys.add(normalizedKey);

    specifications.push({
      key: key,
      value: value,
      sort_order: index
    });
  });

  return {
    specifications,
    hasIncompleteRow,
    duplicateKey
  };
}

function appendSpecificationsToFormData(formData) {
  const result = collectProductSpecifications();

  if (result.hasIncompleteRow) {
    sendNotif("Bitte fülle bei jeder Spezifikation sowohl Bezeichnung als auch Wert aus.", "error");
    return false;
  }

  if (result.duplicateKey) {
    sendNotif(`Die Spezifikation "${result.duplicateKey}" ist doppelt vorhanden.`, "error");
    return false;
  }

  formData.append("specifications", JSON.stringify(result.specifications));
  return true;
}

function appendTaxonomyToFormData(formData) {
  const taxonomy = typeof window.getProductTaxonomy === "function"
    ? window.getProductTaxonomy()
    : { group: "", brand: "", categories: [] };

  setFormDataValue(formData, "hersteller", taxonomy.brand);
  setFormDataValue(formData, "group", taxonomy.group);
  setFormDataValue(formData, "selected_categories", JSON.stringify(taxonomy.categories));
}

function quillImageHandler() {
  if (!descriptionImageUrl) {
    sendNotif("Der Bild Upload ist nicht konfiguriert. Bitte lade die Seite neu.", "error");
    return;
  }

  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/png,image/jpeg,image/jpg,image/webp,image/gif";

  input.onchange = function () {
    const file = input.files && input.files[0];
    if (!file) {
      return;
    }

    sendNotif("Bild wird hochgeladen...", "info");

    const uploadData = new FormData();
    uploadData.append("image", file);

    $.ajax({
      url: descriptionImageUrl,
      type: "POST",
      data: uploadData,
      contentType: false,
      processData: false,
      dataType: "json",
      beforeSend: function (xhr) {
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
      },
      success: function (response) {
        if (!response.url) {
          sendNotif(response.error || "Bild konnte nicht hochgeladen werden.", "error");
          return;
        }

        const range = descriptionEditor.getSelection(true) || { index: descriptionEditor.getLength() };
        descriptionEditor.insertEmbed(range.index, "image", response.url, "user");
        descriptionEditor.setSelection(range.index + 1, 0, "user");
        sendNotif("Bild wurde eingefügt.", "success");
      },
      error: function (xhr) {
        sendNotif(getAjaxErrorMessage(xhr, "Bild konnte nicht hochgeladen werden."), "error");
      }
    });
  };

  input.click();
}

function initDescriptionEditor() {
  const container = document.getElementById("descriptionEditor");

  if (!container || typeof Quill === "undefined") {
    return;
  }

  descriptionEditor = new Quill(container, {
    theme: "snow",
    placeholder: "Beschreibe das Produkt – Formatierungen, Listen, Links und Bilder sind möglich",
    modules: {
      toolbar: {
        container: [
          [{ header: [2, 3, false] }],
          ["bold", "italic", "underline", "strike"],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ align: [] }],
          ["link", "image", "blockquote"],
          ["clean"]
        ],
        handlers: {
          image: quillImageHandler
        }
      }
    }
  });

  const initialValue = ($("#description").val() || "").trim();

  if (initialValue) {
    if (/<[a-z][^>]*>/i.test(initialValue)) {
      descriptionEditor.clipboard.dangerouslyPasteHTML(initialValue);
    } else {
      descriptionEditor.setText(initialValue);
    }
    descriptionEditor.history.clear();
  }
}

function initImageSizeControls() {
  const wrap = document.getElementById("descriptionEditorWrap");
  const editorRoot = document.getElementById("descriptionEditor");

  if (!wrap || !editorRoot || !descriptionEditor) {
    return;
  }

  wrap.style.position = "relative";

  const SIZE_PRESETS = [
    { label: "S", width: "240", title: "Klein (240px)" },
    { label: "M", width: "480", title: "Mittel (480px)" },
    { label: "L", width: "720", title: "Groß (720px)" },
    { label: "Voll", width: null, title: "Originalgröße" }
  ];

  const bubble = document.createElement("div");
  bubble.id = "imageSizeBubble";
  bubble.className = "absolute z-40 hidden items-center gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-lg";

  let activeImage = null;

  function hideBubble() {
    bubble.classList.add("hidden");
    bubble.classList.remove("flex");
    if (activeImage) {
      activeImage.style.outline = "";
      activeImage = null;
    }
  }

  function applyWidth(width) {
    if (!activeImage) {
      return;
    }

    const blot = Quill.find(activeImage);
    if (blot) {
      const index = descriptionEditor.getIndex(blot);
      descriptionEditor.formatText(index, 1, { width: width, height: null }, "user");
    } else if (width) {
      activeImage.setAttribute("width", width);
      activeImage.removeAttribute("height");
    } else {
      activeImage.removeAttribute("width");
      activeImage.removeAttribute("height");
    }

    hideBubble();
  }

  function removeImage() {
    if (!activeImage) {
      return;
    }

    const blot = Quill.find(activeImage);
    if (blot) {
      const index = descriptionEditor.getIndex(blot);
      descriptionEditor.deleteText(index, 1, "user");
    } else {
      activeImage.remove();
    }

    hideBubble();
  }

  const sizeLabel = document.createElement("span");
  sizeLabel.className = "px-2 text-xs font-semibold uppercase tracking-wide text-gray-400";
  sizeLabel.textContent = "Größe";
  bubble.appendChild(sizeLabel);

  SIZE_PRESETS.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.title = preset.title;
    button.className = "rounded-lg px-2.5 py-1.5 text-sm font-semibold text-gray-700 transition hover:bg-blue-50 hover:text-blue-700";
    button.textContent = preset.label;
    button.addEventListener("click", function (event) {
      event.preventDefault();
      applyWidth(preset.width);
    });
    bubble.appendChild(button);
  });

  const divider = document.createElement("span");
  divider.className = "mx-0.5 h-5 w-px bg-gray-200";
  bubble.appendChild(divider);

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.title = "Bild entfernen";
  deleteButton.className = "rounded-lg px-2.5 py-1.5 text-sm text-red-500 transition hover:bg-red-50 hover:text-red-700";
  deleteButton.innerHTML = '<i class="bi bi-trash"></i>';
  deleteButton.addEventListener("click", function (event) {
    event.preventDefault();
    removeImage();
  });
  bubble.appendChild(deleteButton);

  wrap.appendChild(bubble);

  editorRoot.addEventListener("click", function (event) {
    const target = event.target;

    if (target && target.tagName === "IMG") {
      if (activeImage && activeImage !== target) {
        activeImage.style.outline = "";
      }

      activeImage = target;
      activeImage.style.outline = "3px solid rgba(59, 130, 246, 0.55)";

      const wrapRect = wrap.getBoundingClientRect();
      const imageRect = target.getBoundingClientRect();

      bubble.classList.remove("hidden");
      bubble.classList.add("flex");

      const top = Math.max(imageRect.top - wrapRect.top - 44, 4);
      let left = imageRect.left - wrapRect.left;
      left = Math.min(left, wrap.clientWidth - bubble.offsetWidth - 8);

      bubble.style.top = `${top}px`;
      bubble.style.left = `${Math.max(left, 4)}px`;
      return;
    }

    if (!bubble.contains(target)) {
      hideBubble();
    }
  });

  descriptionEditor.on("text-change", function (delta, oldDelta, source) {
    if (source === "user" && activeImage && !editorRoot.contains(activeImage)) {
      hideBubble();
    }
  });

  document.addEventListener("click", function (event) {
    if (!wrap.contains(event.target)) {
      hideBubble();
    }
  });
}

function syncDescriptionField() {
  if (!descriptionEditor) {
    return;
  }

  const text = descriptionEditor.getText().trim();
  const html = descriptionEditor.getSemanticHTML();
  const isEmpty = !text && html.indexOf("<img") === -1;

  $("#description").val(isEmpty ? "" : html);
}

function syncShowcaseState() {
  const $showcaseSwitch = $("#showcaseOnlySwitch");
  const isShowcaseOnly = $showcaseSwitch.is(":checked");
  const $showPriceSwitch = $("#showPriceWhenShowcaseSwitch");

  // Showcase ist aktuell Standard: solange aktiv, lässt es sich nicht
  // deaktivieren. Nur falls es (z.B. durch einen Bug) aus ist, kann es
  // wieder eingeschaltet werden.
  $showcaseSwitch.prop("disabled", isShowcaseOnly);
  $showcaseSwitch.closest("label").toggleClass("cursor-not-allowed", isShowcaseOnly);

  $showPriceSwitch.prop("disabled", !isShowcaseOnly);
  $showPriceSwitch.closest("label").toggleClass("opacity-60", !isShowcaseOnly);
}

$(document).ready(function () {
  toggleSpecificationPlaceholder();
  syncShowcaseState();
  initDescriptionEditor();
  initImageSizeControls();

  $("#addSpecificationRow").on("click", function () {
    $("#productSpecificationsList").append(createSpecificationRow());
    toggleSpecificationPlaceholder();
  });

  $("#productSpecificationsList").on("click", ".remove-specification-row", function () {
    $(this).closest(".specification-row").remove();
    toggleSpecificationPlaceholder();
  });

  $("#showcaseOnlySwitch").on("change", function () {
    syncShowcaseState();
  });

  $("#title").on("input", function () {
    $("#titleSpan").text($(this).val());
  });

  $("#titleImgUpload").on("change", function () {
    const file = this.files[0];

    if (file) {
      const reader = new FileReader();

      reader.onload = function (e) {
        $("#productImage").attr("src", e.target.result);
        imageData = e.target.result;
        newImage = true;
      };

      reader.readAsDataURL(file);
    } else {
      $("#productImage").attr("src", "");
      newImage = false;
    }
  });

  $("#createProduct").on("click", function () {
    $("#createProductForm").submit();
  });

  $("#updateProduct").on("click", function () {
    $("#updateProductForm").submit();
  });

  $("#updateProductForm").on("submit", function (event) {
    event.preventDefault();
    enableSpinner($("#updateProduct"));

    if (!updateUrl) {
      disableSpinner($("#updateProduct"));
      sendNotif("Die Update URL fehlt. Bitte lade die Seite neu.", "error");
      return;
    }

    syncDescriptionField();

    const files = $("#titleImgUpload").prop("files");
    const requiredFields = ["#title", "#description", "#price"];
    const isValid = isFormValid(requiredFields);

    if (!isValid) {
      disableSpinner($("#updateProduct"));
      return;
    }

    const formData = new FormData(this);
    setFormDataValue(formData, "title", $("#title").val());
    setFormDataValue(formData, "description", $("#description").val());
    setFormDataValue(formData, "isActive", $("#activeSwitch").is(":checked"));
    setFormDataValue(formData, "isInStock", $("#stockSwitch").is(":checked"));
    setFormDataValue(formData, "isReduced", $("#reducedSwitch").is(":checked"));
    setFormDataValue(formData, "price", $("#price").val());
    setFormDataValue(formData, "weight", $("#weight").val());
    setFormDataValue(formData, "isOnlineAvailable", $("#onlineSwitch").is(":checked"));
    setFormDataValue(formData, "reducedPrice", $("#reducedPrice").val());
    setFormDataValue(formData, "isShowcaseOnly", $("#showcaseOnlySwitch").is(":checked"));
    setFormDataValue(formData, "showPriceWhenShowcase", $("#showPriceWhenShowcaseSwitch").is(":checked"));
    setFormDataValue(formData, "isFeatured", $("#featuredSwitch").is(":checked"));
    setFormDataValue(formData, "sku", $("#sku").val() || "");
    setFormDataValue(formData, "priceNote", $("#priceNote").val() || "");
    appendTaxonomyToFormData(formData);

    if (!appendSpecificationsToFormData(formData)) {
      disableSpinner($("#updateProduct"));
      return;
    }

    const selectedFileIds = typeof window.getSelectedProductFileIds === "function"
      ? window.getSelectedProductFileIds()
      : [];

    formData.append("selected_file_ids", JSON.stringify(selectedFileIds));

    const galeryId = $("#productGalery").attr("galery-id");
    if (galeryId && parseInt(galeryId, 10) > 0) {
      formData.append("galeryId", galeryId);
    }

    if (files && files[0]) {
      formData.append("title_image", files[0], "productTitleImage");
    }

    $.ajax({
      url: updateUrl,
      type: "POST",
      data: formData,
      contentType: false,
      processData: false,
      dataType: "json",
      beforeSend: function (xhr) {
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
      },
      success: function (response) {
        disableSpinner($("#updateProduct"));

        if (response.success) {
          sendNotif("Das Produkt wurde erfolgreich gespeichert.", "success");
        } else {
          sendNotif(response.error || "Speichern fehlgeschlagen.", "error");
        }
      },
      error: function (xhr) {
        console.error(xhr);
        disableSpinner($("#updateProduct"));
        sendNotif(getAjaxErrorMessage(xhr), "error");
      }
    });
  });

  $("#deleteProduct").on("click", function () {
  if (!deleteUrl) {
    sendNotif("Die Delete URL fehlt. Bitte lade die Seite neu.", "error");
    return;
  }

  Swal.fire({
    title: "Produkt wirklich löschen?",
    text: "Das Produkt wird dauerhaft gelöscht. Diese Aktion kann nicht rückgängig gemacht werden.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#e3342f",
    cancelButtonColor: "#6c757d",
    confirmButtonText: "Ja, löschen!",
    cancelButtonText: "Abbrechen",
  }).then((result) => {
    if (!result.isConfirmed) {
      return;
    }

    sendNotif("Das Produkt wird gelöscht...", "info");

    $.ajax({
      url: deleteUrl,
      type: "POST",
      data: {
        csrfmiddlewaretoken: getCsrfToken(),
      },
      dataType: "json",
      success: function (response) {
        if (response.error) {
          Swal.fire({
            title: "Fehler",
            text: response.error || "Das Produkt konnte nicht gelöscht werden.",
            icon: "error",
          });
          return;
        }

        Swal.fire({
          title: "Gelöscht!",
          text: "Das Produkt wurde erfolgreich entfernt.",
          icon: "success",
          timer: 1500,
          showConfirmButton: false,
        }).then(() => {
          window.location.href = productsUrl;
        });
      },
      error: function (xhr) {
        console.error(xhr.responseText);
        Swal.fire({
          title: "Fehler",
          text: "Beim Löschen ist ein Fehler aufgetreten.",
          icon: "error",
        });
      }
    });
  });
});

  $("#createProductForm").on("submit", function (event) {
    event.preventDefault();
    enableSpinner($("#createProduct"));

    if (!createUrl) {
      disableSpinner($("#createProduct"));
      sendNotif("Die Create URL fehlt. Bitte lade die Seite neu.", "error");
      return;
    }

    syncDescriptionField();

    const files = $("#titleImgUpload").prop("files");

    if (!files || files.length === 0) {
      disableSpinner($("#createProduct"));
      sendNotif("Bitte wähle ein Titelbild aus!", "error");
      return;
    }

    const requiredFields = ["#title", "#description", "#price"];
    const isValid = isFormValid(requiredFields);

    if (!isValid) {
      disableSpinner($("#createProduct"));
      return;
    }

    const formData = new FormData(this);
    const titleImage = files[0];

    setFormDataValue(formData, "title", $("#title").val());
    setFormDataValue(formData, "description", $("#description").val());
    setFormDataValue(formData, "isActive", $("#activeSwitch").is(":checked"));
    setFormDataValue(formData, "isInStock", $("#stockSwitch").is(":checked"));
    setFormDataValue(formData, "isReduced", $("#reducedSwitch").is(":checked"));
    setFormDataValue(formData, "price", $("#price").val());
    setFormDataValue(formData, "weight", $("#weight").val());
    setFormDataValue(formData, "isOnlineAvailable", $("#onlineSwitch").is(":checked"));
    setFormDataValue(formData, "reducedPrice", $("#reducedPrice").val());
    setFormDataValue(formData, "isShowcaseOnly", $("#showcaseOnlySwitch").is(":checked"));
    setFormDataValue(formData, "showPriceWhenShowcase", $("#showPriceWhenShowcaseSwitch").is(":checked"));
    setFormDataValue(formData, "isFeatured", $("#featuredSwitch").is(":checked"));
    setFormDataValue(formData, "sku", $("#sku").val() || "");
    setFormDataValue(formData, "priceNote", $("#priceNote").val() || "");
    appendTaxonomyToFormData(formData);
    formData.append("title_image", titleImage, "productTitleImage");

    if (!appendSpecificationsToFormData(formData)) {
      disableSpinner($("#createProduct"));
      return;
    }

    const selectedFileIds = typeof window.getSelectedProductFileIds === "function"
      ? window.getSelectedProductFileIds()
      : [];

    formData.append("selected_file_ids", JSON.stringify(selectedFileIds));

    const galeryId = $("#productGalery").attr("galery-id");
    if (galeryId && parseInt(galeryId, 10) > 0) {
      formData.append("galeryId", galeryId);
    }

    $.ajax({
      url: createUrl,
      type: "POST",
      data: formData,
      contentType: false,
      processData: false,
      dataType: "json",
      beforeSend: function (xhr) {
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
      },
      success: function (response) {
        if (response.success) {
          sendNotif("Das Produkt wurde erfolgreich erstellt.", "success");
          setTimeout(function () {
            window.location.href = buildProductDetailUrl(response.productId, response.slug);
            disableSpinner($("#createProduct"));
          }, 2000);
        } else {
          disableSpinner($("#createProduct"));
          sendNotif("Etwas lief schief. " + (response.error || ""), "error");
        }
      },
      error: function (xhr) {
        console.error(xhr);
        disableSpinner($("#createProduct"));
        sendNotif(getAjaxErrorMessage(xhr), "error");
      }
    });
  });
});
