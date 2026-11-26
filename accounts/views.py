from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .emails import MailResult, MailSendError, send_code_email, send_code_email_or_raise
from .audit import record_domain_event
from .forms import (EmailCodeForm, LoginForm, ResetConfirmForm,
                    ResetRequestForm, StaffRegistrationForm,
                    StudentProfileForm, StudentRegistrationForm)
from .models import OneTimeCode, User, Invitation, StudentProfile
from .services import (kill_user_sessions, login_locked,
                       register_login_failure, reset_login_failures)

GENERIC_ERROR = "Не удалось войти. Проверьте данные для входа"


def _start_verification(request, user):
    """Создать код, отправить письмо, положить контекст в сессию."""
    code = OneTimeCode.generate(user, OneTimeCode.Purpose.EMAIL_VERIFY,
                                settings.EMAIL_CODE_TTL_MINUTES)
    send_code_email_or_raise(user.email, code.code, "email_verify")
    request.session["pending_verify_user_id"] = user.pk


def register_staff(request):
    if request.method == "POST":
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            old = getattr(form, "_replaces_user", None)
            if old:
                old.delete()
            user = form.save()
            try:
                _start_verification(request, user)
            except MailSendError:
                return render(request, "auth/form.html", {
                    "heading": "Не удалось отправить письмо",
                    "message": "Регистрация сохранена. Попробуйте запросить код позже.",
                })
            return redirect("auth:verify_email")
    else:
        form = StaffRegistrationForm()
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Регистрация", "button": "Зарегистрироваться"})


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
    """Общая проверка кода: срок, попытки, одноразовость (D03/D04)."""
    code = (OneTimeCode.objects
            .filter(user=user, purpose=purpose, used_at__isnull=True)
            .order_by("-created_at").first())
    if not code or not code.is_usable():
        return None
    code.attempts += 1
    code.save(update_fields=["attempts"])
    if code.code != code_str:
        return None
    code.used_at = timezone.now()
    code.save(update_fields=["used_at"])
    return code


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
                # TODO: когда Арег добавит send_approval_request — вызвать здесь
                # для curator/buddy с is_approved=False
                return redirect("auth:login")
            form.add_error("code", "Код неверный или больше не действует")
    else:
        form = EmailCodeForm()
    return render(request, "auth/form.html", {
        "form": form, "button": "Подтвердить",
        "heading": f"Введите код из письма, отправленного на {user.email}",
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
    """Повторная отправка: старый код отключается только после принятия письма."""
    user_id = request.session.get("pending_verify_user_id")
    if not user_id:
        return redirect("auth:login")

    user = User.objects.filter(pk=user_id).first()
    if not user:
        return redirect("auth:login")

    code = OneTimeCode.generate_candidate(
        user,
        OneTimeCode.Purpose.EMAIL_VERIFY,
        settings.EMAIL_CODE_TTL_MINUTES,
    )

    result = send_code_email(user.email, code.code, "email_verify")

    if result is MailResult.ACCEPTED:
        OneTimeCode.objects.filter(
            user=user,
            purpose=OneTimeCode.Purpose.EMAIL_VERIFY,
            used_at__isnull=True,
        ).exclude(pk=code.pk).update(used_at=timezone.now())

        return redirect("auth:verify_email")

    if result is MailResult.REJECTED:
        code.delete()
        message = "Почтовый сервер отказал. Прежний код продолжает действовать."
    else:
        message = (
            "Не удалось узнать, принял ли почтовый сервер письмо. "
            "Прежний и новый коды пока действуют."
        )

    return render(request, "auth/form.html", {
        "heading": "Не удалось подтвердить отправку",
        "message": message,
    })


def login_view(request):
    """Вход; фиксируем успехи и отказы без email и пароля."""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            if login_locked(email):
                record_domain_event(
                    operation="auth.login",
                    object_type="authentication",
                    result="denied",
                    reason_code="login_locked",
                    request_id=getattr(request, "event_id", None),
                )
                return render(request, "auth/form.html", {
                    "heading": "Слишком много попыток",
                    "message": f"Повторите через {settings.LOGIN_LOCK_MINUTES} минут "
                               f"или восстановите пароль.",
                })

            user = authenticate(
                request,
                username=email,
                password=form.cleaned_data["password"],
            )

            if user is None or not user.is_active:
                record_domain_event(
                    operation="auth.login",
                    object_type="authentication",
                    result="denied",
                    reason_code="bad_credentials",
                    request_id=getattr(request, "event_id", None),
                )
                register_login_failure(email)
                form.add_error(None, GENERIC_ERROR)
            elif not user.email_verified:
                record_domain_event(
                    operation="auth.login",
                    object_type="user",
                    object_id=user.pk,
                    actor_id=user.pk,
                    result="denied",
                    reason_code="email_unverified",
                    request_id=getattr(request, "event_id", None),
                )
                form.add_error(
                    None,
                    "Подтвердите электронную почту — код уже отправлен",
                )
            elif user.role != User.Role.STUDENT and not user.is_approved:
                record_domain_event(
                    operation="auth.login",
                    object_type="user",
                    object_id=user.pk,
                    actor_id=user.pk,
                    result="denied",
                    reason_code="approval_pending",
                    request_id=getattr(request, "event_id", None),
                )
                form.add_error(
                    None,
                    "Регистрация ожидает проверки командой проекта",
                )
            else:
                reset_login_failures(email)
                login(request, user)
                record_domain_event(
                    operation="auth.login",
                    object_type="user",
                    object_id=user.pk,
                    actor_id=user.pk,
                    result="success",
                    request_id=getattr(request, "event_id", None),
                )

                nxt = request.GET.get("next", "")
                if nxt and url_has_allowed_host_and_scheme(
                    nxt,
                    {request.get_host()},
                ):
                    return redirect(nxt)
                return redirect("home")
    else:
        form = LoginForm()

    return render(
        request,
        "auth/form.html",
        {"form": form, "heading": "Вход", "button": "Войти"},
    )


@require_POST
def logout_view(request):
    """C06: выход только POST, сессия аннулируется на сервере."""
    logout(request)
    return redirect("auth:login")


def reset_request(request):
    """одинаковый ответ для любого адреса — не раскрываем аккаунт."""
    message = "Если адрес зарегистрирован, мы отправим инструкцию по восстановлению"
    if request.method == "POST":
        form = ResetRequestForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data["email"], is_active=True).first()
            if user:
                try:
                    code = OneTimeCode.generate(
                        user, OneTimeCode.Purpose.PASSWORD_RESET,
                        settings.RESET_CODE_TTL_MINUTES)
                    send_code_email_or_raise(user.email, code.code, "password_reset")
                except MailSendError:
                    pass  # публичный ответ не меняется (C07)
            return render(request, "auth/form.html",
                          {"heading": "Проверьте почту", "message": message})
    else:
        form = ResetRequestForm()
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Восстановление пароля",
                   "button": "Отправить код"})


def reset_confirm(request):
    """смена пароля по коду, отзыв всех сессий."""
    if request.method == "POST":
        form = ResetConfirmForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data["email"], is_active=True).first()
            ok = user and _check_code(user, OneTimeCode.Purpose.PASSWORD_RESET,
                                      form.cleaned_data["code"])
            if not ok:
                form.add_error("code", "Код неверный или больше не действует")
            else:
                user.set_password(form.cleaned_data["new_password"])
                user.save(update_fields=["password"])
                kill_user_sessions(user)  # прежние сессии аннулированы
                return redirect("auth:login")
    else:
        form = ResetConfirmForm()
    return render(request, "auth/form.html",
                  {"form": form, "heading": "Новый пароль", "button": "Сохранить"})


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
    return render(request, "auth/form.html", {
        "heading": "Регистрация ожидает проверки командой проекта"})


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