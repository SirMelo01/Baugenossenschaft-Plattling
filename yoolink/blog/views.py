import re
from html import escape
from html.parser import HTMLParser

from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import ListView, DetailView
from yoolink.ycms.models import Blog
from yoolink.ycms.applications.blog.services import render_markdown_to_html
from django.conf import settings
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import get_language

from yoolink.ycms.applications.content.models import TextContent


class ConsentIframeParser(HTMLParser):
    """Move iframe sources behind the consent gate without sanitizing CMS HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self._wrap_iframe_stack = []

    def _render_attrs(self, attrs):
        rendered = []
        for key, value in attrs:
            if value is None:
                rendered.append(f" {key}")
            else:
                rendered.append(f' {key}="{escape(value, quote=True)}"')
        return "".join(rendered)

    def _consent_attrs(self, attrs):
        src = None
        class_value = ""
        next_attrs = []

        for key, value in attrs:
            key_lower = key.lower()
            if key_lower == "src":
                src = value
            elif key_lower == "class":
                class_value = value or ""
            else:
                next_attrs.append((key, value))

        if not src:
            return attrs

        classes = class_value.split()
        if "hidden" not in classes:
            classes.append("hidden")

        next_attrs.append(("class", " ".join(classes)))
        next_attrs.append(("data-cookie-src", src))
        return next_attrs

    def _placeholder(self):
        return (
            '<div class="rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-700" data-cookie-placeholder>'
            '<p class="font-semibold text-gray-800">Externer Inhalt ist deaktiviert.</p>'
            '<p class="mt-1 text-sm text-gray-600">'
            'Dieser Inhalt wird erst nach Ihrer Einwilligung für externe Medien geladen.'
            '</p>'
            '<button type="button" class="mt-3 inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-center font-bold text-slate-900 transition hover:bg-slate-100" '
            'data-consent-action="open-settings">Cookie-Auswahl öffnen</button>'
            '</div>'
        )

    def _wrapper_open(self):
        return '<div class="my-4">'

    def _wrapper_close(self):
        return "</div>"

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "iframe" and any(key.lower() == "src" for key, _ in attrs):
            self.output.append(self._wrapper_open())
            self.output.append(self._placeholder())
            attrs = self._consent_attrs(attrs)
            self._wrap_iframe_stack.append(True)
            self.output.append(f"<{tag}{self._render_attrs(attrs)}>")
            return
        self.output.append(f"<{tag}{self._render_attrs(attrs)}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "iframe" and any(key.lower() == "src" for key, _ in attrs):
            self.output.append(self._wrapper_open())
            self.output.append(self._placeholder())
            attrs = self._consent_attrs(attrs)
            self.output.append(f"<{tag}{self._render_attrs(attrs)} />")
            self.output.append(self._wrapper_close())
            return
        self.output.append(f"<{tag}{self._render_attrs(attrs)} />")

    def handle_endtag(self, tag):
        if tag.lower() == "iframe" and self._wrap_iframe_stack:
            self._wrap_iframe_stack.pop()
            self.output.append(f"</{tag}>")
            self.output.append(self._wrapper_close())
            return
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_comment(self, data):
        self.output.append(f"<!--{data}-->")

    def get_html(self):
        return "".join(self.output)


def consent_gate_iframes(html):
    parser = ConsentIframeParser()
    parser.feed(html or "")
    parser.close()
    return parser.get_html()

def get_active_language(request):
    """
    Liefert die „aktive“ Sprache:
    - bevorzugt das, was LocaleMiddleware gesetzt hat (request.LANGUAGE_CODE)
    - Fallback: get_language()
    - Fallback 2: settings.LANGUAGE_CODE
    """
    lang = getattr(request, "LANGUAGE_CODE", None) or get_language()
    available_languages = dict(settings.LANGUAGES)

    if lang not in available_languages:
        # Für dich: default ist Deutsch
        lang = settings.LANGUAGE_CODE  # z.B. "de"

    # WICHTIG: KEIN activate(lang) hier!
    return lang


class Load_Index_Blog(ListView):
    model = Blog
    template_name = 'blog/index_blog.html'
    context_object_name = 'blogs'
    paginate_by = 6
    ordering = '-date'

    def get_queryset(self):
        self._lang = get_active_language(self.request)
        return (Blog.objects
                .filter(original__isnull=True, active=True)   # << nur aktive
                .order_by(self.ordering)
                .prefetch_related('translations'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lang = getattr(self, '_lang', None)
        originals_on_page = ctx['object_list']
        mapped = []
        for blog in originals_on_page:
            variant = blog.translations.filter(language=lang, active=True).first() if lang else None
            mapped.append(variant or blog)
        ctx['object_list'] = mapped
        ctx['blogs'] = mapped
        ctx['blog_overview_hero'] = TextContent.objects.filter(name="main_blog_overview_hero").first()
        return ctx


class BlogDetailView(DetailView):
    model = Blog
    template_name = 'blog/blog_detail.html'
    context_object_name = 'blog'

    def get_queryset(self):
        queryset = (
            Blog.objects
            .select_related("author", "original")
            .prefetch_related("translations")
        )

        if self.request.user.is_authenticated and self.request.user.is_staff:
            return queryset

        return queryset.filter(active=True)

    def _reading_time(self, blog):
        source = blog.markdown or blog.body or ""
        word_count = len(strip_tags(source).split())
        return max(1, round(word_count / 220))

    def _word_count(self, blog):
        source = blog.markdown or blog.body or ""
        return len(strip_tags(source).split())

    def _excerpt(self, blog):
        source = blog.description or strip_tags(blog.markdown or blog.body or "")
        return Truncator(" ".join(source.split())).chars(155)

    def _absolute_image_url(self, blog):
        if not blog.title_image:
            return ""
        return self.request.build_absolute_uri(blog.title_image.url)

    def _image_alt(self, blog):
        return (blog.title_image_alt or blog.title_image_title or blog.title or "").strip()

    def _image_title(self, blog):
        return (blog.title_image_title or blog.title_image_alt or blog.title or "").strip()

    def _strip_duplicate_intro_heading(self, html, title):
        title = " ".join((title or "").split())
        if not html or not title:
            return html

        match = re.match(r"^\s*<h[12]\b[^>]*>.*?</h[12]>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return html

        heading_text = " ".join(strip_tags(match.group(0)).split())
        if heading_text == title:
            return html[match.end():]
        return html

    def _demote_body_h1(self, html):
        if not html:
            return html
        return re.sub(r"<(/?)h1(\b[^>]*)>", r"<\1h2\2>", html, flags=re.IGNORECASE)

    def _localized_blog(self, blog, lang):
        if blog.language == lang and blog.active:
            return blog
        variant = blog.translations.filter(language=lang, active=True).first() if lang else None
        return variant or blog

    def _related_blogs(self, blog, lang):
        root = blog.original or blog
        related_roots = (
            Blog.objects
            .filter(original__isnull=True, active=True)
            .exclude(pk=root.pk)
            .prefetch_related("translations")
            .order_by("-date")[:6]
        )

        related = []
        for related_blog in related_roots:
            related.append(self._localized_blog(related_blog, lang))
            if len(related) >= 3:
                break
        return related

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        blog = context["blog"]
        lang = get_active_language(self.request)
        rendered_body = render_markdown_to_html(blog.markdown) if blog.markdown else blog.body
        rendered_body = self._demote_body_h1(rendered_body)
        rendered_body = self._strip_duplicate_intro_heading(rendered_body, blog.title)
        context["consent_safe_body"] = consent_gate_iframes(rendered_body)
        context["blog_excerpt"] = self._excerpt(blog)
        context["blog_word_count"] = self._word_count(blog)
        context["blog_language"] = blog.language or lang
        context["blog_reading_time"] = self._reading_time(blog)
        context["blog_image_url"] = self._absolute_image_url(blog)
        context["blog_image_alt"] = self._image_alt(blog)
        context["blog_image_title"] = self._image_title(blog)
        context["blog_image_caption"] = blog.title_image_caption
        context["canonical_url"] = self.request.build_absolute_uri(blog.get_absolute_url())
        context["related_blogs"] = self._related_blogs(blog, lang)
        return context

    def get(self, request, *args, **kwargs):
        # Objekt laden
        self.object = self.get_object()

        if not self.object.active and not (request.user.is_authenticated and request.user.is_staff):
            raise Http404("Blog nicht gefunden")

        # 1) Canonical Slug sicherstellen
        # Permanenter Redirect (301): der Slug ist unveränderlich, alte/kürzere
        # Slug-Varianten (z. B. ehemalige "-en"-Slugs) zeigen dauerhaft auf die
        # aktuelle URL, damit Google das Ranking überträgt statt neu zu bewerten.
        url_slug = kwargs.get('slug_title')
        if url_slug != self.object.slug:
            return redirect(self.object.get_absolute_url(), permanent=True)

        # 2) Sprachvariante prüfen → ggf. Redirect
        lang = get_active_language(request)

        # „Familie“: Original + Übersetzungen
        root = self.object.original or self.object  # Original ist Root, sonst self
        if root.language == lang:
            target = root
        else:
            target = root.translations.filter(language=lang, active=True).first() or root

        if target.pk != self.object.pk:
            return redirect(target.get_absolute_url())

        # passt → normal rendern
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
