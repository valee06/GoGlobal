import secrets
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email обязателен")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_approved", True)
        extra.setdefault("role", User.Role.CURATOR)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент-обменник"
        BUDDY = "buddy", "Study-buddy"
        CURATOR = "curator", "Куратор"

    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    is_approved = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=20, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=150, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    @property
    def profile_complete(self):
        if self.role != self.Role.STUDENT:
            return True
        return bool(self.full_name.strip())


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    curator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="students",
        verbose_name="закреплённый куратор",
    )


class BuddyProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="buddy_profile"
    )


class CuratorProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="curator_profile"
    )


class Invitation(models.Model):
    """Код куратора для регистрации студента."""
    code = models.CharField(max_length=12, unique=True)
    curator = models.ForeignKey("User", on_delete=models.CASCADE, related_name="invitations")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)

    @classmethod
    def generate_code(cls):
        return secrets.token_hex(4).upper()  # 8 символов: "9F3AC2E1"

    def is_valid(self):
        return not self.is_revoked and timezone.now() < self.expires_at


class OneTimeCode(models.Model):
    """Одноразовый код: подтверждение email или сброс пароля."""
    class Purpose(models.TextChoices):
        EMAIL_VERIFY = "email_verify", "Подтверждение email"
        PASSWORD_RESET = "password_reset", "Сброс пароля"

    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="one_time_codes")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code = models.CharField(max_length=6)  # не число а строка
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    reset_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate(cls, user, purpose, ttl_minutes):
        # атомарно гасим прежние активные коды того же назначения
        cls.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        return cls.objects.create(
            user=user, purpose=purpose,
            code=str(secrets.randbelow(900000) + 100000),  # 100000–999999 (D02)
            expires_at=timezone.now() + timezone.timedelta(minutes=ttl_minutes),
        )

    @classmethod
    def generate_candidate(cls, user, purpose, ttl_minutes):
        """Создать новый код, пока не отключая прежние коды."""
        return cls.objects.create(
            user=user,
            purpose=purpose,
            code=str(secrets.randbelow(900000) + 100000),
            expires_at=timezone.now() + timezone.timedelta(minutes=ttl_minutes),
        )

    def is_usable(self):
        return (
            self.used_at is None
            and timezone.now() < self.expires_at
            and self.attempts < settings.CODE_MAX_ATTEMPTS
        )


class AuditEvent(models.Model):
    """Служебная запись о важном действии или отказе."""

    class Result(models.TextChoices):
        SUCCESS = "success", "Успешно"
        DENIED = "denied", "Отказано"
        ERROR = "error", "Ошибка"

    event_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    operation = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64, blank=True, default="")
    result = models.CharField(
        max_length=12,
        choices=Result.choices,
        db_index=True,
    )
    reason_code = models.CharField(max_length=64, blank=True, default="")
    request_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["occurred_at", "operation"],
                name="audit_time_op_idx",
            ),
            models.Index(
                fields=["occurred_at", "result"],
                name="audit_time_result_idx",
            ),
        ]