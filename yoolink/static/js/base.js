const menu = document.querySelector("#navbar-cta");

function toggleMenu() {
  if (menu.classList.contains("hidden")) {
    menu.classList.remove("hidden");
  } else {
    menu.classList.add("hidden");
  }
}

function acceptCookie() {
  window.YooLinkConsent && window.YooLinkConsent.acceptAll();
}

function refuseCookie() {
  window.YooLinkConsent && window.YooLinkConsent.rejectAll();
}

/** Notifications Button */

(function () {
  const $btn = $('#notif-button');
  const $menu = $('#notif-menu');

  function closeMenu() {
    $menu.addClass('hidden');
    $btn.attr('aria-expanded', 'false');
  }
  function openMenu() {
    $menu.removeClass('hidden');
    $btn.attr('aria-expanded', 'true');
  }
  function toggleMenu() {
    if ($menu.hasClass('hidden')) openMenu(); else closeMenu();
  }

  // Toggle on click
  $btn.on('click', function (e) {
    e.stopPropagation();
    toggleMenu();
  });

  // Click outside schließt
  $(document).on('click', function (e) {
    // Alles schließen, wenn Klick nicht im Wrapper ist
    if ($(e.target).closest('#notif-wrapper').length === 0) {
      closeMenu();
    }
  });

  // Esc schließt
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });

  // Optional: Schließen beim Tab-Focus raus
  $menu.on('keydown', function (e) {
    if (e.key === 'Tab') {
      // Wenn letzter Fokus rausfällt, schließen
      // (einfach: immer schließen)
      closeMenu();
    }
  });
})();

/** Leistungen Dropdown – Desktop */
(function () {
  const wrapper = document.querySelector('[data-leistungen-dropdown]');
  if (!wrapper) return;
  const button = wrapper.querySelector('#leistungenDropdownButtonDesktop');
  const menu = wrapper.querySelector('#leistungenDropdownMenuDesktop');
  const chevron = wrapper.querySelector('[data-leistungen-chevron]');
  if (!button || !menu) return;

  function close() {
    menu.classList.add('hidden');
    button.setAttribute('aria-expanded', 'false');
    if (chevron) chevron.classList.remove('rotate-180');
  }
  function open() {
    menu.classList.remove('hidden');
    button.setAttribute('aria-expanded', 'true');
    if (chevron) chevron.classList.add('rotate-180');
  }
  function toggle() {
    if (menu.classList.contains('hidden')) open(); else close();
  }

  button.addEventListener('click', function (e) {
    e.stopPropagation();
    toggle();
  });
  document.addEventListener('click', function (e) {
    if (!wrapper.contains(e.target)) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });
})();

/** Leistungen Dropdown – Mobile (Akkordeon) */
(function () {
  const wrapper = document.querySelector('[data-leistungen-dropdown-mobile]');
  if (!wrapper) return;
  const button = wrapper.querySelector('#leistungenDropdownButtonMobile');
  const menu = wrapper.querySelector('#leistungenDropdownMenuMobile');
  const chevron = wrapper.querySelector('[data-leistungen-chevron-mobile]');
  if (!button || !menu) return;

  button.addEventListener('click', function () {
    const isOpen = !menu.classList.contains('hidden');
    if (isOpen) {
      menu.classList.add('hidden');
      button.setAttribute('aria-expanded', 'false');
      if (chevron) chevron.classList.remove('rotate-180');
    } else {
      menu.classList.remove('hidden');
      button.setAttribute('aria-expanded', 'true');
      if (chevron) chevron.classList.add('rotate-180');
    }
  });
})();

/**
 * Auto-Hide-Navbar:
 * - Beim Herunterscrollen blendet die Navbar aus.
 * - Beim Hochscrollen erscheint sie wieder sauber von oben (zum Navigieren).
 * - Ganz oben ist sie immer sichtbar.
 */
(function () {
  var nav = document.getElementById('mainNavbar');
  if (!nav) return;

  var mobileMenu = document.getElementById('navbar-cta');
  var ticking = false;
  var DELTA = 6; // winzige Scrollbewegungen ignorieren

  // Robust die aktuelle Scroll-Position lesen – egal ob das Fenster,
  // <html> oder <body> der eigentliche Scroll-Container ist
  // (manche Seiten setzen html/body overflow, wodurch nicht das window scrollt).
  function getScrollTop() {
    var de = document.documentElement;
    var b = document.body;
    return window.pageYOffset
      || Math.max(de ? de.scrollTop : 0, b ? b.scrollTop : 0)
      || 0;
  }

  var lastY = getScrollTop();

  function update() {
    ticking = false;
    var y = getScrollTop();

    // Mobiles Menü offen -> Navbar sichtbar lassen
    if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
      nav.style.transform = '';
      lastY = y;
      return;
    }

    // Ganz oben immer zeigen
    if (y <= 0) {
      nav.style.transform = '';
      lastY = 0;
      return;
    }

    if (Math.abs(y - lastY) < DELTA) return;

    if (y > lastY && y > nav.offsetHeight) {
      // runter scrollen -> ausblenden
      nav.style.transform = 'translateY(-100%)';
    } else {
      // hoch scrollen -> einblenden
      nav.style.transform = '';
    }
    lastY = y;
  }

  function onScroll() {
    if (!ticking) {
      window.requestAnimationFrame(update);
      ticking = true;
    }
  }

  // capture:true fängt Scroll-Events auch dann ab, wenn nicht das window,
  // sondern ein innerer Container (html/body) scrollt.
  window.addEventListener('scroll', onScroll, { passive: true, capture: true });
})();
