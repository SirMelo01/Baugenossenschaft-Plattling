/**
 * CMS shell interactions for the redesigned sidebar layout.
 *
 * Opening the mobile drawer is handled by cms.js (#mobile-menu-button toggles
 * #mobile-menu). This file adds the closing affordances that an off-canvas
 * drawer needs: backdrop click, close button, navigating via a link, and Esc.
 */
(function () {
    "use strict";

    function closeDrawer() {
        var $menu = $("#mobile-menu");
        if (!$menu.length || $menu.hasClass("hidden")) return;
        $menu.addClass("hidden");
        $("#mobile-menu-open-icon").removeClass("hidden");
        $("#mobile-menu-close-icon").addClass("hidden");
        $("#mobile-menu-button").attr("aria-expanded", "false");
    }

    $(document).ready(function () {
        // Backdrop, explicit close button, and link clicks all close the drawer.
        $("#mobile-menu").on("click", "[data-drawer-backdrop], [data-drawer-close], a[href]", function () {
            closeDrawer();
        });

        // Esc closes the drawer.
        $(document).on("keydown", function (e) {
            if (e.key === "Escape") closeDrawer();
        });

        // Safety: if the viewport grows to desktop, make sure the drawer is closed.
        var mq = window.matchMedia("(min-width: 1024px)");
        function handleMq(e) {
            if (e.matches) closeDrawer();
        }
        if (mq.addEventListener) {
            mq.addEventListener("change", handleMq);
        } else if (mq.addListener) {
            mq.addListener(handleMq);
        }
    });
})();
