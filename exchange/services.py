from django.db import transaction
from django.utils import timezone

from .models import BuddyAssignment, ExchangeParticipation, Stage
from .permissions import can_edit_participation, is_active_buddy


class PermissionDenied_(Exception):
    pass


def advance_stage(user, participation):
    """Перевод этапа 1→2→3, только вперёд."""
    if not can_edit_participation(user, participation):
        raise PermissionDenied_("Нет права менять это участие")
    if participation.current_stage >= Stage.RETURN:
        raise ValueError("Участие уже на последнем этапе")
    with transaction.atomic():
        participation.current_stage += 1
        participation.save(update_fields=["current_stage"])
        # TODO (карточка задач): заархивировать задачи прежнего этапа (FR-33)
    return participation


def complete_exchange(user, participation):
    """Завершение обмена. обезличивание — отдельная карточка."""
    if not can_edit_participation(user, participation):
        raise PermissionDenied_("Нет права завершать это участие")
    with transaction.atomic():
        participation.is_completed = True
        participation.completed_at = timezone.now()
        participation.save(update_fields=["is_completed", "completed_at"])
        active = participation.buddy_assignments.filter(ended_at__isnull=True)
        active.update(ended_at=timezone.now())  # назначение buddy закрывается
    return participation


def assign_buddy(user, participation, buddy):
    """единственный легальный путь назначить buddy.

    Прямое назначение через форму участия запрещено — только здесь.
    """
    if not can_edit_participation(user, participation):
        raise PermissionDenied_("Только закреплённый куратор назначает buddy")
    if not is_active_buddy(buddy):
        raise ValueError("Buddy должен быть одобренным активным пользователем с ролью buddy")
    with transaction.atomic():
        now = timezone.now()
        participation.buddy_assignments.filter(ended_at__isnull=True).update(ended_at=now)
        return BuddyAssignment.objects.create(
            participation=participation, buddy=buddy,
            assigned_by=user, assigned_at=now,
        )


def end_assignment(user, assignment):
    """завершение назначения с сохранением истории."""
    if not can_edit_participation(user, assignment.participation):
        raise PermissionDenied_("Нет права завершать это назначение")
    assignment.ended_at = timezone.now()
    assignment.save(update_fields=["ended_at"])
    return assignment