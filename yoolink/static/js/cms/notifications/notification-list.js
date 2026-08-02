
(function ($) {
    // === CSRF: sichtbaren Token bevorzugen, sonst ersten nehmen ===
    function getCsrfToken() {
        const $visible = $('[name=csrfmiddlewaretoken]:visible').first();
        const $csrf = $visible.length ? $visible : $('[name=csrfmiddlewaretoken]').first();
        return $csrf.val();
    }

    // Helpers -------------------------------------------------------
    function cap99(n) { return n > 99 ? '99+' : String(n); }

    function getUnreadCountFromDOM() {
        // bevorzugt via Klasse .unread auf .notif-item
        const viaClass = $('.notif-list .notif-item.unread').length;
        if (viaClass) return viaClass;
        // Fallback: blauer Hintergrund
        return $('.notif-list .notif-item.bg-blue-50').length;
    }

    function updatePageHeaderCount(newCount) {
        const $wrap = $('.js-page-count');
        const $txt  = $('.js-page-count-text');

        if (!$wrap.length) return; // falls Header nicht vorhanden

        if (newCount > 0) {
            $wrap.removeClass('hidden');
            $txt.text(cap99(newCount));
        } else {
            $txt.text('0');
            $wrap.addClass('hidden');
        }
    }

    function updateNavCounter(newCount) {
        const $btn = $('#notif-button');
        let $badge = $btn.find('.js-nav-badge');

        if (!newCount || newCount <= 0) {
            $badge.remove();
            $('#notif-menu .js-footer-count').remove();
            return;
        }
        if ($badge.length === 0) {
            $btn.append(
                '<span class="js-nav-badge absolute -top-1 -right-1 inline-flex min-w-[18px] h-[18px] items-center justify-center rounded-full bg-blue-500 px-1" title="Ungelesene">' +
                '<span class="js-nav-badge-text text-[10px] font-semibold text-white leading-none"></span>' +
                '</span>'
            );
            $badge = $btn.find('.js-nav-badge');
        }
        $badge.find('.js-nav-badge-text').text(cap99(newCount));

        // Dropdown-Footer-Zahl
        const $footerCount = $('#notif-menu .js-footer-count');
        if ($footerCount.length) {
            $footerCount.text('(' + cap99(newCount) + ')');
        } else {
            $('#notif-menu .border-t a span').append(' <span class="js-footer-count">(' + cap99(newCount) + ')</span>');
        }
    }

    function markAllAsReadInDOM() {
        const $items = $('.notif-list .notif-item');
        $items.removeClass('unread bg-blue-50 border-blue-100').addClass('bg-white border-gray-200');
        $items.find('.js-badge-new').remove();
        $items.find('span').filter(function () { return $(this).text().trim() === 'Neu'; }).remove();
        $('form[action*="/notifications/"][action$="/mark-read/"]').remove();
    }

    // === Alle als gelesen ===
    $(document).on('submit', '#mark-all-read-form', function (e) {
        e.preventDefault();
        const actionUrl = this.action;

        Swal.fire({
            title: "Wirklich alle als gelesen markieren?",
            text: "Diese Aktion markiert alle Benachrichtigungen als gelesen.",
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#3b82f6",  // blue-500
            cancelButtonColor: "#6b7280",   // gray-500
            confirmButtonText: "Ja, alle lesen",
            cancelButtonText: "Abbrechen",
        }).then((result) => {
            if (!result.isConfirmed) return;

            $.ajax({
                url: actionUrl,
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function () {
                    markAllAsReadInDOM();
                    updateNavCounter(0);
                    updatePageHeaderCount(0);
                    if (typeof sendNotif === 'function') {
                        sendNotif("Alle Benachrichtigungen wurden als gelesen markiert.", "success");
                    }
                },
                error: function () {
                    if (typeof sendNotif === 'function') {
                        sendNotif("Fehler beim Markieren. Bitte erneut versuchen.", "error");
                    } else {
                        alert('Fehler beim Markieren.');
                    }
                }
            });
        });
    });

    // === Einzelne als gelesen ===
    $(document).on('submit', 'form[action*="/notifications/"][action$="/mark-read/"]', function (e) {
        e.preventDefault();
        const $form = $(this);

        $.ajax({
            url: this.action,
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function () {
                const $item = $form.closest('.notif-item');
                // Hintergrund/Border „weiß“ machen
                $item.removeClass('unread bg-blue-50 border-blue-100').addClass('bg-white border-gray-200');
                // „Neu“-Badge entfernen
                $item.find('.js-badge-new').remove();
                $item.find('span').filter(function(){ return $(this).text().trim() === 'Neu'; }).remove();
                // Button entfernen
                $form.remove();

                const newCount = Math.max(getUnreadCountFromDOM(), 0);
                updateNavCounter(newCount);
                updatePageHeaderCount(newCount);

                if (typeof sendNotif === 'function') {
                    sendNotif("Benachrichtigung als gelesen markiert.", "success");
                }
            },
            error: function () {
                if (typeof sendNotif === 'function') {
                    sendNotif("Konnte nicht als gelesen markiert werden.", "error");
                }
            }
        });
    });

    // === Einzelne Spam-Nachricht als "Kein Spam" markieren ===
    $(document).on('submit', 'form[action*="/notifications/"][action$="/mark-ham/"]', function (e) {
        e.preventDefault();
        const $form = $(this);
        const $item = $form.closest('.notif-item');

        $.ajax({
            url: this.action,
            method: 'POST',
            headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
            },
            success: function () {
            // Aus der Spam-Liste entfernen
            $item.slideUp(150, function () {
                $(this).remove();
            });

            if (typeof sendNotif === 'function') {
                sendNotif("Benachrichtigung wurde aus dem Spam verschoben.", "success");
            } else if (typeof Swal !== 'undefined') {
                Swal.fire({
                title: "Aktualisiert",
                text: "Die Benachrichtigung wurde aus dem Spam entfernt.",
                icon: "success",
                confirmButtonColor: "#3b82f6" // blue-500
                });
            }
            },
            error: function () {
            if (typeof sendNotif === 'function') {
                sendNotif("Konnte nicht aus dem Spam entfernt werden.", "error");
            } else if (typeof Swal !== 'undefined') {
                Swal.fire({
                title: "Fehler",
                text: "Aktion fehlgeschlagen. Bitte erneut versuchen.",
                icon: "error",
                confirmButtonColor: "#3b82f6"
                });
            }
            }
        });
    });


    // === Einzelne in Spam verschieben ===
    $(document).on('submit', 'form[action*="/notifications/"][action$="/mark-spam/"]', function (e) {
        e.preventDefault();
        const $form = $(this);
        const $item = $form.closest('.notif-item');

        $.ajax({
            url: this.action,
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function () {
                // Element aus der Liste entfernen (Inbox zeigt ja kein Spam)
                $item.slideUp(150, function () {
                    $(this).remove();

                    // Unread-Count neu aus DOM bestimmen (nur nicht-Spam in dieser Liste)
                    const newCount = Math.max(getUnreadCountFromDOM(), 0);
                    updateNavCounter(newCount);
                    updatePageHeaderCount(newCount);
                });

                if (typeof sendNotif === 'function') {
                    sendNotif("Benachrichtigung wurde in den Spam verschoben.", "success");
                }
            },
            error: function () {
                if (typeof sendNotif === 'function') {
                    sendNotif("Konnte nicht in den Spam verschoben werden.", "error");
                }
            }
        });
    });

    // === Alle Spam-Benachrichtigungen löschen (SPAM) ===
    $(document).on('submit', '#spam-delete-all-form', function (e) {
        e.preventDefault();
        const actionUrl = this.action;

        Swal.fire({
            title: "Alle Spam-Benachrichtigungen löschen?",
            text: "Diese Aktion kann nicht rückgängig gemacht werden.",
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#e3342f", // rot
            cancelButtonColor: "#6b7280",  // gray-500
            confirmButtonText: "Ja, löschen",
            cancelButtonText: "Abbrechen",
        }).then((result) => {
            if (!result.isConfirmed) return;

            $.ajax({
                url: actionUrl,
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function () {
                    Swal.fire({
                        title: "Gelöscht",
                        text: "Alle Spam-Benachrichtigungen wurden gelöscht.",
                        icon: "success",
                        confirmButtonColor: "#3b82f6"
                    }).then(() => {
                        window.location.reload();
                    });
                },
                error: function () {
                    Swal.fire({
                        title: "Fehler",
                        text: "Löschen fehlgeschlagen. Bitte erneut versuchen.",
                        icon: "error",
                        confirmButtonColor: "#3b82f6"
                    });
                }
            });
        });
    });
})(jQuery);

// === Einzelne Notification löschen ===
$(document).on('click', '.js-del-notif', function (e) {
  e.preventDefault();
  const url = $(this).data('url');

  Swal.fire({
    title: "Benachrichtigung löschen?",
    text: "Dieser Vorgang kann nicht rückgängig gemacht werden.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#e3342f", // rot
    cancelButtonColor: "#6b7280",  // gray-500
    confirmButtonText: "Ja, löschen",
    cancelButtonText: "Abbrechen",
  }).then((result) => {
    if (!result.isConfirmed) return;

    $.ajax({
      url: url,
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'X-Requested-With': 'XMLHttpRequest'
      },
      success: function () {
        Swal.fire({
          title: "Gelöscht",
          text: "Die Benachrichtigung wurde entfernt.",
          icon: "success",
          confirmButtonColor: "#3b82f6" // blue-500
        }).then(() => {
          // Seite komplett neu laden (Filter/Pagination bleiben via URL erhalten)
          window.location.reload();
        });
      },
      error: function () {
        Swal.fire({
          title: "Fehler",
          text: "Löschen fehlgeschlagen. Bitte erneut versuchen.",
          icon: "error",
          confirmButtonColor: "#3b82f6"
        });
      }
    });
  });
});

function getCsrfToken() {
    const $visible = $('[name=csrfmiddlewaretoken]:visible').first();
    const $csrf = $visible.length ? $visible : $('[name=csrfmiddlewaretoken]').first();
    return $csrf.val();
}


