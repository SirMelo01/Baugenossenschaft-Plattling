/**
 * Button-Slot-Editor: öffnet ein geteiltes Modal an der jeweiligen Stelle
 * im Seiten-Editor, um den platzierten Button auszuwählen & anzupassen
 * (Text, Design, Icon, Link, Tab). Persistiert wird beim Seiten-Speichern
 * über save-text.js (.content-button data-Attribute).
 */
(function ($) {
  if (!$('#buttonSlotModal').length) return;

  const COLOR_CLASSES = {
    blue: 'bg-blue-600 text-white',
    navy: 'bg-blue-900 text-white',
    dark: 'bg-slate-900 text-white',
    emerald: 'bg-emerald-600 text-white',
    white: 'bg-white text-blue-900 ring-1 ring-gray-200',
    outline: 'border border-blue-900 bg-transparent text-blue-900',
    link: '',
  };
  const COLOR_LABELS = {
    blue: 'Blau', navy: 'Dunkelblau', dark: 'Schwarz', emerald: 'Grün',
    white: 'Weiß', outline: 'Umrandet', link: 'Textlink',
  };
  const EDIT_URL = $('#buttonSlotModal').data('edit-url') || '';

  let $activeSlot = null;

  function esc(v) { return $('<div>').text(v == null ? '' : v).html(); }

  function renderSummary($slot) {
    const id = $slot.attr('data-button-id');
    const $sum = $slot.find('.slot-summary');
    if (!id || id === '-1') {
      $sum.text('Kein Button – Standard-Link wird angezeigt')
        .addClass('text-slate-400').removeClass('text-slate-800');
      return;
    }
    const text = $slot.attr('data-text') || '(ohne Text)';
    const color = $slot.attr('data-color') || 'navy';
    $sum.text('„' + text + '“ · ' + (COLOR_LABELS[color] || color))
      .addClass('text-slate-800').removeClass('text-slate-400');
  }

  function setSwatch(color) {
    $('#bsm-color').val(color);
    $('#bsm-swatches .bsm-swatch').each(function () {
      const active = $(this).data('color') === color;
      $(this).toggleClass('border-blue-500 ring-2 ring-blue-100', active)
        .toggleClass('border-slate-200', !active);
    });
  }

  function setLinkType(type) {
    $('#buttonSlotModal .bsm-linktype').each(function () {
      const active = $(this).data('link-type') === type;
      $(this).toggleClass('border-blue-500 bg-blue-50 text-blue-700', active)
        .toggleClass('border-slate-200 text-slate-600', !active);
    });
    $('#bsm-internal').toggleClass('hidden', type !== 'internal');
    $('#bsm-external').toggleClass('hidden', type !== 'external');
  }

  function updatePreview() {
    const text = $('#bsm-text').val() || 'Button';
    const color = $('#bsm-color').val() || 'navy';
    const icon = ($('#bsm-icon').val() || '').trim();
    let html, cls;
    if (color === 'link') {
      cls = 'inline-flex items-center text-sm font-medium text-blue-900';
      html = esc(text) + (icon ? ' <i class="' + esc(icon) + ' ml-1"></i>' : '');
    } else {
      cls = 'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-bold ' + (COLOR_CLASSES[color] || COLOR_CLASSES.navy);
      html = (icon ? '<i class="' + esc(icon) + '"></i>' : '') + esc(text);
    }
    $('#bsm-preview').attr('class', 'pointer-events-none ' + cls).html(html);
  }

  function updateDesignerLink(id) {
    const $a = $('#bsm-designer-link');
    if (id && id !== '-1' && EDIT_URL) {
      $a.attr('href', EDIT_URL.replace('/0/', '/' + id + '/')).removeClass('hidden');
    } else {
      $a.addClass('hidden');
    }
  }

  function loadFields(d) {
    $('#bsm-select').val(d.id || '-1');
    $('#bsm-text').val(d.text || '');
    setSwatch(d.color || 'navy');
    $('#bsm-icon').val(d.icon || '');
    if (d.pageLink) {
      setLinkType('internal');
      $('#bsm-page-link').val(String(d.pageLink));
      $('#bsm-url').val('');
    } else {
      setLinkType('external');
      $('#bsm-url').val(d.url || '');
      $('#bsm-page-link').val('');
    }
    $('#bsm-newtab').prop('checked', d.target === '_blank');
    updateDesignerLink(d.id);
    updatePreview();
  }

  function openModal($slot) {
    $activeSlot = $slot;
    $('#bsm-slot-label').text($slot.attr('data-label') || '');
    loadFields({
      id: $slot.attr('data-button-id'),
      text: $slot.attr('data-text'),
      color: $slot.attr('data-color'),
      icon: $slot.attr('data-icon'),
      url: $slot.attr('data-url'),
      pageLink: $slot.attr('data-page-link'),
      target: $slot.attr('data-target'),
    });
    $('#buttonSlotModal').addClass('is-open');
  }

  function closeModal() {
    $('#buttonSlotModal').removeClass('is-open');
    $activeSlot = null;
  }

  function applyModal() {
    if (!$activeSlot) return;
    const id = $('#bsm-select').val() || '-1';
    const internal = !$('#bsm-internal').hasClass('hidden');
    $activeSlot.attr('data-button-id', id);
    $activeSlot.attr('data-text', $('#bsm-text').val() || '');
    $activeSlot.attr('data-color', $('#bsm-color').val() || 'navy');
    $activeSlot.attr('data-icon', ($('#bsm-icon').val() || '').trim());
    $activeSlot.attr('data-page-link', internal ? ($('#bsm-page-link').val() || '') : '');
    $activeSlot.attr('data-url', internal ? '' : ($('#bsm-url').val() || '').trim());
    $activeSlot.attr('data-target', $('#bsm-newtab').is(':checked') ? '_blank' : '_self');
    renderSummary($activeSlot);
    closeModal();
  }

  $(function () {
    $('.content-button').each(function () { renderSummary($(this)); });

    $(document).on('click', '.open-button-modal', function () {
      openModal($(this).closest('.content-button'));
    });
    $('#bsm-close, #bsm-cancel').on('click', closeModal);
    $('#buttonSlotModal').on('click', function (e) { if (e.target === this) closeModal(); });
    $('#bsm-apply').on('click', applyModal);

    $('#bsm-select').on('change', function () {
      const o = $(this).find('option:selected');
      loadFields({
        id: $(this).val(),
        text: o.attr('data-text'),
        color: o.attr('data-color'),
        icon: o.attr('data-icon'),
        url: o.attr('data-url'),
        pageLink: o.attr('data-page-link'),
        target: o.attr('data-target'),
      });
    });
    $('#bsm-swatches').on('click', '.bsm-swatch', function () {
      setSwatch($(this).data('color'));
      updatePreview();
    });
    $('#buttonSlotModal').on('click', '.bsm-linktype', function () {
      setLinkType($(this).data('link-type'));
      updatePreview();
    });
    $('#bsm-text, #bsm-icon, #bsm-url').on('input', updatePreview);
    $('#bsm-page-link').on('change', updatePreview);

    $(document).on('keydown', function (e) {
      if (e.key === 'Escape' && $('#buttonSlotModal').hasClass('is-open')) closeModal();
    });
  });
})(jQuery);
