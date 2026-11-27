from enum import Enum
from smtplib import SMTPRecipientsRefused, SMTPResponseException

from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import get_language


class MailResult(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class MailSendError(Exception):
    """Ошибка отправки письма."""

    def __init__(self, result: MailResult):
        self.result = result
        super().__init__(f"Email send result: {result.value}")


def send_email(to: str, subject: str, message: str) -> MailResult:
    """Общая отправка письма через настроенный Django mail backend."""
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
    except (SMTPRecipientsRefused, SMTPResponseException):
        return MailResult.REJECTED
    except Exception:
        # В том числе таймаут: неизвестно, успел ли сервер принять письмо.
        return MailResult.UNKNOWN

    return MailResult.ACCEPTED if sent_count == 1 else MailResult.REJECTED


def _code_email_texts(purpose: str, code: str) -> tuple[str, str]:
    """Тема и текст письма с кодом на языке текущего запроса (RU/EN)."""
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

    return subject, message


def send_code_email(to: str, code: str, purpose: str) -> MailResult:
    subject, message = _code_email_texts(purpose, code)
    return send_email(to, subject, message)


def send_code_email_or_raise(to: str, code: str, purpose: str) -> None:
    result = send_code_email(to, code, purpose)

    if result is not MailResult.ACCEPTED:
        raise MailSendError(result)
