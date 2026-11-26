from django.conf import settings
from django.core.mail import send_mail


class MailSendError(Exception):
    """Ошибка отправки письма."""


def send_code_email(to: str, code: str, purpose: str) -> None:
    if purpose == "email_verify":
        ttl_minutes = settings.EMAIL_CODE_TTL_MINUTES
        subject = "Подтверждение электронной почты"
        action = "подтверждения электронной почты"
    elif purpose == "password_reset":
        ttl_minutes = settings.RESET_CODE_TTL_MINUTES
        subject = "Восстановление пароля"
        action = "восстановления пароля"
    else:
        raise ValueError(f"Unknown email purpose: {purpose}")

    message = (
        f"Ваш код для {action}: {code}\n"
        f"Срок действия кода — {ttl_minutes} минут."
    )

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