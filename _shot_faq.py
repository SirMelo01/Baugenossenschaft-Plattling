import os
from django.test import Client
from django.contrib.auth import get_user_model
U = get_user_model()
u = U.objects.filter(is_superuser=True).first() or U.objects.first()
c = Client()
c.force_login(u)
r = c.get('/cms/faq/', HTTP_HOST='localhost')
print('status', r.status_code)
html = r.content.decode()
for m in ['id="simpleList"','id="save-btn"','id="add-btn"','id="editModal"','class="modal-container','id="closeModal"','id="updateSingleFAQ"','class="handle','class="question','class="answer','edit-faq','list-group-item']:
    print(('OK ' if m in html else 'MISS '), m)
html = html.replace('href="/', 'href="http://localhost:8000/').replace('src="/', 'src="http://localhost:8000/')
style = '<style>[id*="ookie"],[class*="ookie"]{display:none!important;}#notif-menu,#userDropDown{display:none!important;}</style></body>'
html = html.replace('</body>', style, 1)
d='media/_design_preview'; os.makedirs(d, exist_ok=True)
open(d+'/faq.html','w',encoding='utf-8').write(html)
print('wrote')
