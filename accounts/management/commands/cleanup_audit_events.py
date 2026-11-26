from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import AuditEvent


class Command(BaseCommand):
    help = "Показать или удалить записи аудита старше срока хранения"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Выполнить удаление. Без этого флага только показать количество.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            days=settings.AUDIT_LOG_RETENTION_DAYS
        )
        old_events = AuditEvent.objects.filter(occurred_at__lt=cutoff)
        count = old_events.count()

        if not options["apply"]:
            self.stdout.write(
                f"Старых записей: {count}. Удаление не выполнялось. "
                "Для удаления запустите команду с --apply."
            )
            return

        deleted_count, _ = old_events.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Удалено записей аудита: {deleted_count}")
        )