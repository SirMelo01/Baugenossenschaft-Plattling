$(document).ready(function () {
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
                answer: answer
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
    var innerElement = $('<div>').addClass('group flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow lg:flex-row lg:items-center');

    // Drag-Handle
    innerElement.append($('<span class="handle grid h-9 w-9 flex-shrink-0 cursor-grab place-items-center rounded-lg text-slate-300 transition hover:bg-slate-100 hover:text-slate-500 active:cursor-grabbing" title="Zum Sortieren ziehen"><i class="bi bi-grip-vertical text-xl"></i></span>'));

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

    innerElement.append(fieldsWrap, buttonElement);
    faqElement.append(innerElement);
    $('#simpleList').append(faqElement)
}