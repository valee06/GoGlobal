from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .models import User

REGISTER_URL = reverse("auth:register_staff")
PENDING_URL = reverse("auth:pending")

VALID = {
    "full_name": "Тестовый Куратор",
    "email": "curator@example.com",
    "password": "Strong1!pass",
    "role": "curator",
    "consent_personal_data": "on",
}


class StaffRegistrationTests(TestCase):
    """Контракт C02: регистрация куратора/buddy."""

    def test_successful_registration_no_auto_access(self):
        """Позитивный сценарий: создан, но без автодоступа (FR-22, FR-27)."""
        response = self.client.post(REGISTER_URL, VALID)

        self.assertRedirects(response, PENDING_URL)
        user = User.objects.get(email="curator@example.com")
        self.assertEqual(user.role, User.Role.CURATOR)
        self.assertEqual(user.full_name, "Тестовый Куратор")
        self.assertFalse(user.is_approved)       # ждёт ручного одобрения
        self.assertFalse(user.email_verified)    # подтверждение email — C03
        self.assertEqual(user.consent_version, settings.CONSENT_VERSION)
        self.assertIsNotNone(user.consented_at)
        # пароль захэширован, а не лежит открытым текстом
        self.assertNotEqual(user.password, VALID["password"])
        self.assertTrue(user.check_password(VALID["password"]))

    def test_no_auto_login_after_registration(self):
        """После регистрации пользователь НЕ залогинен."""
        self.client.post(REGISTER_URL, VALID)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_duplicate_email_rejected(self):
        """Повторный email не создаёт второй аккаунт (FR-22, D12)."""
        self.client.post(REGISTER_URL, VALID)
        response = self.client.post(REGISTER_URL, {**VALID, "full_name": "Другой Человек"})

        self.assertEqual(User.objects.count(), 1)
        self.assertIn("уже зарегистрирован", response.content.decode())

    def test_role_substitution_rejected(self):
        """Подмена роли в POST не создаёт пользователя (FR-25)."""
        for bad_role in ("student", "admin", "superuser"):
            response = self.client.post(REGISTER_URL, {**VALID, "role": bad_role})
            self.assertEqual(User.objects.count(), 0, bad_role)
            self.assertEqual(response.status_code, 200)  # форма с ошибкой, не успех

    def test_missing_consent_rejected(self):
        """Без согласия регистрация невозможна (FR-43)."""
        data = {k: v for k, v in VALID.items() if k != "consent_personal_data"}
        self.client.post(REGISTER_URL, data)
        self.assertEqual(User.objects.count(), 0)

    def test_weak_passwords_rejected(self):
        """Политика D01: короткий, кириллица, без цифры, без спецзнака."""
        weak = ["Sh1!", "Кириллица1!", "nodigits!!x", "NoSpecial123"]
        for password in weak:
            self.client.post(REGISTER_URL, {**VALID, "password": password})
            self.assertEqual(User.objects.count(), 0, password)


class ApproveUserCommandTests(TestCase):
    """Контракт C10: служебное одобрение/деактивация."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="staff@example.com", password="Strong1!pass",
            full_name="Сотрудник", role=User.Role.BUDDY,
        )

    def call(self, *args):
        out = StringIO()
        call_command("approve_user", *args, stdout=out)
        return out.getvalue()

    def test_approve_records_executor_and_time(self):
        self.call("staff@example.com", "--by", "Иля", "--approve")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_approved)
        self.assertEqual(self.user.approved_by, "Иля")
        self.assertIsNotNone(self.user.approved_at)

    def test_deactivate_blocks_user(self):
        self.call("staff@example.com", "--by", "Иля", "--approve")
        self.call("staff@example.com", "--by", "Иля", "--deactivate")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_approved)
        self.assertFalse(self.user.is_active)

    def test_student_cannot_be_manually_approved(self):
        """Студент не проходит ручное одобрение (C10)."""
        student = User.objects.create_user(
            email="st@example.com", password="Strong1!pass",
            full_name="Студент", role=User.Role.STUDENT,
        )
        with self.assertRaises(CommandError):
            self.call("st@example.com", "--by", "Иля", "--approve")

    def test_unknown_email_rejected(self):
        with self.assertRaises(CommandError):
            self.call("ghost@example.com", "--by", "Иля", "--approve")