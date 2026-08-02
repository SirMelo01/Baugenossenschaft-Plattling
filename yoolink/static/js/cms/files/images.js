var csrftoken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;

$(document).ready(function () {
    var $editImg = null;
    var imageViewSettings = {
        large: {
            gallery: 'mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 sm:mt-8',
            card: 'image-card relative overflow-hidden rounded-lg',
            link: 'image-link block',
            image: 'image-thumb h-64 w-full object-cover border rounded-lg shadow-lg',
            details: 'image-list-details hidden min-w-0 flex-1 pr-20',
            badge: 'image-format-badge absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full bg-white/95 px-2 py-1 text-xs font-semibold text-gray-700 shadow ring-1 ring-gray-200',
            mobileButton: 'generate-mobile absolute left-1/2 top-1/2 z-30 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-lg ring-2 ring-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300'
        },
        small: {
            gallery: 'mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 sm:mt-8',
            card: 'image-card relative overflow-hidden rounded-lg',
            link: 'image-link block',
            image: 'image-thumb h-36 w-full object-cover border rounded-lg shadow-md',
            details: 'image-list-details hidden min-w-0 flex-1 pr-20',
            badge: 'image-format-badge absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full bg-white/95 px-2 py-1 text-[10px] font-semibold text-gray-700 shadow ring-1 ring-gray-200',
            mobileButton: 'generate-mobile absolute left-1/2 top-1/2 z-30 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1.5 text-[10px] font-bold text-white shadow-lg ring-2 ring-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300'
        },
        list: {
            gallery: 'mt-6 grid grid-cols-1 gap-3 sm:mt-8',
            card: 'image-card relative flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 shadow-sm',
            link: 'image-link block h-20 w-28 flex-shrink-0 overflow-hidden rounded-md sm:h-24 sm:w-36',
            image: 'image-thumb h-full w-full rounded-md object-cover',
            details: 'image-list-details min-w-0 flex-1 pr-24',
            badge: 'image-format-badge hidden rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-gray-700 ring-1 ring-blue-100 sm:inline-flex sm:items-center sm:gap-1',
            mobileButton: 'generate-mobile absolute left-16 top-1/2 z-30 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1.5 text-[10px] font-bold text-white shadow-lg ring-2 ring-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300 sm:left-20'
        }
    };

    function setImageView(view) {
        var nextView = imageViewSettings[view] ? view : 'large';
        var settings = imageViewSettings[nextView];

        $('#imageGallery').attr('class', settings.gallery);
        $('.image-card').attr('class', settings.card);
        $('.image-link').attr('class', settings.link);
        $('.image-thumb').attr('class', settings.image);
        $('.image-list-details').attr('class', settings.details);
        $('.image-format-badge').attr('class', settings.badge);
        $('.generate-mobile').attr('class', settings.mobileButton);

        $('.image-view-btn').each(function () {
            var button = $(this);
            var isActive = button.data('view') === nextView;
            button.toggleClass('bg-blue-600 text-white border-blue-600 shadow-sm', isActive);
            button.toggleClass('bg-white text-gray-600 border-transparent hover:bg-gray-100', !isActive);
        });

        try {
            localStorage.setItem('ycms-image-view', nextView);
        } catch (error) {
            // localStorage can be unavailable in private or locked-down contexts.
        }
    }

    $('.image-view-btn').on('click', function () {
        setImageView($(this).data('view'));
    });

    var savedImageView = 'large';
    try {
        savedImageView = localStorage.getItem('ycms-image-view') || 'large';
    } catch (error) {
        savedImageView = 'large';
    }
    setImageView(savedImageView);

    $('.deleter').each(function () {
        $(this).on('click', function () {
            var elem = $(this);

            // SweetAlert Confirm
            Swal.fire({
                title: 'Bist du sicher?',
                text: 'Dieses Bild wird dauerhaft gelöscht.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Ja, löschen!',
                cancelButtonText: 'Abbrechen'
            }).then((result) => {
                if (result.isConfirmed) {
                    $.ajax({
                        url: 'delete/' + elem.attr('id') + '/',
                        method: 'POST',
                        data: {
                            csrfmiddlewaretoken: csrftoken,
                        },
                        success: function (response) {
                            console.log(response);
                            sendNotif("Das ausgewählte Bild wurde erfolgreich gelöscht", "success");
                            elem.closest('.relative').remove();
                        },
                        error: function (error) {
                            console.log(error);
                            sendNotif("Beim Löschen des Bildes ist etwas schief gelaufen", "error");
                        }
                    });
                }
            });
        });
    });



    $('.generate-mobile').each(function () {
        $(this).on('click', function () {
            var button = $(this);
            var imageId = button.data('id');
            var card = button.closest('.image-card');
            var image = card.find('img').first();
            var badge = card.find('.image-format-badge').first();

            button.prop('disabled', true);
            button.html('<i class="bi bi-arrow-repeat animate-spin"></i> Wird erstellt...');

            $.ajax({
                url: 'mobile/' + imageId + '/',
                method: 'POST',
                data: {
                    csrfmiddlewaretoken: csrftoken,
                },
                success: function (response) {
                    if (response.srcset) {
                        image.attr('srcset', response.srcset);
                        image.attr('sizes', '(min-width: 1280px) 25vw, (min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw');
                    }
                    if (response.mobile_url) {
                        image.attr('data-mobile-url', response.mobile_url);
                    }
                    badge.html(badge.text().trim() + ' <span class="text-blue-600">+ Mobil</span>');
                    button.remove();
                    sendNotif(response.success || "Mobile Variante wurde erstellt", "success");
                },
                error: function (error) {
                    var message = error.responseJSON && error.responseJSON.error
                        ? error.responseJSON.error
                        : "Mobile Variante konnte nicht erstellt werden";
                    button.prop('disabled', false);
                    button.html('<i class="bi bi-phone"></i> Mobil erstellen');
                    sendNotif(message, "error");
                }
            });
        });
    });

    $('#convertWebpImages').on('click', function () {
        var button = $(this);
        var originalHtml = button.html();
        button.prop('disabled', true).html('<i class="bi bi-arrow-repeat animate-spin"></i> Konvertiere...');

        $.ajax({
            url: 'convert-webp/',
            method: 'POST',
            data: {
                csrfmiddlewaretoken: csrftoken,
            },
            success: function (response) {
                var converted = response.converted_images || 0;
                var skipped = response.skipped_variants || 0;
                var suffix = skipped ? ' (' + skipped + ' Varianten übersprungen)' : '';
                sendNotif(converted + ' Bilder zu WebP konvertiert' + suffix, 'success');
                window.location.reload();
            },
            error: function () {
                button.prop('disabled', false).html(originalHtml);
                sendNotif('WebP-Konvertierung konnte nicht abgeschlossen werden', 'error');
            }
        });
    });

    // Klick-Handler für das aktuelle Element definieren
    $('#selectImg').on('click', function () {
        var elem = $(this)
        // Hier können Sie den Klick-Handler-Code für jedes Element schreiben
        if ($editImg === null) {
            sendNotif("Etwas ist schiefgelaufen. Versuche es später erneut.", "error")
            return;
        }
        $.ajax({
            url: 'update/' + $editImg.attr('key') + '/',
            method: 'POST',  // Methode auf "POST" setzen
            data: {
                // Daten, die an den Server gesendet werden sollen
                csrfmiddlewaretoken: csrftoken,
                title: $('#imgTitle').val(),
                place: $('#imgPlace').val()
            },
            success: function (response) {
                // Funktion, die ausgeführt wird, wenn die Anfrage erfolgreich ist
                if (response.success) {
                    sendNotif("Das ausgewählte Bild wurde erfolgreich bearbeitet!", "success")
                    $editImg.attr('title', $('#imgTitle').val())
                    $editImg.attr('place', $('#imgPlace').val())
                } else {
                    sendNotif(response.error, "error")
                }
                $('#editModal').addClass('hidden').removeClass('flex')

            },
            error: function (xhr) {
                // Serverseitige Fehlermeldung (z. B. "Bildtitel zu lang") bevorzugt anzeigen
                var msg = (xhr.responseJSON && xhr.responseJSON.error)
                    ? xhr.responseJSON.error
                    : "Beim Speichern des Bildes ist etwas schief gelaufen";
                sendNotif(msg, "error")
            }
        });
    });


    $('.edit-img').click(function () {
        // Find the parent div containing the image
        var parentDiv = $(this).closest('.relative');

        // Find the image element within the parent div
        var imgElement = parentDiv.find('img');

        // Get image source, title, and alt attributes
        var title = imgElement.attr('title');
        var place = imgElement.attr('place');
        var src = imgElement.attr('src');
        $editImg = imgElement

        if (place) {
            $('#imgPlace').val(place)
        } else {
            $('#imgPlace').val("nothing")
        }
        $('#imgTitle').val(title)

        // Vorschau befüllen
        $('#editPreview').attr('src', src || '');
        var fileName = (title && title.trim()) ? title : (src ? src.split('/').pop().split('?')[0] : 'Bild');
        $('#editPreviewName').text(decodeURIComponent(fileName));

        $('#editModal').removeClass('hidden').addClass('flex')
    })

    function closeEditModal() {
        $('#editModal').addClass('hidden').removeClass('flex')
    }

    $('#closeModal').click(closeEditModal)
    $('#cancelEdit').click(closeEditModal)

    // Close the modal when clicking outside of it
    const modalContainer = $('.modal-container');
    const editModal = $('#editModal');
    $(document).mouseup(function (e) {
        if (!modalContainer.is(e.target) && modalContainer.has(e.target).length === 0) {
            editModal.addClass('hidden').removeClass('flex');
        }
    });
});
