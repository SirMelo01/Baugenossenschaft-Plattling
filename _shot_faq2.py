import os
from django.test import Client
from django.contrib.auth import get_user_model
from yoolink.ycms.models import FAQ
created=[]
if FAQ.objects.count()==0:
    for q,a in [("Wie lange dauert die Erstellung meiner Website?","In der Regel 2–4 Wochen, abhängig vom Umfang."),
                ("Bekomme ich auch Hosting und Wartung?","Ja, wir bieten optionale Hosting- und Wartungspakete an."),
                ("Kann ich Inhalte selbst pflegen?","Natürlich – über das integrierte CMS pflegst du alles selbst.")]:
        created.append(FAQ.objects.create(question=q, answer=a))
U = get_user_model()
u = U.objects.filter(is_superuser=True).first() or U.objects.first()
c = Client(); c.force_login(u)
r = c.get('/cms/faq/', HTTP_HOST='localhost')
html = r.content.decode()
for m in ['class="handle','class="question','class="answer','edit-faq',' delete ','list-group-item']:
    print(('OK ' if m in html else 'MISS '), m)
html = html.replace('href="/', 'href="http://localhost:8000/').replace('src="/', 'src="http://localhost:8000/')
html = html.replace('</body>', '<style>[id*="ookie"],[class*="ookie"]{display:none!important;}#notif-menu,#userDropDown{display:none!important;}</style></body>', 1)
d='media/_design_preview'; os.makedirs(d, exist_ok=True)
open(d+'/faq.html','w',encoding='utf-8').write(html)
# cleanup temp faqs
for f in created: f.delete()
print('temp_faqs_deleted', len(created))
