// Team-Verwaltung.
//
// Die Bildauswahl läuft über den zentralen Picker (js/cms/media-picker.js). Vorher gab
// es hier eine eigene, abgespeckte Kopie: ohne Paginierung (die Buttons im
// Modal waren wirkungslos, es stand dauerhaft "Seite 1"), mit einer Suche nur
// über die geladene Liste - und ein einfacher Klick hat das Bild sofort
// übernommen, statt es erst links in der Vorschau zu zeigen.

$(document).ready(function () {
    let memberIdToDelete = null;
    const $teamMemberModal = $('#teamMemberModal');
    const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    $('#bImageSelect').click(function () {
        if (!window.CmsMediaPicker) return;
        const currentId = $('#imagePreview').attr('imgId');

        window.CmsMediaPicker.open({
            title: 'Profilbild auswählen',
            subtitle: 'Bild anklicken, links prüfen und mit „Bild übernehmen“ einsetzen.',
            applyLabel: 'Bild übernehmen',
            currentImageId: currentId && currentId !== '-1' ? currentId : null,
            currentImageSrc: $('#imagePreview').attr('src') || '',
            onApply: function (image) {
                setTeamPreviewImage(image.url, image.id);
                sendNotif('Neues Bild ausgewählt', 'success');
            },
            onRemove: function () {
                setTeamPreviewImage('', '-1');
                sendNotif('Bild entfernt', 'success');
            }
        });
    });

    // Funktion zum Erstellen eines neuen Teammitglieds
    $('#bCreateNewMember').click(function () {
        $('#teamMemberForm')[0].reset();  // Formular zurücksetzen
        $('#memberId').val('');  // Member ID löschen
        $('#modalTitle').text('Neues Teammitglied erstellen');
        $('#modalSubmitLabel').text('Erstellen');
        setTeamPreviewImage('');  // Bildvorschau zurücksetzen
        openTeamMemberModal();  // Modal anzeigen
    });

    // Funktion zum Bearbeiten eines bestehenden Teammitglieds (Event-Delegation)
    $('#teamSortableGrid').on('click', '.edit-member', function () {
        const memberId = $(this).closest('.team-card').data('memberId');
        openEditModal(memberId);
    });

    // Klick-Event für das Löschen (Event-Delegation)
    $('#teamSortableGrid').on('click', '.delete-member', function () {
        memberIdToDelete = $(this).closest('.team-card').data('memberId');
        $('#confirmDeleteModal').removeClass('hidden');
    });

    // AJAX-Request zum Erstellen oder Aktualisieren eines Teammitglieds
    $('#teamMemberForm').submit(function (event) {
        event.preventDefault();

        const memberId = $('#memberId').val();
        const isNewMember = !memberId;
        const url = isNewMember ? 'create/' : `${memberId}/update/`;
        const method = isNewMember ? 'POST' : 'PUT';

        const formData = {
            'full_name': $('#full_name').val(),
            'position': $('#position').val(),
            'years_with_team': $('#years_with_team').val(),
            'age': $('#age').val(),
            'email': $('#email').val(),
            'note': $('#notes').val(),
            'active': $('#activeSwitch').is(':checked'),
            'image': $('#imagePreview').attr('src'),
            'csrfmiddlewaretoken': csrfToken
        };

        $.ajax({
            url: url,
            type: method,
            data: formData,
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (response) {
                sendNotif(response.success || 'Daten erfolgreich verarbeitet', "success");
                closeTeamMemberModal();

                if (isNewMember) {
                    const newId = response.member_id;

                    const statusText = formData.active ? 'Aktiv' : 'Inaktiv';
                    const statusClass = formData.active ? 'bg-emerald-500' : 'bg-amber-500';

                    const newMemberHtml = `
                        <div class="team-card group relative flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-slate-300 hover:shadow"
                            data-member-id="${newId}">

                            <span class="member-id hidden">${newId}</span>

                            <div class="relative aspect-[4/5] w-full overflow-hidden bg-slate-100">
                                <img src="${formData.image || ''}" alt="${escapeTeamHtml(formData.full_name)}" class="member-image h-full w-full object-cover" />

                                <button type="button"
                                    class="drag-handle absolute left-2 top-2 z-10 inline-flex cursor-move items-center justify-center rounded-lg bg-white/90 p-1.5 text-slate-600 shadow-sm backdrop-blur transition hover:bg-white"
                                    title="Zum Sortieren ziehen">
                                    <i class="bi bi-grip-vertical text-base leading-none"></i>
                                </button>

                                <span class="member-status absolute right-2 top-2 z-10 inline-flex items-center gap-1 rounded-full ${statusClass} px-2.5 py-0.5 text-xs font-semibold text-white shadow-sm">
                                    ${statusText}
                                </span>
                            </div>

                            <div class="flex flex-1 flex-col p-4">
                                <h3 class="member-name truncate font-semibold text-slate-900">${escapeTeamHtml(formData.full_name)}</h3>
                                <p class="member-position truncate text-sm font-medium text-blue-600">${escapeTeamHtml(formData.position || '')}</p>
                                <p class="member-years mt-1 text-xs text-slate-400">Dabei seit ${formData.years_with_team || 0}</p>

                                <div class="mt-auto flex gap-2 pt-4">
                                    <button type="button"
                                        class="edit-member inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700">
                                        <i class="bi bi-pencil-square"></i> Verwalten
                                    </button>
                                    <button type="button"
                                        class="delete-member inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-red-600 transition hover:border-red-200 hover:bg-red-50"
                                        title="Löschen">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                        `;

                    // Empty-State ausblenden und Karte anhängen (Events laufen über Delegation)
                    $('#teamEmptyState').addClass('hidden');
                    $('#teamSortableGrid').append(newMemberHtml);
                } else {
                    // Aktualisiere die vorhandenen Daten ohne Neuladen
                    const $card = $(`.team-card[data-member-id="${memberId}"]`);

                    $card.find('.member-image').attr('src', formData.image);
                    $card.find('.member-name').text(formData.full_name);
                    $card.find('.member-position').text(formData.position);
                    $card.find('.member-years').text(`Dabei seit ${formData.years_with_team}`);

                    $card.find('.member-status')
                        .text(formData.active ? 'Aktiv' : 'Inaktiv')
                        .removeClass('bg-emerald-500 bg-amber-500')
                        .addClass(formData.active ? 'bg-emerald-500' : 'bg-amber-500');
                }
            },
            error: function (error) {
                sendNotif((error.responseJSON && error.responseJSON.error) || 'Fehler beim Speichern der Daten.', "error");
            }
        });
    });

    // Klick-Event für Bestätigungs-Button im Bestätigungs-Modal
    $('#bConfirmDelete').click(function () {
        if (memberIdToDelete) {
            $.ajax({
                url: `${memberIdToDelete}/delete/`,
                type: 'DELETE',
                headers: { 'X-CSRFToken': csrfToken },
                success: function (response) {
                    sendNotif(response.success || 'Teammitglied erfolgreich gelöscht', "success");
                    $('#confirmDeleteModal').addClass('hidden');

                    // Entferne das gelöschte Teammitglied aus der Ansicht
                    $(`.team-card[data-member-id="${memberIdToDelete}"]`).remove();
                    if ($('#teamSortableGrid .team-card').length === 0) {
                        $('#teamEmptyState').removeClass('hidden');
                    }
                },
                error: function () {
                    sendNotif('Fehler beim Löschen des Teammitglieds', "error");
                    $('#confirmDeleteModal').addClass('hidden');
                }
            });
        }
    });

    // Create-Modal schließen, wenn außerhalb geklickt wird - aber nicht, solange
    // der Bild-Picker darüber liegt.
    $teamMemberModal.on('click', function (event) {
        const pickerOpen = window.CmsMediaPicker && window.CmsMediaPicker.isOpen();
        if (event.target === this && !pickerOpen) {
            closeTeamMemberModal();
        }
    });

    // Klick-Event für den Abbrechen-Button im Bestätigungs-Modal
    $('#bDeclineDelete').click(function () {
        $('#confirmDeleteModal').addClass('hidden');  // Bestätigungs-Modal schließen
        memberIdToDelete = null;  // memberId zurücksetzen
    });


    // SORTABLE
    let pendingTeamOrder = null; // merkt sich neue Reihenfolge, bis gespeichert
    const $saveOrderBtn = $('#bSaveTeamOrder');

    const grid = document.getElementById('teamSortableGrid');

    if (grid) {
        new Sortable(grid, {
            animation: 150,
            handle: '.drag-handle',
            draggable: '.team-card',
            onEnd: function () {
                // nur merken, NICHT speichern
                pendingTeamOrder = Array.from(grid.querySelectorAll('.team-card'))
                    .map(el => el.getAttribute('data-member-id'));

                // Save-Button aktivieren
                $saveOrderBtn.prop('disabled', false);
            }
        });
    }

    // Save per Klick
    $saveOrderBtn.on('click', function (e) {
        e.preventDefault();

        if (!pendingTeamOrder || pendingTeamOrder.length === 0) {
            sendNotif('Keine Änderungen zum Speichern', 'error');
            return;
        }

        $saveOrderBtn.prop('disabled', true);

        $.ajax({
            url: '/cms/team/reorder/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order: pendingTeamOrder }),
            beforeSend: function (xhr) {
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function () {
                sendNotif('Sortierung gespeichert', 'success');
                pendingTeamOrder = null; // Änderungen „verbraucht“
            },
            error: function (xhr) {
                console.error(xhr.responseText);
                sendNotif('Fehler beim Speichern der Sortierung', 'error');
                // Button wieder aktiv lassen, damit man nochmal speichern kann
                $saveOrderBtn.prop('disabled', false);
            }
        });
    });
});

// Modal öffnen/schließen
function openTeamMemberModal() {
    $('#teamMemberModal').removeClass('hidden').addClass('flex');
}

function closeTeamMemberModal() {
    $('#teamMemberModal').addClass('hidden').removeClass('flex');
}

function closeModal() {
    closeTeamMemberModal();
}

// Setzt das Vorschaubild im Teammitglied-Modal und schaltet den Platzhalter um
function setTeamPreviewImage(src, imgId) {
    const $imagePreview = $('#imagePreview');
    $imagePreview.attr('src', src || '');
    if (typeof imgId !== 'undefined') {
        $imagePreview.attr('imgId', imgId);
    }
    if (src) {
        $imagePreview.removeClass('hidden');
        $('#imagePreviewPlaceholder').addClass('hidden');
    } else {
        $imagePreview.addClass('hidden');
        $('#imagePreviewPlaceholder').removeClass('hidden');
    }
}

function escapeTeamHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Öffnet das Bearbeiten-Modal für ein Teammitglied und füllt es mit den vorhandenen Daten
function openEditModal(memberId) {
    // AJAX-Request, um die Daten des Teammitglieds zu laden
    $.ajax({
        url: `${memberId}/`,  // Endpoint, der die Daten des Teammitglieds bereitstellt
        type: 'GET',
        success: function (data) {
            // Fülle das Formular mit den vorhandenen Daten
            $('#memberId').val(memberId);
            $('#full_name').val(data.full_name);
            $('#position').val(data.position);
            $('#years_with_team').val(data.years_with_team);
            $('#age').val(data.age);
            $('#email').val(data.email);
            $('#notes').val(data.note);
            $('#activeSwitch').prop('checked', data.active);
            setTeamPreviewImage(data.image); // Setze Bildvorschau

            // Passe die Modalüberschrift und den Button an
            $('#modalTitle').text('Teammitglied bearbeiten');
            $('#modalSubmitLabel').text('Speichern');

            // Zeige das Modal an
            openTeamMemberModal();
        },
        error: function () {
            sendNotif('Fehler beim Laden der Teammitglied-Daten.', 'error');
        }
    });
}
