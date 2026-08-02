/*
 * Logo-Kontrast im CMS.
 *
 * Das Seiten-Logo ist oft fürs dunkle Navbar-Design in Weiß gehalten und wäre
 * auf hellem CMS-Hintergrund unsichtbar. Statt eines festen Hintergrunds messen
 * wir hier die durchschnittliche Helligkeit der (sichtbaren) Logo-Pixel und
 * setzen dahinter eine kontrastierende Fläche:
 *   - helles/weißes Logo  -> dunkler Backdrop
 *   - dunkles Logo        -> heller Backdrop
 *   - mittel/farbig        -> dezenter neutraler Backdrop
 *
 * Markup:
 *   <img data-logo-contrast ...>                 -> Hintergrund am <img> selbst
 *   <img data-logo-contrast data-logo-target="surface"> innerhalb von
 *   <... data-logo-surface>                      -> Hintergrund am Eltern-Container
 */
(function () {
    "use strict";

    var DARK = "#1f2937";   // slate-800: Backdrop für helle Logos
    var LIGHT = "#f8fafc";  // slate-50:  Backdrop für dunkle Logos
    var LIGHT_THRESHOLD = 145; // 0..255 mittlere Luminanz -> darüber gilt Logo als "hell"

    function resolveTarget(img) {
        if (img.getAttribute("data-logo-target") === "surface") {
            return img.closest("[data-logo-surface]") || img;
        }
        return img;
    }

    function averageLuminance(img) {
        var size = 24;
        var canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, size, size);

        var data;
        try {
            data = ctx.getImageData(0, 0, size, size).data;
        } catch (e) {
            return null; // z.B. fremde Domain ohne CORS -> Canvas "tainted"
        }

        var lumSum = 0;
        var alphaSum = 0;
        for (var i = 0; i < data.length; i += 4) {
            var alpha = data[i + 3] / 255;
            if (alpha < 0.15) continue; // transparente Bereiche ignorieren
            var lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
            lumSum += lum * alpha;
            alphaSum += alpha;
        }
        if (alphaSum === 0) return null; // komplett transparent
        return lumSum / alphaSum;
    }

    function applyContrast(img) {
        var avg = averageLuminance(img);
        if (avg === null) return;
        var target = resolveTarget(img);
        target.style.backgroundColor = avg > LIGHT_THRESHOLD ? DARK : LIGHT;
    }

    function process(img) {
        if (img.dataset.logoContrastDone === "1") return;
        img.dataset.logoContrastDone = "1";
        if (img.complete && img.naturalWidth) {
            applyContrast(img);
        } else {
            img.addEventListener("load", function () { applyContrast(img); }, { once: true });
        }
    }

    function init() {
        document.querySelectorAll("img[data-logo-contrast]").forEach(process);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
