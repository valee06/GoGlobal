from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Invitation, User


class Command(BaseCommand):
    help = "Выдать код приглашения студента от имени куратора"

    def add_arguments(self, parser):
        parser.add_argument("curator_email")
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        try:
            curator = User.objects.get(email__iexact=opts["curator_email"])
        except User.DoesNotExist:
            raise CommandError("Куратор не найден")
        if curator.role != User.Role.CURATOR or not curator.is_approved:
            raise CommandError("Только одобренный куратор выдаёт приглашения")
        inv = Invitation.objects.create(
            code=Invitation.generate_code(), curator=curator,
            expires_at=timezone.now() + timezone.timedelta(days=opts["days"]),
        )
        self.stdout.write(self.style.SUCCESS(f"Код приглашения: {inv.code}"))