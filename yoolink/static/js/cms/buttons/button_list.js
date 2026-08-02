/**
 * Button-Übersicht: Löschen von Buttons + CRUD für Seiten-Links (Modal, AJAX).
 */
$(function () {
    const $page = $('#buttonListPage');
    if (!$page.length) {
        return;
    }

    const csrfToken = $('#pageLinkForm input[name=csrfmiddlewaretoken]').val();
    let editingLinkId = null;
    let pendingDelete = null;

    function urlFromTemplate(template, id) {
        return template.replace('/0/', `/${id}/`);
    }

    function postJson(url, payload) {
        return $.ajax({
            url: url,
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            contentType: 'application/json',
            data: JSON.stringify(payload || {}),
        });
    }

    function ajaxErrorMessage(xhr) {
        return (xhr.responseJSON && xhr.responseJSON.error) || 'Aktion fehlgeschlagen';
    }

    // ---------- Seiten-Link Modal ----------

    function openPageLinkModal(linkId) {
        editingLinkId = linkId || null;
        if (editingLinkId) {
            const $row = $(`.page-link-row[data-link-id="${editingLinkId}"]`);
            $('#pageLinkModalTitle').text('Seiten-Link bearbeiten');
            $('#pageLinkTitle').val($row.data('title'));
            $('#pageLinkPath').val($row.data('path'));
            $('#pageLinkAnchor').val($row.data('anchor'));
        } else {
            $('#pageLinkModalTitle').text('Seiten-Link hinzufügen');
            $('#pageLinkForm')[0].reset();
        }
        $('#pageLinkModal').removeClass('hidden');
        $('#pageLinkTitle').trigger('focus');
    }

    function closePageLinkModal() {
        $('#pageLinkModal').addClass('hidden');
        editingLinkId = null;
    }

    $('#addPageLink').on('click', function () {
        openPageLinkModal(null);
    });

    $('#pageLinkList').on('click', '.edit-page-link', function () {
        openPageLinkModal($(this).closest('.page-link-row').data('linkId'));
    });

    $('#closePageLinkModal, #cancelPageLinkModal').on('click', closePageLinkModal);
    $('#pageLinkModal').on('click', function (e) {
        if (e.target === this) {
            closePageLinkModal();
        }
    });

    $('#pageLinkForm').on('submit', function (e) {
        e.preventDefault();

        const payload = {
            title: ($('#pageLinkTitle').val() || '').trim(),
            path: ($('#pageLinkPath').val() || '').trim(),
            anchor: ($('#pageLinkAnchor').val() || '').trim(),
        };
        const url = editingLinkId
            ? urlFromTemplate($page.data('pagelinkEditUrlTemplate'), editingLinkId)
            : $page.data('pagelinkCreateUrl');

        postJson(url, payload)
            .done(function () {
                // Neu laden, damit Button-Karten und Auswahllisten konsistent bleiben
                window.location.hash = 'seiten-links';
                window.location.reload();
            })
            .fail(function (xhr) {
                sendNotif(ajaxErrorMessage(xhr), 'error');
            });
    });

    // ---------- Löschen (Buttons + Seiten-Links) ----------

    function openDeleteModal(message, onConfirm) {
        pendingDelete = onConfirm;
        $('#confirmDeleteMessage').text(message);
        $('#confirmDeleteModal').removeClass('hidden');
    }

    function closeDeleteModal() {
        $('#confirmDeleteModal').addClass('hidden');
        pendingDelete = null;
    }

    $('#cancelDelete').on('click', closeDeleteModal);
    $('#confirmDeleteModal').on('click', function (e) {
        if (e.target === this) {
            closeDeleteModal();
        }
    });

    $('#confirmDelete').on('click', function () {
        if (pendingDelete) {
            pendingDelete();
        }
    });

    $('#buttonGrid').on('click', '.delete-button', function () {
        const $card = $(this).closest('.button-card');
        const buttonId = $card.data('buttonId');
        const name = $(this).data('name');

        openDeleteModal(`Der Button „${name}“ wird dauerhaft gelöscht.`, function () {
            postJson(urlFromTemplate($page.data('buttonDeleteUrlTemplate'), buttonId))
                .done(function () {
                    closeDeleteModal();
                    $card.remove();
                    if (!$('#buttonGrid .button-card').length) {
                        $('#buttonEmptyState').removeClass('hidden');
                    }
                    sendNotif('Der Button wurde gelöscht', 'success');
                })
                .fail(function (xhr) {
                    sendNotif(ajaxErrorMessage(xhr), 'error');
                });
        });
    });

    $('#pageLinkList').on('click', '.delete-page-link', function () {
        const $row = $(this).closest('.page-link-row');
        const linkId = $row.data('linkId');
        const title = $row.data('title');

        openDeleteModal(`Der Seiten-Link „${title}“ wird gelöscht. Buttons, die ihn nutzen, verlieren ihr Linkziel.`, function () {
            postJson(urlFromTemplate($page.data('pagelinkDeleteUrlTemplate'), linkId))
                .done(function () {
                    closeDeleteModal();
                    window.location.hash = 'seiten-links';
                    window.location.reload();
                })
                .fail(function (xhr) {
                    sendNotif(ajaxErrorMessage(xhr), 'error');
                });
        });
    });
});
