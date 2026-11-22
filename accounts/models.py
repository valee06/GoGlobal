from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент-обменник"
        BUDDY = "buddy", "Study-buddy"
        CURATOR = "curator", "Куратор"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    is_approved = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []


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