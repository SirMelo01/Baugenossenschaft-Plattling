import os
from django.test import Client
from django.contrib.auth import get_user_model
U=get_user_model(); u=U.objects.filter(is_superuser=True).first()
c=Client(); c.force_login(u)
h=c.get('/cms/blog/add/', HTTP_HOST='localhost').content.decode()
h=h.replace('href="/','href="http://localhost:8000/').replace('src="/','src="http://localhost:8000/')
sample = ('<h1 class="text-3xl font-bold">Warum dich gerade niemand findet</h1>'
          '<p>Wenn Menschen im Raum Deggendorf „Elektriker in der Nähe“ suchen, hat fast die Hälfte aller Google-Suchen eine lokale Absicht.</p>'
          '<h2 class="text-2xl font-bold">Was du nach diesem Artikel kannst</h2>'
          '<ul class="list-disc pl-6"><li>Dein Profil anlegen und verifizieren</li><li>Die Hebel kennen</li><li>Bewertungen sammeln</li></ul>')
# force preview modal open + fill body + hide cms chrome overlays/debug
inject = ('<style>#djDebug,#djDebugToolbar,#djDebugToolbarHandle{display:none!important;}[id*="ookie"],[class*="ookie"]{display:none!important;}#notif-menu,#userDropDown{display:none!important;}'
          '#previewModal{display:flex!important;}</style>'
          '<script>window.addEventListener("load",function(){document.getElementById("previewModal").classList.remove("hidden");document.getElementById("previewBody").innerHTML=' + repr(sample) + ';});</script></body>')
h=h.replace('</body>', inject, 1)
d='media/_design_preview'; os.makedirs(d,exist_ok=True)
open(d+'/blog_preview.html','w',encoding='utf-8').write(h); print('wrote')
