// Icons je Dateiendung - gleiche Zuordnung wie AnyFile.ICON_BY_EXTENSION, damit
// ein frisch angehaengter Anhang genauso aussieht wie nach dem Neuladen.
var FAQ_FILE_ICONS = {
    '.pdf': 'bi-file-earmark-pdf-fill',
    '.doc': 'bi-file-earmark-word-fill',
    '.docx': 'bi-file-earmark-word-fill',
    '.xls': 'bi-file-earmark-excel-fill',
    '.xlsx': 'bi-file-earmark-excel-fill',
    '.ppt': 'bi-file-earmark-ppt-fill',
    '.pptx': 'bi-file-earmark-ppt-fill',
    '.zip': 'bi-file-earmark-zip-fill',
    '.txt': 'bi-file-earmark-text-fill'
};

function faqFileIcon(ext) {
    return FAQ_FILE_ICONS[(ext || '').toLowerCase()] || 'bi-file-earmark-fill';
}

function faqFileChip(file) {
    var $chip = $('<span>')
        .addClass('faq-file inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 py-1.5 pl-2.5 pr-1.5')
        .attr('data-file-id', file.id);
    $chip.append($('<i>').addClass('bi ' + faqFileIcon(file.ext) + ' text-slate-500'));
    $chip.append($('<a>')
        .addClass('max-w-[16rem] truncate text-sm font-medium text-slate-700 hover:text-blue-700')
        .attr({ href: file.url || '#', target: '_blank', rel: 'noopener' })
        .text(file.display_name || file.title || file.filename || 'Datei'));
    $chip.append($('<button>')
        .addClass('faq-file-remove grid h-6 w-6 place-items-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600')
        .attr({ type: 'button', title: 'Anhang entfernen', 'aria-label': 'Anhang entfernen' })
        .html('<i class="bi bi-x-lg text-xs"></i>'));
    return $chip;
}

function faqFileIds($listItem) {
    return $listItem.find('.faq-file').map(function () {
        return $(this).attr('data-file-id');
    }).get();
}

$(document).ready(function () {
    // Datei anhaengen: der zentrale Datei-Dialog kann auch gleich hochladen, damit
    // man die FAQ-Seite zum Nachliefern einer PDF nicht verlassen muss.
    $(document).on('click', '.faq-file-add', function () {
        var $listItem = $(this).closest('.list-group-item');
        var $files = $listItem.find('.faq-files');

        if (!window.CmsDocumentPicker) {
            sendNotif('Der Datei-Dialog konnte nicht geladen werden', 'error');
            return;
        }

        window.CmsDocumentPicker.open({
            title: 'Datei anhängen',
            subtitle: 'Die Datei steht danach unter der Antwort zum Download.',
            applyLabel: 'Anhängen',
            onApply: function (file) {
                if (!file) { return; }
                if ($files.find('[data-file-id="' + file.id + '"]').length) {
                    sendNotif('Diese Datei hängt bereits an der Frage', 'info');
                    return;
                }
                $files.append(faqFileChip(file));
            }
        });
    });

    $(document).on('click', '.faq-file-remove', function () {
        $(this).closest('.faq-file').remove();
    });

    // Create Sortable FAQ List
    Sortable.create(simpleList, {
        animation: 150,
        ghostClass: 'blue-background-class',
        handle: '.handle', // handle's class
    });
    var csrftoken = $('input[name="csrfmiddlewaretoken"]').val();
    // Delete FAQ
    $(document).on("click", ".delete", function () {
        // Code for handling the click event on the "delete" button
        var $listItem = $(this).closest('.list-group-item')
        var id = $listItem.attr('data-id')
        $.ajax({
            url: 'delete/' + id + "/",
            type: 'POST',
            data: {
                csrfmiddlewaretoken: csrftoken,
            },
            dataType: 'json',
            success: function (response) {
                sendNotif("Das ausgewählte FAQ wurde erfolgreich gelöscht!", "success")
                if (response.success) { $listItem.remove() }
            },
            error: function (xhr, status, error) {
                sendNotif("Fehler beim Löschen des FAQ's", "error")
            }
        });
    });
    // Update FAQ
    $(document).on("click", ".update", function () {
        // Code for handling the click event on the "update" button
        var $listItem = $(this).closest('.list-group-item')
        var question = $listItem.find('.question').val()
        var answer = $listItem.find('.answer').val()
        var id = $listItem.attr('data-id')
        $.ajax({
            url: 'update/',
            type: 'POST',
            data: {
                'answer': answer,
                'question': question,
                'faq_id': id,
                'files': JSON.stringify(faqFileIds($listItem)),
                csrfmiddlewaretoken: csrftoken,
            },
            dataType: 'json',
            success: function (response) {
                sendNotif("Das ausgewählte FAQ wurde erfolgreich gespeichert!", "success")
            },
            error: function (xhr, status, error) {
                sendNotif("Fehler beim Speichern des FAQ's", "error")
            }
        });
    });
    // Save order
    $('#save-btn').click(function () {
        var faqs = [];
        $('#simpleList .list-group-item').each(function () {
            var question = $(this).find('.question').val()
            var answer = $(this).find('.answer').val()
            var id = $(this).attr('data-id')
            faqs.push({
                id: id,
                question: question,
                answer: answer,
                files: faqFileIds($(this))
            })
        });

        $.ajax({
            url: 'sort/',
            type: 'POST',
            data: { 'faqs': JSON.stringify(faqs), csrfmiddlewaretoken: csrftoken},
            dataType: 'json',
            success: function (response) {
                if(response.success) {
                    sendNotif("Das FAQ wurde erfolgreich gespeichert!", "success")
                } else {
                    sendNotif("Das FAQ konnte nicht gespeichert werden", "error")
                }  
            },
            error: function (xhr, status, error) {
                sendNotif("Fehler beim Speichern der Sortierung", "error")
            }
        });
    });

    // Create faq
    $('#add-btn').click(function () {
        $.ajax({
            url: 'update/',
            type: 'GET',
            data: { "question": "Frage", "answer": "Antwort" },
            success: function (response) {
                if (response.success) {
                    createFaq(response.id, response.answer, response.question)
                    sendNotif("Ein FAQ wurde erfolgreich hinzugefügt!", "success")
                }
            },
            error: function (xhr, status, error) {
                sendNotif("Fehler beim Hinzufügen eines neuen FAQ's", "error")
            }
        });
    });

    const modalContainer = $('.modal-container');
    const editModal = $('#editModal');
    $(document).mouseup(function (e) {
        if (!modalContainer.is(e.target) && modalContainer.has(e.target).length === 0) {
            editModal.addClass('hidden');
        }
    });

    /* Edit Modal Functions */
    $('#closeModal').click(function() {
        $('#editModal').addClass("hidden");
    });

    $('.edit-faq').click(function() {
        const $faq = $(this).closest('.list-group-item');
        const id = $faq.attr('data-id');
        const question = $faq.find('.question').val();
        const answer = $faq.find('.answer').val();

        // Add Data to Modal
        $('#question').val(question);
        $('#answer').val(answer);
        $('#updateSingleFAQ').attr('faq-id', id);

        // Save it
        $('#editModal').removeClass("hidden");
    });

    $('#updateSingleFAQ').click(function() {
        const question = $('#question').val();
        const answer = $('#answer').val();
        
        if(question != '' && answer != '') {
            const id = $(this).attr('faq-id');
            if(id==="-1") {
                sendNotif("Etwas ist schief gelaufen. Versuche es nochmal!", "error");
            } else {
                var element = $('[data-id="'+ id +'"]');
                if(element) {
                    element.find(".question").val(question);
                    element.find(".answer").val(answer);
                    $('#save-btn').click();
                } else {
                    sendNotif("Etwas ist schief gelaufen. Versuche es nochmal!", "error");
                }
            }
        } else {
            sendNotif("Bitte trage bei beiden etwas ein!", "error");
            return;
        }
        $('#editModal').addClass("hidden");

    })

});
function createFaq(id, answer, question) {
    // Leeren Zustand entfernen, falls vorhanden
    $('#faqEmptyState').remove();

    // create the element
    var faqElement = $('<div>').addClass('list-group-item').attr('data-id', id);
    var innerElement = $('<div>').addClass('group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow');
    var headRow = $('<div>').addClass('flex flex-col gap-3 lg:flex-row lg:items-center');

    // Drag-Handle
    headRow.append($('<span class="handle grid h-9 w-9 flex-shrink-0 cursor-grab place-items-center rounded-lg text-slate-300 transition hover:bg-slate-100 hover:text-slate-500 active:cursor-grabbing" title="Zum Sortieren ziehen"><i class="bi bi-grip-vertical text-xl"></i></span>'));

    // Eingaben (Frage / Antwort)
    var fieldsWrap = $('<div>').addClass('grid flex-1 gap-3 sm:grid-cols-2');

    var questionElement = $('<div>');
    questionElement.append($('<label>').addClass('mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-400').text('Frage'));
    var questionInput = $('<input>').attr({
        'type': 'text',
        'value': question,
        'placeholder': "Deine Frage",
        'class': 'question w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100'
    });
    questionElement.append(questionInput);

    var answerElement = $('<div>');
    answerElement.append($('<label>').addClass('mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-400').text('Antwort'));
    var answerInput = $('<input>').attr({
        'type': 'text',
        'value': answer,
        'placeholder': "Deine Antwort",
        'class': 'answer w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100'
    });
    answerElement.append(answerInput);
    fieldsWrap.append(questionElement, answerElement);

    // Aktionen
    var buttonElement = $('<div>').addClass('flex flex-shrink-0 items-center gap-2 lg:self-end');
    var updateButton = $('<button>').addClass('edit-faq inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 lg:flex-none').attr('type', 'button').html('<i class="bi bi-arrows-angle-expand"></i> Anzeigen');
    updateButton.click(function() {
        const $faq = $(this).closest('.list-group-item');
        const id = $faq.attr('data-id');
        const question = $faq.find('.question').val();
        const answer = $faq.find('.answer').val();

        // Add Data to Modal
        $('#question').val(question);
        $('#answer').val(answer);
        $('#updateSingleFAQ').attr('faq-id', id);

        // Save it
        $('#editModal').removeClass("hidden");
    });
    var deleteButton = $('<button>').addClass('delete inline-flex h-[38px] w-[38px] flex-shrink-0 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition hover:bg-rose-100').attr('type', 'button').attr('title', 'Löschen').attr('aria-label', 'Löschen').html('<i class="bi bi-trash"></i>');
    buttonElement.append(updateButton, deleteButton);

    headRow.append(fieldsWrap, buttonElement);

    // Anhang-Leiste wie im Template - neue FAQs koennen sofort Dateien bekommen.
    var filesRow = $('<div>').addClass('mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3');
    filesRow.append($('<span>').addClass('text-xs font-semibold uppercase tracking-wide text-slate-400').text('Anhänge'));
    filesRow.append($('<div>').addClass('faq-files flex flex-wrap items-center gap-2'));
    filesRow.append($('<button>')
        .addClass('faq-file-add inline-flex items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-600 transition hover:border-blue-400 hover:text-blue-700')
        .attr('type', 'button')
        .html('<i class="bi bi-paperclip"></i> Datei anhängen'));

    innerElement.append(headRow, filesRow);
    faqElement.append(innerElement);
    $('#simpleList').append(faqElement)
}