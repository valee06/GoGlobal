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

        self.assertRedirects(response, "/auth/email/verify/")
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
        # первый пользователь подтвердил почту — теперь email занят по-настоящему
        u = User.objects.get(email=VALID["email"])
        u.email_verified = True
        u.save()

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


from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .models import Invitation, OneTimeCode, User


def make_curator():
    """Одобренный куратор — владелец кодов приглашений."""
    curator = User.objects.create_user(
        email="curator@example.com", password="Passw0rd!",
        role=User.Role.CURATOR, is_approved=True,
    )
    curator.email_verified = True
    curator.save()
    return curator


def make_invitation(curator, code="TESTCODE1"):
    return Invitation.objects.create(
        code=code, curator=curator,
        expires_at=timezone.now() + timedelta(days=7),
    )


def make_student(email="student@example.com"):
    """Подтверждённый студент с заполненной анкетой."""
    user = User.objects.create_user(
        email=email, password="Passw0rd!",
        role=User.Role.STUDENT, is_approved=True,
        full_name="Тестов Студент",
    )
    user.email_verified = True
    user.save()
    return user


class StudentRegistrationTests(TestCase):

    def test_invalid_invitation_code_rejected(self):
        make_invitation(make_curator())
        self.client.post("/auth/register/student/", {
            "invitation_code": "WRONGCODE",
            "email": "s@example.com",
            "password": "Passw0rd!",
            "consent_personal_data": "on",
        })
        self.assertFalse(User.objects.filter(email="s@example.com").exists())

    def test_valid_code_creates_student_and_sends_code(self):
        make_invitation(make_curator())
        response = self.client.post("/auth/register/student/", {
            "invitation_code": "TESTCODE1",
            "email": "s@example.com",
            "password": "Passw0rd!",
            "consent_personal_data": "on",
        })
        user = User.objects.get(email="s@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.is_approved)        # студенту approve не нужен
        self.assertFalse(user.email_verified)    # но почту подтвердить надо
        self.assertTrue(OneTimeCode.objects.filter(
            user=user, purpose="email_verify",
        ).exists())

    def test_revoked_code_rejected(self):
        inv = make_invitation(make_curator())
        inv.is_revoked = True
        inv.save()
        self.client.post("/auth/register/student/", {
            "invitation_code": "TESTCODE1",
            "email": "s@example.com",
            "password": "Passw0rd!",
            "consent_personal_data": "on",
        })
        self.assertFalse(User.objects.filter(email="s@example.com").exists())


class EmailVerificationTests(TestCase):

    def register_student(self):
        make_invitation(make_curator())
        self.client.post("/auth/register/student/", {
            "invitation_code": "TESTCODE1",
            "email": "s@example.com",
            "password": "Passw0rd!",
            "consent_personal_data": "on",
        })
        return User.objects.get(email="s@example.com")

    def test_correct_code_verifies_email(self):
        user = self.register_student()
        code = OneTimeCode.objects.get(user=user, purpose="email_verify")
        self.client.post("/auth/email/verify/", {"code": code.code})
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_code_dies_after_three_wrong_attempts(self):
        user = self.register_student()
        code = OneTimeCode.objects.get(user=user, purpose="email_verify")
        wrong = "000000" if code.code != "000000" else "000001"
        for _ in range(3):
            self.client.post("/auth/email/verify/", {"code": wrong})
        code.refresh_from_db()
        self.assertFalse(code.is_usable())       # код мёртв
        # даже правильный код больше не сработает
        self.client.post("/auth/email/verify/", {"code": code.code})
        user.refresh_from_db()
        self.assertFalse(user.email_verified)


class LoginLockoutTests(TestCase):

    def test_ten_failures_lock_login(self):
        make_student()
        for _ in range(10):
            self.client.post("/auth/login/", {
                "email": "student@example.com", "password": "WrongPass1!",
            })
        # теперь даже правильный пароль не пускает
        self.client.post("/auth/login/", {
            "email": "student@example.com", "password": "Passw0rd!",
        })
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.url)  # не залогинен


class PasswordResetTests(TestCase):

    def test_request_creates_code_for_known_email_only(self):
        make_student()
        self.client.post("/auth/password/reset/request/",
                         {"email": "student@example.com"})
        self.assertTrue(OneTimeCode.objects.filter(
            purpose="password_reset",
        ).exists())

    def test_unknown_email_gives_same_answer_and_no_code(self):
        response = self.client.post("/auth/password/reset/request/",
                                    {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(OneTimeCode.objects.filter(
            purpose="password_reset",
        ).exists())

    def test_reset_changes_password_and_kills_sessions(self):
        user = make_student()
        self.client.login(email="student@example.com", password="Passw0rd!")
        self.client.post("/auth/password/reset/request/",
                         {"email": "student@example.com"})
        code = OneTimeCode.objects.get(purpose="password_reset")
        self.client.post("/auth/password/reset/confirm/", {
            "email": "student@example.com",
            "code": code.code,
            "new_password": "N3wPass!word",
            "new_password_confirm": "N3wPass!word",
        })
        user.refresh_from_db()
        self.assertTrue(user.check_password("N3wPass!word"))
        # старая сессия умерла — главная снова ведёт на вход
        response = self.client.get("/")
        self.assertIn("/auth/login", response.url)


class StudentProfileTests(TestCase):

    def test_student_without_fullname_redirected_to_profile(self):
        user = User.objects.create_user(
            email="s@example.com", password="Passw0rd!",
            role=User.Role.STUDENT, is_approved=True,
        )
        user.email_verified = True
        user.save()
        self.client.login(email="s@example.com", password="Passw0rd!")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/profile/student", response.url)

    def test_unverified_email_can_be_reused(self):
        User.objects.create_user(email="ghost@example.com", password="Passw0rd!")
        self.client.post("/auth/register/staff/", {
            "full_name": "Новый Человек",
            "email": "ghost@example.com",
            "password": "N3wPass!word",
            "role": "buddy",
            "consent_personal_data": "on",
        })
        self.assertEqual(User.objects.filter(email="ghost@example.com").count(), 1)
        self.assertEqual(
            User.objects.get(email="ghost@example.com").full_name, "Новый Человек",
        )

    def test_verified_email_stays_unique(self):
        u = User.objects.create_user(email="real@example.com", password="Passw0rd!")
        u.email_verified = True
        u.save()
        response = self.client.post("/auth/register/staff/", {
            "full_name": "Самозванец",
            "email": "real@example.com",
            "password": "N3wPass!word",
            "role": "buddy",
            "consent_personal_data": "on",
        })
        self.assertContains(response, "уже зарегистрирован")