const shopConfig = document.getElementById("shopOverviewConfig")
const searchProductsUrl = shopConfig?.dataset.searchUrl
const placeholderImage = shopConfig?.dataset.placeholderImage || ""

function escapeHtml(value) {
  return $("<div>").text(value || "").html()
}

function getCheckedRadioValue(name) {
  return $(`input[name="${name}"]:checked`).val() || ""
}

function getCurrentShopFilters() {
  return {
    q: $("#shopSearchInput").val().trim(),
    min_price: $("#filterMinPrice").val().trim(),
    max_price: $("#filterMaxPrice").val().trim(),
    is_reduced: $("#filterReduced").is(":checked"),
    is_in_stock: $("#filterInStock").is(":checked"),
    online_only: $("#filterOnlineOnly").is(":checked"),
    type: getCheckedRadioValue("shopProductType"),
    brand: getCheckedRadioValue("shopBrand"),
    category: getCheckedRadioValue("shopCategory"),
    ordering: $("#shopSortSelect").val() || "title_asc",
  }
}

function getActiveShopFilterCount() {
  const filters = getCurrentShopFilters()
  let count = 0

  if (filters.q) count += 1
  if (filters.min_price) count += 1
  if (filters.max_price) count += 1
  if (filters.is_reduced) count += 1
  if (filters.is_in_stock) count += 1
  if (filters.online_only) count += 1
  if (filters.type) count += 1
  if (filters.brand) count += 1
  if (filters.category) count += 1
  if (filters.ordering && filters.ordering !== "title_asc") count += 1

  return count
}

function updateShopFilterCount() {
  const count = getActiveShopFilterCount()
  const $mobile = $("#mobileActiveFilterCount")
  const $desktop = $("#desktopActiveFilterCount")

  if (count > 0) {
    $mobile.text(count).removeClass("hidden")
    $desktop.text(count).removeClass("hidden")
  } else {
    $mobile.addClass("hidden")
    $desktop.addClass("hidden")
  }
}

function buildShopSearchParams(page = 1) {
  const filters = getCurrentShopFilters()
  const params = new URLSearchParams()

  if (filters.q) params.set("q", filters.q)
  if (filters.min_price) params.set("min_price", filters.min_price)
  if (filters.max_price) params.set("max_price", filters.max_price)
  if (filters.is_reduced) params.set("is_reduced", "true")
  if (filters.is_in_stock) params.set("is_in_stock", "true")
  if (filters.online_only) params.set("online_only", "true")
  if (filters.type) params.set("type", filters.type)
  if (filters.brand) params.set("brand", filters.brand)
  if (filters.category) params.set("category", filters.category)
  if (filters.ordering) params.set("ordering", filters.ordering)

  params.set("page", page)
  return params
}

function buildPublicProductCard(product) {
  const detailUrl = product.detail_url || "#"
  const imageUrl = product.image_url || placeholderImage
  const title = escapeHtml(product.title)
  const description = escapeHtml(product.description || "Keine Beschreibung vorhanden")
  const brand = escapeHtml(product.brand || "")
  const priceNote = escapeHtml(product.price_note || "")
  const showPriceCard = !product.showcase_only || product.show_price_when_showcase

  const topBadges = []
  if (product.is_reduced && product.discount_price && showPriceCard) {
    topBadges.push('<span class="rounded-full bg-red-500 px-3 py-1 text-xs font-semibold text-white">Angebot</span>')
  }
  if (product.featured) {
    topBadges.push('<span class="rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white">Empfehlung</span>')
  }

  const badges = []
  if (product.is_in_stock) {
    badges.push('<span class="rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">Verfügbar</span>')
  } else {
    badges.push('<span class="rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700">Aktuell nicht verfügbar</span>')
  }

  if (product.online_sell) {
    badges.push('<span class="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">Lieferung möglich</span>')
  }

  let priceHtml = ""
  if (!showPriceCard) {
    priceHtml = '<span class="text-sm font-semibold text-gray-500">Mehr erfahren</span>'
  } else if (product.is_reduced && product.discount_price) {
    priceHtml = `
      <div class="flex flex-wrap items-end gap-2">
        <span class="text-xl font-bold text-blue-600">${escapeHtml(product.discount_price)} €</span>
        <span class="pb-0.5 text-sm text-gray-400 line-through">${escapeHtml(product.price)} €</span>
      </div>
    `
  } else {
    priceHtml = `<span class="text-xl font-bold text-gray-900">${escapeHtml(product.price)} €</span>`
  }

  if (showPriceCard && priceNote) {
    priceHtml += `<p class="mt-0.5 truncate text-xs text-gray-500">${priceNote}</p>`
  }

  const cardBorder = product.featured
    ? "border-blue-200 ring-1 ring-blue-100"
    : "border-gray-200"

  return `
    <a href="${detailUrl}" class="group block h-full">
      <div class="flex h-full flex-col overflow-hidden rounded-3xl border bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg ${cardBorder}">
        <div class="relative">
          <div class="flex h-52 items-center justify-center bg-gray-50 p-4 sm:h-60">
            <img src="${imageUrl}" alt="${title}" loading="lazy" class="max-h-full max-w-full object-contain">
          </div>

          <div class="absolute left-3 top-3 flex flex-wrap gap-2">
            ${topBadges.join("")}
          </div>
        </div>

        <div class="flex flex-1 flex-col p-5">
          <div class="min-w-0">
            ${brand ? `<p class="text-xs font-semibold uppercase tracking-wide text-gray-400">${brand}</p>` : ""}
            <h3 class="mt-1 text-lg font-bold leading-snug text-gray-900 group-hover:text-blue-700">${title}</h3>
          </div>

          <p class="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">${description}</p>

          <div class="mt-4 flex flex-wrap gap-2">
            ${badges.join("")}
          </div>

          <div class="mt-auto flex items-end justify-between gap-3 pt-5">
            <div class="min-w-0">${priceHtml}</div>

            <span class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white transition group-hover:bg-blue-700">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path fill-rule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </a>
  `
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

function updateShopProductGrid(products) {
  const $grid = $("#shopProductGrid")
  $grid.empty()

  if (!products || products.length === 0) {
    $grid.html(`
      <div class="col-span-full rounded-3xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500 shadow-sm">
        Keine Produkte für diese Filter gefunden
      </div>
    `)
    return
  }

  products.forEach((product) => {
    $grid.append(buildPublicProductCard(product))
  })
}

function updateShopPagination(pagination) {
  const $pagination = $("#shopPagination")
  $pagination.empty()

  if (!pagination || pagination.num_pages <= 1) {
    return
  }

  if (pagination.has_previous) {
    $pagination.append(`
      <button
        type="button"
        data-page="${pagination.previous_page_number}"
        class="shop-pagination-btn rounded-2xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        Zurück
      </button>
    `)
  }

  const items = buildPaginationItems(pagination.current_page, pagination.num_pages)

  items.forEach((item) => {
    if (typeof item === "string") {
      $pagination.append('<span class="px-2 text-sm text-gray-400">…</span>')
      return
    }

    if (item === pagination.current_page) {
      $pagination.append(`
        <button
          type="button"
          data-page="${item}"
          class="shop-pagination-btn rounded-2xl bg-blue-500 px-4 py-2 text-sm font-semibold text-white"
        >
          ${item}
        </button>
      `)
      return
    }

    $pagination.append(`
      <button
        type="button"
        data-page="${item}"
        class="shop-pagination-btn rounded-2xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        ${item}
      </button>
    `)
  })

  if (pagination.has_next) {
    $pagination.append(`
      <button
        type="button"
        data-page="${pagination.next_page_number}"
        class="shop-pagination-btn rounded-2xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:border-blue-300 hover:text-blue-700"
      >
        Weiter
      </button>
    `)
  }
}

function updateShopResultsInfo(pagination) {
  $("#shopResultsInfo").text(`${pagination.total_count} Produkte gefunden`)
}

function updateShopUrl(params) {
  const url = `${window.location.pathname}?${params.toString()}`
  window.history.replaceState({}, "", url)
}

function loadShopProducts(page = 1) {
  if (!searchProductsUrl) {
    return
  }

  const params = buildShopSearchParams(page)

  $.ajax({
    url: `${searchProductsUrl}?${params.toString()}`,
    type: "GET",
    dataType: "json",
    success: function (data) {
      const products = data.products || []
      const pagination = data.pagination || {
        current_page: 1,
        num_pages: 1,
        total_count: products.length,
      }

      updateShopProductGrid(products)
      updateShopPagination(pagination)
      updateShopResultsInfo(pagination)
      updateShopFilterCount()
      updateShopUrl(params)
    },
    error: function () {
      if (typeof sendNotif === "function") {
        sendNotif("Die Produktsuche konnte nicht geladen werden.", "error")
      }
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
  const debouncedSearch = debounce(function () {
    loadShopProducts(1)
  }, 300)

  updateShopFilterCount()

  $("#toggleShopFilters").on("click", function () {
    $("#shopFiltersPanel").toggleClass("hidden")
  })

  $("#searchProductsBtn, #applyShopFilters").on("click", function () {
    loadShopProducts(1)
  })

  $("#shopSearchInput").on("input", function () {
    updateShopFilterCount()
    debouncedSearch()
  })

  $("#shopSearchInput").on("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault()
      loadShopProducts(1)
    }
  })

  $("#filterReduced, #filterInStock, #filterOnlineOnly, #filterMinPrice, #filterMaxPrice, #shopSortSelect").on("change input", function () {
    updateShopFilterCount()
    loadShopProducts(1)
  })

  $('input[name="shopProductType"], input[name="shopBrand"], input[name="shopCategory"]').on("change", function () {
    updateShopFilterCount()
    loadShopProducts(1)
  })

  $("#resetShopFilters").on("click", function () {
    $("#shopSearchInput").val("")
    $("#filterReduced").prop("checked", false)
    $("#filterInStock").prop("checked", false)
    $("#filterOnlineOnly").prop("checked", false)
    $("#filterMinPrice").val("")
    $("#filterMaxPrice").val("")
    $('#shopSortSelect').val("title_asc")
    $('input[name="shopProductType"][value=""]').prop("checked", true)
    $('input[name="shopBrand"][value=""]').prop("checked", true)
    $('input[name="shopCategory"][value=""]').prop("checked", true)

    updateShopFilterCount()
    loadShopProducts(1)
  })

  $(document).on("click", ".shop-pagination-btn", function () {
    const page = parseInt($(this).data("page"), 10)

    if (!page) {
      return
    }

    loadShopProducts(page)

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    })
  })
})