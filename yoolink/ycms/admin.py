from django.contrib import admin

from .models import (
    FAQ,
    Blog,
    Button,
    CMSRole,
    CMSUserRole,
    DeveloperApiKey,
    GaleryImage,
    Galerie,
    ContactFormSettings,
    Message,
    MessageAttachment,
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


admin.site.register(Galerie)
admin.site.register(GaleryImage)
admin.site.register(FAQ)
admin.site.register(fileentry)
admin.site.register(Blog)
admin.site.register(UserSettings)
admin.site.register(WebsiteSettings)
admin.site.register(CMSRole)
admin.site.register(CMSUserRole)
admin.site.register(OpeningHours)
admin.site.register(TeamMember)
admin.site.register(PricingFeature)
admin.site.register(Button)
admin.site.register(PageLink)
admin.site.register(PricingCard)
admin.site.register(VideoFile)


@admin.register(RecoveryBackup)
class RecoveryBackupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trigger",
        "status",
        "slot",
        "filename",
        "size_bytes",
        "created_by",
        "created_at",
        "finished_at",
    )
    list_filter = ("trigger", "status", "include_media", "created_at")
    search_fields = ("filename", "object_key", "encrypted_sha256", "created_by__username")
    readonly_fields = (
        "trigger",
        "status",
        "slot",
        "object_key",
        "filename",
        "size_bytes",
        "encrypted_sha256",
        "include_media",
        "storage_bucket",
        "storage_endpoint",
        "error_message",
        "created_by",
        "created_at",
        "started_at",
        "finished_at",
    )


@admin.register(DeveloperApiKey)
class DeveloperApiKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "prefix",
        "created_by",
        "access_level",
        "allowed_apps",
        "expires_at",
        "revoked_at",
        "last_used_at",
    )
    list_filter = ("access_level", "revoked_at", "expires_at")
    search_fields = ("name", "prefix", "created_by__username", "created_by__email")
    readonly_fields = ("prefix", "key_hash", "created_at", "updated_at", "last_used_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "category", "title", "date", "seen")
    search_fields = ("name", "email", "title", "message", "phone")
    list_filter = ("category", "seen", "date")
    ordering = ("-date",)


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "message", "kind", "size", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("original_name", "message__name", "message__email")
    # Die Datei liegt in der privaten Ablage und wird nur ueber die CMS-Ansicht
    # ausgeliefert; im Admin gibt es sie deshalb nur lesend zu sehen.
    readonly_fields = ("file", "original_name", "content_type", "kind", "size", "created_at")


@admin.register(ContactFormSettings)
class ContactFormSettingsAdmin(admin.ModelAdmin):
    list_display = ("form_key", "document", "uploads_enabled", "max_uploads", "allow_images", "allow_documents")
    list_filter = ("uploads_enabled",)
