(function () {
    'use strict';

    function init() {
        const field = document.getElementById('blogDescription');
        const count = document.getElementById('blogDescriptionCount');
        const notice = document.getElementById('blogDescriptionNotice');
        if (!field || !count || !notice) return;

        const limit = 400;
        function update(event) {
            if (field.value.length > limit) {
                field.value = field.value.slice(0, limit);
                notice.textContent = 'Die Beschreibung war zu lang und wurde auf 400 Zeichen gekürzt.';
                notice.classList.remove('hidden');
                if (event && event.inputType === 'insertFromPaste' && typeof window.sendNotif === 'function') {
                    window.sendNotif('Beschreibung auf 400 Zeichen gekürzt.', 'warning');
                }
            } else if (field.value.length < limit) {
                notice.textContent = '';
                notice.classList.add('hidden');
            }
            const words = field.value.trim() ? field.value.trim().split(/\s+/u).length : 0;
            count.textContent = words + ' Wörter · ' + field.value.length + ' / ' + limit + ' Zeichen';
            count.classList.toggle('text-amber-700', field.value.length === limit);
            count.classList.toggle('text-slate-500', field.value.length < limit);
        }

        field.addEventListener('input', update);
        update();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
