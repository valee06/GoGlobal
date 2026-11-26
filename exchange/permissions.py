from accounts.models import User


def is_active_curator(user):
    return (user.is_authenticated and user.is_active
            and user.role == User.Role.CURATOR and user.is_approved)


def is_active_buddy(user):
    return (user.is_authenticated and user.is_active
            and user.role == User.Role.BUDDY and user.is_approved)


# объектный уровень 

def can_manage_catalog(user):
    """Вузы, маршруты, пункты чек-листа — только одобренный куратор (FR-30, FR-31)."""
    return is_active_curator(user)


def can_view_participation(user, p):
    if not (user.is_authenticated and user.is_active and user.is_approved):
        return False
    if user.role == User.Role.STUDENT:
        return p.student_id == user.id            # студент — только своё
    if user.role == User.Role.CURATOR:
        return p.curator_id == user.id            # куратор — только своих студентов
    if user.role == User.Role.BUDDY:
        return p.buddy_assignments.filter(        # buddy — только действующие подопечные
            buddy=user, ended_at__isnull=True).exists()
    return False


def can_edit_participation(user, p):
    """маршрут и этап меняет только закреплённый куратор и только в активном обмене."""
    return is_active_curator(user) and p.curator_id == user.id and not p.is_completed


# полевой уровень 

PARTICIPATION_EDITABLE_FIELDS = {"route", "current_stage"}
# Закрытые поля: student, curator задаются при создании; buddy — НИКОГДА,
# назначение идёт только через BuddyAssignment (запрет прямого назначения).

CHECKLIST_ITEM_EDITABLE_FIELDS = {"title", "stage", "display_order"}
# route после создания закрыт: перенос пункта = архив + новый пункт.