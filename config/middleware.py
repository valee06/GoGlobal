import logging
import uuid

from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger("accounts")


class RequestEventIdMiddleware(MiddlewareMixin):
    """Добавляет ID запросу и записывает ID необработанной ошибки."""

    def process_request(self, request):
        request.event_id = uuid.uuid4()

    def process_exception(self, request, exception):
        event_id = getattr(request, "event_id", uuid.uuid4())

        logger.error(
            "Ошибка обработки запроса; тип_ошибки=%s",
            type(exception).__name__,
            extra={"event_id": str(event_id)},
        )

        # Пусть Django сам вернёт стандартный ответ 500.
        return None

    def process_response(self, request, response):
        event_id = getattr(request, "event_id", None)
        if event_id is not None:
            response["X-Event-ID"] = str(event_id)
        return response