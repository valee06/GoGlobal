import logging
import re
import uuid


class SafeLogFilter(logging.Filter):
    """Добавляет ID события и скрывает секреты и адреса почты."""

    SECRET_PATTERN = re.compile(
        r"""(?i)\b(password|passwd|secret|token|authorization|api[_-]?key)"""
        r"""(\s*[:=]\s*)"""
        r"""(?:"[^"]*"|'[^']*'|[^\s,;]+)"""
    )
    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )
    BEARER_PATTERN = re.compile(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"
    )

    def filter(self, record):
        # У каждой записи будет ID. Позже его можно будет сообщить
        # пользователю, чтобы найти соответствующую ошибку в журнале.
        if not getattr(record, "event_id", None):
            record.event_id = uuid.uuid4().hex

        try:
            message = record.getMessage()
        except Exception:
            message = "Не удалось прочитать сообщение журнала"

        message = self.SECRET_PATTERN.sub(r"\1\2[СКРЫТО]", message)
        message = self.BEARER_PATTERN.sub("Bearer [СКРЫТО]", message)
        message = self.EMAIL_PATTERN.sub("[EMAIL]", message)

        record.msg = message
        record.args = ()

        # Не печатаем текст исключения: в нём могут случайно оказаться
        # пароль, токен или личные данные. Оставляем только тип ошибки.
        if record.exc_info:
            exception_type = record.exc_info[0].__name__
            record.exc_info = None
            record.exc_text = None
            record.msg = f"{record.msg} тип_ошибки={exception_type}"

        record.stack_info = None
        return True