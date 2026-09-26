(function () {
    'use strict';

    function init() {
        const fileIcons = {
            pdf: 'bi-file-earmark-pdf-fill text-red-600',
            doc: 'bi-file-earmark-word-fill text-blue-700',
            docx: 'bi-file-earmark-word-fill text-blue-700',
            xls: 'bi-file-earmark-excel-fill text-green-600',
            xlsx: 'bi-file-earmark-excel-fill text-green-600',
            zip: 'bi-file-earmark-zip-fill text-slate-600',
            rar: 'bi-file-earmark-zip-fill text-slate-600',
            txt: 'bi-file-earmark-text-fill text-slate-600',
            jpg: 'bi-file-earmark-image-fill text-amber-600',
            jpeg: 'bi-file-earmark-image-fill text-amber-600',
            png: 'bi-file-earmark-image-fill text-amber-600',
            mp4: 'bi-file-earmark-play-fill text-purple-600'
        };
        document.querySelectorAll('article a[href], .bgp-article .rich-text a[href]').forEach(function (link) {
            const match = link.getAttribute('href').split(/[?#]/, 1)[0].match(/\.([a-z0-9]+)$/i);
            const extension = (link.getAttribute('data-ext') || (match && match[1]) || '').replace(/^\./, '').toLowerCase();
            if (!fileIcons[extension] && !link.classList.contains('file-attachment')) return;
            link.classList.add('file-attachment');
            if (link.querySelector('i.bi')) return;
            const icon = document.createElement('i');
            icon.className = 'bi ' + (fileIcons[extension] || 'bi-file-earmark-fill text-slate-600');
            icon.setAttribute('aria-hidden', 'true');
            link.prepend(icon);
        });

        const $ = window.jQuery;
        if ($ && $.fn && $.fn.slick) {
            $('article .carousel, .bgp-article .rich-text .carousel').each(function () {
                const carousel = $(this);
                if (carousel.hasClass('slick-initialized') || !carousel.children().length) return;
                carousel.slick({
                    dots: true,
                    arrows: true,
                    infinite: true,
                    slidesToShow: 1,
                    slidesToScroll: 1,
                    autoplay: carousel.attr('data-autoplay') !== 'false',
                    autoplaySpeed: Number(carousel.attr('data-autoplay-speed')) || 3000,
                    adaptiveHeight: true
                });
            });

            $('.next-button').on('click', function () {
                $(this).closest('.carousel-container').find('.carousel.slick-initialized').slick('slickNext');
            });
            $('.prev-button').on('click', function () {
                $(this).closest('.carousel-container').find('.carousel.slick-initialized').slick('slickPrev');
            });
        }
        if (window.Prism) window.Prism.highlightAll();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
