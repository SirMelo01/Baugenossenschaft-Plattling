/**
 * Zuordnung (Gruppierung / Hersteller / Kategorien) für Produkte.
 *
 * Statt Freitext-Eingaben öffnet sich ein Modal, in dem aus bestehenden
 * Einträgen gewählt oder ein neuer Eintrag angelegt werden kann.
 * Gruppen können zusätzlich sortiert und gelöscht werden, da ihre
 * Reihenfolge die Abschnitte der öffentlichen Produktseite bestimmt.
 */
(function () {
  const formConfig = document.getElementById("productFormConfig");
  const modal = document.getElementById("taxonomyModal");

  if (!formConfig || !modal) {
    return;
  }

  const endpoints = {
    category: formConfig.dataset.categoriesUrl,
    brand: formConfig.dataset.brandsUrl,
    group: formConfig.dataset.groupsUrl
  };
  const groupCreateUrl = formConfig.dataset.groupCreateUrl;
  const groupMoveUrlTemplate = formConfig.dataset.groupMoveUrl;
  const groupDeleteUrlTemplate = formConfig.dataset.groupDeleteUrl;

  const KIND_CONFIG = {
    group: {
      title: "Gruppierung wählen",
      subtitle: "Gruppen bestimmen die Abschnitte und deren Reihenfolge auf der öffentlichen Produktseite.",
      createLabel: "Neue Gruppe anlegen",
      chipContainer: "selectedGroupChips",
      multi: false,
      manageOrder: true
    },
    brand: {
      title: "Hersteller wählen",
      subtitle: "Wähle den Hersteller des Produkts oder lege einen neuen an.",
      createLabel: "Neuen Hersteller anlegen",
      chipContainer: "selectedBrandChips",
      multi: false,
      manageOrder: false
    },
    category: {
      title: "Kategorien wählen",
      subtitle: "Kategorien dienen als Filter-Schlagworte. Mehrfachauswahl möglich.",
      createLabel: "Neue Kategorie anlegen",
      chipContainer: "selectedCategoryChips",
      multi: true,
      manageOrder: false
    }
  };

  const state = {
    group: [],
    brand: [],
    category: []
  };

  let activeKind = null;
  let items = [];
  let pendingSelection = [];

  function getCsrfToken() {
    return $('input[name="csrfmiddlewaretoken"]').val();
  }

  function buildGroupActionUrl(template, id) {
    return (template || "").replace("/0/", `/${id}/`);
  }

  function notify(message, type) {
    if (typeof sendNotif === "function") {
      sendNotif(message, type);
    }
  }

  // ---------- Chips im Formular ----------

  function renderChips(kind) {
    const config = KIND_CONFIG[kind];
    const container = document.getElementById(config.chipContainer);
    if (!container) {
      return;
    }

    const values = state[kind];
    container.innerHTML = "";

    if (!values.length) {
      const empty = document.createElement("p");
      empty.className = "text-xs text-gray-400";
      empty.textContent = container.dataset.emptyText || "Nichts zugeordnet";
      container.appendChild(empty);
      return;
    }

    values.forEach((value) => {
      const chip = document.createElement("span");
      chip.className = "taxonomy-chip inline-flex max-w-full items-center gap-1.5 rounded-full bg-blue-100 py-1 pl-3 pr-1.5 text-sm font-medium text-blue-900";
      chip.setAttribute("data-taxonomy-value", value);

      const label = document.createElement("span");
      label.className = "truncate";
      label.textContent = value;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "taxonomy-chip-remove inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-blue-500 transition hover:bg-blue-200 hover:text-blue-800";
      removeBtn.setAttribute("data-kind", kind);
      removeBtn.setAttribute("data-value", value);
      removeBtn.setAttribute("aria-label", `${value} entfernen`);
      removeBtn.innerHTML = "&times;";

      chip.appendChild(label);
      chip.appendChild(removeBtn);
      container.appendChild(chip);
    });
  }

  function initStateFromDom() {
    Object.keys(KIND_CONFIG).forEach((kind) => {
      const container = document.getElementById(KIND_CONFIG[kind].chipContainer);
      if (!container) {
        return;
      }

      state[kind] = Array.from(container.querySelectorAll("[data-taxonomy-value]"))
        .map((node) => node.getAttribute("data-taxonomy-value"))
        .filter(Boolean);

      renderChips(kind);
    });
  }

  // ---------- Modal ----------

  function setModalTexts(kind) {
    const config = KIND_CONFIG[kind];
    document.getElementById("taxonomyModalTitle").textContent = config.title;
    document.getElementById("taxonomyModalSubtitle").textContent = config.subtitle;
    document.getElementById("taxonomyCreateLabel").textContent = config.createLabel;
    document.getElementById("taxonomySearch").value = "";
    document.getElementById("taxonomyCreateInput").value = "";
  }

  function updateSelectionInfo() {
    const config = KIND_CONFIG[activeKind];
    const info = document.getElementById("taxonomySelectionInfo");

    if (config.multi) {
      info.textContent = `${pendingSelection.length} ausgewählt`;
    } else {
      info.textContent = pendingSelection.length ? `Ausgewählt: ${pendingSelection[0]}` : "Nichts ausgewählt (Zuordnung wird entfernt)";
    }
  }

  function renderList() {
    const config = KIND_CONFIG[activeKind];
    const list = document.getElementById("taxonomyList");
    const emptyState = document.getElementById("taxonomyEmptyState");
    const query = (document.getElementById("taxonomySearch").value || "").trim().toLowerCase();

    const visibleItems = items.filter((item) => !query || item.name.toLowerCase().includes(query));

    list.innerHTML = "";
    emptyState.classList.toggle("hidden", visibleItems.length > 0);

    visibleItems.forEach((item, index) => {
      const isSelected = pendingSelection.includes(item.name);

      const row = document.createElement("div");
      row.className = `flex items-center gap-2 rounded-lg border bg-white p-1.5 transition ${
        isSelected ? "border-blue-500 ring-2 ring-blue-100" : "border-slate-200 hover:border-blue-300"
      }`;

      const selectBtn = document.createElement("button");
      selectBtn.type = "button";
      selectBtn.className = "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left";

      const check = document.createElement("span");
      check.className = `inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
        isSelected ? "bg-blue-600 text-white" : "bg-slate-100 text-transparent"
      }`;
      check.innerHTML = '<i class="bi bi-check-lg"></i>';

      const name = document.createElement("span");
      name.className = "truncate text-sm font-medium text-slate-800";
      name.textContent = item.name;

      const count = document.createElement("span");
      count.className = "ml-auto shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500";
      count.textContent = item.product_count === 1 ? "1 Produkt" : `${item.product_count || 0} Produkte`;

      selectBtn.appendChild(check);
      selectBtn.appendChild(name);
      selectBtn.appendChild(count);
      selectBtn.addEventListener("click", () => toggleSelection(item.name));
      row.appendChild(selectBtn);

      if (config.manageOrder && !query && item.id) {
        const controls = document.createElement("div");
        controls.className = "flex shrink-0 items-center gap-0.5 border-l border-slate-100 pl-1.5";

        const upBtn = createIconButton("bi-chevron-up", "Nach oben", index === 0);
        upBtn.addEventListener("click", () => moveGroup(item.id, "up"));

        const downBtn = createIconButton("bi-chevron-down", "Nach unten", index === visibleItems.length - 1);
        downBtn.addEventListener("click", () => moveGroup(item.id, "down"));

        const deleteBtn = createIconButton("bi-trash", "Gruppe löschen", false, true);
        deleteBtn.addEventListener("click", () => deleteGroup(item));

        controls.appendChild(upBtn);
        controls.appendChild(downBtn);
        controls.appendChild(deleteBtn);
        row.appendChild(controls);
      }

      list.appendChild(row);
    });

    updateSelectionInfo();
  }

  function createIconButton(icon, label, disabled, danger) {
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = Boolean(disabled);
    button.className = `inline-flex h-7 w-7 items-center justify-center rounded-md transition ${
      danger
        ? "text-slate-400 hover:bg-red-50 hover:text-red-600"
        : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
    } disabled:cursor-not-allowed disabled:opacity-30`;
    button.setAttribute("aria-label", label);
    button.innerHTML = `<i class="bi ${icon} text-sm"></i>`;
    return button;
  }

  function toggleSelection(name) {
    const config = KIND_CONFIG[activeKind];

    if (config.multi) {
      const index = pendingSelection.indexOf(name);
      if (index === -1) {
        pendingSelection.push(name);
      } else {
        pendingSelection.splice(index, 1);
      }
    } else {
      pendingSelection = pendingSelection[0] === name ? [] : [name];
    }

    renderList();
  }

  function loadItems() {
    const list = document.getElementById("taxonomyList");
    const loading = document.getElementById("taxonomyLoading");
    const url = endpoints[activeKind];

    if (!url) {
      return;
    }

    list.innerHTML = "";
    loading.classList.remove("hidden");
    document.getElementById("taxonomyEmptyState").classList.add("hidden");

    $.ajax({
      url: url,
      type: "GET",
      dataType: "json",
      success: function (response) {
        loading.classList.add("hidden");
        items = response.items || [];
        renderList();
      },
      error: function () {
        loading.classList.add("hidden");
        notify("Die Einträge konnten nicht geladen werden.", "error");
      }
    });
  }

  function openModal(kind) {
    activeKind = kind;
    pendingSelection = state[kind].slice();
    items = [];
    setModalTexts(kind);
    modal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    loadItems();
  }

  function closeModal() {
    modal.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
    activeKind = null;
  }

  function confirmSelection() {
    if (!activeKind) {
      return;
    }
    state[activeKind] = pendingSelection.slice();
    renderChips(activeKind);
    closeModal();
  }

  function createEntry() {
    const input = document.getElementById("taxonomyCreateInput");
    const name = (input.value || "").trim();

    if (!name) {
      notify("Bitte gib einen Namen ein.", "error");
      return;
    }

    const exists = items.some((item) => item.name.toLowerCase() === name.toLowerCase());
    if (exists) {
      notify("Dieser Eintrag existiert bereits – wähle ihn einfach aus der Liste.", "error");
      return;
    }

    if (activeKind === "group") {
      $.ajax({
        url: groupCreateUrl,
        type: "POST",
        data: { name: name, csrfmiddlewaretoken: getCsrfToken() },
        dataType: "json",
        success: function (response) {
          input.value = "";
          items.push({ id: response.id, name: response.name, product_count: 0 });
          toggleSelection(response.name);
          notify("Gruppe wurde angelegt.", "success");
        },
        error: function (xhr) {
          const message = xhr.responseJSON && xhr.responseJSON.error
            ? xhr.responseJSON.error
            : "Die Gruppe konnte nicht angelegt werden.";
          notify(message, "error");
        }
      });
      return;
    }

    // Kategorien und Hersteller werden beim Speichern des Produkts angelegt.
    input.value = "";
    items.push({ id: null, name: name, product_count: 0 });
    items.sort((a, b) => a.name.localeCompare(b.name, "de"));
    toggleSelection(name);
  }

  function moveGroup(groupId, direction) {
    $.ajax({
      url: buildGroupActionUrl(groupMoveUrlTemplate, groupId),
      type: "POST",
      data: { direction: direction, csrfmiddlewaretoken: getCsrfToken() },
      dataType: "json",
      success: function () {
        loadItems();
      },
      error: function () {
        notify("Die Reihenfolge konnte nicht angepasst werden.", "error");
      }
    });
  }

  function deleteGroup(item) {
    Swal.fire({
      title: `Gruppe "${item.name}" löschen?`,
      text: "Produkte in dieser Gruppe bleiben erhalten und erscheinen dann unter \"Weitere Produkte\".",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#e3342f",
      cancelButtonColor: "#6c757d",
      confirmButtonText: "Ja, löschen",
      cancelButtonText: "Abbrechen"
    }).then((result) => {
      if (!result.isConfirmed) {
        return;
      }

      $.ajax({
        url: buildGroupActionUrl(groupDeleteUrlTemplate, item.id),
        type: "POST",
        data: { csrfmiddlewaretoken: getCsrfToken() },
        dataType: "json",
        success: function () {
          pendingSelection = pendingSelection.filter((value) => value !== item.name);
          if (state.group.includes(item.name)) {
            state.group = [];
            renderChips("group");
          }
          notify("Gruppe wurde gelöscht.", "success");
          loadItems();
        },
        error: function () {
          notify("Die Gruppe konnte nicht gelöscht werden.", "error");
        }
      });
    });
  }

  // ---------- Öffentliche API für das Produktformular ----------

  window.getProductTaxonomy = function () {
    return {
      group: state.group[0] || "",
      brand: state.brand[0] || "",
      categories: state.category.slice()
    };
  };

  // ---------- Events ----------

  $(document).ready(function () {
    initStateFromDom();

    $(document).on("click", ".taxonomy-open", function () {
      openModal($(this).data("kind"));
    });

    $(document).on("click", ".taxonomy-chip-remove", function () {
      const kind = $(this).data("kind");
      const value = $(this).data("value");
      state[kind] = state[kind].filter((entry) => entry !== value);
      renderChips(kind);
    });

    $("#closeTaxonomyModal").on("click", closeModal);
    $("#confirmTaxonomy").on("click", confirmSelection);
    $("#taxonomyCreateBtn").on("click", createEntry);

    $("#taxonomyCreateInput").on("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        createEntry();
      }
    });

    $("#taxonomySearch").on("input", function () {
      renderList();
    });

    modal.addEventListener("click", function (event) {
      if (event.target === modal) {
        closeModal();
      }
    });

    $(document).on("keydown", function (event) {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        closeModal();
      }
    });
  });
})();
