from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.conf import settings

from .models import User


class StaffRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=[
        (User.Role.CURATOR, "Куратор"),
        (User.Role.BUDDY, "Buddy"),
    ], widget=forms.RadioSelect)
    consent_personal_data = forms.BooleanField()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже зарегистрирован")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role not in (User.Role.CURATOR, User.Role.BUDDY):
            raise forms.ValidationError("Недопустимая роль") 
        return role

    def save(self):
        data = self.cleaned_data
        return User.objects.create_user(
            email=data["email"],
            password=data["password"],   # create_user сам хэширует (PBKDF2)
            full_name=data["full_name"],
            role=data["role"],
            is_approved=False,
            email_verified=False,
            consent_version=settings.CONSENT_VERSION,
            consented_at=timezone.now(),
        )