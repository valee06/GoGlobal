from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "Одобрить или деактивировать регистрацию curator/buddy"

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--by", required=True, help="Кто выполняет")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--approve", action="store_true")
        group.add_argument("--deactivate", action="store_true")

    def handle(self, *args, **opts):
        try:
            user = User.objects.get(email__iexact=opts["email"])
        except User.DoesNotExist:
            raise CommandError("Пользователь не найден")

        if user.role == User.Role.STUDENT:
            raise CommandError("Студенты не проходят ручное одобрение")

        if opts["approve"]:
            if not user.email_verified:
                self.stderr.write("Внимание: email ещё не подтверждён")
            user.is_approved = True
            user.approved_by = opts["by"]
            user.approved_at = timezone.now()
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Одобрен: {user.email} ({user.role})"))
        else:
            user.is_approved = False
            user.is_active = False
            user.approved_by = opts["by"]
            user.approved_at = timezone.now()
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Деактивирован: {user.email}"))