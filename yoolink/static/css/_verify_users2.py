from django.test import Client
from django.contrib.auth import get_user_model
U = get_user_model()
admin = U.objects.filter(is_superuser=True).first() or U.objects.first()
c = Client(); c.force_login(admin)

# GET renders 200 + new controls present
r = c.get('/cms/settings/users/', HTTP_HOST='localhost')
html = r.content.decode()
print('GET', r.status_code)
for m in ['js-user-update-form','js-user-status','js-user-card','cms-switch-track','peer-checked:[&>.chk]','js-user-save','X-Requested-With','peer sr-only']:
    print(('OK ' if m in html else 'MISS '), m)

# pick a target user to update (prefer a non-admin to avoid touching admin)
target = U.objects.exclude(id=admin.id).first() or admin
orig_name = target.name
orig_active = target.is_active

# AJAX update
r2 = c.post('/cms/settings/users/', {
    'action':'update','user_id':target.id,
    'username':target.username,'email':target.email or 'x@example.com',
    'full_name':'AJAX Testname','is_active':'on',
}, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_HOST='localhost')
print('AJAX update status', r2.status_code, 'ctype', r2.headers.get('Content-Type'))
print('AJAX body', r2.json())

# AJAX duplicate-username error path
other = U.objects.exclude(id=target.id).first()
if other:
    r3 = c.post('/cms/settings/users/', {
        'action':'update','user_id':target.id,
        'username':other.username,'email':target.email or 'x@example.com','full_name':'x','is_active':'on',
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_HOST='localhost')
    print('AJAX dup status', r3.status_code, r3.json())

# restore
target.refresh_from_db()
target.name = orig_name; target.is_active = orig_active
target.save(update_fields=['name','is_active'])
print('restored', target.username)
