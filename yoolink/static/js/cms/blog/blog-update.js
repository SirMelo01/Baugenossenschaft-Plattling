$(document).ready(function () {
    /* UPDATE */

    function loadUpdateDetails() {
        const $blogContent = $('#blogContent')

        const delSpan = $('<span class="absolute top-0 right-0 inline-block px-2 py-1 text-sm font-semibold text-white bg-red-500 rounded-full not-sortable z-40 hover:cursor-pointer del-elem"><i class="bi bi-trash"></i></span>')
        const moveHandle = $('<span class="absolute top-0 right-1/2 inline-block px-2 py-1 text-sm text-white bg-blue-500 rounded-full not-sortable z-40 hover:cursor-pointer handle"><i class="bi bi-arrows-move"></i></span>');

        $blogContent.empty()

        // Get Code
        sendNotif('Daten werden geladen...', "notice")
        $.ajax({
            type: 'GET',
            url: 'getCode/',
            success: function (data) {
                // Handle the success response
                if (window.YooLinkBlogMarkdown) {
                    YooLinkBlogMarkdown.setMarkdown(data.markdown || '');
                }
                if (window.YooLinkBlogBuilder && typeof YooLinkBlogBuilder.applyCode === 'function') {
                    YooLinkBlogBuilder.applyCode(data.code || []);
                    sendNotif('Daten wurden geladen', "success")
                    // Unsaved-Guard erst scharf schalten, wenn der Inhalt aufgebaut ist.
                    if (window.UnsavedGuard) setTimeout(function () { UnsavedGuard.arm(); }, 0);
                    return;
                }
                $.each(data.code, function (index, element) {
                    const $container = $('<div class="relative">')
                    switch (element.name) {
                        case 'title-1':
                            $container.attr('element-type', 'title-1')
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $('<input/>', {
                                type: "text",
                                class: "title-1 my-3 text-2xl font-bold text-gray-900 w-full px-4 py-2 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
                                placeholder: "Titel 1",
                                value: element.value
                            }).appendTo($container)
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $blogContent.append($container)
                            break;
                        case 'title-2':
                            $container.attr('element-type', 'title-2')
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $('<input/>', {
                                type: "text",
                                class: "title-2 text-xl font-semibold w-full px-4 py-2 my-3 border border-gray-300 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent relative",
                                placeholder: "Titel 2",
                                value: element.value
                            }).appendTo($container)
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $blogContent.append($container)
                            break;
                        case 'title-3':
                            $container.attr('element-type', 'textArea')
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $('<textarea/>', {
                                id: "textArea" + index,
                                class: "textArea w-full px-4 py-2 my-3 rounded-2xl border border-gray-300 focus:outline-none focus:border-blue-500 min-h-[5rem]",
                                placeholder: "Text",
                            }).text(element.value).appendTo($container)
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $blogContent.append($container)
                            break;
                        case 'textArea':
                            $container.attr('element-type', 'textArea')
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $('<textarea/>', {
                                id: "textArea" + index,
                                class: "textArea w-full px-4 py-2 my-3 rounded-2xl border border-gray-300 focus:outline-none focus:border-blue-500 min-h-[5rem]",
                                placeholder: "Text",
                            }).text(element.value).appendTo($container)
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $blogContent.append($container)
                            break;
                        case 'image':
                            $container.attr('element-type', 'image').addClass("w-fit my-3")
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-img"><i class="bi bi-pencil-square"></i></span>'))
                            $('<img>', {
                                title: element.attributes.title,
                                class: "rounded-2xl w-auto h-80",
                                src: element.attributes.src,
                            }).css('width', element.css.width).css('height', element.css.height).appendTo($container)
                            $container.height(element.css.height)
                            $container.width(element.css.width)
                            // Click event handler for the span with class del-elem
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $container.find('.edit-img').click(function () {
                                openBlogImageModal($(this).siblings('img'));
                            });
                            $blogContent.append($container)
                            break;
                        case 'yt-video':
                            $container.attr('element-type', 'yt-video').addClass("w-fit py-4 my-3")
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-youtube"><i class="bi bi-pencil-square"></i></span>'))
                            $('<iframe/>', element.attributes).appendTo($container)
                            $container.height(element.attributes.height + 20)
                            $container.width(element.attributes.width)
                            $container.find('iframe').removeClass("my-8").addClass("rounded-2xl")
                            // Click event handler for the span with class del-elem
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $container.find('.edit-youtube').click(function () {
                                $editYoutube = $(this).siblings('iframe');

                                height = $editYoutube[0].style.height ? $editYoutube[0].style.height : $editYoutube.height();
                                width = $editYoutube[0].style.width ? $editYoutube[0].style.width : $editYoutube.width();

                                $('#youtubeHeight').val(height)
                                $('#youtubeWidth').val(width)

                                $('#youtubeURL').val($editYoutube.attr('src'))
                                $('#youtubeText').val($editYoutube.attr('title'))
                                $('#youtubeModal').toggleClass("hidden");
                            });
                            $blogContent.append($container)
                            break;
                        case 'galery':
                            $container.attr('element-type', 'galery').addClass("w-full my-4")
                            $container.append(delSpan.clone()).append(moveHandle.clone())
                            $container.append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-slider"><i class="bi bi-pencil-square"></i></span>'))
                            const $carouselContainer = $('<div class="carousel rounded-lg">')
                            $container.css("height", element.css.height).css("width", element.css.width)
                            $(element.images).each(function (index, elementX) {
                                const $divContainer = $('<div>')
                                $('<img>', {
                                    src: elementX,
                                    class: "rounded-xl",
                                }).css("height", element.css.height).css("width", element.css.width).appendTo($divContainer)
                                $carouselContainer.append($divContainer)
                            })
                            $container.append($carouselContainer)
                            $container.find('.del-elem').click(function () {
                                $(this).parent().remove()
                            });
                            $container.find('.edit-slider').click(function () {
                                openBlogGalleryModal($(this).siblings('.carousel'));
                            });
                            $blogContent.append($container)
                            break;
                        case 'video':
                            $container.attr('element-type', 'video').addClass("py-4 my-3")
                                .append(delSpan.clone()).append(moveHandle.clone())
                                .append($('<span class="absolute top-0 left-0 inline-block px-2 py-1 text-sm text-white bg-orange-500 rounded-full not-sortable z-40 hover:cursor-pointer edit-cmsvideo"><i class="bi bi-pencil-square"></i></span>'));

                            // <video> Element mit allen Attributen & CSS
                            const $videoEl = $('<video>');
                            if (element.attributes) {
                                $.each(element.attributes, function (k, v) {
                                    if (k === 'class') {
                                        $videoEl.addClass(v); // behält "my-8 rounded-2xl" etc.
                                    } else if (k.startsWith('data-')) {
                                        // SEO Felder: data-*
                                        $videoEl.attr(k, v);
                                        const dataKey = k.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
                                        $videoEl.data(dataKey, v);
                                    } else if (['autoplay', 'muted', 'loop', 'playsinline', 'controls'].includes(k)) {
                                        // Boolean-Attribute als prop
                                        $videoEl.prop(k, true);
                                    } else {
                                        $videoEl.attr(k, v);
                                    }
                                });
                            }
                            if (element.css) {
                                if (element.css.width) $videoEl.css('width', element.css.width);
                                if (element.css.height) $videoEl.css('height', element.css.height);
                            }
                            $container.append($videoEl);

                            // Delete
                            $container.find('.del-elem').click(function () { $(this).parent().remove() });

                            // Edit: aktuelles Video -> Modal mit Props füllen + ggf. vorselektieren
                            $container.find('.edit-cmsvideo').click(function () {
                                openBlogVideoModal($(this).parent());
                            });

                            $blogContent.append($container);
                            break;
                        case 'file':
                            // JSON aus receiveContent liefert:
                            // element.type === 'a'
                            // element.attributes.href, title, data-id, data-ext, class ...
                            // element.value = sichtbarer Titel
                            $container.attr('element-type', 'file').addClass('my-3');
                            $container.append(delSpan.clone()).append(moveHandle.clone());

                            // Icon anhand der Extension auswählen
                            const ext = (element.attributes && (element.attributes['data-ext'] || element.attributes['data- ext'])) || '';
                            const iconCls = fileIconForExt(ext);

                            // Anchor neu aufbauen (wir nehmen die gespeicherten Attribute)
                            const $a = $('<a>');
                            if (element.attributes) {
                                $.each(element.attributes, function (k, v) {
                                    if (k === 'class') $a.addClass(v);
                                    else $a.attr(k, v);
                                });
                            } else {
                                // Fallback, falls alte Datenstruktur
                                $a.attr({
                                    href: element.href || '#',
                                    target: '_blank',
                                    rel: 'noopener',
                                    class: 'file-attachment flex items-center gap-2 p-3 border rounded my-3'
                                });
                            }

                            // Icon + Titel in den Link packen
                            $a.prepend($('<i>').addClass('bi ' + iconCls + ' text-xl mr-2'));
                            const titleText = element.value || element.attributes?.title || 'Datei';
                            $a.append($('<span class="file-title truncate">').text(titleText));

                            $container.append($a);

                            // Löschen des Blocks
                            $container.find('.del-elem').click(function () { $(this).parent().remove(); });

                            $blogContent.append($container);
                            break;

                        // Add more cases for other types if needed
                        default:
                            break;
                    }
                });
                sendNotif('Daten wurden geladen', "success")
                loadSlick()
                loadNicEditors()
                // ... Perform any other actions with the data ...
                // Schutz erst scharf schalten, wenn der Inhalt fertig aufgebaut ist
                // (setTimeout 0, damit die MutationObserver-Callbacks vorher durch sind).
                if (window.UnsavedGuard) setTimeout(function () { UnsavedGuard.arm(); }, 0);
            },
            error: function (xhr, status, error) {
                // Handle the error if the request fails
                sendNotif('Fehler beim Laden der Daten. Lade die Seite bitte nochmal neu', "error")
                if (window.UnsavedGuard) setTimeout(function () { UnsavedGuard.arm(); }, 0);
            }
        });

    }

    loadUpdateDetails()
    // Initialize your carousel with configuration options

    $('#updateBlog').click(function () {
        // Check for errors
        enableSpinner($(this))

        const title = $('#blogTitle').val()
        const description = ($('#blogDescription').val() || '').trim()
        var files = $('#titleImgUpload').prop("files");

        if (title === "" || title === undefined) {
            sendNotif("Bitte gebe einen Titel für den Blog (rechts) ein.", "error");
            disableSpinner($(this))
            return;
        }

        if (description === "") {
            sendNotif("Bitte gebe eine Beschreibung für den Blog ein.", "error")
            disableSpinner($(this))
            return;
        }

        var csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

        if (window.YooLinkBlogMarkdown && YooLinkBlogMarkdown.isMarkdownMode()) {
            if (YooLinkBlogMarkdown.getMarkdown().trim() === "") {
                sendNotif("Bitte füge Markdown-Inhalt ein.", "error")
                disableSpinner($(this))
                return;
            }

            var markdownFormData = new FormData();
            markdownFormData.append('title', $('#blogTitle').val());
            markdownFormData.append('active', $('#activeSwitch').is(':checked'));
            markdownFormData.append('description', description);
            markdownFormData.append('title_image_alt', $('#titleImageAlt').val() || '');
            markdownFormData.append('title_image_title', $('#titleImageTitle').val() || '');
            markdownFormData.append('title_image_caption', $('#titleImageCaption').val() || '');
            YooLinkBlogMarkdown.appendMarkdownToFormData(markdownFormData);
            if (files.length > 0) markdownFormData.append('title_image', files[0]);

            $.ajax({
                type: "POST",
                url: "update/",
                data: markdownFormData,
                processData: false,
                contentType: false,
                dataType: "json",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                },
                success: function (response) {
                    if (response.error) {
                        sendNotif(response.error, "error")
                        $(document).trigger("blogSaveError")
                        return;
                    }
                    sendNotif("Der Blog wurde erfolgreich gespeichert", "success")
                    $(document).trigger("blogSaved")
                },
                error: function (xhr, status, error) {
                    console.error("Request failed:", error);
                    const message = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Es kam zu einem unerwarten Fehler. Versuche es später nochmal";
                    sendNotif(message, "error")
                    $(document).trigger("blogSaveError")
                },
                complete: function () {
                    disableSpinner($('#updateBlog'))
                }
            });
            return;
        }

        // Get Code
        const $blockContent = $('#blogContent')
        // Select the first element with attr("element-type") = 'textArea' within elements with class 'relative' in 'blockContent'
        var $firstTextArea = $blockContent.children('.relative').find('.textArea').first();
        if ($firstTextArea.length == 0) {
            sendNotif("Es muss mindestens ein gefüllter Text hinzugefügt werden!", "error")
            disableSpinner($(this))
            return;
        }
        var firstTextAreaId = $firstTextArea.attr('id')
        var firstRtInstance = window.BlogRichText ? BlogRichText.instanceById(firstTextAreaId) : null
        var firstTextAreaContent = firstRtInstance ? firstRtInstance.getContent() : ''
        var tempDiv = document.createElement("div");
        tempDiv.innerHTML = firstTextAreaContent;
        var plainText = tempDiv.textContent || tempDiv.innerText || ""
        // Überprüfen, ob ein Element gefunden wurde
        if (plainText.trim() === '') {
            // Ein Element wurde gefunden
            // Du kannst hier weiter mit 'firstTextArea' arbeiten
            sendNotif("Es muss mindestens ein gefüllter Text hinzugefügt werden!", "error")
            disableSpinner($(this))
            return;
        }
        const content = receiveContent($blockContent)
        // Load to previewBody
        const $directCodeContainer = $('<div>')
        const $modalBody = $('<div class"space-y-6">')
        const blogLayout = $('#blogLayout').val()
        if (blogLayout.includes('center')) {
            $modalBody.addClass('flex flex-col items-center')
        } else if (blogLayout.includes('right')) {
            $modalBody.removeClass('items-center').addClass('flex flex-col items-end')
        } else {
            $modalBody.removeClass('flex flex-col items-center items-end')
        }
        content.forEach(function (element) {
            // Führe eine Aktion für jedes Element aus
            const $elem = (element.name !== "galery") ? getWebElement(element) : getGaleryElement(element)
            $modalBody.append($elem);
        });
        $directCodeContainer.append($modalBody)
        // Create a new FormData object
        var formData = new FormData();
        formData.append('title', $('#blogTitle').val());
        formData.append('body', $directCodeContainer.html());
        formData.append('code', JSON.stringify(content));
        formData.append('active', $('#activeSwitch').is(':checked'));
        formData.append('description', description);
        formData.append('title_image_alt', $('#titleImageAlt').val() || '');
        formData.append('title_image_title', $('#titleImageTitle').val() || '');
        formData.append('title_image_caption', $('#titleImageCaption').val() || '');
        if (files.length > 0) formData.append('title_image', files[0]);
        // Send the Ajax POST request //
        $.ajax({
            type: "POST",
            url: "update/",
            data: formData,
            processData: false, // Prevent jQuery from processing the data
            contentType: false, // Prevent jQuery from setting the content type
            dataType: "json",
            beforeSend: function (xhr) {
                // Add the CSRF token to the request headers
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            },
            success: function (response) {
                // Handle the success response here
                if (response.error) {
                    sendNotif(response.error, "error")
                    $(document).trigger("blogSaveError")
                    return;
                }
                sendNotif("Der Blog wurde erfolgreich gespeichert", "success")
                $(document).trigger("blogSaved")
            },
            error: function (xhr, status, error) {
                // Handle the error response here
                console.error("Request failed:", error);
                sendNotif("Es kam zu einem unerwarten Fehler. Versuche es später nochmal", "error")
                $(document).trigger("blogSaveError")
            },
            complete: function (result, status) {
                disableSpinner($('#updateBlog'))
            }
        });

    })
})
