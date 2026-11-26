from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import get_language


class MailSendError(Exception):
    """Ошибка отправки письма."""


def send_code_email(to: str, code: str, purpose: str) -> None:
    english = (get_language() or "ru").startswith("en")

    if purpose == "email_verify":
        ttl_minutes = settings.EMAIL_CODE_TTL_MINUTES

        if english:
            subject = "Verify your email — GoGlobal"
            message = (
                f"Your email verification code: {code}\n"
                f"The code is valid for {ttl_minutes} minutes.\n"
                "If you did not request this code, ignore this email."
            )
        else:
            subject = "Подтверждение почты — GoGlobal"
            message = (
                f"Ваш код подтверждения почты: {code}\n"
                f"Срок действия кода — {ttl_minutes} минут.\n"
                "Если вы не запрашивали код, проигнорируйте письмо."
            )

    elif purpose == "password_reset":
        ttl_minutes = settings.RESET_CODE_TTL_MINUTES

        if english:
            subject = "Password recovery — GoGlobal"
            message = (
                f"Your password recovery code: {code}\n"
                f"The code is valid for {ttl_minutes} minutes.\n"
                "If you did not request this code, ignore this email."
            )
        else:
            subject = "Восстановление пароля — GoGlobal"
            message = (
                f"Ваш код восстановления пароля: {code}\n"
                f"Срок действия кода — {ttl_minutes} минут.\n"
                "Если вы не запрашивали код, проигнорируйте письмо."
            )

    else:
        raise ValueError(f"Unknown email purpose: {purpose}")

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
    except Exception as exc:
        raise MailSendError("Не удалось отправить письмо") from exc