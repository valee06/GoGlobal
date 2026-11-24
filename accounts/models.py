from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


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