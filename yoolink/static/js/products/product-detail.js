const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]')
const csrftoken = csrfInput ? csrfInput.value : null

$(document).ready(function () {
  const $productImage = $("#productImage")
  const $thumbs = $(".product-image")
  const $addToCartButton = $("#addToCart")
  const $amountInput = $("#amount")
  const $increaseAmount = $("#increaseAmount")
  const $decreaseAmount = $("#decreaseAmount")

  function getAmount() {
    const amount = parseInt($amountInput.val(), 10)
    return !amount || amount < 1 ? 1 : amount
  }

  function setAmount(value) {
    const normalizedValue = value < 1 ? 1 : value
    if ($amountInput.length) {
      $amountInput.val(normalizedValue)
    }
  }

  function setActiveThumb($thumb) {
    $thumbs
      .removeClass("border-blue-500 ring-4 ring-blue-100")
      .addClass("border-transparent")

    $thumb
      .removeClass("border-transparent")
      .addClass("border-blue-500 ring-4 ring-blue-100")
  }

  if ($thumbs.length && $productImage.length) {
    $thumbs.on("click", function () {
      const $currentThumb = $(this)
      const imageSrc = $currentThumb.data("image-src")

      if (!imageSrc) {
        return
      }

      $productImage.attr("src", imageSrc)
      setActiveThumb($currentThumb)
    })
  }

  if ($increaseAmount.length && $decreaseAmount.length && $amountInput.length) {
    $increaseAmount.on("click", function () {
      setAmount(getAmount() + 1)
    })

    $decreaseAmount.on("click", function () {
      setAmount(getAmount() - 1)
    })

    $amountInput.on("change blur", function () {
      setAmount(getAmount())
    })
  }

  if ($addToCartButton.length) {
    $addToCartButton.on("click", function () {
      if ($addToCartButton.is(":disabled")) {
        return
      }

      const productId = $(this).data("product-id")
      const addToCartUrl = $(this).data("add-to-cart-url")
      const amount = $amountInput.length ? getAmount() : 1

      if (!productId) {
        sendNotif("Die Produkt ID fehlt. Bitte lade die Seite neu.", "error")
        return
      }

      if (!addToCartUrl) {
        sendNotif("Die Warenkorb URL fehlt. Bitte lade die Seite neu.", "error")
        return
      }

      $addToCartButton.prop("disabled", true)

      $.ajax({
        url: addToCartUrl,
        type: "POST",
        data: {
          amount: amount,
          csrfmiddlewaretoken: csrftoken,
        },
        success: function (response) {
          if (response.success) {
            sendNotif("Das Produkt wurde zum Warenkorb hinzugefügt.", "success")
          } else if (response.error) {
            sendNotif(response.error, "error")
          } else {
            sendNotif("Der Warenkorb wurde aktualisiert.", "success")
          }
        },
        error: function (xhr) {
          const errorMessage =
            xhr.responseJSON && xhr.responseJSON.error
              ? xhr.responseJSON.error
              : "Es ist ein Fehler aufgetreten. Bitte versuche es erneut."

          sendNotif(errorMessage, "error")
        },
        complete: function () {
          if (!$addToCartButton.hasClass("bg-gray-300")) {
            $addToCartButton.prop("disabled", false)
          }
        }
      })
    })
  }
})