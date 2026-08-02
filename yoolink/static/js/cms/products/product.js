const overviewConfig = document.getElementById("productOverviewConfig")
const searchUrl = overviewConfig?.dataset.searchUrl
const productsUrl = overviewConfig?.dataset.productsUrl
const placeholderImage = overviewConfig?.dataset.placeholderImage || ""

function normalizeBaseUrl(url) {
  if (!url) {
    return ""
  }
  return url.endsWith("/") ? url : `${url}/`
}

function buildProductDetailUrl(product) {
  if (product.detail_url) {
    return product.detail_url
  }

  const baseUrl = normalizeBaseUrl(productsUrl)

  if (product.id && product.slug) {
    return `${baseUrl}${product.id}/${product.slug}/`
  }

  return "#"
}

function escapeHtml(value) {
  return $("<div>").text(value || "").html()
}

function getCurrentFilters() {
  return {
    q: $("#searchProductInput").val().trim(),
    status: $("#filterStatus").val(),
    availability: $("#filterAvailability").val(),
    type: $("#filterType").val(),
    ordering: $("#filterOrdering").val(),
  }
}

function getActiveFilterCount() {
  const filters = getCurrentFilters()
  let count = 0

  if (filters.q) {
    count += 1
  }
  if (filters.status) {
    count += 1
  }
  if (filters.availability) {
    count += 1
  }
  if (filters.type) {
    count += 1
  }
  if (filters.ordering && filters.ordering !== "title_asc") {
    count += 1
  }

  return count
}

function updateFilterToggleState() {
  const $panel = $("#productFiltersPanel")
  const $icon = $("#toggleProductFiltersIcon")
  const $count = $("#activeProductFilterCount")
  const activeCount = getActiveFilterCount()

  if ($panel.hasClass("hidden")) {
    $icon.removeClass("rotate-180")
  } else {
    $icon.addClass("rotate-180")
  }

  if (activeCount > 0) {
    $count.text(activeCount)
    $count.removeClass("hidden")
  } else {
    $count.addClass("hidden")
  }
}

function buildSearchParams(page = 1) {
  const filters = getCurrentFilters()
  const params = new URLSearchParams()

  if (filters.q) {
    params.set("q", filters.q)
  }
  if (filters.status) {
    params.set("status", filters.status)
  }
  if (filters.availability) {
    params.set("availability", filters.availability)
  }
  if (filters.type) {
    params.set("type", filters.type)
  }
  if (filters.ordering) {
    params.set("ordering", filters.ordering)
  }

  params.set("page", page)
  return params
}

function buildStatusBadges(product) {
  const badges = []

  if (product.is_in_stock) {
    badges.push('<span class="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">Auf Lager</span>')
  } else {
    badges.push('<span class="rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700">Nicht auf Lager</span>')
  }

  if (product.online_sell) {
    badges.push('<span class="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">Lieferung</span>')
  }

  if (product.showcase_only) {
    badges.push('<span class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">Showcase</span>')
  }

  if (product.is_reduced) {
    badges.push('<span class="rounded-full bg-orange-50 px-2.5 py-1 text-xs font-medium text-orange-700">Reduziert</span>')
  }

  if (product.featured) {
    badges.push('<span class="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">Hervorgehoben</span>')
  }

  return badges.join("")
}

function buildPriceBadge(product) {
  if (product.showcase_only && !product.show_price_when_showcase) {
    return '<span class="rounded-full bg-gray-900 px-3 py-1 text-xs font-semibold text-white">Showcase</span>'
  }

  if (product.is_reduced && product.discount_price) {
    return `
      <span class="rounded-full bg-red-500 px-3 py-1 text-xs font-semibold text-white">${escapeHtml(product.discount_price)} €</span>
      <span class="rounded-full bg-white/95 px-3 py-1 text-xs font-semibold text-gray-500 line-through shadow-sm">${escapeHtml(product.price)} €</span>
    `
  }

  return `<span class="rounded-full bg-green-500 px-3 py-1 text-xs font-semibold text-white">${escapeHtml(product.price)} €</span>`
}

function buildTranslationBadges(product) {
  const badges = [
    `<span class="rounded-full bg-blue-100 px-2.5 py-1 font-medium text-blue-800">Original: ${escapeHtml(String(product.language || "").toUpperCase())}</span>`
  ]

  if (!Array.isArray(product.translations) || product.translations.length === 0) {
    badges.push('<span class="text-gray-400">Keine Varianten</span>')
    return badges.join("")
  }

  product.translations.forEach((translation) => {
    const icon = translation.is_active
      ? '<i class="bi bi-check-circle-fill text-green-600"></i>'
      : '<i class="bi bi-x-circle-fill text-red-600"></i>'
    const url = translation.detail_url || "#"
    badges.push(`
      <a href="${url}" class="rounded-full bg-gray-100 px-2.5 py-1 font-medium text-gray-700 transition hover:bg-blue-100 hover:text-blue-800">
        ${escapeHtml(String(translation.language || "").toUpperCase())}
        ${icon}
      </a>
    `)
  })

  return badges.join("")
}

function buildCategoryBadges(categories) {
  if (!Array.isArray(categories) || categories.length === 0) {
    return ""
  }

  return categories.slice(0, 3).map((category) => {
    return `<span class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">${escapeHtml(category)}</span>`
  }).join("")
}

function buildPaginationItems(currentPage, numPages) {
  const items = []

  if (numPages <= 7) {
    for (let i = 1; i <= numPages; i += 1) {
      items.push(i)
    }
    return items
  }

  items.push(1)

  if (currentPage > 3) {
    items.push("ellipsis-left")
  }

  const start = Math.max(2, currentPage - 1)
  const end = Math.min(numPages - 1, currentPage + 1)

  for (let i = start; i <= end; i += 1) {
    items.push(i)
  }

  if (currentPage < numPages - 2) {
    items.push("ellipsis-right")
  }

  items.push(numPages)

  return items
}

function updateProductGrid(products) {
  const productGrid = $("#productGrid")
  productGrid.empty()

  if (!products || products.length === 0) {
    productGrid.html(`
      <div class="col-span-full rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500 shadow-sm">
        Keine Produkte für diese Filter gefunden
      </div>
    `)
    return
  }

  products.forEach(function (product) {
    const detailUrl = buildProductDetailUrl(product)
    const imageUrl = product.image_url || placeholderImage
    const title = escapeHtml(product.title)
    const description = escapeHtml(product.description || "Keine Beschreibung vorhanden")
    const brand = escapeHtml(product.brand || "")
    const updatedAt = escapeHtml(product.updated_at || "")
    const activeBadge = product.is_active
      ? '<span class="rounded-full bg-green-100 px-2.5 py-1 text-xs font-semibold text-green-700">Aktiv</span>'
      : '<span class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-700">Inaktiv</span>'

    const productHtml = `
      <div class="group flex h-full flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
        <div class="relative">
          <img src="${imageUrl}" alt="${title}" class="h-52 w-full object-cover">
          <div class="absolute left-3 top-3 flex flex-wrap gap-2">
            ${buildPriceBadge(product)}
          </div>
        </div>

        <div class="flex flex-1 flex-col p-5">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="truncate text-lg font-semibold text-gray-900">${title}</h2>
              ${brand ? `<p class="mt-1 text-sm text-gray-500">${brand}</p>` : ""}
            </div>
            ${activeBadge}
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            ${buildStatusBadges(product)}
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-2 text-xs">
            ${buildTranslationBadges(product)}
          </div>

          <p class="mt-4 min-h-[4.5rem] text-sm leading-6 text-gray-600">${description}</p>

          <div class="mt-4 flex flex-wrap gap-2">
            ${buildCategoryBadges(product.categories)}
          </div>

          <div class="mt-5 flex items-center justify-between gap-3">
            <p class="text-xs text-gray-500">${updatedAt ? `Aktualisiert ${updatedAt}` : ""}</p>
            <a href="${detailUrl}" class="rounded-xl bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700">Verwalten</a>
          </div>
        </div>
      </div>
    `

    productGrid.append(productHtml)
  })
}

function updatePagination(pagination) {
  const paginationContainer = $("#productPagination")
  paginationContainer.empty()

  if (!pagination || pagination.num_pages <= 1) {
    return
  }

  if (pagination.has_previous) {
    paginationContainer.append(`
      <button
        type="button"
        data-page="${pagination.previous_page_number}"
        class="pagination-btn rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        Zurück
      </button>
    `)
  }

  const items = buildPaginationItems(pagination.current_page, pagination.num_pages)

  items.forEach((item) => {
    if (typeof item === "string" && item.includes("ellipsis")) {
      paginationContainer.append('<span class="px-2 text-sm text-gray-400">…</span>')
      return
    }

    if (item === pagination.current_page) {
      paginationContainer.append(`
        <button
          type="button"
          data-page="${item}"
          class="pagination-btn rounded-xl bg-blue-500 px-4 py-2 text-sm font-semibold text-white"
        >
          ${item}
        </button>
      `)
      return
    }

    paginationContainer.append(`
      <button
        type="button"
        data-page="${item}"
        class="pagination-btn rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        ${item}
      </button>
    `)
  })

  if (pagination.has_next) {
    paginationContainer.append(`
      <button
        type="button"
        data-page="${pagination.next_page_number}"
        class="pagination-btn rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        Weiter
      </button>
    `)
  }
}

function updateResultsInfo(pagination) {
  $("#productResultsInfo").text(`${pagination.total_count} Produkte gefunden`)
  $("#currentPageLabel").text(pagination.current_page)
  $("#totalPagesLabel").text(pagination.num_pages)
}

function loadProducts(page = 1) {
  if (!searchUrl) {
    sendNotif("Die Such URL fehlt. Bitte lade die Seite neu.", "error")
    return
  }

  const params = buildSearchParams(page)

  $.ajax({
    url: `${searchUrl}?${params.toString()}`,
    type: "GET",
    dataType: "json",
    success: function (data) {
      const products = Array.isArray(data) ? data : (data.products || [])
      const pagination = data.pagination || {
        current_page: 1,
        num_pages: 1,
        total_count: products.length,
        has_previous: false,
        has_next: false,
      }

      updateProductGrid(products)
      updatePagination(pagination)
      updateResultsInfo(pagination)
      updateFilterToggleState()
    },
    error: function (xhr) {
      console.error(xhr)
      sendNotif("Die Produktsuche konnte nicht ausgeführt werden.", "error")
    }
  })
}

function debounce(fn, delay) {
  let timeoutId = null

  return function (...args) {
    window.clearTimeout(timeoutId)
    timeoutId = window.setTimeout(() => fn.apply(this, args), delay)
  }
}

$(document).ready(function () {
  const debouncedLoad = debounce(function () {
    loadProducts(1)
  }, 300)

  updateFilterToggleState()

  $("#toggleProductFilters").on("click", function () {
    $("#productFiltersPanel").toggleClass("hidden")
    updateFilterToggleState()
  })

  $("#searchProduct").on("click", function () {
    loadProducts(1)
  })

  $("#searchProductInput").on("input", function () {
    updateFilterToggleState()
    debouncedLoad()
  })

  $("#searchProductInput").on("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault()
      loadProducts(1)
    }
  })

  $("#filterStatus, #filterAvailability, #filterType, #filterOrdering").on("change", function () {
    updateFilterToggleState()
    loadProducts(1)
  })

  $("#resetProductFilters").on("click", function () {
    $("#searchProductInput").val("")
    $("#filterStatus").val("")
    $("#filterAvailability").val("")
    $("#filterType").val("")
    $("#filterOrdering").val("title_asc")
    updateFilterToggleState()
    loadProducts(1)
  })

  $(document).on("click", ".pagination-btn", function () {
    const page = parseInt($(this).data("page"), 10)

    if (!page) {
      return
    }

    loadProducts(page)
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    })
  })
})
