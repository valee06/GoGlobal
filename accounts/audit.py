import logging
import re
import uuid

from django.utils import timezone

from .models import AuditEvent


logger = logging.getLogger("accounts")

ALLOWED_OPERATIONS = {
    "auth.login",
    "access.denied",
    "buddy.assign",
    "stage.change",
    "deadline.change",
    "task.check",
    "task.publish",
    "role.change",
}

SAFE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
SAFE_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def record_domain_event(
    *,
    operation,
    object_type,
    result,
    actor_id=None,
    object_id=None,
    reason_code="",
    request_id=None,
    occurred_at=None,
):
    """Сохранить безопасное описание важного действия в журнал."""

    if operation not in ALLOWED_OPERATIONS:
        raise ValueError("Неизвестный код операции")

    if not SAFE_CODE_PATTERN.fullmatch(object_type):
        raise ValueError("Тип объекта должен быть коротким кодом")

    if result not in AuditEvent.Result.values:
        raise ValueError("Неизвестный результат операции")

    if reason_code and not SAFE_CODE_PATTERN.fullmatch(reason_code):
        raise ValueError("Причина должна быть коротким кодом, без текста")

    if object_id is None:
        object_id = ""
    else:
        object_id = str(object_id)
        if not SAFE_OBJECT_ID_PATTERN.fullmatch(object_id):
            raise ValueError("ID объекта имеет недопустимый формат")

    if request_id is not None and not isinstance(request_id, uuid.UUID):
        request_id = uuid.UUID(str(request_id))

    event_id = uuid.uuid4()

    try:
        event = AuditEvent.objects.create(
            event_id=event_id,
            occurred_at=occurred_at or timezone.now(),
            actor_id=actor_id,
            operation=operation,
            object_type=object_type,
            object_id=object_id,
            result=result,
            reason_code=reason_code,
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "Не удалось сохранить запись аудита; тип_ошибки=%s",
            type(exc).__name__,
            extra={"event_id": str(event_id)},
        )
        raise

    logger.info(
        "audit operation=%s object_type=%s object_id=%s "
        "result=%s reason_code=%s",
        operation,
        object_type,
        object_id or "-",
        result,
        reason_code or "-",
        extra={"event_id": str(event.event_id)},
    )

    return event