from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class University(models.Model):
    """Вуз (отправляющий/принимающий). Часовой пояс нужен для правил ввода сроков."""
    name = models.CharField(max_length=255, unique=True)
    city = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Moscow")
    is_archived = models.BooleanField(default=False)  # удаления нет, только архив

    def __str__(self):
        return self.name


class ExchangeRoute(models.Model):
    """Маршрут обмена между двумя вузами. Владелец чек-листа."""
    name = models.CharField(max_length=255)
    from_university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="routes_from")
    to_university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="routes_to")
    is_archived = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_university=models.F("to_university")),
                name="route_universities_differ",
            ),
        ]

    def __str__(self):
        return self.name


class Stage(models.IntegerChoices):
    """Этапы обмена."""
    PREPARATION = 1, "Подготовка"
    STAY = 2, "Пребывание"
    RETURN = 3, "Возвращение"


class ChecklistItem(models.Model):
    """Общий пункт чек-листа маршрута, привязан к этапу."""
    route = models.ForeignKey(
        ExchangeRoute, on_delete=models.CASCADE, related_name="checklist_items")
    stage = models.PositiveSmallIntegerField(choices=Stage.choices)
    title = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["stage", "display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "stage", "display_order"],
                name="unique_item_order_per_stage",
            ),
        ]

    def __str__(self):
        return self.title


class ExchangeParticipation(models.Model):
    """Участие студента в обмене: маршрут + текущий этап.

    buddy здесь нет нарочно: назначение — только через BuddyAssignment
    и сервис assign_buddy(), не через редактирование участия.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="participations")
    curator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="curated_participations")
    route = models.ForeignKey(
        ExchangeRoute, on_delete=models.PROTECT, related_name="participations")
    current_stage = models.PositiveSmallIntegerField(
        choices=Stage.choices, default=Stage.PREPARATION)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # один активный обмен на студента
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_completed=False),
                name="one_active_participation_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student.email} — {self.route.name}"


class BuddyAssignment(models.Model):
    """Назначение buddy на участие.

    История неизменна: завершение = выставить ended_at, не удалять.
    """
    participation = models.ForeignKey(
        ExchangeParticipation, on_delete=models.CASCADE,
        related_name="buddy_assignments")
    buddy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="made_assignments")
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # не более одного активного назначения на участие
            models.UniqueConstraint(
                fields=["participation"],
                condition=Q(ended_at__isnull=True),
                name="one_active_buddy_per_participation",
            ),
        ]