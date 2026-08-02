/**
 * BlogRichText
 * ============
 * Ersetzt den alten nicEditor im Blog-Builder durch Quill 2 (wie im Produkt-Editor).
 * Jeder Text-Block (`.textArea`) wird zu einem eigenständigen Quill-Editor.
 *
 * Bewusst klein gehaltene API, die exakt die nicEditor-Aufrufe ersetzt, die der
 * Blog-Code nutzte:
 *   BlogRichText.mountAll()            -> alle noch nicht initialisierten .textArea aufsetzen
 *   BlogRichText.mount(el, html)       -> einen Editor aufsetzen (optional Start-HTML)
 *   BlogRichText.instanceById(id)      -> { getContent(): "<html>" }  (wie myNicEditor.instanceById)
 *   BlogRichText.create(id, html)      -> jQuery-<div class="textArea" id=id> (Start-HTML als innerHTML)
 *
 * Inhalt wird als semantisches HTML gespeichert (Quill.getSemanticHTML) – dasselbe
 * Format wie zuvor (HTML-String im `value` des `textArea`-Elements).
 */
(function (window, $) {
    "use strict";

    var instances = {};   // id -> Quill
    var IMAGE_UPLOAD_URL = "/cms/upload/post";

    function csrfToken() {
        return $('input[name="csrfmiddlewaretoken"]').val() || "";
    }

    /* Reicher Funktionsumfang – mindestens das, was nicEdit bot, plus mehr:
       Font, Größe, Überschriften, Fett/Kursiv/Unterstr./Durchgestr., Farbe & Hintergrund,
       Hoch-/Tiefstellen, Listen, Einzug, Ausrichtung, Zitat, Code, Link, Bild, (Formel), Clean. */
    function toolbarContainer() {
        var rows = [
            [{ font: [] }, { size: [] }],
            [{ header: [2, 3, 4, false] }],
            ["bold", "italic", "underline", "strike"],
            [{ color: [] }, { background: [] }],
            [{ script: "sub" }, { script: "super" }],
            [{ list: "ordered" }, { list: "bullet" }],
            [{ indent: "-1" }, { indent: "+1" }],
            [{ align: [] }],
            ["blockquote", "code-block"],
            ["link", "image"]
        ];
        // Formeln nur anbieten, wenn KaTeX geladen ist (sonst wirft Quill beim Einfügen).
        if (typeof window.katex !== "undefined") {
            rows.push(["formula"]);
        }
        rows.push(["clean"]);
        return rows;
    }

    // Bild einfügen: öffnet den normalen CMS-Bild-Dialog (Mediathek + Upload),
    // genau wie beim Bild-Element. Das gewählte Bild wird inline eingefügt.
    function imageHandler() {
        var quill = this.quill;
        if (typeof window.openBlogEditorImagePicker === "function") {
            window.openBlogEditorImagePicker(quill);
            return;
        }
        // Fallback (sollte im Blog nie nötig sein): direkter Datei-Upload.
        var input = document.createElement("input");
        input.type = "file";
        input.accept = "image/png,image/jpeg,image/jpg,image/webp,image/gif";
        input.onchange = function () {
            var file = input.files && input.files[0];
            if (!file) return;
            var data = new FormData();
            data.append("file", file);
            $.ajax({
                url: IMAGE_UPLOAD_URL, type: "POST", data: data,
                contentType: false, processData: false, dataType: "json",
                beforeSend: function (xhr) { xhr.setRequestHeader("X-CSRFToken", csrfToken()); },
                success: function (response) {
                    var url = response && response.image ? (response.image.url || response.image.upload_url) : (response && response.url);
                    if (!url) return;
                    var range = quill.getSelection(true) || { index: quill.getLength() };
                    quill.insertEmbed(range.index, "image", url, "user");
                    quill.setSelection(range.index + 1, 0, "user");
                }
            });
        };
        input.click();
    }

    function mount(el, initialHtml) {
        if (!el || typeof window.Quill === "undefined") return null;
        if (el.tagName === "TEXTAREA") return null;   // Quill nur auf Container-Divs
        if (el.dataset && el.dataset.rtMounted === "1") return instances[el.id] || null;

        // Start-Inhalt: explizit übergeben oder bereits im Container vorhandenes HTML.
        var initial = (typeof initialHtml === "string") ? initialHtml : el.innerHTML;
        el.innerHTML = "";

        var quill = new window.Quill(el, {
            theme: "snow",
            placeholder: "Text – Formatierungen, Listen, Links, Bilder" + (typeof window.katex !== "undefined" ? ", Formeln" : "") + " …",
            modules: {
                toolbar: {
                    container: toolbarContainer(),
                    handlers: { image: imageHandler }
                }
            }
        });

        if (initial && initial.trim()) {
            quill.clipboard.dangerouslyPasteHTML(initial, "silent");
            quill.history.clear();
        }

        // Änderungen an den UnsavedGuard / Builder weiterreichen.
        quill.on("text-change", function (delta, old, source) {
            if (source === "user") {
                $("#blogContent").trigger("yoolink:builder-change");
            }
        });

        if (el.dataset) el.dataset.rtMounted = "1";
        el.classList.add("blog-rt-mounted");
        if (el.id) instances[el.id] = quill;
        return quill;
    }

    function mountAll() {
        $(".textArea").each(function () {
            if (this.dataset && this.dataset.rtMounted === "1") return;
            mount(this);
        });
    }

    function instanceById(id) {
        var quill = instances[id];
        if (!quill) return null;
        return {
            getContent: function () { return quill.getSemanticHTML(); },
            setContent: function (html) {
                quill.setText("");
                if (html && html.trim()) quill.clipboard.dangerouslyPasteHTML(html, "silent");
            },
            quill: quill
        };
    }

    /* Baut den Text-Block: Wrapper .blog-rt mit innerem Ziel-Div (.textArea, id).
       Quill wird auf das innere Div gesetzt -> Toolbar + Container liegen beide im
       Wrapper (sonst landet die Toolbar als Geschwister AUSSERHALB und das CSS greift nicht). */
    function create(id, initialHtml) {
        var $target = $('<div></div>').attr("id", id).addClass("textArea");
        if (initialHtml) $target.html(initialHtml);
        return $('<div class="blog-rt"></div>').append($target);
    }

    window.BlogRichText = {
        mount: mount,
        mountAll: mountAll,
        instanceById: instanceById,
        create: create
    };
})(window, jQuery);
