from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from .emails import MailSendError, send_code_email
from .forms import (EmailCodeForm, LoginForm, ResetConfirmForm,
                    ResetRequestForm, StaffRegistrationForm,
                    StudentProfileForm, StudentRegistrationForm)
from .models import OneTimeCode, User, Invitation, StudentProfile
from .services import (kill_user_sessions, login_locked,
                       register_login_failure, reset_login_failures)

from django.contrib import messages
from .codes import (
    CodeRateLimit,
    check_code,
    send_code_limited,
    wait_before_resend,
)              

from django.db import transaction

GENERIC_ERROR = "Не удалось войти. Проверьте данные для входа"


def _start_verification(request, user):
    request.session["pending_verify_user_id"] = user.pk

    send_code_limited(
        user,
        OneTimeCode.Purpose.EMAIL_VERIFY,
        settings.EMAIL_CODE_TTL_MINUTES,
    )


def register_staff(request):
    selected_role = (
        request.GET.get("role")
        or request.POST.get("role")
    )

    if selected_role not in (
        User.Role.CURATOR,
        User.Role.BUDDY,
    ):
        return redirect(
            "auth:choose_role",
            mode="register",
        )

    if selected_role == User.Role.CURATOR:
        heading = "Регистрация куратора"
    else:
        heading = "Регистрация buddy"

    if request.method == "POST":
        form = StaffRegistrationForm(
            request.POST,
            selected_role=selected_role,
        )

        if form.is_valid():
            user = form.save()

            try:
                _start_verification(request, user)
            except MailSendError:
                return render(
                    request,
                    "auth/form.html",
                    {
                        "heading": "Не удалось отправить письмо",
                        "message": (
                            "Регистрация сохранена. "
                            "Попробуйте запросить код позже."
                        ),
                    },
                )

            return redirect("auth:verify_email")

    else:
        form = StaffRegistrationForm(
            selected_role=selected_role,
        )

    return render(
        request,
        "auth/form.html",
        {
            "form": form,
            "heading": heading,
            "button": "Зарегистрироваться",
        },
    )


def register_student(request):
    """студент по коду куратора, без ручного одобрения."""
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            old = getattr(form, "_replaces_user", None)
            if old:
                old.delete()
            user = User.objects.create_user(
                email=data["email"], password=data["password"],
                role=User.Role.STUDENT, is_approved=True,  # студенту одобрение не нужно
                email_verified=False,
                consent_version=settings.CONSENT_VERSION,
                consented_at=timezone.now(),
            )
            StudentProfile.objects.get_or_create(user=user)
            try:
                _start_verification(request, user)
            except MailSendError:
                return render(request, "auth/form.html", {
                    "heading": "Не удалось отправить письмо",
                    "message": "Регистрация сохранена. Попробуйте запросить код позже.",
                })
            return redirect("auth:verify_email")
    else:
        form = StudentRegistrationForm()
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Регистрация по коду куратора",
                   "button": "Зарегистрироваться"})


def _check_code(user, purpose, code_str):
    return check_code(user, purpose, code_str)


def verify_email(request):
    """C03: подтверждение email кодом. Контекст — из сессии, не из формы."""
    user_id = request.session.get("pending_verify_user_id")
    if not user_id:
        return redirect("auth:login")
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return redirect("auth:login")

    if request.method == "POST":
        form = EmailCodeForm(request.POST)
        if form.is_valid():
            if _check_code(user, OneTimeCode.Purpose.EMAIL_VERIFY,
                           form.cleaned_data["code"]):
                user.email_verified = True
                user.save(update_fields=["email_verified"])
                request.session.pop("pending_verify_user_id", None)

                # Уведомление команде об одобрении подключим отдельно.
                if (
                    user.role in (User.Role.CURATOR, User.Role.BUDDY)
                    and not user.is_approved
                ):
                    request.session["pending_approval_user_id"] = user.pk
                    return redirect("auth:pending")

                return redirect("auth:login")
            form.add_error("code", "Код неверный или больше не действует")
    else:
        form = EmailCodeForm()

    return render(request, "auth/form.html", {
        "form": form,
        "button": "Подтвердить",
        "heading": _("Подтверждение электронной почты"),
        "message": _(
            "Введите код для адреса %(email)s. "
            "Проверьте входящие и папку «Спам»."
        ) % {"email": user.email},
        "resend_wait": wait_before_resend(
            user,
            OneTimeCode.Purpose.EMAIL_VERIFY,
        ),
    })


def curator_required(view):
    """Только одобренный куратор (остальных — на home)."""
    @login_required
    def wrapper(request, *args, **kwargs):
        u = request.user
        if u.role != User.Role.CURATOR or not u.is_approved:
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapper


@require_POST
def resend_code(request):
    user_id = request.session.get("pending_verify_user_id")

    if not user_id:
        return redirect("auth:login")

    user = User.objects.filter(
        pk=user_id,
        email_verified=False,
    ).first()

    if user is None:
        request.session.pop("pending_verify_user_id", None)
        return redirect("auth:login")

    try:
        send_code_limited(
            user,
            OneTimeCode.Purpose.EMAIL_VERIFY,
            settings.EMAIL_CODE_TTL_MINUTES,
        )

    except CodeRateLimit as exc:
        messages.error(
            request,
            _("Запросите новый код через %(seconds)s сек.")
            % {"seconds": exc.seconds},
        )

    except MailSendError:
        messages.error(
            request,
            _("Не удалось отправить письмо. Попробуйте позже."),
        )

    else:
        messages.success(
            request,
            _("Новый код отправлен. Предыдущий больше не действует."),
        )

    return redirect("auth:verify_email")


def login_view(request):
    """вход. Роль — только из БД, ошибка всегда общая."""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            if login_locked(email):
                return render(request, "auth/form.html", {
                    "heading": "Слишком много попыток",
                    "message": f"Повторите через {settings.LOGIN_LOCK_MINUTES} минут "
                               f"или восстановите пароль.",
                })
            user = authenticate(request, username=email,
                                password=form.cleaned_data["password"])
            if user is None or not user.is_active:
                register_login_failure(email)
                form.add_error(None, GENERIC_ERROR)  # без раскрытия аккаунта
            else:
                reset_login_failures(email)
                if not user.email_verified:
                    request.session["pending_verify_user_id"] = user.pk
                    return redirect("auth:verify_email")
                elif user.role != User.Role.STUDENT and not user.is_approved:
                    request.session["pending_approval_user_id"] = user.pk
                    return redirect("auth:pending")
                else:
                    login(request, user)
                    nxt = request.GET.get("next", "")
                    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
                        return redirect(nxt)
                    return redirect("home")
    else:
        form = LoginForm()
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Вход", "button": "Войти"})


@require_POST
def logout_view(request):
    """Выход с аннулированием сессии и сохранением языка."""
    language = getattr(request, "ui_language", "ru")

    logout(request)

    request.session["auth_ui_language"] = (
        language if language in ("ru", "en") else "ru"
    )

    return redirect("auth:login")


def _reset_grant_valid(code):
    if (
        code is None
        or code.purpose != OneTimeCode.Purpose.PASSWORD_RESET
        or code.used_at is None
        or code.reset_completed_at is not None
        or timezone.now() >= code.expires_at
        or not code.user.is_active
        or not code.user.email_verified
    ):
        return False

    latest_id = (
        OneTimeCode.objects.filter(
            user_id=code.user_id,
            purpose=OneTimeCode.Purpose.PASSWORD_RESET,
        )
        .order_by("-created_at", "-pk")
        .values_list("pk", flat=True)
        .first()
    )

    return latest_id == code.pk


def _restart_reset(request):
    request.session.pop("password_reset_grant", None)

    messages.error(
        request,
        _("Восстановление недоступно. Запросите новый код."),
    )

    return redirect("auth:reset_request")


def reset_request(request):
    if request.method == "POST":
        form = ResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            request.session["pending_reset_email"] = email

            user = User.objects.filter(
                email__iexact=email,
                is_active=True,
                email_verified=True,
            ).first()

            if user:
                try:
                    send_code_limited(
                        user,
                        OneTimeCode.Purpose.PASSWORD_RESET,
                        settings.RESET_CODE_TTL_MINUTES,
                    )
                except (MailSendError, CodeRateLimit):
                    pass

            return redirect("auth:reset_verify")

    else:
        form = ResetRequestForm()

    return render(request, "auth/form.html", {
        "form": form,
        "heading": _("Восстановление пароля"),
        "button": _("Отправить код"),
    })


def reset_verify(request):
    email = request.session.get("pending_reset_email")

    if not email:
        return redirect("auth:reset_request")

    if request.method == "POST":
        form = EmailCodeForm(request.POST)

        if form.is_valid():
            user = User.objects.filter(
                email__iexact=email,
                is_active=True,
                email_verified=True,
            ).first()

            code = None

            if user:
                code = _check_code(
                    user,
                    OneTimeCode.Purpose.PASSWORD_RESET,
                    form.cleaned_data["code"],
                )

            if code:
                request.session["password_reset_grant"] = {
                    "code_id": code.pk,
                }
                request.session.pop("pending_reset_email", None)

                return redirect("auth:reset_confirm")

            form.add_error(
                "code",
                _("Код неверный или больше не действует"),
            )

    else:
        form = EmailCodeForm()

    return render(request, "auth/form.html", {
        "form": form,
        "heading": _("Код восстановления"),
        "message": _(
            "Если адрес зарегистрирован, мы отправим инструкцию по восстановлению"
        ),
        "button": _("Установить новый пароль"),
    })


def reset_confirm(request):
    grant = request.session.get("password_reset_grant", {})

    code = (
        OneTimeCode.objects.select_related("user")
        .filter(
            pk=grant.get("code_id"),
            purpose=OneTimeCode.Purpose.PASSWORD_RESET,
        )
        .first()
    )

    if not _reset_grant_valid(code):
        return _restart_reset(request)

    if request.method == "POST":
        form = ResetConfirmForm(request.POST)

        if form.is_valid():
            changed = False

            with transaction.atomic():
                user = (
                    User.objects.select_for_update()
                    .filter(pk=code.user_id)
                    .first()
                )

                fresh_code = (
                    OneTimeCode.objects.select_related("user")
                    .filter(pk=code.pk)
                    .first()
                )

                if user and _reset_grant_valid(fresh_code):
                    user.set_password(
                        form.cleaned_data["new_password"]
                    )
                    user.save(update_fields=["password"])

                    fresh_code.reset_completed_at = timezone.now()
                    fresh_code.save(
                        update_fields=["reset_completed_at"]
                    )

                    kill_user_sessions(user)
                    changed = True

            if not changed:
                return _restart_reset(request)

            language = getattr(request, "ui_language", "ru")

            logout(request)
            request.session["auth_ui_language"] = language

            messages.success(
                request,
                _("Пароль обновлён. Войдите с новым паролем."),
            )

            return redirect("auth:login")

    else:
        form = ResetConfirmForm()

    return render(request, "auth/form.html", {
        "form": form,
        "heading": _("Новый пароль"),
        "message": _("Введите новый пароль для %(email)s.")
        % {"email": code.user.email},
        "button": _("Обновить пароль"),
    })

@login_required
def profile_student(request):
    """анкета студента. Чужие/системные поля формой не принимаются."""
    user = request.user
    if user.role != User.Role.STUDENT:
        return redirect("home")
    if request.method == "POST":
        form = StudentProfileForm(request.POST)
        if form.is_valid():
            user.full_name = form.cleaned_data["full_name"]
            user.save(update_fields=["full_name"])
            return redirect("home")
    else:
        form = StudentProfileForm(initial={"full_name": user.full_name})
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Анкета студента", "button": "Сохранить"})


def pending(request):
    user_id = request.session.get("pending_approval_user_id")

    if not user_id:
        return redirect("auth:login")

    user = User.objects.filter(
        pk=user_id,
        role__in=(User.Role.CURATOR, User.Role.BUDDY),
        email_verified=True,
        is_active=True,
    ).first()

    if user is None:
        request.session.pop("pending_approval_user_id", None)
        return redirect("auth:login")

    english = (
        user.role == User.Role.BUDDY
        or getattr(request, "ui_language", "ru") == "en"
    )

    if english:
        request.session["auth_ui_language"] = "en"

    if user.is_approved:
        request.session.pop("pending_approval_user_id", None)

        messages.success(
            request,
            "Your account has been approved. Log in to continue."
            if english
            else "Ваш аккаунт одобрен. Войдите, чтобы продолжить.",
        )

        return redirect("auth:login")

    return render(
        request,
        "auth/pending.html",
        {
            "pending_english": english,
            "ui_language": "en" if english else "ru",
        },
    )


@login_required
def home(request):
    """Заглушка кабинета до блоков 2–3; студента без анкеты — в анкету."""
    if request.user.role == User.Role.STUDENT and not request.user.profile_complete:
        return redirect("profile_student")
    return render(request, "auth/home.html")


@curator_required
def invitations(request):
    """FR-23/24: куратор сам создаёт, видит и отзывает коды приглашений."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            Invitation.objects.create(
                code=Invitation.generate_code(),
                curator=request.user,
                expires_at=timezone.now() + timedelta(days=7),
            )
        elif action == "revoke":
            Invitation.objects.filter(
                pk=request.POST.get("invitation_id"),
                curator=request.user,  # только свои коды!
            ).update(is_revoked=True)
        return redirect("auth:invitations")
    codes = Invitation.objects.filter(curator=request.user).order_by("-created_at")
    return render(request, "auth/invitations.html", {"codes": codes, "now": timezone.now()})


def entry_page(request, mode="welcome"):
    from urllib.parse import urlencode
    from django.urls import reverse

    if mode not in ("welcome", "login", "register"):
        return redirect("welcome")

    language = getattr(request, "ui_language", "ru")

    english = language == "en"

    if mode == "login":
        heading = "Log in as" if english else "Войти как"
    elif mode == "register":
        heading = "Sign up as" if english else "Зарегистрироваться как"
    else:
        heading = "GoGlobal"

    roles = []

    for role, ru_label, en_label in [
        ("curator", "Куратор", "Curator"),
        ("student", "Студент", "Student"),
        ("buddy", "Buddy", "Buddy"),
    ]:
        if mode == "login":
            target = reverse("auth:login")
        elif role == "student":
            target = reverse("auth:register_student")
        else:
            target = reverse("auth:register_staff")

        roles.append({
            "name": role,
            "label": en_label if english else ru_label,
            "url": target + "?" + urlencode({
                "role": role,
                "lang": language,
            }),
        })

    return render(request, "auth/entry.html", {
        "mode": mode,
        "heading": heading,
        "ui_language": language,
        "english": english,
        "hide_header": True,
        "roles": roles,
        "login_url": reverse(
            "auth:choose_role", kwargs={"mode": "login"}
        ) + "?" + urlencode({"lang": language}),
        "register_url": reverse(
            "auth:choose_role", kwargs={"mode": "register"}
        ) + "?" + urlencode({"lang": language}),
        "back_url": reverse("welcome") + "?" + urlencode({
            "lang": language,
        }),
    })


def personal_data_consent(request):
    return render(request, "auth/personal_data_consent.html")