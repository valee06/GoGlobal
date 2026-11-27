import math
import secrets
from datetime import timedelta
from secrets import compare_digest

from django.db import transaction
from django.utils import timezone

from .emails import send_code_email_or_raise
from .models import OneTimeCode, User


class CodeRateLimit(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(str(seconds))


def wait_before_resend(user, purpose):
    now = timezone.now()
    codes = OneTimeCode.objects.filter(
        user=user,
        purpose=purpose,
    )
    latest = codes.order_by("-created_at", "-pk").first()
    deadlines = [now]

    if latest:
        deadlines.append(
            latest.created_at + timedelta(seconds=60)
        )

        if latest.attempts >= 3 and latest.used_at:
            deadlines.append(
                latest.used_at + timedelta(minutes=3)
            )

    recent_dates = list(
        codes.filter(
            created_at__gt=now - timedelta(minutes=30)
        )
        .order_by("-created_at", "-pk")
        .values_list("created_at", flat=True)[:5]
    )

    if len(recent_dates) == 5:
        deadlines.append(
            recent_dates[-1] + timedelta(minutes=30)
        )

    return max(
        0,
        math.ceil(
            (max(deadlines) - now).total_seconds()
        ),
    )


def send_code_limited(user, purpose, ttl_minutes):
    with transaction.atomic():
        locked_user = (
            User.objects.select_for_update()
            .get(pk=user.pk)
        )

        if (
            purpose == OneTimeCode.Purpose.EMAIL_VERIFY
            and locked_user.email_verified
        ):
            return None

        seconds = wait_before_resend(locked_user, purpose)

        if seconds:
            raise CodeRateLimit(seconds)

        previous_values = set(
            OneTimeCode.objects.filter(
                user=locked_user,
                purpose=purpose,
                expires_at__gt=timezone.now(),
            ).values_list("code", flat=True)
        )

        code = OneTimeCode.generate(
            locked_user,
            purpose,
            ttl_minutes,
        )

        while code.code in previous_values:
            code.code = str(
                secrets.randbelow(900000) + 100000
            )

        code.save(update_fields=["code"])

        send_code_email_or_raise(
            locked_user.email,
            code.code,
            purpose,
        )

        return code


def check_code(user, purpose, candidate):
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)

        code = (
            OneTimeCode.objects.filter(
                user=user,
                purpose=purpose,
            )
            .order_by("-created_at", "-pk")
            .first()
        )

        if code is None or not code.is_usable():
            return None

        matches = compare_digest(
            code.code.encode("utf-8"),
            candidate.encode("utf-8"),
        )

        if not matches:
            code.attempts += 1

            if code.attempts >= 3:
                code.used_at = timezone.now()

            code.save(
                update_fields=["attempts", "used_at"]
            )
            return None

        code.used_at = timezone.now()
        code.save(update_fields=["used_at"])

        return code