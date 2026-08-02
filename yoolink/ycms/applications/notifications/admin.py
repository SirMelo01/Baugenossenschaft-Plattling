from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "priority", "seen", "created_at", "linked_object")
    list_filter = ("priority", "seen", "created_at")
    search_fields = (
        "title",
        "description",
        "message__name",
        "message__email",
        "message__title",
        "order__buyer_email",
    )
    autocomplete_fields = ("message",)
    ordering = ("-created_at",)
    actions = ["mark_as_read", "mark_as_unread"]

    def linked_object(self, obj):
        if obj.message_id:
            return f"Message #{obj.message_id}"
        if obj.link_url:
            return obj.link_url
        return "â€”"

    linked_object.short_description = "VerknÃ¼pft mit"

    def mark_as_read(self, request, queryset):
        updated = queryset.update(seen=True)
        self.message_user(request, f"{updated} Benachrichtigung(en) als gelesen markiert.")

    mark_as_read.short_description = "AusgewÃ¤hlte als gelesen markieren"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(seen=False)
        self.message_user(request, f"{updated} Benachrichtigung(en) als ungelesen markiert.")

    mark_as_unread.short_description = "AusgewÃ¤hlte als ungelesen markieren"
