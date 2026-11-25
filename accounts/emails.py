from enum import Enum
from smtplib import SMTPRecipientsRefused, SMTPResponseException

from django.conf import settings
from django.core.mail import send_mail


class MailResult(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class MailSendError(Exception):
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


def send_code_email(to: str, code: str, purpose: str) -> MailResult:
    if purpose == "email_verify":
        ttl_minutes = settings.EMAIL_CODE_TTL_MINUTES
        subject = "Подтверждение электронной почты"
        action = "подтверждения электронной почты"
    elif purpose == "password_reset":
        ttl_minutes = settings.RESET_CODE_TTL_MINUTES
        subject = "Восстановление пароля"
        action = "восстановления пароля"
    else:
        raise ValueError("Unknown email purpose")

    message = (
        f"Ваш код для {action}: {code}\n"
        f"Срок действия кода — {ttl_minutes} минут."
    )
    return send_email(to, subject, message)


def send_code_email_or_raise(to: str, code: str, purpose: str) -> None:
    result = send_code_email(to, code, purpose)

    if result is not MailResult.ACCEPTED:
        raise MailSendError(result)