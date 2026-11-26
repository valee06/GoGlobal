from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.conf import settings

from .models import Invitation, OneTimeCode, User


class StaffRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label="Имя и фамилия",
    )
    email = forms.EmailField(
        label="Электронная почта",
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Пароль",
    )
    role = forms.ChoiceField(
        choices=[
            (User.Role.CURATOR, "Куратор"),
            (User.Role.BUDDY, "Buddy"),
        ],
        widget=forms.RadioSelect,
        label="Роль",
    )
    consent_personal_data = forms.BooleanField(
        label="Согласие на обработку персональных данных",
    )

    def __init__(self, *args, selected_role=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.selected_role = selected_role

        if selected_role in (User.Role.CURATOR, User.Role.BUDDY):
            self.fields["role"].widget = forms.HiddenInput()
            self.fields["role"].initial = selected_role

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing = User.objects.filter(email=email).first()
        if existing:
            if existing.email_verified:
                raise forms.ValidationError(
                    "Пользователь с таким email уже зарегистрирован"
                )
            # Почта не подтверждена — старый аккаунт заменим
            self._replaces_user = existing
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean_role(self):
        role = self.cleaned_data["role"]

        if role not in (User.Role.CURATOR, User.Role.BUDDY):
            raise forms.ValidationError("Недопустимая роль")

        if self.selected_role and role != self.selected_role:
            raise forms.ValidationError(
                "Роль не соответствует выбранной форме регистрации"
            )

        return role

    def save(self):
        data = self.cleaned_data

        return User.objects.create_user(
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            role=data["role"],
            is_approved=False,
            email_verified=False,
            consent_version=settings.CONSENT_VERSION,
            consented_at=timezone.now(),
        )


class StudentRegistrationForm(forms.Form):
    """регистрация студента по коду куратора."""
    invitation_code = forms.CharField(max_length=12, label="Код куратора")
    email = forms.EmailField(label="Электронная почта")
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    consent_personal_data = forms.BooleanField(
        label="Согласие на обработку персональных данных")

    def clean_invitation_code(self):
        code = self.cleaned_data["invitation_code"].strip().upper()
        try:
            invitation = Invitation.objects.get(code=code)
        except Invitation.DoesNotExist:
            raise forms.ValidationError(
                "Код недействителен или больше не действует. Уточните код у куратора")
        if not invitation.is_valid():
            raise forms.ValidationError(
                "Код недействителен или больше не действует. Уточните код у куратора")
        self.invitation = invitation  
        return code

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing = User.objects.filter(email=email).first()
        if existing:
            if existing.email_verified:
                raise forms.ValidationError(
                    "Пользователь с таким email уже зарегистрирован"
                )
            # Почта не подтверждена — старый аккаунт заменим 
            self._replaces_user = existing
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class EmailCodeForm(forms.Form):
    """ввод 6-значного кода."""
    code = forms.CharField(max_length=6, min_length=6, label="Код из письма")

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Код — 6 цифр из письма")
        return code


class LoginForm(forms.Form):
    """вход."""
    email = forms.EmailField(label="Электронная почта")
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")


class ResetRequestForm(forms.Form):
    """запрос восстановления."""
    email = forms.EmailField(label="Электронная почта")


class ResetConfirmForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Новый пароль",
    )
    new_password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        label="Повторите новый пароль",
    )

    def clean(self):
        cleaned = super().clean()

        password = cleaned.get("new_password")
        confirmation = cleaned.get("new_password_confirm")

        if password and confirmation and password != confirmation:
            self.add_error(
                "new_password_confirm",
                "Пароли не совпадают",
            )

        if password:
            try:
                validate_password(password)
            except forms.ValidationError as exc:
                self.add_error("new_password", exc)

        return cleaned


class StudentProfileForm(forms.Form):
    """обязательная анкета студента (пока только имя)."""
    full_name = forms.CharField(max_length=150, label="Имя и фамилия")

