from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    date_hierarchy = "occurred_at"
    list_display = (
        "event_id",
        "occurred_at",
        "actor_id_value",
        "operation",
        "object_type",
        "object_id",
        "result",
        "reason_code",
    )
    list_filter = ("operation", "result")
    search_fields = ("event_id", "object_id", "operation", "reason_code")
    ordering = ("-occurred_at",)
    readonly_fields = (
        "event_id",
        "occurred_at",
        "actor_id_value",
        "operation",
        "object_type",
        "object_id",
        "result",
        "reason_code",
        "request_id",
    )

    @admin.display(description="ID пользователя")
    def actor_id_value(self, obj):
        return obj.actor_id or "-"

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False