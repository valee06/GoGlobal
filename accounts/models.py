from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import secrets
from django.conf import settings
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
        return (self.used_at is None
                and timezone.now() < self.expires_at
                and self.attempts < settings.CODE_MAX_ATTEMPTS)