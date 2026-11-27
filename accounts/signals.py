from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .audit import record_domain_event


@receiver(user_logged_in)
def audit_admin_login_success(sender, request, user, **kwargs):
    if request is None or not request.path.startswith("/admin/"):
        return

    record_domain_event(
        operation="auth.login",
        object_type="admin",
        object_id=user.pk,
        actor_id=user.pk,
        result="success",
        reason_code="admin_login",
        request_id=getattr(request, "event_id", None),
    )


@receiver(user_login_failed)
def audit_admin_login_failure(sender, credentials, request, **kwargs):
    if request is None or not request.path.startswith("/admin/"):
        return

    record_domain_event(
        operation="auth.login",
        object_type="authentication",
        result="denied",
        reason_code="bad_credentials",
        request_id=getattr(request, "event_id", None),
    )