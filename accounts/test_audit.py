from datetime import timedelta
from unittest.mock import Mock
import uuid

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from accounts.admin import AuditEventAdmin
from accounts.audit import record_domain_event
from accounts.models import AuditEvent, User

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middleware import RequestEventIdMiddleware


class AuditEventTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            email="audit-test@example.invalid",
            password="Test-pass-123!",
            role=User.Role.CURATOR,
            is_staff=True,
            is_superuser=True,
        )

    def test_records_a_safe_domain_event(self):
        event = record_domain_event(
            operation="buddy.assign",
            object_type="student",
            object_id="42",
            result=AuditEvent.Result.SUCCESS,
            actor_id=self.actor.pk,
            reason_code="",
        )

        self.assertEqual(event.actor_id, self.actor.pk)
        self.assertEqual(event.operation, "buddy.assign")
        self.assertEqual(event.object_id, "42")
        self.assertEqual(event.result, AuditEvent.Result.SUCCESS)
        self.assertIsNotNone(event.event_id)

    def test_rejects_email_as_object_id(self):
        with self.assertRaises(ValueError):
            record_domain_event(
                operation="buddy.assign",
                object_type="student",
                object_id="person@example.com",
                result=AuditEvent.Result.SUCCESS,
                actor_id=self.actor.pk,
            )

    def test_audit_records_cannot_be_changed_or_deleted_in_admin(self):
        model_admin = AuditEventAdmin(AuditEvent, AdminSite())
        request = Mock()
        request.user = self.actor

        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

        request.user.is_superuser = False
        self.assertFalse(model_admin.has_view_permission(request))

class RequestEventIdMiddlewareTests(SimpleTestCase):
    def test_error_id_matches_response_header_and_log(self):
        request = RequestFactory().get("/")
        middleware = RequestEventIdMiddleware(lambda request: None)
        middleware.process_request(request)

        with self.assertLogs("accounts", level="ERROR") as captured:
            middleware.process_exception(
                request,
                RuntimeError("текст ошибки с секретными данными"),
            )

        response = middleware.process_response(
            request,
            HttpResponse(status=500),
        )

        event_id = str(request.event_id)
        self.assertEqual(response["X-Event-ID"], event_id)
        self.assertEqual(captured.records[0].event_id, event_id)
        self.assertNotIn(
            "секретными данными",
            captured.output[0],
        )