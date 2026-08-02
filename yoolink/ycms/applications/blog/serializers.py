import os
from html import escape

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from yoolink.ycms.models import Blog, DeveloperApiKey, fileentry
from yoolink.ycms.upload_validation import validate_image_upload, validation_error_message

from .services import (
    blog_code_to_markdown,
    build_default_code_from_html,
    build_default_code_from_markdown,
    normalize_blog_code,
    render_blog_code_to_html,
    render_markdown_to_html,
    strip_generated_blog_intro,
)


ALLOWED_BLOG_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class ExternalBlogTranslationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    language = serializers.CharField(read_only=True)
    active = serializers.BooleanField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    is_original = serializers.BooleanField(read_only=True)
    api_url = serializers.URLField(read_only=True)
    absolute_url = serializers.URLField(read_only=True)


class ExternalApiPingSerializer(serializers.Serializer):
    ok = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
    authenticated = serializers.BooleanField(read_only=True)
    user = serializers.CharField(read_only=True)
    access_level = serializers.ChoiceField(
        choices=DeveloperApiKey.ACCESS_LEVEL_CHOICES,
        read_only=True,
    )
    allowed_apps = serializers.ListField(child=serializers.CharField(), read_only=True)


class ExternalConnectTokenRequestSerializer(serializers.Serializer):
    grant_type = serializers.ChoiceField(
        choices=[("authorization_code", "authorization_code")],
        default="authorization_code",
        required=False,
    )
    code = serializers.CharField()
    code_verifier = serializers.CharField(min_length=43, max_length=128)
    redirect_uri = serializers.URLField(max_length=2048)


class ExternalConnectTokenResponseSerializer(serializers.Serializer):
    token_type = serializers.CharField(read_only=True)
    api_key = serializers.CharField(read_only=True)
    base_url = serializers.URLField(read_only=True)
    ping_url = serializers.URLField(read_only=True)
    docs_url = serializers.URLField(read_only=True)
    schema_url = serializers.URLField(read_only=True)
    access_level = serializers.ChoiceField(
        choices=DeveloperApiKey.ACCESS_LEVEL_CHOICES,
        read_only=True,
    )
    allowed_apps = serializers.ListField(child=serializers.CharField(), read_only=True)


class ExternalBlogListSerializer(serializers.ModelSerializer):
    absolute_url = serializers.SerializerMethodField()
    api_url = serializers.SerializerMethodField()
    title_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "title_image_alt",
            "title_image_title",
            "title_image_caption",
            "active",
            "language",
            "original",
            "title_image_url",
            "absolute_url",
            "api_url",
            "date",
            "last_updated",
        ]
        read_only_fields = fields

    def get_absolute_url(self, obj) -> str:
        request = self.context.get("request")
        if not request:
            return obj.get_absolute_url()
        return request.build_absolute_uri(obj.get_absolute_url())

    def get_api_url(self, obj) -> str:
        request = self.context.get("request")
        path = f"/api/cms/blog/{obj.pk}/"
        if not request:
            return path
        return request.build_absolute_uri(path)

    def get_title_image_url(self, obj) -> str:
        if not obj.title_image:
            return ""

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.title_image.url)

        return obj.title_image.url


class ExternalBlogSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    absolute_url = serializers.SerializerMethodField()
    title_image_url = serializers.SerializerMethodField()
    translations = serializers.SerializerMethodField()
    code = serializers.JSONField(required=False)
    title_image = serializers.ImageField(required=False, allow_null=True)
    title_image_media_id = serializers.PrimaryKeyRelatedField(
        queryset=fileentry.objects.all(),
        required=False,
        write_only=True,
        source="title_image_media",
    )
    original = serializers.PrimaryKeyRelatedField(
        queryset=Blog.objects.filter(original__isnull=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Blog
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "body",
            "markdown",
            "code",
            "title_image_alt",
            "title_image_title",
            "title_image_caption",
            "active",
            "language",
            "original",
            "author",
            "title_image",
            "title_image_media_id",
            "title_image_url",
            "absolute_url",
            "translations",
            "date",
            "last_updated",
        ]
        read_only_fields = ["id", "slug", "author", "absolute_url", "title_image_url", "translations", "date", "last_updated"]

    def get_absolute_url(self, obj) -> str:
        request = self.context.get("request")
        if not request:
            return obj.get_absolute_url()
        return request.build_absolute_uri(obj.get_absolute_url())

    def get_title_image_url(self, obj) -> str:
        if not obj.title_image:
            return ""

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.title_image.url)

        return obj.title_image.url

    @extend_schema_field(ExternalBlogTranslationSerializer(many=True))
    def get_translations(self, obj) -> list[dict]:
        root = obj.original if obj.original_id else obj
        variants = [root, *list(root.translations.all())]

        return [
            {
                "id": variant.id,
                "title": variant.title,
                "language": variant.language,
                "active": variant.active,
                "is_current": variant.pk == obj.pk,
                "is_original": variant.pk == root.pk,
                "api_url": self._absolute_api_url(variant),
                "absolute_url": self.get_absolute_url(variant),
            }
            for variant in variants
        ]

    def _absolute_api_url(self, obj) -> str:
        request = self.context.get("request")
        path = f"/api/cms/blog/{obj.pk}/"
        if not request:
            return path
        return request.build_absolute_uri(path)

    def validate_title_image(self, value):
        if value:
            try:
                validate_image_upload(value)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(validation_error_message(exc)) from exc
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        initial_data = getattr(self, "initial_data", {}) or {}
        instance = self.instance

        body_provided = "body" in initial_data
        markdown_provided = "markdown" in initial_data
        code_provided = "code" in initial_data
        if "title_image" in initial_data and "title_image_media_id" in initial_data:
            raise serializers.ValidationError(
                {"title_image": "Bitte entweder title_image als Datei oder title_image_media_id senden, nicht beides."}
            )

        markdown = attrs.get("markdown")
        if markdown is None and instance:
            markdown = instance.markdown
        markdown = (markdown or "").strip()

        body = attrs.get("body")
        if body is None and instance:
            body = instance.body
        body = (body or "").strip()

        if markdown_provided:
            attrs["markdown"] = markdown
            attrs["body"] = render_markdown_to_html(markdown)
            if not code_provided:
                attrs["code"] = build_default_code_from_markdown(markdown)
            body = attrs["body"]

        if code_provided:
            try:
                normalized_code = normalize_blog_code(attrs.get("code"), body)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError({"code": str(exc)}) from exc

            attrs["code"] = normalized_code
            if not body_provided:
                body = render_blog_code_to_html(normalized_code)
                attrs["body"] = body
            if not markdown_provided:
                attrs["markdown"] = blog_code_to_markdown(normalized_code, attrs.get("body", body))
        elif body_provided or (instance is None and not markdown_provided):
            attrs["code"] = build_default_code_from_html(body)
            if not markdown_provided:
                attrs["markdown"] = blog_code_to_markdown(attrs["code"], body)

        if instance is None and not (markdown or body or attrs.get("code")):
            raise serializers.ValidationError({"markdown": "markdown, body oder code muss gesetzt sein."})

        description = attrs.get("description")
        if description is None and instance:
            description = instance.description
        if not (description or "").strip():
            raise serializers.ValidationError({"description": "Die Beschreibung darf nicht leer sein."})

        title = attrs.get("title")
        if title is None and instance:
            title = instance.title
        if not (title or "").strip():
            raise serializers.ValidationError({"title": "Der Titel darf nicht leer sein."})

        original = attrs.get("original")
        if original is None and instance:
            original = instance.original
        language = attrs.get("language")
        if language is None and instance:
            language = instance.language
        language = language or "de"

        if original:
            root = original.original or original
            duplicate = root.translations.filter(language=language)
            if instance:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists() or (root.language == language and (not instance or instance.pk != root.pk)):
                raise serializers.ValidationError(
                    {"language": "Für diese Sprache existiert bereits eine Variante dieses Blogs."}
                )

        if "body" in attrs:
            attrs["body"] = strip_generated_blog_intro(attrs["body"], title, description)

        return attrs

    def create(self, validated_data):
        title_image = validated_data.pop("title_image", None)
        title_image_media = validated_data.pop("title_image_media", None)
        request = self.context["request"]
        if validated_data.get("original"):
            # Kein Sprach-Suffix mehr im Slug: die Sprache steckt bereits im
            # URL-Pfad (z. B. /en/blog/...), daher wäre "-en" im Slug redundant.
            # Der Slug wird aus dem Titel der Übersetzung erzeugt; Eindeutigkeit
            # und dauerhafte Stabilität stellt das Blog-Modell in save() sicher.
            validated_data["slug"] = slugify(validated_data.get("title") or "blog")

        blog = Blog.objects.create(author=request.user, **validated_data)

        if title_image:
            from yoolink.ycms.views import optimize_image_for_upload

            blog.title_image = optimize_image_for_upload(title_image)
            blog.save(update_fields=["title_image", "last_updated"])
        elif title_image_media:
            self._copy_title_image_from_media(blog, title_image_media)

        return blog

    def update(self, instance, validated_data):
        title_image_supplied = "title_image" in validated_data
        title_image = validated_data.pop("title_image", None)
        title_image_media = validated_data.pop("title_image_media", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if title_image_supplied:
            if title_image:
                from yoolink.ycms.views import optimize_image_for_upload

                instance.title_image = optimize_image_for_upload(title_image)
            else:
                instance.title_image = ""

        instance.save()
        if title_image_media:
            self._copy_title_image_from_media(instance, title_image_media)
        return instance

    def _copy_title_image_from_media(self, blog, media):
        media.file.open("rb")
        try:
            filename = os.path.basename(media.file.name)
            blog.title_image.save(filename, media.file, save=True)
            if not blog.title_image_title:
                blog.title_image_title = media.title or ""
            if not blog.title_image_alt:
                blog.title_image_alt = media.title or blog.title
            blog.save(update_fields=["title_image_title", "title_image_alt", "last_updated"])
        finally:
            media.file.close()


class ExternalBlogImageUploadSerializer(serializers.Serializer):
    file = serializers.ImageField(write_only=True)
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    alt_text = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_file(self, value):
        filename = (value.name or "").lower()
        if not any(filename.endswith(extension) for extension in ALLOWED_BLOG_IMAGE_EXTENSIONS):
            raise serializers.ValidationError("Erlaubte Bildformate: jpg, jpeg, png, gif, webp.")

        try:
            validate_image_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(validation_error_message(exc)) from exc

        return value

    def create(self, validated_data):
        upload = validated_data["file"]
        alt_text = (validated_data.get("alt_text") or "").strip()
        title = (validated_data.get("title") or alt_text or upload.name).strip()

        from yoolink.ycms.views import (
            DESKTOP_IMAGE_MAX_DIMENSIONS,
            DESKTOP_IMAGE_TARGET_KB,
            MOBILE_IMAGE_MAX_DIMENSIONS,
            MOBILE_IMAGE_TARGET_KB,
            optimize_image_for_upload,
        )

        desktop_image = optimize_image_for_upload(
            upload,
            max_dimensions=DESKTOP_IMAGE_MAX_DIMENSIONS,
            max_size_kb=DESKTOP_IMAGE_TARGET_KB,
            variant_suffix="desktop",
        )
        mobile_image = optimize_image_for_upload(
            upload,
            max_dimensions=MOBILE_IMAGE_MAX_DIMENSIONS,
            max_size_kb=MOBILE_IMAGE_TARGET_KB,
            variant_suffix="mobile",
        )
        image = fileentry.objects.create(file=desktop_image, mobile_file=mobile_image, title=title)
        url = self._absolute_url(image.file.url)
        markdown_alt = alt_text.replace("[", "").replace("]", "").replace("\n", " ")
        html_alt = escape(alt_text, quote=True)
        html_url = escape(url, quote=True)

        return {
            "id": image.id,
            "title": image.title,
            "alt_text": alt_text,
            "url": url,
            "markdown": f"![{markdown_alt}]({url})",
            "html": f'<img src="{html_url}" alt="{html_alt}" class="rounded-2xl my-4">',
        }

    def _absolute_url(self, url):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url
