from datetime import datetime
import json
import logging
import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from yoolink.forms import ContactForm
from yoolink.views import get_opening_hours
from yoolink.ycms.applications.blog.services import (
    blog_code_to_markdown,
    build_default_code_from_markdown,
    render_markdown_to_html,
)
from django.shortcuts import get_object_or_404, render, redirect
from yoolink.ycms.applications.shop.models import Order, Product
from yoolink.ycms.models import (
    FAQ,
    AnyFile,
    Blog,
    Button,
    CMS_PERMISSION_CHOICES,
    CMSRole,
    CMSUserRole,
    DeveloperApiConnectAuthorization,
    DeveloperApiKey,
    GaleryImage,
    Galerie,
    Message,
    OpeningHours,
    PageLink,
    PricingCard,
    PricingFeature,
    RecoveryBackup,
    TeamMember,
    UserSettings,
    VideoFile,
    WebsiteSettings,
    fileentry,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib import messages
from django.db.models import Sum, F, DecimalField
from django.urls import reverse
from django.http import FileResponse, Http404, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.http import HttpResponse
from .forms import fileform, Blogform
from django.conf import settings
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import DataError, DatabaseError, IntegrityError, models, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAdminUser
from drf_spectacular.utils import extend_schema
from django.core.mail import send_mail
from yoolink.users.models import User
from rest_framework.permissions import IsAuthenticated
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.utils import translation
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from random import SystemRandom
from yoolink.ycms.tasks import create_remote_recovery_backup, send_login_2fa_email
from yoolink.ycms.upload_validation import (
    validate_anyfile_upload,
    validate_image_upload,
    validate_subtitle_upload,
    validate_video_thumbnail_upload,
    validate_video_upload,
    validation_error_message,
)
from yoolink.ycms.permissions import cms_permission_required, ensure_system_roles, user_permissions
from yoolink.ycms.recovery import (
    build_backup_archive,
    get_recovery_overview,
    get_remote_backup_records,
    get_remote_backup_storage_slots,
    remote_backups_configured,
    restore_backup_archive,
    restore_remote_backup,
    restore_remote_backup_object,
)

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"
DESKTOP_IMAGE_MAX_DIMENSIONS = (1920, 1920)
MOBILE_IMAGE_MAX_DIMENSIONS = (900, 900)
DESKTOP_IMAGE_TARGET_KB = 500
MOBILE_IMAGE_TARGET_KB = 260
PNG_TO_JPEG_THRESHOLD_KB = 300


def upload_validation_error_response(error):
    return JsonResponse({"error": validation_error_message(error)}, status=400)


def get_active_language(request):
    """Holt die aktuelle Sprache aus dem Request oder setzt Fallback auf 'en'"""
    lang = get_language_from_request(request)  # Browser-Sprache holen
    available_languages = dict(settings.LANGUAGES)  # Unterstützte Sprachen aus settings.py

    if lang not in available_languages:
        lang = "en"  # Standard-Sprache setzen

    activate(lang)  # Sprache für diese Anfrage aktiv setzen
    return lang

@login_required
def cms_set_language(request, lang_code):
    """
    Sprache nur für das CMS setzen (ohne /en-Prefix).
    Nutzt Cookie (wie das eingebaute set_language).
    """
    available_languages = dict(settings.LANGUAGES)

    if lang_code not in available_languages:
        return JsonResponse({'error': 'Invalid language'}, status=400)

    # Sprache für diese Request aktivieren
    activate(lang_code)

    # Cookie setzen – LocaleMiddleware liest das beim nächsten Request
    response = JsonResponse({'message': 'Language changed', 'language': lang_code})
    response.set_cookie(
        getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language"),
        lang_code,
        max_age=60 * 60 * 24 * 30,  # 30 Tage
        path="/",
    )
    return response

def set_mt_fields(instance, lang, payload):
    """
    payload = dict mit evtl. Keys: title, description, alt_text, tags, place
    Setzt <field>_<lang>; für Default-Sprache zusätzlich das Basisfeld.
    """
    for field in ('title', 'description', 'alt_text', 'tags', 'place'):
        val = (payload.get(field) or '').strip()
        if val == '':
            continue
        setattr(instance, f'{field}_{lang}', val)
        if lang == DEFAULT_LANGUAGE:
            setattr(instance, field, val)

def ensure_video_slug(instance, source_title):
    """
    Erzeuge einen eindeutigen Slug, falls keiner gesetzt ist.
    Nutzt den übergebenen Titel (der in beliebiger Sprache sein kann),
    ohne das Basisfeld (title) zu überschreiben.
    """
    if instance.slug:
        return
    base_slug = slugify(source_title) or 'video'
    slug = base_slug
    i = 1
    while VideoFile.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{i}"
        i += 1
    instance.slug = slug

def get_or_create_translated_blog(request, id):
    lang = get_active_language(request)
    blog = get_object_or_404(Blog, id=id)

    # Finde Original
    original_blog = blog.original if blog.original else blog

    # Wenn Original bereits die richtige Sprache hat → zurückgeben
    if original_blog.language == lang:
        return original_blog

    # Prüfen ob Variante existiert
    variant = original_blog.translations.filter(language=lang).first()
    if variant:
        return variant

    # Neue Variante anlegen. Kein Sprach-Suffix im Slug – das Modell erzeugt
    # beim Speichern einen eindeutigen, suffixfreien Slug aus dem Titel (die
    # Sprache steckt bereits im URL-Pfad, z. B. /en/blog/...).
    new_blog = Blog.objects.create(
        title=original_blog.title,
        title_image=original_blog.title_image,
        title_image_alt=original_blog.title_image_alt,
        title_image_title=original_blog.title_image_title,
        title_image_caption=original_blog.title_image_caption,
        author=original_blog.author,
        body=original_blog.body,
        code=original_blog.code,
        markdown=original_blog.markdown,
        active=False,
        description=original_blog.description,
        language=lang,
        original=original_blog,
    )
    return new_blog

@login_required(login_url='login')
@cms_permission_required("media.edit")
def cms_files(request):
    data = {
        "file_count":  fileentry.objects.count(),
        'anyfile_count': AnyFile.objects.count(),
        'videofile_count': VideoFile.objects.count(),
    }
    return render(request, 'pages/cms/files/files.html', data)

@login_required(login_url='login')
def cms(request):

    # Ensure anonymous users are redirected to the CMS login.
    if not request.user.is_authenticated:
        return redirect(reverse(settings.LOGIN_URL) + f"?next={request.path}")
    if "dashboard.view" not in user_permissions(request.user):
        return HttpResponse("Du hast für das CMS keine Berechtigung.", status=403)

    context = {'form': None, 'last': None}

    if request.method == 'POST':
        if "media.edit" not in user_permissions(request.user):
            return HttpResponse("Du hast für Medien-Uploads keine Berechtigung.", status=403)
        form = fileform(request.POST, request.FILES)
        if form.is_valid():
            context['last'] = '\n'.join([f.name for f in request.FILES.getlist('file')])
            
            for file in request.FILES.getlist('file'):
                try:
                    validate_image_upload(file)
                except ValidationError as error:
                    context['last'] = validation_error_message(error)
                    break
                desktop_image = optimize_image_for_upload(
                    file,
                    max_dimensions=DESKTOP_IMAGE_MAX_DIMENSIONS,
                    max_size_kb=DESKTOP_IMAGE_TARGET_KB,
                    variant_suffix="desktop",
                )
                mobile_image = optimize_image_for_upload(
                    file,
                    max_dimensions=MOBILE_IMAGE_MAX_DIMENSIONS,
                    max_size_kb=MOBILE_IMAGE_TARGET_KB,
                    variant_suffix="mobile",
                )
                new_file = fileentry(
                    file=desktop_image,
                    mobile_file=mobile_image,
                    title=getattr(file, "name", "Bild"),
                )
                new_file.save()

    else:
        form = fileform()

    data = {
        "file_count":  fileentry.objects.count(),
        "button_count": Button.objects.count(),
        "galery_count":  Galerie.objects.count(),
        "blog_count": Blog.objects.filter(original__isnull=True).count(),
        "product_count": Product.objects.count(),
        "order_count": Order.objects.filter(verified=True).count(),
        "order_not_closed_count": Order.objects.exclude(status='COMPLETED').count(),
        'form': form,
        'anyfile_count': AnyFile.objects.count(),
        'videofile_count': VideoFile.objects.count()
    }
    return render(request, 'pages/cms/cms.html', data)


#########################################
############ Authentication #############
#########################################

User = get_user_model()

CMS_2FA_SESSION_USER_ID = "cms_2fa_user_id"
CMS_2FA_SESSION_BACKEND = "cms_2fa_backend"
CMS_2FA_SESSION_ATTEMPTS = "cms_2fa_attempts"
CMS_2FA_MAX_ATTEMPTS = 5

def _generate_2fa_code():
    return f"{SystemRandom().randrange(0, 1000000):06d}"

def _mask_email(email):
    if not email or "@" not in email:
        return email

    local_part, domain_part = email.split("@", 1)

    if len(local_part) <= 2:
        masked_local = local_part[0] + "*" * max(len(local_part) - 1, 1)
    else:
        masked_local = local_part[:2] + "*" * (len(local_part) - 2)

    return f"{masked_local}@{domain_part}"

def _store_login_2fa_session(request, authenticated_user):
    request.session[CMS_2FA_SESSION_USER_ID] = authenticated_user.id
    request.session[CMS_2FA_SESSION_BACKEND] = authenticated_user.backend
    request.session[CMS_2FA_SESSION_ATTEMPTS] = 0


def _clear_login_2fa_session(request):
    request.session.pop(CMS_2FA_SESSION_USER_ID, None)
    request.session.pop(CMS_2FA_SESSION_BACKEND, None)
    request.session.pop(CMS_2FA_SESSION_ATTEMPTS, None)

def _issue_login_2fa_code(user_settings, user):
    email = (user_settings.email or "").strip()

    if not email:
        raise ValidationError("Für die E-Mail-2FA ist keine E-Mail-Adresse hinterlegt.")

    validate_email(email)

    code = _generate_2fa_code()
    expires_at = timezone.now() + timedelta(minutes=10)

    user_settings.two_factor_email_code = code
    user_settings.two_factor_email_code_expires_at = expires_at
    user_settings.two_factor_email_verified = False
    user_settings.save(update_fields=[
        "two_factor_email_code",
        "two_factor_email_code_expires_at",
        "two_factor_email_verified",
    ])

    try:
        send_login_2fa_email.delay(
            recipient_email=email,
            recipient_name=user_settings.full_name or user.get_username(),
            code=code,
            expires_at=expires_at.isoformat(),
        )
    except Exception as exc:
        user_settings.two_factor_email_code = ""
        user_settings.two_factor_email_code_expires_at = None
        user_settings.save(update_fields=[
            "two_factor_email_code",
            "two_factor_email_code_expires_at",
        ])
        raise RuntimeError("Die Bestätigungs-E-Mail konnte nicht vorbereitet werden.") from exc

    return code, expires_at, email

def _queue_login_2fa_for_user(user_settings, user):
    code, expires_at, email = _issue_login_2fa_code(user_settings, user)
    return code, expires_at, email

def custom_logout(request):
    _clear_login_2fa_session(request)
    logout(request)
    return redirect("ycms:login")

def Login_Cms(request):
    if request.user.is_authenticated:
        return redirect("ycms:cms")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username and not password:
            login_error = "Bitte Nutzername und Passwort eingeben."
            messages.error(request, login_error)
            return render(
                request,
                "registration/login.html",
                {
                    "currentPath": request.get_full_path(),
                    "login_error": login_error,
                    "username_value": username,
                },
            )

        if not username:
            login_error = "Bitte einen Nutzernamen eingeben."
            messages.error(request, login_error)
            return render(
                request,
                "registration/login.html",
                {
                    "currentPath": request.get_full_path(),
                    "login_error": login_error,
                    "username_value": username,
                },
            )

        if not password:
            login_error = "Bitte ein Passwort eingeben."
            messages.error(request, login_error)
            return render(
                request,
                "registration/login.html",
                {
                    "currentPath": request.get_full_path(),
                    "login_error": login_error,
                    "username_value": username,
                },
            )

        authenticated_user = authenticate(
            request,
            username=username,
            password=password,
        )

        if authenticated_user is None:
            login_error = "Benutzername oder Passwort ist ungültig."
            messages.error(request, login_error)
            return render(
                request,
                "registration/login.html",
                {
                    "currentPath": request.get_full_path(),
                    "login_error": login_error,
                    "username_value": username,
                },
            )

        user_settings = _get_user_settings(authenticated_user)

        if user_settings.two_factor_email_enabled:
            try:
                _queue_login_2fa_for_user(user_settings, authenticated_user)
            except ValidationError as exc:
                return render(
                    request,
                    "registration/login.html",
                    {
                        "currentPath": request.get_full_path(),
                        "login_error": str(exc),
                        "username_value": username,
                    },
                )
            except RuntimeError:
                return render(
                    request,
                    "registration/login.html",
                    {
                        "currentPath": request.get_full_path(),
                        "login_error": "Der Sicherheitscode konnte nicht per E-Mail versendet werden.",
                        "username_value": username,
                    },
                )

            _store_login_2fa_session(request, authenticated_user)

            return redirect("ycms:login-2fa")

        login(request, authenticated_user)
        if user_settings.must_change_password:
            return redirect("ycms:password_change")
        return redirect("ycms:cms")

    return render(
        request,
        "registration/login.html",
        {
            "currentPath": request.get_full_path(),
        },
    )

def Login_Cms_2FA_Verify(request):
    pending_user_id = request.session.get(CMS_2FA_SESSION_USER_ID)
    backend = request.session.get(CMS_2FA_SESSION_BACKEND)

    if not pending_user_id or not backend:
        return redirect("ycms:login")

    try:
        pending_user = User.objects.get(id=pending_user_id)
    except User.DoesNotExist:
        _clear_login_2fa_session(request)
        return redirect("ycms:login")

    user_settings = _get_user_settings(pending_user)
    masked_email = _mask_email(user_settings.email)

    if request.method == "POST":
        action = request.POST.get("action", "verify")

        if action == "resend":
            try:
                _queue_login_2fa_for_user(user_settings, pending_user)
                request.session[CMS_2FA_SESSION_ATTEMPTS] = 0
                return render(
                    request,
                    "registration/login_2fa.html",
                    {
                        "masked_email": masked_email,
                        "success_message": "Ein neuer Sicherheitscode wurde versendet.",
                    },
                )
            except ValidationError as exc:
                return render(
                    request,
                    "registration/login_2fa.html",
                    {
                        "masked_email": masked_email,
                        "error_message": str(exc),
                    },
                )
            except RuntimeError:
                return render(
                    request,
                    "registration/login_2fa.html",
                    {
                        "masked_email": masked_email,
                        "error_message": "Der Sicherheitscode konnte nicht erneut versendet werden.",
                    },
                )

        entered_code = request.POST.get("code", "").strip()

        if not entered_code:
            return render(
                request,
                "registration/login_2fa.html",
                {
                    "masked_email": masked_email,
                    "error_message": "Bitte gib den Sicherheitscode ein.",
                },
            )

        if not user_settings.two_factor_email_code:
            return render(
                request,
                "registration/login_2fa.html",
                {
                    "masked_email": masked_email,
                    "error_message": "Es wurde noch kein Sicherheitscode erzeugt.",
                },
            )

        if (
            user_settings.two_factor_email_code_expires_at
            and timezone.now() > user_settings.two_factor_email_code_expires_at
        ):
            user_settings.two_factor_email_code = ""
            user_settings.two_factor_email_code_expires_at = None
            user_settings.two_factor_email_verified = False
            user_settings.save(update_fields=[
                "two_factor_email_code",
                "two_factor_email_code_expires_at",
                "two_factor_email_verified",
            ])

            return render(
                request,
                "registration/login_2fa.html",
                {
                    "masked_email": masked_email,
                    "error_message": "Der Sicherheitscode ist abgelaufen. Bitte fordere einen neuen Code an.",
                },
            )

        if entered_code != user_settings.two_factor_email_code:
            attempts = int(request.session.get(CMS_2FA_SESSION_ATTEMPTS, 0)) + 1
            request.session[CMS_2FA_SESSION_ATTEMPTS] = attempts

            if attempts >= CMS_2FA_MAX_ATTEMPTS:
                _clear_login_2fa_session(request)
                return render(
                    request,
                    "registration/login_2fa.html",
                    {
                        "masked_email": masked_email,
                        "error_message": "Zu viele Fehlversuche. Bitte melde dich erneut an.",
                    },
                )

            return render(
                request,
                "registration/login_2fa.html",
                {
                    "masked_email": masked_email,
                    "error_message": "Der eingegebene Sicherheitscode ist ungültig.",
                },
            )

        user_settings.two_factor_email_verified = True
        user_settings.two_factor_email_code = ""
        user_settings.two_factor_email_code_expires_at = None
        user_settings.save(update_fields=[
            "two_factor_email_verified",
            "two_factor_email_code",
            "two_factor_email_code_expires_at",
        ])

        login(request, pending_user, backend=backend)
        _clear_login_2fa_session(request)

        if user_settings.must_change_password:
            return redirect("ycms:password_change")

        return redirect("ycms:cms")

    return render(
        request,
        "registration/login_2fa.html",
        {
            "masked_email": masked_email,
        },
    )

# --------------- [FILES] ---------------
# Displays Document Upload Page
@login_required(login_url='login')
@cms_permission_required("media.edit")
def upload_view(request):


    data = {
        
    }
    return render(request, "pages/cms/upload.html", data)

# Uploads File (used by dropzone.js)
@login_required(login_url='login')
@cms_permission_required("media.edit")
def file_upload_view(request):
    if request.method == 'POST':
        my_file = request.FILES.get('file')
        if not my_file:
            return JsonResponse({'error': 'Keine Datei übermittelt'}, status=400)

        try:
            validate_image_upload(my_file)
        except ValidationError as error:
            return upload_validation_error_response(error)

        desktop_image = optimize_image_for_upload(
            my_file,
            max_dimensions=DESKTOP_IMAGE_MAX_DIMENSIONS,
            max_size_kb=DESKTOP_IMAGE_TARGET_KB,
            variant_suffix="desktop",
        )
        mobile_image = optimize_image_for_upload(
            my_file,
            max_dimensions=MOBILE_IMAGE_MAX_DIMENSIONS,
            max_size_kb=MOBILE_IMAGE_TARGET_KB,
            variant_suffix="mobile",
        )
        optimization = image_optimization_metadata(my_file, desktop_image, mobile_image)

        image = fileentry.objects.create(
            file=desktop_image,
            mobile_file=mobile_image,
            title=getattr(my_file, 'name', 'Bild'),
        )
        return JsonResponse({
            'success': 'Bild erfolgreich hochgeladen',
            'image': serialize_image_entry(image, optimization=optimization),
        })
    return JsonResponse({'post': 'false'})

# Delete File
@login_required(login_url='login')
@cms_permission_required("media.edit")
def delete_file(request, id):
    if request.method != 'POST':
        return JsonResponse({"error": "Ungültige Anfrage"}, status=405)

    file = get_object_or_404(fileentry, id=id)
    file.delete()
    return JsonResponse({"success": "File wurde erfolgreich gelöscht"})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def generate_mobile_file(request, id):
    if request.method != 'POST':
        return JsonResponse({"error": "Ungültige Anfrage"}, status=405)

    image = get_object_or_404(fileentry, id=id)
    if image.mobile_file:
        return JsonResponse({
            "success": "Mobile Variante ist bereits vorhanden",
            "mobile_url": image.mobile_file.url,
            "srcset": image.responsive_srcset,
            "has_mobile": True,
        })

    try:
        image.file.open("rb")
        mobile_image = optimize_image_for_upload(
            image.file,
            max_dimensions=MOBILE_IMAGE_MAX_DIMENSIONS,
            max_size_kb=MOBILE_IMAGE_TARGET_KB,
            variant_suffix="mobile",
        )
    except Exception:
        return JsonResponse(
            {"error": "Mobile Variante konnte nicht erstellt werden."},
            status=400,
        )
    finally:
        image.file.close()

    image.mobile_file.save(mobile_image.name, mobile_image, save=True)

    return JsonResponse({
        "success": "Mobile Variante wurde erstellt",
        "mobile_url": image.mobile_file.url,
        "srcset": image.responsive_srcset,
        "has_mobile": True,
        "mobile": image_variant_metadata(mobile_image),
    })


# Oberes, großzügiges Limit für den Bildtitel / Alt-Text.
# Der Titel dient auch als Alt-Text (Barrierefreiheit) und darf daher länger sein,
# aber nicht beliebig groß werden.
FILE_TITLE_MAX_LENGTH = 2000


@login_required(login_url='login')
@cms_permission_required("media.edit")
def update_file(request, id):
    if request.method != 'POST':
        return JsonResponse({"error": "Ungültige Anfrage."}, status=405)

    file = fileentry.objects.filter(id=id).first()
    if file is None:
        return JsonResponse({"error": "Das Bild wurde nicht gefunden."}, status=404)

    title = (request.POST.get('title', '') or '').strip()
    place = request.POST.get('place', '')

    if len(title) > FILE_TITLE_MAX_LENGTH:
        return JsonResponse(
            {"error": f"Der Bildtitel ist zu lang (max. {FILE_TITLE_MAX_LENGTH} Zeichen, aktuell {len(title)})."},
            status=400,
        )

    lang = get_active_language(request)
    if title:
        setattr(file, f'title_{lang}', title)
        # Falls Standardsprache → auch Hauptfeld setzen
        if lang == DEFAULT_LANGUAGE:
            file.title = title
    if place and not place == 'nothing':
        existing = fileentry.objects.filter(place=place).exclude(id=file.id).first()
        if existing is not None:
            existing.place = "nothing"
            existing.save(update_fields=["place"])
        file.place = place

    try:
        file.save()
    except (DataError, DatabaseError) as exc:
        logger.warning("update_file failed for fileentry %s: %s", id, exc)
        return JsonResponse(
            {"error": "Das Bild konnte nicht gespeichert werden. Bitte kürze den Titel und versuche es erneut."},
            status=400,
        )

    return JsonResponse({"success": "File wurde erfolgreich bearbeitet"})


@login_required(login_url='login')
@cms_permission_required("media.edit")
def image_info(request, id):
    """Liefert die serialisierten Daten eines einzelnen Bildes (für das
    Vorauswählen im Bild-Modal). Der Titel respektiert die aktive Sprache."""
    get_active_language(request)
    file = fileentry.objects.filter(id=id).first()
    if file is None:
        return JsonResponse({"error": "Das Bild wurde nicht gefunden."}, status=404)
    return JsonResponse({"image": serialize_image_entry(file)})


# Delete File
@login_required(login_url='login')
@cms_permission_required("media.edit")
def delete_file_by_name(request, name):
    try:
        cName = "yoolink/" + name
        docs = fileentry.objects.filter(file=cName)
        for doc in docs:
            doc.delete()
        """if docs.count() == 1:
            docs.first().delete()
        else:
            for doc in docs:
                doc.delete_model_only()"""
        return HttpResponse('')
        # Do something with the document
    except fileentry.DoesNotExist:
        # Handle the case where the document does not exist
        return JsonResponse({"error": "Dieses Image existiert nicht"})

# Displays all your uploaded images
@login_required(login_url='login')
@cms_permission_required("media.edit")
def images_view(request):
    # wie viele pro Seite (Default 24)
    try:
        per_page = max(1, min(200, int(request.GET.get('per_page', 24))))
    except ValueError:
        per_page = 24

    qs = fileentry.objects.all().order_by('-uploaddate')

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    preserved = request.GET.copy()
    preserved.pop('page', None)  # Page raus für die Links
    querystring = preserved.urlencode()

    return render(
        request,
        "pages/cms/images.html",
        {
            "files": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "per_page": per_page,
            "querystring": querystring,
            "total_count": paginator.count,
            "non_webp_count": non_webp_image_count(),
        },
    )

def image_has_alpha(img):
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)


def image_upload_name(image, variant_suffix, extension):
    base_name = os.path.splitext(os.path.basename(getattr(image, "name", "image")))[0]
    safe_base = slugify(base_name) or "image"
    return f"{safe_base}_{variant_suffix}.{extension}"


def uploaded_image(buffer, image, variant_suffix, extension, content_type):
    buffer.seek(0)
    return InMemoryUploadedFile(
        buffer,
        None,
        image_upload_name(image, variant_suffix, extension),
        content_type,
        buffer.getbuffer().nbytes,
        None,
    )


def original_uploaded_image(image, variant_suffix):
    image.seek(0)
    buffer = BytesIO(image.read())
    extension = os.path.splitext(getattr(image, "name", ""))[1].lstrip(".").lower() or "jpg"
    content_type = getattr(image, "content_type", "") or f"image/{extension}"
    image.seek(0)
    return uploaded_image(buffer, image, variant_suffix, extension, content_type)


def filesize_kb(size):
    return int(round((size or 0) / 1024))


def image_variant_metadata(file_obj):
    return {
        "name": os.path.basename(file_obj.name),
        "size": file_obj.size,
        "size_kb": filesize_kb(file_obj.size),
        "format": os.path.splitext(file_obj.name)[1].lstrip(".").upper(),
    }


def normalized_image_format(img, image):
    source_format = (img.format or "").upper()
    if source_format:
        return "JPEG" if source_format == "JPG" else source_format

    extension = os.path.splitext(getattr(image, "name", ""))[1].lower()
    if extension in (".jpg", ".jpeg"):
        return "JPEG"
    if extension == ".png":
        return "PNG"
    if extension == ".webp":
        return "WEBP"
    return "JPEG"


def save_optimized_png(img, image, max_dimensions, max_size_kb, variant_suffix):
    target_size = max_size_kb * 1024
    working = img.copy()
    working.thumbnail(max_dimensions, Image.Resampling.LANCZOS)

    if image_has_alpha(working):
        working = working.convert("RGBA")
    elif working.mode not in ("RGB", "L", "P"):
        working = working.convert("RGB")

    buffer = BytesIO()
    while True:
        buffer.seek(0)
        buffer.truncate()
        working.save(buffer, format="PNG", optimize=True)

        smallest_side = min(working.size) if working.size else 0
        if buffer.tell() <= target_size or smallest_side <= 420:
            break

        next_size = (
            max(1, int(working.width * 0.9)),
            max(1, int(working.height * 0.9)),
        )
        working = working.resize(next_size, Image.Resampling.LANCZOS)

    return uploaded_image(buffer, image, variant_suffix, "png", "image/png")


def save_optimized_lossy(img, image, max_dimensions, max_size_kb, variant_suffix, output_format):
    target_size = max_size_kb * 1024
    has_alpha = image_has_alpha(img)
    working = img.copy()
    working.thumbnail(max_dimensions, Image.Resampling.LANCZOS)

    if output_format == "WEBP":
        extension = "webp"
        content_type = "image/webp"
        if has_alpha:
            working = working.convert("RGBA")
        else:
            working = working.convert("RGB")
    else:
        extension = "jpeg"
        content_type = "image/jpeg"
        working = working.convert("RGB")

    buffer = BytesIO()
    quality = 92
    while True:
        buffer.seek(0)
        buffer.truncate()
        save_kwargs = {"quality": quality, "optimize": True}
        if output_format == "JPEG":
            save_kwargs["progressive"] = True
        if output_format == "WEBP":
            save_kwargs["method"] = 6
        working.save(buffer, format=output_format, **save_kwargs)

        if buffer.tell() <= target_size or quality <= 55:
            break
        quality -= 7

    return uploaded_image(buffer, image, variant_suffix, extension, content_type)


def optimize_image_for_upload(
    image,
    max_dimensions=DESKTOP_IMAGE_MAX_DIMENSIONS,
    max_size_kb=DESKTOP_IMAGE_TARGET_KB,
    variant_suffix="desktop",
):
    """
    Create an optimized WebP upload. Animated images stay in their source format.
    """
    image.seek(0)
    img = Image.open(image)

    if getattr(img, "is_animated", False):
        image.seek(0)
        buffer = BytesIO(image.read())
        return uploaded_image(
            buffer,
            image,
            variant_suffix,
            os.path.splitext(image.name)[1].lstrip(".") or "gif",
            getattr(image, "content_type", "image/gif"),
        )

    optimized = save_optimized_lossy(img, image, max_dimensions, max_size_kb, variant_suffix, "WEBP")

    image.seek(0)
    return optimized


def resize_image(image):
    return optimize_image_for_upload(image, variant_suffix="desktop")


def scale_image(image, max_dimensions=(1920, 1920)):
    return optimize_image_for_upload(image, max_dimensions=max_dimensions, variant_suffix="desktop")


def compress_image(image, max_size_kb=500):
    return optimize_image_for_upload(image, max_size_kb=max_size_kb, variant_suffix="desktop")


def field_file_is_webp(field_file):
    return bool(field_file and os.path.splitext(field_file.name)[1].lower() == ".webp")


def image_entry_needs_webp(entry):
    return not field_file_is_webp(entry.file) or bool(entry.mobile_file and not field_file_is_webp(entry.mobile_file))


def non_webp_image_count():
    return sum(1 for entry in fileentry.objects.all().only("file", "mobile_file") if image_entry_needs_webp(entry))


def convert_field_file_to_webp(field_file, max_dimensions, max_size_kb, variant_suffix):
    if not field_file or field_file_is_webp(field_file):
        return None, "unchanged"

    try:
        field_file.open("rb")
        img = Image.open(field_file)
        if getattr(img, "is_animated", False):
            return None, "animated"
        converted = save_optimized_lossy(img, field_file, max_dimensions, max_size_kb, variant_suffix, "WEBP")
        return converted, "converted"
    except Exception:
        return None, "error"
    finally:
        try:
            field_file.close()
        except Exception:
            pass


def convert_image_entry_to_webp(entry):
    converted_count = 0
    skipped_count = 0
    old_files = []

    desktop_file, desktop_status = convert_field_file_to_webp(
        entry.file,
        DESKTOP_IMAGE_MAX_DIMENSIONS,
        DESKTOP_IMAGE_TARGET_KB,
        "desktop",
    )
    if desktop_status == "converted":
        old_files.append(entry.file.name)
        entry.file.save(desktop_file.name, desktop_file, save=False)
        converted_count += 1
    elif desktop_status not in ("unchanged",):
        skipped_count += 1

    if entry.mobile_file:
        mobile_file, mobile_status = convert_field_file_to_webp(
            entry.mobile_file,
            MOBILE_IMAGE_MAX_DIMENSIONS,
            MOBILE_IMAGE_TARGET_KB,
            "mobile",
        )
        if mobile_status == "converted":
            old_files.append(entry.mobile_file.name)
            entry.mobile_file.save(mobile_file.name, mobile_file, save=False)
            converted_count += 1
        elif mobile_status not in ("unchanged",):
            skipped_count += 1

    if converted_count:
        entry.save()
        for old_name in old_files:
            if old_name and old_name not in (entry.file.name, getattr(entry.mobile_file, "name", "")):
                try:
                    entry.file.storage.delete(old_name)
                except Exception:
                    pass

    return converted_count, skipped_count


def image_optimization_metadata(original, desktop_image, mobile_image):
    original_size = getattr(original, "size", 0)
    desktop_saved_bytes = original_size - desktop_image.size
    mobile_saved_bytes = original_size - mobile_image.size
    desktop_saved_percent = round((desktop_saved_bytes / original_size) * 100) if original_size else 0
    mobile_saved_percent = round((mobile_saved_bytes / original_size) * 100) if original_size else 0

    original_format = os.path.splitext(getattr(original, "name", ""))[1].lstrip(".").upper()
    desktop_format = os.path.splitext(desktop_image.name)[1].lstrip(".").upper()

    note = "Bild wurde als WebP für Web und Mobil optimiert."
    if original_format == "GIF" and desktop_format == "GIF":
        note = "Animierte GIFs bleiben im Originalformat, damit die Animation erhalten bleibt."

    return {
        "original_size": original_size,
        "original_size_kb": filesize_kb(original_size),
        "desktop": image_variant_metadata(desktop_image),
        "mobile": image_variant_metadata(mobile_image),
        "desktop_saved_bytes": desktop_saved_bytes,
        "desktop_saved_percent": desktop_saved_percent,
        "mobile_saved_bytes": mobile_saved_bytes,
        "mobile_saved_percent": mobile_saved_percent,
        "note": note,
    }

from django.utils.translation import get_language_from_request, activate

# --------------- [FAQ] ---------------
@login_required(login_url='login')
@cms_permission_required("faq.edit")
def faq_view(request):
    lang = get_active_language(request)
    activate(lang)
    data = {
        "faqs":  FAQ.objects.all(),
        "selected_language": lang
    }
    return render(request, "pages/cms/faq.html", data)

# Update or create FAQ
@login_required(login_url='login')
@cms_permission_required("faq.edit")
def update_faq(request):
    """FAQ aktualisieren oder neu erstellen, mit Unterstützung für Mehrsprachigkeit"""
    lang = get_active_language(request)  # Aktuelle Sprache holen

    if request.method == 'POST':
        faq_id = request.POST.get('faq_id')
        faq = get_object_or_404(FAQ, id=faq_id)

        question = request.POST.get('question')
        answer = request.POST.get('answer')
        # Dynamisch die Sprachvarianten setzen
        setattr(faq, f'question_{lang}', question)
        setattr(faq, f'answer_{lang}', answer)
        # Falls Standardsprache → auch Hauptfeld setzen
        if lang == DEFAULT_LANGUAGE:
            faq.question = question
            faq.answer = answer
        faq.save()

        return JsonResponse({'success': True})

    elif request.method == 'GET':
        new_question = request.GET.get('question')
        new_answer = request.GET.get('answer')

        # Neues FAQ mit Hauptfeld (falls Standardsprache) und Sprachfeld erstellen
        faq_data = {f'question_{lang}': new_question, f'answer_{lang}': new_answer}

        if lang == DEFAULT_LANGUAGE:
            faq_data["question"] = new_question
            faq_data["answer"] = new_answer

        faq = FAQ.objects.create(**faq_data)

        return JsonResponse({
            'id': faq.id,
            'question': getattr(faq, f'question_{lang}'),
            'answer': getattr(faq, f'answer_{lang}'),
            'order': faq.order,
            'success': True
        })

    return JsonResponse({'success': False})

# Delete FAQ
@login_required(login_url='login')
@cms_permission_required("faq.edit")
def del_faq(request, id):
    if request.method == 'POST':
        instance = get_object_or_404(FAQ, id=id)
        instance.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

# Update the FAQ order
@login_required(login_url='login')
@cms_permission_required("faq.edit")
def update_faq_order(request):
    if request.method == 'POST':
        faqs = json.loads(request.POST.get('faqs', '[]'))
        for i, faq in enumerate(faqs):
            realFaq = FAQ.objects.get(id=faq['id'])
            realFaq.order = i + 1
            realFaq.question = faq['question']
            realFaq.answer = faq['answer']
            realFaq.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': True})


# --------------- [Blog] ---------------
from django.core.paginator import Paginator

def _strip_generated_blog_intro(body, title, description):
    if not body:
        return body

    prefix = ""
    rest = body
    wrapper_match = re.match(r"^(\s*<div\b[^>]*>\s*)(.*)$", rest, flags=re.IGNORECASE | re.DOTALL)
    if wrapper_match:
        prefix = wrapper_match.group(1)
        rest = wrapper_match.group(2)

    def remove_leading_tag(html, tag_name, expected_text):
        expected_text = (expected_text or "").strip()
        if not expected_text:
            return html

        tag_match = re.match(
            rf"^\s*<{tag_name}\b[^>]*>.*?</{tag_name}>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not tag_match:
            return html

        tag_html = tag_match.group(0)
        tag_text = " ".join(strip_tags(tag_html).split())
        expected_text = " ".join(expected_text.split())
        if tag_text == expected_text:
            return html[tag_match.end():]

        return html

    rest = remove_leading_tag(rest, "h1", title)
    rest = remove_leading_tag(rest, "p", description)
    return prefix + rest

@login_required(login_url='login')
@cms_permission_required("blog.edit")
def blog_view(request):
    query = request.GET.get("q", "")
    sort = request.GET.get("sort", "-date")  # Standard: neueste zuerst
    active_filter = request.GET.get("active", "all")
    allowed_sorts = {"-date", "date", "-last_updated", "last_updated", "title"}
    if sort not in allowed_sorts:
        sort = "-date"

    # Nur Original-Blogs anzeigen
    blogs = Blog.objects.filter(original__isnull=True).select_related("author").prefetch_related("translations")

    if query:
        blogs = blogs.filter(title__icontains=query)

    if active_filter == "true":
        blogs = blogs.filter(active=True)
    elif active_filter == "false":
        blogs = blogs.filter(active=False)

    blogs = blogs.order_by(sort)

    paginator = Paginator(blogs, 6)  # 6 Blogs pro Seite
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    base_blogs = Blog.objects.filter(original__isnull=True)

    # Titel + Beschreibung in der aktiven CMS-Sprache anzeigen (Rest wie Datum
    # bleibt bewusst unverändert). Nutzt den prefetch-Cache der Übersetzungen,
    # daher keine zusätzlichen Queries.
    lang = get_active_language(request)
    for blog in page_obj.object_list:
        if blog.language == lang:
            variant = blog
        else:
            variant = next(
                (t for t in blog.translations.all() if t.language == lang), None
            ) or blog
        blog.display_title = variant.title
        blog.display_description = variant.description

    return render(request, "pages/cms/blog/blog.html", {
        "page_obj": page_obj,
        "blogs": page_obj.object_list,
        "query": query,
        "active_filter": active_filter,
        "sort": sort,
        "total_blog_count": base_blogs.count(),
        "active_blog_count": base_blogs.filter(active=True).count(),
        "draft_blog_count": base_blogs.filter(active=False).count(),
        "translation_count": Blog.objects.filter(original__isnull=False).count(),
    })


@login_required(login_url='login')
@cms_permission_required("blog.edit")
def download_blog_markdown_guidelines(request):
    guidelines_path = os.path.join(settings.BASE_DIR, "docs", "yoolink-blog-markdown-guidelines.md")

    if not os.path.exists(guidelines_path):
        raise Http404("Blog Markdown Guidelines nicht gefunden.")

    return FileResponse(
        open(guidelines_path, "rb"),
        as_attachment=True,
        filename="yoolink-blog-markdown-guidelines.md",
        content_type="text/markdown; charset=utf-8",
    )


# Delete Blog
@login_required(login_url='login')
@login_required(login_url='login')
@cms_permission_required("blog.edit")
def delete_blog(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=400)

    blog = get_object_or_404(Blog, id=id)

    if blog.original:
        return JsonResponse({'error': 'Nur Original-Blogs dürfen gelöscht werden.'}, status=403)

    blog.delete()
    return JsonResponse({'success': True}, status=200)


def _blog_content_from_cms_request(request, title, description):
    content_source = (request.POST.get("content_source") or "").strip().lower()
    markdown_provided = "markdown" in request.POST

    if content_source == "markdown" or (markdown_provided and not request.POST.get("code")):
        markdown = (request.POST.get("markdown") or "").strip()
        if not markdown:
            return None, JsonResponse({"error": "Der Markdown-Inhalt darf nicht leer sein!"}, status=400)

        return {
            "body": render_markdown_to_html(markdown),
            "code": build_default_code_from_markdown(markdown),
            "markdown": markdown,
        }, None

    body = request.POST.get("body") or ""
    raw_code = request.POST.get("code")
    if not raw_code:
        return None, JsonResponse({"error": "Der Blog-Inhalt darf nicht leer sein!"}, status=400)

    try:
        code = json.loads(raw_code)
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Der Blog-Inhalt konnte nicht gelesen werden."}, status=400)

    body = _strip_generated_blog_intro(body, title, description)
    markdown = blog_code_to_markdown(code, body)
    rendered_body = render_markdown_to_html(markdown) or body

    return {
        "body": rendered_body,
        "code": code,
        "markdown": markdown,
    }, None


@login_required(login_url='login')
@cms_permission_required("blog.edit")
def create_blog(request):
    if request.method == 'POST':
        # The request is a POST request
        # Retrieve POST parameters
        title = request.POST.get('title')

        if Blog.objects.filter(title=title).exists():
            return JsonResponse({'error': 'Ein Blog mit diesem Titel existiert bereits!'}, status=400)

        description = (request.POST.get('description') or '').strip()
        title_image_alt = (request.POST.get('title_image_alt') or '').strip()
        title_image_title = (request.POST.get('title_image_title') or '').strip()
        title_image_caption = (request.POST.get('title_image_caption') or '').strip()
        active = request.POST.get('active', False)
        
        title_image = request.FILES.get('title_image', '')
        if title_image:
            try:
                validate_image_upload(title_image)
            except ValidationError as error:
                return upload_validation_error_response(error)
    
        #return JsonResponse({'title': title, 'body': body, 'code': code})

        if title:
            if not description:
                return JsonResponse({'error': 'Die Beschreibung darf nicht leer sein!'}, status=400)

            content_data, error_response = _blog_content_from_cms_request(request, title, description)
            if error_response:
                return error_response

            # Create
            blog = Blog(
                title=title,
                body=content_data["body"],
                markdown=content_data["markdown"],
                code=content_data["code"],
                author=request.user,
                title_image_alt=title_image_alt,
                title_image_title=title_image_title,
                title_image_caption=title_image_caption,
            )
            if active == "true":
                blog.active = True
            else:
                blog.active = False
            blog.save()
            if title_image:
                blog.title_image = optimize_image_for_upload(title_image)
            blog.description = description
            blog.title_image_alt = title_image_alt
            blog.title_image_title = title_image_title
            blog.title_image_caption = title_image_caption
            blog.save()
            return JsonResponse({'success': 'Blog successfully created', 'blogId': blog.id}, status=201)

        else:
            return JsonResponse({'error': 'Der Titel darf nicht leer sein!'}, status=400)

        # Do something with the POST parameters (e.g., save them to the database)
        # ...

        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Invalid request method. Only POST requests are allowed.'}, status=400)

@login_required(login_url='login')
@cms_permission_required("blog.edit")
def update_blog(request, id):
    if request.method == 'POST':
        # The request is a POST request
        # Retrieve POST parameters
        blog = get_or_create_translated_blog(request, id)

        title = request.POST.get('title')
        # Original und seine Übersetzungen teilen sich bewusst denselben Titel,
        # daher die Dubletten-Prüfung auf Blogs AUSSERHALB der eigenen Familie
        # beschränken. Sonst schlägt z. B. das Angleichen des Original-Titels an
        # einen bereits korrigierten Übersetzungstitel fälschlich mit einem
        # "Bad Request" fehl.
        root = blog.original or blog
        family_ids = [root.id, *root.translations.values_list('id', flat=True)]
        if (
            blog.title != title
            and Blog.objects.filter(title=title).exclude(id__in=family_ids).exists()
        ):
            return JsonResponse({'error': 'Ein Blog mit diesem Titel existiert bereits!'}, status=400)
        description = (request.POST.get('description') or '').strip()
        title_image_alt = (request.POST.get('title_image_alt') or '').strip()
        title_image_title = (request.POST.get('title_image_title') or '').strip()
        title_image_caption = (request.POST.get('title_image_caption') or '').strip()
        active = request.POST.get('active', False)
        title_image = request.FILES.get('title_image', '')
        if title_image:
            try:
                validate_image_upload(title_image)
            except ValidationError as error:
                return upload_validation_error_response(error)

        if title:
            if not description:
                return JsonResponse({'error': 'Die Beschreibung darf nicht leer sein!'}, status=400)

            content_data, error_response = _blog_content_from_cms_request(request, title, description)
            if error_response:
                return error_response

            # Create
            blog.description = description
            blog.title_image_alt = title_image_alt
            blog.title_image_title = title_image_title
            blog.title_image_caption = title_image_caption
            blog.title = title
            # Der Slug wird bewusst NICHT aus dem Titel neu gesetzt: er bleibt
            # ab der Erstellung stabil, damit sich die öffentliche URL bei einer
            # Titeländerung nicht ändert (verhindert Google-Weiterleitungen).
            blog.markdown = content_data["markdown"]
            blog.body = content_data["body"]
            blog.code = content_data["code"]
            if active == "true":
                blog.active = True
            else:
                blog.active = False
            if title_image:
                blog.title_image = optimize_image_for_upload(title_image)
            blog.save()
            return JsonResponse({'success': 'Blog successfully updated', 'blogId': blog.id}, status=201)

        else:
            return JsonResponse({'error': 'Error request. Title is empty.'}, status=400)

    else:
        return JsonResponse({'error': 'Invalid request method. Only POST requests are allowed.'}, status=400)




@login_required(login_url='login')
@cms_permission_required("blog.edit")
def add_blog(request):
            
    data = {
        "galerien": Galerie.objects.all()
    }

    return render(request, "pages/cms/blog/add_blog.html", data)

@login_required(login_url='login')
@cms_permission_required("blog.edit")
def blog_details(request, id):
    lang = get_active_language(request)
    blog = get_object_or_404(Blog, id=id)

    original_blog = blog.original if blog.original else blog

    if original_blog.language != lang:
        translated_blog = original_blog.translations.filter(language=lang).first()
        if translated_blog:
            blog = translated_blog
        else:
            # Erstelle Sprachvariante durch Kopieren
            blog = Blog.objects.create(
                title=original_blog.title,
                slug=original_blog.slug + '-' + lang,
                title_image=original_blog.title_image,
                title_image_alt=original_blog.title_image_alt,
                title_image_title=original_blog.title_image_title,
                title_image_caption=original_blog.title_image_caption,
                author=original_blog.author,
                body=original_blog.body,
                code=original_blog.code,
                markdown=original_blog.markdown,
                active=False,
                description=original_blog.description,
                language=lang,
                original=original_blog,
            )


    data = {"blog": blog,"galerien": Galerie.objects.all()}

    return render(request, "pages/cms/blog/blog_update.html", data)

@login_required(login_url='login')
@cms_permission_required("blog.edit")
def blog_code(request, id):
    blog = get_or_create_translated_blog(request, id)
    code = blog.code or build_default_code_from_markdown(blog.markdown)
    return JsonResponse({"code": code, "markdown": blog.markdown, "success": "true"})


@login_required(login_url='login')
@cms_permission_required("blog.edit")
def preview_blog_markdown(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=400)

    markdown = (request.POST.get("markdown") or "").strip()
    if not markdown:
        return JsonResponse({"error": "Der Markdown-Inhalt darf nicht leer sein!"}, status=400)

    return JsonResponse({
        "success": "true",
        "markdown": markdown,
        "body": render_markdown_to_html(markdown),
        "code": build_default_code_from_markdown(markdown),
    })


@login_required(login_url='login')
@cms_permission_required("blog.edit")
def convert_blog_code_to_markdown(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=400)

    raw_code = request.POST.get("code")
    if not raw_code:
        return JsonResponse({"error": "Der Blog-Inhalt darf nicht leer sein!"}, status=400)

    try:
        code = json.loads(raw_code)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Der Blog-Inhalt konnte nicht gelesen werden."}, status=400)

    markdown = blog_code_to_markdown(code)
    return JsonResponse({
        "success": "true",
        "markdown": markdown,
        "body": render_markdown_to_html(markdown),
    })

# --------------- [GALERY] ---------------
# Render Galery Detail View
@login_required(login_url='login')
@cms_permission_required("media.edit")
def galery_view(request, id):
    galery = get_object_or_404(Galerie, id=id)
    return render(request, "pages/cms/galery/galery.html", {"galery": galery})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def get_galery_images(request):
    id = request.GET.get("galeryId")
    galery = get_object_or_404(Galerie, id=id)
    if galery.images:
        images_list = []
        for image in galery.images.all():
            metadata = stored_image_metadata(image.upload)
            image_dict = {
                'upload_url': image.upload.url,
                'url': image.upload.url,
                'id': image.id,
                'title': image.title,
                'alt': image.title,
                'metadata': metadata,
                'uploaddate': image.uploaddate,
            }
            images_list.append(image_dict)
        return JsonResponse({"images": images_list}, status=200)
    return JsonResponse({}, status=400)
    
@login_required(login_url='login')
@cms_permission_required("media.edit")
def update_galery_image(request, id):
    """Aktualisiert ein GaleryImage mit mehrsprachiger Speicherung"""
    if request.method == 'POST':
        lang = get_active_language(request)
        DEFAULT_LANGUAGE = "de"

        title = request.POST.get('title', '')

        galery_image = get_object_or_404(GaleryImage, id=id)

        if title:
            setattr(galery_image, f'title_{lang}', title)

            # Falls Standardsprache → auch Hauptfeld setzen
            if lang == DEFAULT_LANGUAGE:
                galery_image.title = title

            galery_image.save()
            return JsonResponse({"success": "Bild wurde erfolgreich gespeichert"})

        return JsonResponse({"error": "Bitte gebe einen Titel ein!"})

    return JsonResponse({"error": "Etwas ist schief gelaufen. Versuche es später nochmal"})


# Render Galery Overview
@login_required(login_url='login')
@cms_permission_required("media.edit")
def galerien(request):
    # Per-Page sicher parsen (Default 12, max 200)
    try:
        per_page = max(1, min(200, int(request.GET.get('per_page', 12))))
    except ValueError:
        per_page = 12

    qs = Galerie.objects.all().order_by('-created_at')

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    preserved = request.GET.copy()
    preserved.pop('page', None)  # page aus Query entfernen
    querystring = preserved.urlencode()

    return render(
        request,
        "pages/cms/galery/galerien.html",
        {
            "galerien": page_obj.object_list,  # nur aktuelle Seite
            "page_obj": page_obj,
            "paginator": paginator,
            "per_page": per_page,
            "querystring": querystring,
            "total_count": paginator.count,
        },
    )

# Create a galery
@login_required(login_url='login')
@cms_permission_required("media.edit")
def create_galery(request):
    galery = Galerie.objects.create()
    # Generieren Sie die URL zur Detailseite des erstellten Modells
    url = reverse('cms:galery-view', args=[galery.id])
    # Leiten Sie auf die Detailseite des neuen Modells weiter
    return HttpResponseRedirect(url)

# Update a galery
@login_required(login_url='login')
@cms_permission_required("media.edit")
def save_galery(request, id):
    galery = get_object_or_404(Galerie, id=id)
    if request.method == 'POST':
        lang = get_active_language(request)
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        place = request.POST.get('place', 'nothing')

        
        setattr(galery, f'title_{lang}', title)
        # Falls Standardsprache → auch Hauptfeld setzen
        if lang == DEFAULT_LANGUAGE:
            galery.title = title
        setattr(galery, f'description_{lang}', description)
        # Falls Standardsprache → auch Hauptfeld setzen
        if lang == DEFAULT_LANGUAGE:
            galery.description = description

        if place != 'nothing':
            if Galerie.objects.filter(place=place).exists():
                extra = Galerie.objects.get(place=place)
                extra.place = "nothing"
                extra.save()
            galery.place = place

        galery.save()
        return JsonResponse({"success": "Die Galerie wurde erfolgreich gespeichert"})
    return JsonResponse({"error": "Fehler beim Speichern der Galerie"})

# Upload Image for Galery
@login_required(login_url='login')
@cms_permission_required("media.edit")
def upload_galery_img(request, id):
    if request.method == 'POST':
        my_file = request.FILES.get('file')
        if not my_file:
            return JsonResponse({'error': 'Keine Datei übermittelt'}, status=400)

        try:
            validate_image_upload(my_file)
        except ValidationError as error:
            return upload_validation_error_response(error)

        optimized_image = optimize_image_for_upload(my_file)
        doc = GaleryImage.objects.create(upload=optimized_image)
        galery = Galerie.objects.get(id=id)
        galery.images.add(doc)
        galery.save()
        return HttpResponse('')
    return JsonResponse({'error': 'Falsche Anfrage (Erlaubt: POST)'})

# Delete File
@login_required(login_url='login')
@cms_permission_required("media.edit")
def delete_galery_img(request, id):
    file = get_object_or_404(GaleryImage, id=id)
    file.delete()
    return JsonResponse({"success": "File wurde erfolgreich gelöscht"})


# Delete Galery
@login_required(login_url='login')
@cms_permission_required("media.edit")
def delete_galery(request, id):
    if request.method == 'POST':
        galery = get_object_or_404(Galerie, id=id)
        for img in galery.images.all():
            img.delete()
        galery.delete()
        return JsonResponse({'success': 'Galerie wurde erfolgreich gelöscht'})
    return JsonResponse({'error': 'Falsche Anfrage (Erlaubt: POST)'})


# --------------- [Image Helper] ---------------
def stored_image_metadata(field_file):
    if not field_file:
        return {}

    metadata = {
        "name": os.path.basename(getattr(field_file, "name", "")),
        "size": None,
        "size_kb": None,
        "width": None,
        "height": None,
        "dimensions": "",
    }

    try:
        metadata["size"] = field_file.size
        metadata["size_kb"] = filesize_kb(field_file.size)
    except Exception:
        pass

    try:
        field_file.open("rb")
        with Image.open(field_file) as img:
            width, height = img.size
            metadata["width"] = width
            metadata["height"] = height
            metadata["dimensions"] = f"{width} x {height}px"
    except Exception:
        pass
    finally:
        try:
            field_file.close()
        except Exception:
            pass

    return metadata


def serialize_image_entry(entry, optimization=None):
    try:
        image_url = entry.file.url
    except ValueError:
        image_url = ""

    desktop_meta = stored_image_metadata(entry.file)
    mobile_meta = stored_image_metadata(entry.mobile_file) if entry.mobile_file else {}
    upload_date = entry.uploaddate.strftime("%d.%m.%Y %H:%M") if entry.uploaddate else ""

    data = {
        "url": image_url,
        "preview_url": entry.mobile_file_url or image_url,
        "mobile_url": entry.mobile_file_url,
        "srcset": entry.responsive_srcset,
        "id": entry.id,
        "title": entry.title,
        "format": entry.file_extension,
        "has_mobile": bool(entry.mobile_file),
        "is_webp": field_file_is_webp(entry.file),
        "metadata": {
            "filename": desktop_meta.get("name") or os.path.basename(entry.file.name),
            "size": desktop_meta.get("size"),
            "size_kb": desktop_meta.get("size_kb"),
            "width": desktop_meta.get("width"),
            "height": desktop_meta.get("height"),
            "dimensions": desktop_meta.get("dimensions"),
            "uploaded_at": upload_date,
            "mobile_size_kb": mobile_meta.get("size_kb"),
            "mobile_dimensions": mobile_meta.get("dimensions"),
        },
    }

    if optimization:
        data["optimization"] = optimization

    return data


@login_required(login_url='login')
@cms_permission_required("media.edit")
def convert_images_to_webp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Falsche Anfrage (Erlaubt: POST)'}, status=405)

    entries = fileentry.objects.all().order_by('id')
    converted_variants = 0
    skipped_variants = 0
    touched_images = 0

    for entry in entries:
        if not image_entry_needs_webp(entry):
            continue
        converted_count, skipped_count = convert_image_entry_to_webp(entry)
        converted_variants += converted_count
        skipped_variants += skipped_count
        if converted_count:
            touched_images += 1

    remaining = non_webp_image_count()
    return JsonResponse({
        'success': 'WebP-Konvertierung abgeschlossen',
        'converted_images': touched_images,
        'converted_variants': converted_variants,
        'skipped_variants': skipped_variants,
        'remaining': remaining,
        'has_non_webp': remaining > 0,
    })


# get all images
@login_required(login_url='login')
@cms_permission_required("media.edit")
def all_images(request):
    if request.method == 'GET':
        try:
            per_page = max(1, min(24, int(request.GET.get('per_page', 12))))
        except ValueError:
            per_page = 12

        search = request.GET.get('q', '').strip()
        images = fileentry.objects.all().order_by('-uploaddate')
        if search:
            images = images.filter(title__icontains=search)

        paginator = Paginator(images, per_page)
        page_obj = paginator.get_page(request.GET.get('page', 1))
        image_urls = [serialize_image_entry(entry) for entry in page_obj.object_list]
        non_webp_total = non_webp_image_count()

        return JsonResponse({
            'image_urls': image_urls,
            'pagination': {
                'page': page_obj.number,
                'per_page': per_page,
                'total': paginator.count,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
            },
            'has_non_webp': non_webp_total > 0,
            'non_webp_count': non_webp_total,
        })

        images = fileentry.objects.all().order_by('-uploaddate')
        # Liste zur Speicherung der Bild-URLs erstellen
        image_urls = [] 

        # URLs für jedes fileentry-Objekt erstellen
        for entry in images:
            # URL für das Bild erstellen
            image_url = entry.file.url
            data = {
                "url": image_url,
                "mobile_url": entry.mobile_file_url,
                "srcset": entry.responsive_srcset,
                "id": entry.id,
                "title": entry.title,
                "format": entry.file_extension,
                "has_mobile": bool(entry.mobile_file),
            }
            # URL zur Liste hinzufügen
            image_urls.append(data)

        # JSON-Antwort mit den Bild-URLs senden
        return JsonResponse({'image_urls': image_urls})
    return JsonResponse({'error': 'Falsche Anfrage (Erlaubt: GET)'})

# --------------- [Galery Helper] ---------------
# get all galerys
@login_required(login_url='login')
@cms_permission_required("media.edit")
def all_galerien(request):
    if request.method == 'GET':
        galerien = Galerie.objects.prefetch_related('images').all()
        galerien_list = []
        
        for galerie in galerien:
            image_list = []
            
            for image in galerie.images.all():
                metadata = stored_image_metadata(image.upload)
                image_list.append({
                    'url': image.upload.url,
                    'id': image.id,
                    'title': image.title,
                    'alt': image.title,
                    'metadata': metadata,
                })
            
            galerien_list.append({
                'id': galerie.pk,
                'title': galerie.title,
                'description': galerie.description,
                'active': galerie.active,
                'images': image_list
                # Add other galerie fields as needed
            })
        
        return JsonResponse({'galerien': galerien_list}, safe=False)
    
    return JsonResponse({'error': 'Falsche Anfrage (Erlaubt: GET)'})

@extend_schema(exclude=True)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def email_send(request):
    # Erstelle das Formular mit den POST-Daten
    form = ContactForm(request.POST)
    
    # Validierung des Formulars und reCAPTCHA
    if form.is_valid():
        name = form.cleaned_data.get('name', 'Unbekannt')
        email = form.cleaned_data.get('email')
        title = form.cleaned_data.get('title')
        message_text = form.cleaned_data.get('message')

        # Überprüfen, ob ähnliche Nachricht bereits existiert
        existing_message = Message.objects.filter(name=name, message=message_text, email=email, title=title).first()

        if existing_message:
            return Response({'error': 'Sie haben diese Nachricht bereits gesendet'}, status=status.HTTP_400_BAD_REQUEST)

        # Nachricht speichern
        message = Message.objects.create(name=name, message=message_text, email=email, title=title)

        # Email an Unternehmen senden
        subject_company = "Neue Nachricht in Ihrem CMS"
        message_company = f"Hallo Team,\n\n{name} ({email}) hat eine neue Anfrage gesendet:\n\n"
        message_company += f"Betreff: {title}\n\n"
        message_company += f"Nachricht: {message.message}\n\n"
        message_company += "Vielen Dank!\n\nMit freundlichen Grüßen,\nIhr YooLink"

        # Einstellungen für das Senden der E-Mail
        website_settings = _get_website_settings()
        recipient_email = website_settings.contact_email or settings.EMAIL_HOST_USER
        send_mail(
            subject_company,
            message_company,
            settings.EMAIL_HOST_USER,
            [recipient_email],
            fail_silently=False,
        )

        return Response({'success': 'Ihre Nachricht wurde erfolgreich versendet.'}, status=status.HTTP_200_OK)
    else:
        # Wenn das Formular nicht gültig ist (z. B. durch ein fehlerhaftes reCAPTCHA), wird ein Fehler zurückgegeben
        return Response({'error': 'Formular-Validierung fehlgeschlagen. Bitte versuchen Sie es erneut.'}, status=status.HTTP_400_BAD_REQUEST)

#########################################
############### Settings ################
#########################################
def _get_user_settings(user):
    user_settings, _ = UserSettings.objects.get_or_create(
        user=user,
        defaults={"email": user.email or ""}
    )

    if not user_settings.email and user.email:
        user_settings.email = user.email
        user_settings.save(update_fields=["email"])

    return user_settings


def _get_website_settings():
    return WebsiteSettings.get_solo()


def _get_site_owner_user(fallback_user):
    return User.objects.filter(cms_role_assignments__role__slug="owner").order_by("id").first() or fallback_user


@login_required(login_url='login')
def user_settings_view(request):
    if "website_settings.edit" not in user_permissions(request.user):
        return redirect("ycms:security-settings")

    user_settings = _get_user_settings(request.user)
    website_settings = _get_website_settings()

    context = {
        'settings': user_settings,
        'user_settings': user_settings,
        'website_settings': website_settings,
    }
    return render(request, 'pages/cms/settings/settings.html', context)


@login_required(login_url='login')
@cms_permission_required("website_settings.edit")
def user_settings_update(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Ungültige Anfrage'}, status=405)

    website_settings = _get_website_settings()

    company_name = request.POST.get('company_name', '').strip()
    owner_name = request.POST.get('owner_name', '').strip()
    contact_email = request.POST.get('contact_email', '').strip()
    tel_number = request.POST.get('tel_number', '').strip()
    fax_number = request.POST.get('fax_number', '').strip()
    mobile_number = request.POST.get('mobile_number', '').strip()
    website = request.POST.get('website', '').strip()
    address = request.POST.get('address', '').strip()
    social_instagram = request.POST.get('social_instagram', '').strip()
    social_x = request.POST.get('social_x', '').strip()
    social_facebook = request.POST.get('social_facebook', '').strip()
    social_linkedin = request.POST.get('social_linkedin', '').strip()
    price_range = request.POST.get('price_range', '').strip()
    area_served = request.POST.get('area_served', '').strip()
    business_description = request.POST.get('business_description', '').strip()
    site_meta_description = request.POST.get('site_meta_description', '').strip()
    site_meta_author = request.POST.get('site_meta_author', '').strip()
    address_region = request.POST.get('address_region', '').strip()
    address_country = request.POST.get('address_country', '').strip()
    geo_latitude = request.POST.get('geo_latitude', '').strip()
    geo_longitude = request.POST.get('geo_longitude', '').strip()
    global_font = request.POST.get('global_font', '').strip()

    allowed_fonts = {'', 'font-sans', 'font-serif', 'font-mono'}
    if global_font not in allowed_fonts:
        global_font = 'font-sans'

    if contact_email:
        try:
            validate_email(contact_email)
        except ValidationError:
            return JsonResponse({'error': 'Bitte gib eine gültige Unternehmens-E-Mail-Adresse ein.'}, status=400)

    website_settings.company_name = company_name
    website_settings.owner_name = owner_name
    website_settings.contact_email = contact_email
    website_settings.tel_number = tel_number
    website_settings.fax_number = fax_number
    website_settings.mobile_number = mobile_number
    website_settings.website = website
    website_settings.address = address
    website_settings.social_instagram = social_instagram
    website_settings.social_x = social_x
    website_settings.social_facebook = social_facebook
    website_settings.social_linkedin = social_linkedin
    website_settings.price_range = price_range
    website_settings.area_served = area_served
    website_settings.business_description = business_description
    website_settings.site_meta_description = site_meta_description
    website_settings.site_meta_author = site_meta_author
    website_settings.address_region = address_region
    website_settings.address_country = address_country
    website_settings.geo_latitude = geo_latitude
    website_settings.geo_longitude = geo_longitude
    website_settings.global_font = global_font

    website_settings.save()

    success_message = 'Die Einstellungen wurden erfolgreich gespeichert.'

    return JsonResponse({'success': success_message})


@login_required(login_url='login')
@cms_permission_required("website_settings.edit")
def logo_settings_view(request):
    return render(request, 'pages/cms/settings/profile.html', {'settings': _get_website_settings()})


@login_required(login_url='login')
def security_settings_view(request):
    user_settings = _get_user_settings(request.user)
    return render(request, 'pages/cms/settings/security.html', {'settings': user_settings})


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
def recovery_settings_view(request):
    overview = get_recovery_overview()
    return render(
        request,
        "pages/cms/settings/recovery.html",
        {
            "overview": overview,
        },
    )


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
def recovery_backup_download(request):
    include_media_value = request.GET.get("include_media")
    if include_media_value in {"1", "true", "on", "yes"}:
        include_media = True
    elif include_media_value in {"0", "false", "off", "no"}:
        include_media = False
    else:
        include_media = None

    archive, filename = build_backup_archive(user=request.user, include_media=include_media)
    response = FileResponse(archive, as_attachment=True, filename=filename)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
@require_POST
def recovery_backup_restore(request):
    overview = get_recovery_overview()
    expected_phrase = overview["restore_confirmation_phrase"]
    phrase = (request.POST.get("confirmation_phrase") or "").strip()
    backup_file = request.FILES.get("backup_file")
    restore_media = request.POST.get("restore_media") == "on"

    if phrase != expected_phrase:
        return JsonResponse(
            {
                "success": False,
                "error": "Die Sicherheitsphrase stimmt nicht.",
            },
            status=400,
        )

    if not backup_file:
        return JsonResponse(
            {
                "success": False,
                "error": "Bitte wähle eine Backup-ZIP-Datei aus.",
            },
            status=400,
        )

    try:
        summary = restore_backup_archive(backup_file, restore_media=restore_media)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "message": "Backup wurde wiederhergestellt. Bitte melde dich neu an, falls deine Sitzung abgelaufen ist.",
            "summary": summary,
        }
    )


def _remote_backup_payload(record):
    return {
        "id": record.id,
        "trigger": record.get_trigger_display(),
        "status": record.status,
        "status_label": record.get_status_display(),
        "slot": record.slot,
        "filename": record.filename,
        "size_bytes": record.size_bytes,
        "object_key": record.object_key,
        "encrypted_sha256": record.encrypted_sha256,
        "include_media": record.include_media,
        "created_by": record.created_by.username if record.created_by else "",
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "started_at": record.started_at.isoformat() if record.started_at else "",
        "finished_at": record.finished_at.isoformat() if record.finished_at else "",
        "error_message": record.error_message,
        "source": "database",
        "restore_url": (
            reverse("cms:recovery-remote-backup-restore", args=[record.id])
            if record.status == RecoveryBackup.STATUS_SUCCEEDED
            else ""
        ),
    }


def _remote_backup_payloads():
    payloads = [_remote_backup_payload(record) for record in get_remote_backup_records()]
    known_object_keys = {payload["object_key"] for payload in payloads if payload["object_key"]}
    for storage_slot in get_remote_backup_storage_slots():
        if storage_slot["object_key"] in known_object_keys:
            continue
        storage_slot["restore_url"] = reverse("cms:recovery-remote-backup-object-restore")
        payloads.append(storage_slot)
    return payloads


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
@require_POST
def recovery_remote_backup_start(request):
    if not remote_backups_configured():
        return JsonResponse(
            {
                "success": False,
                "error": "Remote-Backups sind noch nicht vollständig konfiguriert.",
            },
            status=400,
        )

    remote_config = get_recovery_overview()["remote_backup"]
    backup_record = RecoveryBackup.objects.create(
        trigger=RecoveryBackup.TRIGGER_MANUAL,
        status=RecoveryBackup.STATUS_QUEUED,
        created_by=request.user,
        include_media=remote_config["include_media"],
        storage_bucket=remote_config["bucket"],
        storage_endpoint=remote_config["endpoint"],
    )
    task = create_remote_recovery_backup.delay(
        trigger="manual",
        user_id=request.user.id,
        record_id=backup_record.id,
    )
    return JsonResponse(
        {
            "success": True,
            "message": "Verschlüsseltes Remote-Backup wurde gestartet.",
            "task_id": task.id,
            "backup": _remote_backup_payload(backup_record),
        }
    )


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
def recovery_remote_backup_status(request):
    return JsonResponse(
        {
            "success": True,
            "backups": _remote_backup_payloads(),
        }
    )


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
@require_POST
def recovery_remote_backup_restore(request, backup_id):
    overview = get_recovery_overview()
    expected_phrase = overview["restore_confirmation_phrase"]
    phrase = (request.POST.get("confirmation_phrase") or "").strip()
    restore_media = request.POST.get("restore_media") == "on"

    if phrase != expected_phrase:
        return JsonResponse(
            {
                "success": False,
                "error": "Die Sicherheitsphrase stimmt nicht.",
            },
            status=400,
        )

    backup_record = get_object_or_404(
        RecoveryBackup,
        id=backup_id,
        status=RecoveryBackup.STATUS_SUCCEEDED,
    )

    try:
        summary = restore_remote_backup(backup_record, restore_media=restore_media)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "message": "Remote-Backup wurde wiederhergestellt. Bitte melde dich neu an, falls deine Sitzung abgelaufen ist.",
            "summary": summary,
        }
    )


@login_required(login_url='login')
@cms_permission_required("recovery.manage")
@require_POST
def recovery_remote_backup_object_restore(request):
    overview = get_recovery_overview()
    expected_phrase = overview["restore_confirmation_phrase"]
    phrase = (request.POST.get("confirmation_phrase") or "").strip()
    object_key = (request.POST.get("object_key") or "").strip()
    restore_media = request.POST.get("restore_media") == "on"

    if phrase != expected_phrase:
        return JsonResponse(
            {
                "success": False,
                "error": "Die Sicherheitsphrase stimmt nicht.",
            },
            status=400,
        )

    if not object_key:
        return JsonResponse(
            {
                "success": False,
                "error": "Remote-Backup wurde nicht ausgewählt.",
            },
            status=400,
        )

    try:
        summary = restore_remote_backup_object(object_key, restore_media=restore_media)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "message": "Remote-Backup wurde wiederhergestellt. Bitte melde dich neu an, falls deine Sitzung abgelaufen ist.",
            "summary": summary,
        }
    )


def _generate_initial_password():
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*"
    return get_random_string(16, allowed_chars=chars)


def _send_user_credentials_email(user, raw_password, request_user):
    recipient = (user.email or "").strip()
    if not recipient:
        settings_obj = _get_user_settings(user)
        recipient = (settings_obj.email or "").strip()

    if not recipient:
        return "Für diesen Nutzer ist keine E-Mail-Adresse hinterlegt."

    login_url = request_user.build_absolute_uri(reverse("ycms:login"))
    subject = "Dein YooLink CMS Zugang"
    message = (
        f"Hallo {user.username},\n\n"
        "für dich wurde ein YooLink CMS Zugang erstellt oder zurückgesetzt.\n\n"
        f"Login: {login_url}\n"
        f"Benutzername: {user.username}\n"
        f"Initiales Passwort: {raw_password}\n\n"
        "Bitte melde dich an und ändere dein Passwort direkt beim ersten Login.\n"
    )
    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        [recipient],
        fail_silently=False,
    )
    return ""


def _sync_user_roles(user, role_ids):
    role_ids = [role_id for role_id in role_ids if str(role_id).isdigit()]
    roles = CMSRole.objects.filter(id__in=role_ids)
    CMSUserRole.objects.filter(user=user).exclude(role__in=roles).delete()
    for role in roles:
        CMSUserRole.objects.get_or_create(user=user, role=role)


@login_required(login_url='login')
@cms_permission_required("users.manage")
def cms_users_view(request):
    ensure_system_roles()
    generated_credentials = None

    if request.method == "POST":
        action = request.POST.get("action", "create")
        user_id = request.POST.get("user_id")

        if action == "delete":
            target = get_object_or_404(User, id=user_id)
            if target == request.user:
                messages.error(request, "Du kannst deinen eigenen Nutzer nicht löschen.")
            else:
                target.is_active = False
                target.save(update_fields=["is_active"])
                CMSUserRole.objects.filter(user=target).delete()
                messages.success(request, "Nutzer wurde deaktiviert und hat keine CMS-Rollen mehr.")
            return redirect("ycms:users")

        if action == "reset_password":
            target = get_object_or_404(User, id=user_id)
            raw_password = _generate_initial_password()
            target.set_password(raw_password)
            target.save(update_fields=["password"])
            target_settings = _get_user_settings(target)
            target_settings.must_change_password = True
            target_settings.save(update_fields=["must_change_password"])

            send_error = ""
            if request.POST.get("send_email") == "true":
                send_error = _send_user_credentials_email(target, raw_password, request)

            if send_error:
                messages.warning(request, send_error)
            else:
                messages.success(request, "Initiales Passwort wurde erzeugt.")
            generated_credentials = {"user": target, "password": raw_password}
        elif action == "update":
            target = get_object_or_404(User, id=user_id)
            is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
            username = (request.POST.get("username") or "").strip()
            email = (request.POST.get("email") or "").strip()
            full_name = (request.POST.get("full_name") or "").strip()

            def _update_fail(msg):
                if is_ajax:
                    return JsonResponse({"success": False, "error": msg}, status=400)
                messages.error(request, msg)
                return redirect("ycms:users")

            if not username or not email:
                return _update_fail("Benutzername und E-Mail sind Pflichtfelder.")
            # Eindeutigkeit nur prüfen, wenn der Wert tatsächlich geändert wurde,
            # damit bestehende Nutzer (z. B. mit historisch doppelter E-Mail) speicherbar bleiben.
            if username.lower() != (target.username or "").lower() and \
                    User.objects.filter(username__iexact=username).exclude(id=target.id).exists():
                return _update_fail("Dieser Benutzername ist bereits vergeben.")
            if email.lower() != (target.email or "").lower() and \
                    User.objects.filter(email__iexact=email).exclude(id=target.id).exists():
                return _update_fail("Diese E-Mail-Adresse ist bereits vergeben.")

            target.username = username
            target.email = email
            target.name = full_name
            target.is_active = request.POST.get("is_active") == "on"
            target.save(update_fields=["username", "email", "name", "is_active"])

            target_settings = _get_user_settings(target)
            target_settings.email = target.email
            target_settings.full_name = target.name
            target_settings.save(update_fields=["email", "full_name"])
            _sync_user_roles(target, request.POST.getlist("roles"))

            if is_ajax:
                return JsonResponse({
                    "success": True,
                    "message": "Nutzer wurde aktualisiert.",
                    "is_active": target.is_active,
                    "username": target.username,
                    "email": target.email,
                    "name": target.name,
                })
            messages.success(request, "Nutzer wurde aktualisiert.")
            return redirect("ycms:users")
        else:
            username = (request.POST.get("username") or "").strip()
            email = (request.POST.get("email") or "").strip()
            full_name = (request.POST.get("full_name") or "").strip()

            if not username or not email:
                messages.error(request, "Benutzername und E-Mail sind Pflichtfelder.")
            elif User.objects.filter(username__iexact=username).exists():
                messages.error(request, "Dieser Benutzername ist bereits vergeben.")
            elif User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Diese E-Mail-Adresse ist bereits vergeben.")
            else:
                raw_password = (request.POST.get("password") or "").strip() or _generate_initial_password()
                target = User.objects.create_user(
                    username=username,
                    email=email,
                    password=raw_password,
                    name=full_name,
                    is_active=True,
                )
                target_settings = _get_user_settings(target)
                target_settings.email = email
                target_settings.full_name = full_name
                target_settings.must_change_password = True
                target_settings.save(update_fields=["email", "full_name", "must_change_password"])
                _sync_user_roles(target, request.POST.getlist("roles"))

                send_error = ""
                if request.POST.get("send_email") == "on":
                    send_error = _send_user_credentials_email(target, raw_password, request)

                if send_error:
                    messages.warning(request, send_error)
                else:
                    messages.success(request, "Nutzer wurde erstellt.")
                generated_credentials = {"user": target, "password": raw_password}

    roles = CMSRole.objects.all()
    users = User.objects.select_related("usersettings").prefetch_related("cms_role_assignments__role").order_by("username")
    return render(
        request,
        "pages/cms/settings/users.html",
        {
            "users": users,
            "roles": roles,
            "generated_credentials": generated_credentials,
        },
    )


@login_required(login_url='login')
@cms_permission_required("roles.manage")
def cms_roles_view(request):
    ensure_system_roles()

    if request.method == "POST":
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        action = request.POST.get("action", "create")
        role_id = request.POST.get("role_id")

        def _fail(msg, status=400):
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=status)
            messages.error(request, msg)
            return redirect("ycms:roles")

        def _role_payload(role):
            return {
                "id": role.id,
                "name": role.name,
                "slug": role.slug,
                "description": role.description,
                "permissions": role.permissions,
                "permission_count": len(role.permissions or []),
            }

        if action == "delete":
            role = CMSRole.objects.filter(id=role_id).first()
            if role is None:
                return _fail("Rolle wurde nicht gefunden.", status=404)
            if role.is_system:
                return _fail("Systemrollen können nicht gelöscht werden.")
            role.delete()
            if is_ajax:
                return JsonResponse({"success": True, "message": "Rolle wurde gelöscht.", "role_id": int(role_id)})
            messages.success(request, "Rolle wurde gelöscht.")
            return redirect("ycms:roles")

        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        permissions = request.POST.getlist("permissions")
        valid_permissions = {code for code, _label in CMS_PERMISSION_CHOICES}
        permissions = sorted(set(permissions) & valid_permissions)
        slug = slugify(name)

        if not name:
            return _fail("Bitte gib einen Rollennamen an.")
        if not permissions:
            return _fail("Bitte wähle mindestens eine Berechtigung.")

        if action == "update":
            role = CMSRole.objects.filter(id=role_id).first()
            if role is None:
                return _fail("Rolle wurde nicht gefunden.", status=404)
            if role.is_system:
                return _fail("Systemrollen können nicht bearbeitet werden.")
            if CMSRole.objects.filter(slug=slug).exclude(id=role.id).exists():
                return _fail("Eine Rolle mit diesem Namen existiert bereits.")
            role.name = name
            role.slug = slug
            role.description = description
            role.permissions = permissions
            role.save()
            if is_ajax:
                return JsonResponse({"success": True, "message": "Rolle wurde aktualisiert.", "role": _role_payload(role)})
            messages.success(request, "Rolle wurde aktualisiert.")
            return redirect("ycms:roles")

        # create
        if CMSRole.objects.filter(slug=slug).exists():
            return _fail("Eine Rolle mit diesem Namen existiert bereits.")
        role = CMSRole(name=name, slug=slug, description=description, permissions=permissions)
        role.save()
        if is_ajax:
            return JsonResponse({"success": True, "message": "Rolle wurde erstellt.", "role": _role_payload(role)})
        messages.success(request, "Rolle wurde erstellt.")
        return redirect("ycms:roles")

    return render(
        request,
        "pages/cms/settings/roles.html",
        {
            "roles": CMSRole.objects.all(),
            "permission_choices": CMS_PERMISSION_CHOICES,
            "empty_role": {"id": "", "name": "", "description": "", "permissions": [], "is_system": False},
        },
    )


def _parse_developer_key_expiry(request):
    expires_in = request.POST.get("expires_in", "never")

    if expires_in == "never":
        return None, ""

    if expires_in == "custom":
        raw_value = (request.POST.get("custom_expires_at") or "").strip()
        if not raw_value:
            return None, "Bitte gib ein Ablaufdatum an."

        for date_format in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                naive = datetime.strptime(raw_value, date_format)
                expires_at = timezone.make_aware(naive, timezone.get_default_timezone())
                break
            except ValueError:
                expires_at = None

        if not expires_at:
            return None, "Das Ablaufdatum ist ungültig."

        if expires_at <= timezone.now():
            return None, "Das Ablaufdatum muss in der Zukunft liegen."

        return expires_at, ""

    allowed_days = {"30": 30, "90": 90, "365": 365}
    days = allowed_days.get(expires_in)
    if not days:
        return None, "Die ausgewählte Laufzeit ist ungültig."

    return timezone.now() + timedelta(days=days), ""


@login_required(login_url='login')
@cms_permission_required("developer.manage")
def developer_settings_view(request):
    generated_api_key = ""

    if request.method == "POST":
        action = request.POST.get("action", "create")

        if action == "revoke":
            api_key = get_object_or_404(
                DeveloperApiKey,
                id=request.POST.get("key_id"),
                created_by=request.user,
            )
            api_key.revoke()
            messages.success(request, "Der API-Key wurde widerrufen.")
            return redirect("ycms:developer-settings")

        name = (request.POST.get("name") or "").strip()
        access_level = request.POST.get("access_level", DeveloperApiKey.READ)
        allowed_apps = request.POST.getlist("allowed_apps")
        valid_access_levels = {choice[0] for choice in DeveloperApiKey.ACCESS_LEVEL_CHOICES}
        valid_apps = {choice[0] for choice in DeveloperApiKey.APP_CHOICES}
        allowed_apps = [app for app in allowed_apps if app in valid_apps]

        expires_at, expiry_error = _parse_developer_key_expiry(request)

        if not name:
            messages.error(request, "Bitte gib dem API-Key einen Namen.")
        elif access_level not in valid_access_levels:
            messages.error(request, "Die Berechtigungsstufe ist ungültig.")
        elif not allowed_apps:
            messages.error(request, "Bitte wähle mindestens eine App aus.")
        elif expiry_error:
            messages.error(request, expiry_error)
        else:
            _, generated_api_key = DeveloperApiKey.issue_key(
                created_by=request.user,
                name=name,
                access_level=access_level,
                allowed_apps=allowed_apps,
                expires_at=expires_at,
            )
            messages.success(request, "Der API-Key wurde erstellt. Kopiere ihn jetzt, er wird später nicht erneut angezeigt.")

    all_api_keys = DeveloperApiKey.objects.filter(created_by=request.user)
    api_keys = [api_key for api_key in all_api_keys if not api_key.is_revoked()]
    revoked_api_keys = [api_key for api_key in all_api_keys if api_key.is_revoked()]
    active_keys_count = sum(1 for api_key in api_keys if api_key.is_usable())
    api_base_url = request.build_absolute_uri("/api/cms/")
    blog_api_url = request.build_absolute_uri("/api/cms/blog/")
    api_ping_url = request.build_absolute_uri("/api/ping/")
    api_connect_authorize_url = request.build_absolute_uri(reverse("ycms:developer-connect"))
    api_connect_token_url = request.build_absolute_uri(reverse("api:developer-connect-token"))
    api_docs_url = request.build_absolute_uri(reverse("api-docs"))
    api_schema_url = request.build_absolute_uri(reverse("api-schema"))

    return render(
        request,
        "pages/cms/settings/developer.html",
        {
            "api_keys": api_keys,
            "revoked_api_keys": revoked_api_keys,
            "active_keys_count": active_keys_count,
            "app_choices": DeveloperApiKey.APP_CHOICES,
            "access_level_choices": DeveloperApiKey.ACCESS_LEVEL_CHOICES,
            "generated_api_key": generated_api_key,
            "api_base_url": api_base_url,
            "blog_api_url": blog_api_url,
            "api_ping_url": api_ping_url,
            "api_connect_authorize_url": api_connect_authorize_url,
            "api_connect_token_url": api_connect_token_url,
            "api_docs_url": api_docs_url,
            "api_schema_url": api_schema_url,
        },
    )


@login_required(login_url='login')
@cms_permission_required("developer.manage")
def developer_api_docs_view(request):
    return render(
        request,
        "pages/cms/settings/developer_api_docs.html",
        {
            "api_base_url": request.build_absolute_uri("/api/cms/"),
            "blog_api_url": request.build_absolute_uri("/api/cms/blog/"),
            "api_ping_url": request.build_absolute_uri("/api/ping/"),
            "api_connect_authorize_url": request.build_absolute_uri(reverse("ycms:developer-connect")),
            "api_connect_token_url": request.build_absolute_uri(reverse("api:developer-connect-token")),
            "api_docs_url": request.build_absolute_uri(reverse("api-docs")),
            "api_schema_url": request.build_absolute_uri(reverse("api-schema")),
        },
    )


def _connect_error_redirect(redirect_uri, *, error, error_description="", state=""):
    params = {"error": error}
    if error_description:
        params["error_description"] = error_description
    if state:
        params["state"] = state
    return _connect_redirect(redirect_uri, params)


def _connect_redirect(redirect_uri, params):
    parsed = urlparse(redirect_uri)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend((key, value) for key, value in params.items() if value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _validate_connect_redirect_uri(redirect_uri):
    if not redirect_uri:
        return "redirect_uri fehlt."

    parsed = urlparse(redirect_uri)
    if parsed.fragment:
        return "redirect_uri darf keinen Fragment-Teil enthalten."

    if parsed.scheme == "https" and parsed.netloc:
        return ""

    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if settings.DEBUG and parsed.scheme == "http" and parsed.hostname in local_hosts:
        return ""

    return "redirect_uri muss eine HTTPS-URL sein. Im DEBUG-Modus ist localhost per HTTP erlaubt."


def _parse_connect_apps(raw_apps):
    raw_apps = raw_apps or DeveloperApiKey.APP_BLOG
    values = [value.strip().lower() for value in re.split(r"[\s,]+", raw_apps) if value.strip()]
    normalized = []
    valid_apps = {choice[0] for choice in DeveloperApiKey.APP_CHOICES}

    for value in values:
        if value == DeveloperApiKey.LEGACY_APP_BLOGS:
            value = DeveloperApiKey.APP_BLOG
        if value not in valid_apps:
            return [], f"Unbekannter App Scope: {value}"
        normalized.append(value)

    return sorted(set(normalized or [DeveloperApiKey.APP_BLOG])), ""


def _get_connect_context(request):
    source = request.POST if request.method == "POST" else request.GET
    raw_apps = source.get("scope") or source.get("apps") or DeveloperApiKey.APP_BLOG
    allowed_apps, apps_error = _parse_connect_apps(raw_apps)
    access_level = source.get("access_level") or DeveloperApiKey.READ
    redirect_uri = (source.get("redirect_uri") or "").strip()
    code_challenge_method = (source.get("code_challenge_method") or DeveloperApiConnectAuthorization.METHOD_S256).strip()
    client_name = (source.get("client_name") or source.get("client_id") or "Externe Anwendung").strip()[:160]

    errors = []
    redirect_error = _validate_connect_redirect_uri(redirect_uri)
    if redirect_error:
        errors.append(redirect_error)
    if apps_error:
        errors.append(apps_error)
    if access_level not in {choice[0] for choice in DeveloperApiKey.ACCESS_LEVEL_CHOICES}:
        errors.append("access_level muss read oder write sein.")
    if not source.get("code_challenge"):
        errors.append("code_challenge fehlt.")
    if code_challenge_method != DeveloperApiConnectAuthorization.METHOD_S256:
        errors.append("code_challenge_method muss S256 sein.")

    params = {
        "client_name": client_name,
        "redirect_uri": redirect_uri,
        "state": (source.get("state") or "").strip(),
        "code_challenge": (source.get("code_challenge") or "").strip(),
        "code_challenge_method": code_challenge_method,
        "access_level": access_level,
        "scope": " ".join(allowed_apps or [DeveloperApiKey.APP_BLOG]),
    }

    return {
        "errors": errors,
        "connect_params": params,
        "allowed_apps": allowed_apps,
        "access_level_label": dict(DeveloperApiKey.ACCESS_LEVEL_CHOICES).get(access_level, access_level),
        "app_labels": [dict(DeveloperApiKey.APP_CHOICES).get(app, app) for app in allowed_apps],
    }


@login_required(login_url='login')
@cms_permission_required("developer.manage")
def developer_connect_view(request):
    context = _get_connect_context(request)
    params = context["connect_params"]

    if request.method == "POST" and request.POST.get("action") == "deny" and params["redirect_uri"]:
        return redirect(
            _connect_error_redirect(
                params["redirect_uri"],
                error="access_denied",
                error_description="Der YooLink Benutzer hat die Verbindung abgelehnt.",
                state=params["state"],
            )
        )

    if context["errors"]:
        return render(request, "pages/cms/settings/developer_connect.html", context, status=400)

    if request.method == "POST":
        _, raw_code = DeveloperApiConnectAuthorization.issue_code(
            created_by=request.user,
            client_name=params["client_name"],
            redirect_uri=params["redirect_uri"],
            state=params["state"],
            code_challenge=params["code_challenge"],
            code_challenge_method=params["code_challenge_method"],
            access_level=params["access_level"],
            allowed_apps=context["allowed_apps"],
        )
        return redirect(_connect_redirect(params["redirect_uri"], {"code": raw_code, "state": params["state"]}))

    return render(request, "pages/cms/settings/developer_connect.html", context)


@login_required(login_url='login')
@cms_permission_required("website_settings.edit")
def update_logo_favicon(request):
    website_settings = _get_website_settings()
    updated = False

    if request.method == 'POST':
        if 'logo' in request.FILES:
            try:
                validate_image_upload(request.FILES['logo'], label="Logo")
            except ValidationError as error:
                return upload_validation_error_response(error)
            website_settings.logo = request.FILES['logo']
            updated = True
        if 'favicon' in request.FILES:
            try:
                validate_image_upload(request.FILES['favicon'], label="Favicon")
            except ValidationError as error:
                return upload_validation_error_response(error)
            website_settings.favicon = request.FILES['favicon']
            updated = True
        if updated:
            website_settings.save()
            return JsonResponse({'success': 'Datei erfolgreich aktualisiert'})

    return JsonResponse({'error': 'Keine Datei übermittelt'}, status=400)


@login_required(login_url='login')
@cms_permission_required("website_settings.edit")
def delete_logo_favicon(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Ungültige Anfrage'}, status=405)

    website_settings = _get_website_settings()
    file_type = request.POST.get('type')

    if file_type == 'logo' and website_settings.logo:
        website_settings.logo.delete(save=False)
        website_settings.logo = ''
    elif file_type == 'favicon' and website_settings.favicon:
        website_settings.favicon.delete(save=False)
        website_settings.favicon = ''
    else:
        return JsonResponse({'error': 'Ungültiger Typ oder keine Datei vorhanden'}, status=400)

    website_settings.save()
    return JsonResponse({'success': f'{file_type.capitalize()} gelöscht'})


@require_POST
@login_required(login_url='login')
def send_email_2fa_code(request):
    user_settings = _get_user_settings(request.user)
    email = (user_settings.email or '').strip()

    if not email:
        return JsonResponse(
            {'error': 'Bitte speichere zuerst eine E-Mail-Adresse in deinem Profil.'},
            status=400
        )

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'error': 'Die hinterlegte E-Mail-Adresse ist ungültig.'}, status=400)

    try:
        _issue_login_2fa_code(user_settings, request.user)
    except ValidationError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except RuntimeError:
        return JsonResponse({'error': 'Die Bestätigungs-E-Mail konnte nicht versendet werden.'}, status=500)

    return JsonResponse({'success': f'Der Bestätigungscode wurde an {email} gesendet.'})


@require_POST
@login_required(login_url='login')
def verify_email_2fa_code(request):
    user_settings = _get_user_settings(request.user)
    code = request.POST.get('code', '').strip()

    if not code:
        return JsonResponse({'error': 'Bitte gib den Bestätigungscode ein.'}, status=400)

    if not user_settings.two_factor_email_code:
        return JsonResponse({'error': 'Es wurde noch kein Code angefordert.'}, status=400)

    if user_settings.two_factor_email_code_expires_at and timezone.now() > user_settings.two_factor_email_code_expires_at:
        user_settings.two_factor_email_code = ''
        user_settings.two_factor_email_code_expires_at = None
        user_settings.two_factor_email_verified = False
        user_settings.save(update_fields=[
            'two_factor_email_code',
            'two_factor_email_code_expires_at',
            'two_factor_email_verified',
        ])
        return JsonResponse({'error': 'Der Code ist abgelaufen. Bitte fordere einen neuen an.'}, status=400)

    if code != user_settings.two_factor_email_code:
        return JsonResponse({'error': 'Der eingegebene Code ist ungültig.'}, status=400)

    if not (user_settings.email or '').strip():
        return JsonResponse({'error': 'Für die Aktivierung muss eine E-Mail-Adresse hinterlegt sein.'}, status=400)

    user_settings.two_factor_email_enabled = True
    user_settings.two_factor_email_verified = True
    user_settings.two_factor_email_code = ''
    user_settings.two_factor_email_code_expires_at = None
    user_settings.save(update_fields=[
        'two_factor_email_enabled',
        'two_factor_email_verified',
        'two_factor_email_code',
        'two_factor_email_code_expires_at',
    ])

    return JsonResponse({'success': 'Die E-Mail-2FA wurde erfolgreich aktiviert.'})


@require_POST
@login_required(login_url='login')
def disable_email_2fa(request):
    user_settings = _get_user_settings(request.user)

    user_settings.two_factor_email_enabled = False
    user_settings.two_factor_email_verified = False
    user_settings.two_factor_email_code = ''
    user_settings.two_factor_email_code_expires_at = None
    user_settings.save(update_fields=[
        'two_factor_email_enabled',
        'two_factor_email_verified',
        'two_factor_email_code',
        'two_factor_email_code_expires_at',
    ])

    return JsonResponse({'success': 'Die E-Mail-2FA wurde deaktiviert.'})

"""
Opening Hours
"""

@login_required(login_url='login')
@cms_permission_required("opening_hours.edit")
def opening_hours_view(request):
    # Retrieve the UserSettings for the currently logged-in user or any specific user

    website_settings = _get_website_settings()

    for day_abbr, _ in OpeningHours.DAY_CHOICES:
        # Überprüfen, ob bereits Öffnungszeiten für diesen Tag existieren
        obj, created = OpeningHours.objects.get_or_create(
            website=website_settings,
            day=day_abbr,
            defaults={"user": request.user},
        )
        # Wenn Objekt gerade erstellt wurde, können Sie es initialisieren, wenn nötig
        if created:
            # obj.some_field = some_value
            obj.save()

    opening_hours = OpeningHours.objects.filter(website=website_settings).order_by("id")

    context = {
        'opening_hours': opening_hours,
        'settings': website_settings
        # Other context variables if needed
    }

    return render(request, 'pages/cms/openinghours/openingHours.html', context)

from django.utils import timezone as dj_timezone

@extend_schema(exclude=True)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def opening_hours_update(request):
    if "opening_hours.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Öffnungszeiten.'}, status=403)

    opening_hours_data = request.POST.get('opening_hours')
    opening_hours = json.loads(opening_hours_data)
    website_settings = _get_website_settings()
    errors = []
    for item in opening_hours:
        day = item['day']
        is_open = bool(item['isOpen'])  # Convert to boolean
        start_time = item['startTime']
        end_time = item['endTime']
        has_lunch_break = item['hasLunchBreak']
        lunch_break_start = item['lunchBreakStart']
        lunch_break_end = item['lunchBreakEnd']
        
        if is_open and (not start_time or not end_time or not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', start_time) or not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', end_time)):
            errors.append(f"Ungültiges Format für Öffnungszeiten am {day}")
            continue
        
        # Validierung für Mittagspause
        if has_lunch_break:
            if not lunch_break_start or not lunch_break_end or not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', lunch_break_start) or not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', lunch_break_end):
                errors.append(f"Ungültiges Format für Mittagspause am {day}.")
                continue

        opening_hour, _created = OpeningHours.objects.get_or_create(
            website=website_settings,
            day=day,
            defaults={"user": request.user},
        )
        opening_hour.is_open = is_open
        if start_time:
            opening_hour.start_time = start_time
        if end_time:
            opening_hour.end_time = end_time
        opening_hour.has_lunch_break = has_lunch_break if has_lunch_break else False
        opening_hour.lunch_break_start = lunch_break_start if has_lunch_break else None
        opening_hour.lunch_break_end = lunch_break_end if has_lunch_break else None
        opening_hour.save()

    # Toggle + Text
    vacation = request.POST.get('vacation', False)
    website_settings.vacation = (str(vacation).lower() == 'true')

    lang = get_active_language(request)
    vacationText = request.POST.get('vacationText')
    if vacationText is not None:
        setattr(website_settings, f'vacationText_{lang}', vacationText)
        if lang == DEFAULT_LANGUAGE:
            website_settings.vacationText = vacationText

    # ▼ Neu: Zeitraum
    v_start_raw = request.POST.get('vacation_start')  # "YYYY-MM-DDTHH:MM" oder ""
    v_end_raw   = request.POST.get('vacation_end')

    def parse_dt_local(val):
        if not val:
            return None
        # Browser schicken mal ohne/mit Sekunden
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                naive = datetime.strptime(val, fmt)
                # <<< WICHTIG: Default-TZ, nicht current!
                tz = dj_timezone.get_default_timezone()      # i.d.R. Europe/Berlin
                return dj_timezone.make_aware(naive, tz)
            except ValueError:
                continue
        return None

    v_start = parse_dt_local(v_start_raw)
    v_end   = parse_dt_local(v_end_raw)

    # Validierung
    if v_start and v_end and v_start > v_end:
        errors.append("Urlaubsbeginn darf nicht nach dem Urlaubsende liegen.")
    else:
        website_settings.vacation_start = v_start
        website_settings.vacation_end   = v_end

    # Speichern
    try:
        website_settings.clean()
    except Exception as e:
        errors.append(str(e))

    website_settings.save()

    if errors:
        return JsonResponse({'error': 'Eine oder mehrere Öffnungszeiten konnten nicht gespeichert werden', 'errors': errors}, status=400)
    return JsonResponse({'success': 'Öffnungszeiten erfolgreich aktualisiert'})

# View to display all TeamMembers
@login_required(login_url='login')
@cms_permission_required("team.edit")
def team_member_list(request):
    team_members = TeamMember.objects.all().order_by("display_order", "id")
    context = {
        'team_members': team_members,
    }
    return render(request, 'pages/cms/team/team.html', context)

# Kunden-Demos: statische Übersicht, keine DB-Objekte (bewusst hart codiert)
DEMO_PROJECTS = [
    {
        "slug": "baugenossenschaft-plattling",
        "customer": "Baugenossenschaft Plattling eG",
        "title": "Landingpage-Demo: Baugenossenschaft Plattling eG",
        "description": "Modernisierte Landingpage im Original-Farbschema (Schieferblau/Gelb) mit echten Inhalten der Bestandsseite.",
        "icon": "bi-buildings",
        "tone": "slate",
    },
    {
        "slug": "musterkunde",
        "customer": "Café Musterkunde",
        "title": "Landingpage-Demo: Café Musterkunde",
        "description": "Beispiel-Landingpage für ein fiktives Café - als Vorlage für Kundenpräsentationen.",
        "icon": "bi-cup-hot",
        "tone": "amber",
    },
]

# Erlaubte Unterseiten je Demo. Nur diese Slugs landen im Templatepfad.
DEMO_SUBPAGES = {
    "baugenossenschaft-plattling": ["kontakt", "aktuelles"],
}

def _demo_noindex(response):
    # Demos sind ohne Login erreichbar, duerfen aber nicht in Suchmaschinen landen.
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response

@login_required(login_url='login')
def cms_demos_view(request):
    return render(request, 'pages/cms/demos/demos.html', {'demos': DEMO_PROJECTS})

# Bewusst ohne Login: Kunden bekommen den Demo-Link direkt zugeschickt.
def cms_demo_detail(request, slug):
    demo = next((d for d in DEMO_PROJECTS if d["slug"] == slug), None)
    if demo is None:
        raise Http404("Demo nicht gefunden.")
    return _demo_noindex(render(request, f'pages/demos/{slug}.html', {'demo': demo, 'demo_page': 'start'}))

def cms_demo_subpage(request, slug, subpage):
    demo = next((d for d in DEMO_PROJECTS if d["slug"] == slug), None)
    if demo is None or subpage not in DEMO_SUBPAGES.get(slug, []):
        raise Http404("Demo-Unterseite nicht gefunden.")
    return _demo_noindex(render(request, f'pages/demos/{slug}-{subpage}.html', {'demo': demo, 'demo_page': subpage}))

from django.db.models import Max

# View to handle the creation of a TeamMember
@extend_schema(exclude=True)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_team_member(request):
    if "team.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Team.'}, status=403)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        
        # Überprüfen, ob der Name vorhanden ist
        if not full_name:
            return JsonResponse({'error': 'Voller Name ist erforderlich.'}, status=400)

        # Initialisiere optionale Felder
        active = request.POST.get('active', 'true') == "true"
        image = request.POST.get('image', '').strip()
        age = request.POST.get('age')
        email = request.POST.get('email', '').strip()
        raw_years = (request.POST.get('years_with_team') or '').strip()
        years_with_team = int(raw_years) if raw_years.isdigit() else 0
        position = request.POST.get('position', 'Mitarbeiter')
        note = request.POST.get('note', '')

        max_order = TeamMember.objects.aggregate(m=Max('display_order'))['m'] or 0
        next_order = max_order + 1

        # TeamMember erstellen
        try:
            team_member = TeamMember(
                full_name=full_name,
                active=active,
                years_with_team=years_with_team,
                position=position,
                note=note,
                display_order=next_order,
            )

            # Optionale Felder nur setzen, wenn sie vorhanden und nicht leer sind
            if image:
                team_member.image = image
            if age:
                team_member.age = int(age)
            if email:
                if TeamMember.objects.filter(email=email).exists():
                    return JsonResponse({'error': 'Diese E-Mail wird bereits verwendet.'}, status=400)
                team_member.email = email

            team_member.save()

            return JsonResponse({'success': 'Teammitglied wurde erfolgreich erstellt', 'member_id': team_member.id})
        except IntegrityError:
            return JsonResponse({'error': 'Fehler beim Erstellen des Teammitglieds, möglicherweise durch Duplikate.'}, status=400)

    return JsonResponse({'error': 'Fehler beim Erstellen vom Teammitglied'}, status=400)

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_team_member(request, id):
    if "team.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Team.'}, status=403)

    team_member = get_object_or_404(TeamMember, id=id)
    return JsonResponse({
        'full_name': team_member.full_name,
        'active': team_member.active,
        'image': team_member.image,
        'age': team_member.age,
        'email': team_member.email,
        'years_with_team': team_member.years_with_team,
        'position': team_member.position,
        'note': team_member.note
    })

@extend_schema(exclude=True)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_team_member(request, id):
    if "team.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Team.'}, status=403)

    team_member = get_object_or_404(TeamMember, id=id)
    data = request.data

    # E-Mail-Überprüfung auf Duplikate
    new_email = data.get('email', team_member.email).strip()
    if new_email and TeamMember.objects.filter(email=new_email).exclude(id=team_member.id).exists():
        return JsonResponse({'error': 'Diese E-Mail wird bereits verwendet.'}, status=400)

    # Felder aktualisieren
    team_member.full_name = data.get('full_name', team_member.full_name).strip()
    if not team_member.full_name:
        return JsonResponse({'error': 'Voller Name ist erforderlich.'}, status=400)

    team_member.position = data.get('position', team_member.position)
    raw_years = (data.get('years_with_team') or '').strip()
    team_member.years_with_team = int(raw_years) if raw_years.isdigit() else 0

    if 'age' in data and data['age']:
        team_member.age = int(data['age'])
    else:
        team_member.age = None

    if new_email:
        team_member.email = new_email

    team_member.note = data.get('note', team_member.note)
    
    # Active-Feld nur aktualisieren, wenn es explizit im Request vorhanden ist
    if 'active' in data:
        team_member.active = str(data['active']).lower() == "true"
    
    # Image nur aktualisieren, wenn ein nicht-leerer Wert übergeben wurde
    if data.get('image', '').strip():
        team_member.image = data['image']
    
    team_member.save()
    return JsonResponse({'success': 'Teammitglied wurde erfolgreich aktualisiert'})

@extend_schema(exclude=True)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_team_member(request, id):
    if "team.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Team.'}, status=403)

    team_member = get_object_or_404(TeamMember, id=id)
    team_member.delete()
    return JsonResponse({'success': 'Teammitglied wurde erfolgreich gelöscht'})

from django.views.decorators.http import require_POST

@extend_schema(exclude=True)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reorder_team_members(request):
    if "team.edit" not in user_permissions(request.user):
        return JsonResponse({'error': 'Du hast keine Berechtigung für Team.'}, status=403)

    # akzeptiere sowohl JSON ("order":[1,2,3]) als auch Form-POST (order[]=1&order[]=2)
    order = request.data.get('order')

    if order is None:
        order = request.POST.getlist('order[]') or request.POST.getlist('order')

    if not order:
        return JsonResponse({'error': 'Keine Reihenfolge übergeben.'}, status=400)

    # ids cleanen
    try:
        ids = [int(x) for x in order]
    except Exception:
        return JsonResponse({'error': 'Ungültige ID-Liste.'}, status=400)

    # update display_order (1..n)
    for idx, member_id in enumerate(ids, start=1):
        TeamMember.objects.filter(id=member_id).update(display_order=idx)

    return JsonResponse({'success': 'Reihenfolge gespeichert'})

##################
#    PRICING     #
##################
@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def pricing_card_overview(request):
    cards = PricingCard.objects.select_related('button').all().order_by('order')
    return render(request, 'pages/cms/pricing/pricing.html', {
        'pricing_cards': cards
    })

@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def create_pricing_card(request):
    if request.method == "GET":
        # Optional: Alle Buttons anzeigen, um sie im Template als Auswahl zu rendern
        buttons = Button.objects.all().order_by("order")
        return render(request, "pages/cms/pricing/pricing_create.html", {
            "buttons": buttons
        })

    elif request.method == "POST":
        data = json.loads(request.body)
        lang = get_active_language(request)

        button_id = data.get("button_id")
        button = Button.objects.filter(pk=button_id).first() if button_id else None

        card = PricingCard()
        setattr(card, f"title_{lang}", data["title"])
        setattr(card, f"description_{lang}", data.get("description", ""))

        if lang == DEFAULT_LANGUAGE:
            card.title = data["title"]
            card.description = data.get("description", "")

        card.monthly_price = data["monthly_price"]
        card.one_time_price = data["one_time_price"]
        max_order = PricingCard.objects.aggregate(models.Max("order"))["order__max"] or 0
        card.order = max_order + 1
        card.animation = data.get("animation", "fade-up")
        card.animation_delay = data.get("animation_delay", 100)
        card.button = button
        card.active = data.get("active", True)
        card.save()

        return JsonResponse({"id": card.id})

    return HttpResponseBadRequest()


@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def edit_pricing_card(request, pk):
    card = get_object_or_404(PricingCard, pk=pk)

    if request.method == "GET":
        buttons = Button.objects.all().order_by("order")
        return render(request, "pages/cms/pricing/pricing_edit.html", {
            "card": card,
            "buttons": buttons
        })

    elif request.method == "POST":
        data = json.loads(request.body)
        lang = get_active_language(request)

        button_id = data.get("button_id")
        button = Button.objects.filter(pk=button_id).first() if button_id else None

        setattr(card, f"title_{lang}", data["title"])
        setattr(card, f"description_{lang}", data.get("description", ""))

        if lang == DEFAULT_LANGUAGE:
            card.title = data["title"]
            card.description = data.get("description", "")

        card.monthly_price = data["monthly_price"]
        card.one_time_price = data["one_time_price"]

        card.animation = data.get("animation", "fade-up")
        card.animation_delay = data.get("animation_delay", 100)
        card.button = button
        card.active = data.get("active", True)
        card.save()

        return JsonResponse({"success": True})


    return HttpResponseBadRequest()


@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def delete_pricing_card(request, pk):
    if request.method == "POST":
        card = get_object_or_404(PricingCard, pk=pk)
        card.delete()

        # Nach dem Löschen Reihenfolge aktualisieren
        cards = PricingCard.objects.order_by("order")
        for i, c in enumerate(cards):
            c.order = i
            c.save()

        return JsonResponse({"success": True})
    return HttpResponseBadRequest()

@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def pricingcard_reorder(request):
    if request.method == "POST":
        data = json.loads(request.body)
        for item in data.get("order", []):
            try:
                card = PricingCard.objects.get(id=item["id"])
                card.order = item["order"]
                card.save()
            except PricingCard.DoesNotExist:
                continue
        return JsonResponse({"success": True})
    return HttpResponseBadRequest()


@login_required(login_url='login')
@cms_permission_required("pricing.edit")
def manage_features(request, pk):
    card = get_object_or_404(PricingCard, pk=pk)

    if request.method == "GET":
        features = list(card.features.order_by("order").values("id", "text"))
        return JsonResponse({"features": features})

    elif request.method == "POST":
        data = json.loads(request.body)
        lang = get_active_language(request)
        new_items = data.get("features", [])

        # IDs aus dem Request sammeln
        submitted_ids = [int(item["id"]) for item in new_items if item.get("id")]

        # Existierende Features mappen
        existing = {f.id: f for f in card.features.all()}

        # Neue Reihenfolge + Updates
        for i, item in enumerate(new_items):
            text = item["text"].strip()
            fid = item.get("id")

            if fid and int(fid) in existing:
                feature = existing[int(fid)]
            else:
                feature = PricingFeature(pricing_card=card)

            setattr(feature, f"text_{lang}", text)
            if lang == DEFAULT_LANGUAGE:
                feature.text = text

            feature.order = i
            feature.save()

            if not fid:
                submitted_ids.append(feature.id)

        # Nicht mehr vorhandene Features löschen
        if submitted_ids:
            card.features.exclude(id__in=submitted_ids).delete()

        return JsonResponse({"success": True})

    return HttpResponseBadRequest()

# Vorschläge für den Seitenpfad beim Anlegen von Seiten-Links
SITE_PAGE_SUGGESTIONS = [
    ("/", "Startseite"),
    ("/leistungen/", "Leistungen"),
    ("/leistungen/webdesign/", "Leistungen – Webdesign"),
    ("/leistungen/cms/", "Leistungen – CMS"),
    ("/leistungen/logos/", "Leistungen – Logos"),
    ("/leistungen/visitenkarte/", "Leistungen – Visitenkarte"),
    ("/leistungen/medien/", "Leistungen – Medien"),
    ("/webdesign-deggendorf/", "Webdesign Deggendorf"),
    ("/kunden/", "Kunden"),
    ("/blog/", "Blog"),
    ("/shop/", "Shop"),
    ("/kontakt/", "Kontakt"),
    ("/impressum/", "Impressum"),
    ("/datenschutz/", "Datenschutz"),
]


def _apply_button_payload(button, data, lang):
    """Gemeinsame Feld-Zuweisung für Button erstellen/bearbeiten."""
    text = (data.get("text") or "").strip()
    if not text:
        return "Bitte einen Button-Text angeben."

    setattr(button, f"text_{lang}", text)
    setattr(button, f"hover_text_{lang}", data.get("hover_text", ""))
    if lang == DEFAULT_LANGUAGE:
        button.text = text
        button.hover_text = data.get("hover_text", "")

    valid_colors = {value for value, _ in Button.COLOR_CHOICES}
    color = data.get("color", "blue")
    button.color = color if color in valid_colors else "blue"

    page_link_id = data.get("page_link_id")
    button.page_link = PageLink.objects.filter(pk=page_link_id).first() if page_link_id else None
    button.url = (data.get("url") or "").strip()
    if not button.page_link and not button.url:
        return "Bitte ein Link-Ziel angeben (Seite auswählen oder eigene URL eintragen)."

    button.target = "_blank" if data.get("target") == "_blank" else "_self"
    button.icon = (data.get("icon") or "").strip()
    button.order = int(data.get("order") or 0)
    return None


@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def button_list(request):
    buttons = Button.objects.select_related("page_link").order_by("order", "id")
    page_links = PageLink.objects.prefetch_related("buttons").all()
    return render(request, "pages/cms/buttons/button_list.html", {
        "buttons": buttons,
        "page_links": page_links,
        "page_suggestions": SITE_PAGE_SUGGESTIONS,
    })

@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def button_create(request):
    if request.method == "GET":
        return render(request, "pages/cms/buttons/button_create.html", {
            "page_links": PageLink.objects.all(),
            "colors": Button.COLOR_CHOICES,
        })

    elif request.method == "POST":
        data = json.loads(request.body)
        lang = get_active_language(request)

        button = Button()
        error = _apply_button_payload(button, data, lang)
        if error:
            return JsonResponse({"error": error}, status=400)
        button.save()

        return JsonResponse({"id": button.id})

    return HttpResponseBadRequest()

@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def button_edit(request, pk):
    button = get_object_or_404(Button, pk=pk)

    if request.method == "GET":
        return render(request, "pages/cms/buttons/button_edit.html", {
            "button": button,
            "page_links": PageLink.objects.all(),
            "colors": Button.COLOR_CHOICES,
        })

    elif request.method == "POST":
        data = json.loads(request.body)
        lang = get_active_language(request)

        error = _apply_button_payload(button, data, lang)
        if error:
            return JsonResponse({"error": error}, status=400)
        button.save()

        return JsonResponse({"success": True})

    return HttpResponseBadRequest()

@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def button_delete(request, pk):
    if request.method == "POST":
        button = get_object_or_404(Button, pk=pk)
        button.delete()
        return JsonResponse({"success": True})
    return HttpResponseBadRequest()


def _pagelink_payload(data):
    """Validiert und normalisiert die Felder eines Seiten-Links."""
    title = (data.get("title") or "").strip()
    path = (data.get("path") or "").strip()
    anchor = (data.get("anchor") or "").strip().lstrip("#")
    if not title or not path:
        return None, "Bitte Titel und Seitenpfad angeben."
    if not path.startswith("/"):
        path = "/" + path
    return {"title": title, "path": path, "anchor": anchor}, None


def _pagelink_json(link):
    return {
        "id": link.id,
        "title": link.title,
        "path": link.path,
        "anchor": link.anchor,
        "url": link.url,
        "button_count": link.buttons.count(),
    }


@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def pagelink_create(request):
    if request.method == "POST":
        fields, error = _pagelink_payload(json.loads(request.body))
        if error:
            return JsonResponse({"error": error}, status=400)
        link = PageLink.objects.create(**fields)
        return JsonResponse(_pagelink_json(link))
    return HttpResponseBadRequest()


@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def pagelink_edit(request, pk):
    if request.method == "POST":
        link = get_object_or_404(PageLink, pk=pk)
        fields, error = _pagelink_payload(json.loads(request.body))
        if error:
            return JsonResponse({"error": error}, status=400)
        for key, value in fields.items():
            setattr(link, key, value)
        link.save()
        return JsonResponse(_pagelink_json(link))
    return HttpResponseBadRequest()


@login_required(login_url='login')
@cms_permission_required("buttons.edit")
def pagelink_delete(request, pk):
    if request.method == "POST":
        link = get_object_or_404(PageLink, pk=pk)
        link.delete()
        return JsonResponse({"success": True})
    return HttpResponseBadRequest()

# AnyFiles
@login_required(login_url='login')
@cms_permission_required("media.edit")
def anyfile_upload_view(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            try:
                validate_anyfile_upload(uploaded_file)
            except ValidationError as error:
                return upload_validation_error_response(error)

            any_file = AnyFile(file=uploaded_file)
            any_file.full_clean()
            any_file.save()
            return HttpResponse('')
    return JsonResponse({'post': 'false'})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def anyfile_delete_view(request, id):
    try:
        file = AnyFile.objects.get(id=id)
        file.delete()
        return JsonResponse({"success": "Datei erfolgreich gelöscht"})
    except AnyFile.DoesNotExist:
        return JsonResponse({"error": "Datei nicht gefunden"})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def anyfile_uploader(request):
    files = AnyFile.objects.all().order_by('-id') 

    paginator = Paginator(files, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'pages/cms/files/anyfiles-uploader.html', {
        'files': page_obj,
        'page_obj': page_obj, 
    })

@login_required(login_url='login')
@cms_permission_required("media.edit")
def anyfile_list_view(request):
    # Per-Page (12/24/48/96), sicher parsen
    try:
        per_page = max(1, min(200, int(request.GET.get('per_page', 24))))
    except ValueError:
        per_page = 24

    qs = AnyFile.objects.all().order_by('-id')

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    preserved = request.GET.copy()
    preserved.pop('page', None)  # page entfernen für die Links
    querystring = preserved.urlencode()

    return render(
        request,
        'pages/cms/files/anyfiles.html',
        {
            'files': page_obj.object_list,   # nur die aktuelle Seite im Grid
            'page_obj': page_obj,
            'paginator': paginator,
            'per_page': per_page,
            'querystring': querystring,
            'total_count': paginator.count,
        }
    )

@login_required(login_url='login')
@cms_permission_required("media.edit")
def anyfile_update_view(request, id):
    try:
        file = AnyFile.objects.get(id=id)
    except AnyFile.DoesNotExist:
        return JsonResponse({'error': 'Datei nicht gefunden'}, status=404)

    if request.method != 'POST':
        return JsonResponse({'error': 'Ungültige Methode'}, status=400)

    title = (request.POST.get('title') or '').strip()
    description = (request.POST.get('description') or '').strip()  # optional

    # aktive Sprache holen (z. B. "de", "en", …)
    lang = get_active_language(request)

    # Titel in aktueller Sprache speichern
    if title != '':
        # modeltranslation: setzt z. B. title_de / title_en
        setattr(file, f'title_{lang}', title)

        # Wenn es die Default-Sprache ist, zusätzlich das Basisfeld pflegen
        if lang == DEFAULT_LANGUAGE:
            file.title = title

    # Beschreibung ebenfalls unterstützen (falls im Form mitgegeben)
    if description != '':
        setattr(file, f'description_{lang}', description)
        if lang == DEFAULT_LANGUAGE:
            file.description = description

    file.save()

    # Für die Antwort den sprachspezifischen Wert zurückgeben
    current_title = getattr(file, f'title_{lang}', None) or file.title

    return JsonResponse({
        'success': True,
        'title': current_title,
        'lang': lang,
    })

def anyfiles_all(request):
    files = AnyFile.objects.order_by('-uploaded_at')
    data = [{
        "id": f.id,
        "url": f.file.url,
        "title": f.title or os.path.basename(f.file.name),
        "ext": os.path.splitext(f.file.name)[1].lower()
    } for f in files]
    return JsonResponse({"files": data})

# Videos
@login_required(login_url='login')
@cms_permission_required("media.edit")
def list_videos(request):
    # Per-Page sicher parsen (Default 24, max 200)
    try:
        per_page = max(1, min(200, int(request.GET.get('per_page', 24))))
    except ValueError:
        per_page = 24

    qs = VideoFile.objects.all().order_by('-uploaded_at')

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    preserved = request.GET.copy()
    preserved.pop('page', None)  # page aus Query entfernen, damit Links sauber sind
    querystring = preserved.urlencode()

    return render(
        request,
        'pages/cms/video/video-overview.html',
        {
            'videos': page_obj.object_list,   # nur die aktuelle Seite im Grid
            'page_obj': page_obj,
            'paginator': paginator,
            'per_page': per_page,
            'querystring': querystring,
            'total_count': paginator.count,
        }
    )

@login_required(login_url='login')
@cms_permission_required("media.edit")
def create_video(request):
    if request.method == 'POST':
        video = request.FILES.get('file')
        thumbnail = request.FILES.get('thumbnail')
        subtitle = request.FILES.get('subtitle')
        if not video:
            return JsonResponse({'error': 'Bitte wähle eine Videodatei aus.'}, status=400)

        try:
            validate_video_upload(video)
            if thumbnail:
                validate_video_thumbnail_upload(thumbnail)
            if subtitle:
                validate_subtitle_upload(subtitle)
        except ValidationError as error:
            return upload_validation_error_response(error)

        # Sprache bestimmen
        lang = get_active_language(request)

        title = request.POST.get('title')
        description = request.POST.get('description', '')
        alt_text = request.POST.get('alt_text', '')
        tags = request.POST.get('tags', '')
        duration = request.POST.get('duration') or None
        # boolean fields
        is_public = request.POST.get('is_public', 'true') == 'true'
        autoplay = request.POST.get('autoplay') == 'true'
        muted = request.POST.get('muted') == 'true'
        loop = request.POST.get('loop') == 'true'
        playsinline = request.POST.get('playsinline') == 'true'
        show_controls = request.POST.get('show_controls') == 'true'
        preload = request.POST.get('preload', 'metadata')

        video_instance = VideoFile(
            file=video,
            thumbnail=thumbnail,
            subtitle_file=subtitle,
            title=title,
            description=description,
            alt_text=alt_text,
            tags=tags,
            is_public=is_public,
            duration=duration,
            autoplay=autoplay,
            muted=muted,
            loop=loop,
            playsinline=playsinline,
            show_controls=show_controls,
            preload=preload,
        )

        set_mt_fields(video_instance, lang, {
            'title': title,
            'description': description,
            'alt_text': alt_text,
            'tags': tags,
        })

        ensure_video_slug(video_instance, source_title=(title or 'video'))

        video_instance.save()
        return JsonResponse({'success': True, 'redirect': '/cms/videos/'})

    video_options = [
        ("autoplay", "Autoplay"),
        ("muted", "Stumm geschaltet"),
        ("loop", "Loop"),
        ("playsinline", "Auf Seite abspielen (Mobil)"),
        ("show_controls", "Steuerelemente anzeigen"),
    ]

    return render(request, 'pages/cms/video/video-create.html', {
        'video_options': video_options
    })


@login_required(login_url='login')
@cms_permission_required("media.edit")
def edit_video(request, pk):
    video = get_object_or_404(VideoFile, pk=pk)

    if request.method == 'POST':
        lang = get_active_language(request)
        # sprachspezifische Meta
        set_mt_fields(video, lang, {
            'title': request.POST.get('title', ''),
            'description': request.POST.get('description', ''),
            'alt_text': request.POST.get('alt_text', ''),
            'tags': request.POST.get('tags', ''),
        })
        video.title = request.POST.get('title')
        video.description = request.POST.get('description', '')
        video.alt_text = request.POST.get('alt_text', '')
        video.tags = request.POST.get('tags', '')
        video.is_public = request.POST.get('is_public', 'true') == 'true'
        video.duration = request.POST.get('duration') or None
        video.autoplay = request.POST.get('autoplay') == 'true'
        video.muted = request.POST.get('muted') == 'true'
        video.loop = request.POST.get('loop') == 'true'
        video.playsinline = request.POST.get('playsinline') == 'true'
        video.show_controls = request.POST.get('show_controls') == 'true'
        video.preload = request.POST.get('preload', 'metadata')

        if 'file' in request.FILES:
            try:
                validate_video_upload(request.FILES['file'])
            except ValidationError as error:
                return upload_validation_error_response(error)
            video.file = request.FILES['file']
        if 'thumbnail' in request.FILES:
            try:
                validate_video_thumbnail_upload(request.FILES['thumbnail'])
            except ValidationError as error:
                return upload_validation_error_response(error)
            video.thumbnail = request.FILES['thumbnail']
        if 'subtitle' in request.FILES:
            try:
                validate_subtitle_upload(request.FILES['subtitle'])
            except ValidationError as error:
                return upload_validation_error_response(error)
            video.subtitle_file = request.FILES['subtitle']

        if not video.slug:
            source_title = (request.POST.get('title') or video.title or 'video')
            ensure_video_slug(video, source_title)

        video.save()
        return JsonResponse({'success': True, 'redirect': '/cms/videos/'})

    options = ['autoplay', 'muted', 'loop', 'playsinline', 'show_controls']
    option_states = {opt: getattr(video, opt, False) for opt in options}
    video_options = [
        ("autoplay", "Autoplay"),
        ("muted", "Stumm geschaltet"),
        ("loop", "Loop"),
        ("playsinline", "Auf Seite abspielen (Mobil)"),
        ("show_controls", "Steuerelemente anzeigen"),
    ]

    return render(request, 'pages/cms/video/video-edit.html', {'video': video, 'video_options': video_options, 'option_states': option_states})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def delete_video(request, pk):
    video = get_object_or_404(VideoFile, pk=pk)
    video.delete()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@cms_permission_required("media.edit")
def list_all_videos(request):
    """
    Liefert alle VideoFile-Objekte als JSON für das Auswahl-Modal.
    Struktur:
      {
        "video_urls": [
          { "id": 12, "url": "...mp4", "poster": "...jpg" },
          ...
        ]
      }
    """
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    result = []
    for video in VideoFile.objects.all().order_by("-uploaded_at"):
        result.append({
            "id": video.id,
            "url": video.file.url,
            "title": video.title,
            "description": video.description or "",
            "alt_text": video.alt_text or "",
            "tags": video.tags or "",
            "duration": video.duration,
            "poster": video.thumbnail.url if video.thumbnail else static("images/designImg/filler.png"),
            "autoplay": video.autoplay,
            "muted": video.muted,
            "loop": video.loop,
            "playsinline": video.playsinline,
            "show_controls": video.show_controls,
            "preload": video.preload or "metadata"
        })

    return JsonResponse({"video_urls": result}, status=200)

@login_required(login_url='login')
@cms_permission_required("media.edit")
def get_video_details(request, pk):
    video = get_object_or_404(VideoFile, pk=pk)

    return JsonResponse({
        "id": video.id,
        "url": video.file.url,
        "poster": video.thumbnail.url if video.thumbnail else static("images/designImg/filler.png"),
        "title": video.title,
        "description": video.description or "",
        "alt_text": video.alt_text or "",
        "tags": video.tags or "",
        "duration": video.duration,
        "autoplay": video.autoplay,
        "muted": video.muted,
        "loop": video.loop,
        "playsinline": video.playsinline,
        "show_controls": video.show_controls,
        "preload": video.preload,
    }, status=200)
