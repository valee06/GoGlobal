from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import curator_required
from accounts.models import StudentProfile, User

from . import services
from .forms import (AssignBuddyForm, ChecklistItemForm, ParticipationForm,
                    RouteForm, UniversityForm)
from .models import (BuddyAssignment, ChecklistItem, ExchangeParticipation,
                     ExchangeRoute, University)
from .permissions import can_edit_participation

from django.db.models import Prefetch
from .models import Stage

from django.db import IntegrityError, transaction
from django.contrib import messages

def _forbidden(request, message="Это действие вам недоступно."):
    return render(request, "auth/form.html", {
        "heading": "Недостаточно прав", "message": message,
    }, status=403)


# Вузы 

@curator_required
def university_list(request):
    universities = University.objects.filter(
        is_archived=False,
    ).order_by("name", "pk")

    return render(
        request,
        "exchange/universities.html",
        {"objects": universities},
    )


@curator_required
def university_create(request):
    if request.method == "POST":
        form = UniversityForm(request.POST)
        if form.is_valid():
            university = form.save()

            messages.success(
                request,
                f"Вуз «{university.name}» добавлен.",
            )

            return redirect("exchange:university_list")
    else:
        form = UniversityForm()
    return render(request, "auth/form.html", {
        "heading": "Новый вуз", "form": form, "button": "Сохранить",
    })


@curator_required
def university_edit(request, pk):
    university = get_object_or_404(University, pk=pk, is_archived=False)
    if request.method == "POST":
        form = UniversityForm(request.POST, instance=university)
        if form.is_valid():
            university = form.save()

            messages.success(
                request,
                f"Изменения вуза «{university.name}» сохранены.",
            )

            return redirect("exchange:university_list")
    else:
        form = UniversityForm(instance=university)
    return render(request, "auth/form.html", {
        "heading": "Редактировать вуз", "form": form, "button": "Сохранить",
    })


@require_POST
@curator_required
def university_archive(request, pk):
    """FR-33: delete-вьюхи не существует, только архив."""
    university = get_object_or_404(University, pk=pk)
    university.is_archived = True
    university.save(update_fields=["is_archived"])

    messages.success(
        request,
        f"Вуз «{university.name}» архивирован.",
    )

    return redirect("exchange:university_list")


# ---------- Маршруты (FR-30) ----------

@curator_required
def route_list(request):
    routes = (
        ExchangeRoute.objects
        .filter(is_archived=False)
        .select_related("from_university", "to_university")
        .order_by("name", "pk")
    )

    return render(
        request,
        "exchange/routes.html",
        {"objects": routes},
    )


@curator_required
def route_create(request):
    if request.method == "POST":
        form = RouteForm(request.POST)
        if form.is_valid():
            route = form.save()
            messages.success(
                request,
                f"Маршрут «{route.name}» добавлен.",
            )
            return redirect("exchange:route_list")
    else:
        form = RouteForm()
    return render(request, "auth/form.html", {
        "heading": "Новый маршрут", "form": form, "button": "Сохранить",
    })


@curator_required
def route_edit(request, pk):
    route = get_object_or_404(ExchangeRoute, pk=pk, is_archived=False)
    if request.method == "POST":
        form = RouteForm(request.POST, instance=route)
        if form.is_valid():
            route = form.save()
            messages.success(
                request,
                f"Изменения маршрута «{route.name}» сохранены.",
            )
            return redirect("exchange:route_list")
    else:
        form = RouteForm(instance=route)
    return render(request, "auth/form.html", {
        "heading": "Редактировать маршрут", "form": form, "button": "Сохранить",
    })


@require_POST
@curator_required
def route_archive(request, pk):
    route = get_object_or_404(
        ExchangeRoute,
        pk=pk,
        is_archived=False,
    )

    if route.participations.filter(is_completed=False).exists():
        return render(
            request,
            "exchange/route_archive_confirm.html",
            {
                "route": route,
                "has_active_participations": True,
            },
            status=409,
        )

    route.is_archived = True
    route.save(update_fields=["is_archived"])
    messages.success(
        request,
        f"Маршрут «{route.name}» архивирован.",
    )

    return redirect("exchange:route_list")


# Пункты чек-листа

@curator_required
def checklist_item_create(request, route_pk):
    route = get_object_or_404(
        ExchangeRoute,
        pk=route_pk,
        is_archived=False,
    )

    item = ChecklistItem(route=route)

    if request.method == "POST":
        form = ChecklistItemForm(request.POST, instance=item)

        if form.is_valid() and _save_checklist_item(form):
            messages.success(
                request,
                "Пункт чек-листа добавлен.",
            )
            return redirect("exchange:route_detail", pk=route.pk)
    else:
        form = ChecklistItemForm(instance=item)

    return render(
        request,
        "auth/form.html",
        {
            "heading": f"Новый пункт — {route.name}",
            "form": form,
            "button": "Добавить пункт",
            "checklist_route": route,
        },
    )


@curator_required
def checklist_item_edit(request, pk):
    item = get_object_or_404(
        ChecklistItem.objects.select_related("route"),
        pk=pk,
        is_archived=False,
        route__is_archived=False,
    )

    if request.method == "POST":
        form = ChecklistItemForm(request.POST, instance=item)

        if form.is_valid() and _save_checklist_item(form):
            messages.success(
                request,
                "Изменения пункта чек-листа сохранены.",
            )
            return redirect(
                "exchange:route_detail",
                pk=item.route_id,
            )
    else:
        form = ChecklistItemForm(instance=item)

    return render(
        request,
        "auth/form.html",
        {
            "heading": "Редактировать пункт чек-листа",
            "form": form,
            "button": "Сохранить",
            "checklist_route": item.route,
        },
    )


@require_POST
@curator_required
def checklist_item_archive(request, pk):
    item = get_object_or_404(
        ChecklistItem,
        pk=pk,
        is_archived=False,
        route__is_archived=False,
    )

    item.is_archived = True
    item.save(update_fields=["is_archived"])
    messages.success(
        request,
        "Пункт чек-листа архивирован.",
    )

    return redirect(
        "exchange:route_detail",
        pk=item.route_id,
    )


# Студенты куратора и участие 

@curator_required
def student_list(request):
    active_participations = (
        ExchangeParticipation.objects
        .filter(is_completed=False)
        .select_related("route")
    )

    profiles = (
        request.user.students
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "user__participations",
                queryset=active_participations,
                to_attr="active_participations",
            )
        )
        .order_by("user__email")
    )

    return render(
        request,
        "exchange/students.html",
        {"profiles": profiles},
    )


@curator_required
def participation_create(request, student_id):
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    # FR-29: участие создаётся только для СВОЕГО студента
    if profile.curator_id != request.user.id:
        return _forbidden(request, "Этот студент закреплён за другим куратором.")
    if request.method == "POST":
        form = ParticipationForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.student = student      # закрытые поля назначает сервер
            p.curator = request.user  
            p.save()
            return redirect("exchange:student_list")
    else:
        form = ParticipationForm()
    return render(request, "auth/form.html", {
        "heading": f"Новое участие — {student.email}",
        "form": form, "button": "Создать",
    })


@curator_required
def participation_edit(request, pk):
    p = get_object_or_404(ExchangeParticipation, pk=pk)
    if not can_edit_participation(request.user, p):
        return _forbidden(request)
    if request.method == "POST":
        form = ParticipationForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            return redirect("exchange:student_list")
    else:
        form = ParticipationForm(instance=p)
    return render(request, "auth/form.html", {
        "heading": f"Участие — {p.student.email}", "form": form, "button": "Сохранить",
    })


@require_POST
@curator_required
def participation_advance_stage(request, pk):
    p = get_object_or_404(ExchangeParticipation, pk=pk)
    try:
        services.advance_stage(request.user, p)
    except services.PermissionDenied_:
        return _forbidden(request)
    except ValueError as e:
        return _forbidden(request, str(e))
    return redirect("exchange:student_list")


@require_POST
@curator_required
def participation_complete(request, pk):
    p = get_object_or_404(ExchangeParticipation, pk=pk)
    try:
        services.complete_exchange(request.user, p)
    except services.PermissionDenied_:
        return _forbidden(request)
    return redirect("exchange:student_list")


# Назначение buddy

@curator_required
def assign_buddy_view(request, pk):
    """Единственный легальный путь назначить buddy — через сервис."""
    p = get_object_or_404(ExchangeParticipation, pk=pk)
    if not can_edit_participation(request.user, p):
        return _forbidden(request)
    if request.method == "POST":
        form = AssignBuddyForm(request.POST)
        if form.is_valid():
            try:
                services.assign_buddy(request.user, p, form.cleaned_data["buddy"])
            except (services.PermissionDenied_, ValueError) as e:
                return _forbidden(request, str(e))
            return redirect("exchange:student_list")
    else:
        form = AssignBuddyForm()
    return render(request, "auth/form.html", {
        "heading": f"Назначить buddy — {p.student.email}",
        "form": form, "button": "Назначить",
    })


@require_POST
@curator_required
def end_assignment_view(request, pk):
    assignment = get_object_or_404(BuddyAssignment, pk=pk, ended_at__isnull=True)
    try:
        services.end_assignment(request.user, assignment)
    except services.PermissionDenied_:
        return _forbidden(request)
    return redirect("exchange:student_list")

@curator_required
def university_archive_confirm(request, pk):
    university = get_object_or_404(
        University,
        pk=pk,
        is_archived=False,
    )

    return render(
        request,
        "exchange/university_archive_confirm.html",
        {"university": university},
    )

@curator_required
def participation_advance_confirm(request, pk):
    participation = get_object_or_404(
        ExchangeParticipation.objects.select_related(
            "student",
            "route",
        ),
        pk=pk,
    )

    if not can_edit_participation(request.user, participation):
        return _forbidden(request)

    if participation.current_stage >= Stage.RETURN:
        return render(
            request,
            "auth/form.html",
            {
                "heading": "Последний этап обмена",
                "message": (
                    "Студент уже находится на этапе возвращения. "
                    "Следующего этапа нет."
                ),
            },
        )

    next_stage = Stage(participation.current_stage + 1)

    return render(
        request,
        "exchange/participation_advance_confirm.html",
        {
            "participation": participation,
            "next_stage_label": next_stage.label,
        },
    )


@curator_required
def route_detail(request, pk):
    route = get_object_or_404(
        ExchangeRoute.objects.select_related(
            "from_university",
            "to_university",
        ),
        pk=pk,
        is_archived=False,
    )

    items = route.checklist_items.filter(
        is_archived=False,
    ).order_by("stage", "display_order", "pk")

    return render(
        request,
        "exchange/route_detail.html",
        {
            "route": route,
            "items": items,
        },
    )


def _save_checklist_item(form):
    try:
        with transaction.atomic():
            form.save()
    except IntegrityError as exc:
        constraint_name = getattr(
            getattr(exc.__cause__, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name != "unique_item_order_per_stage":
            raise

        form.add_error(
            "display_order",
            "Этот номер уже занят на выбранном этапе. "
            "Укажите другой.",
        )
        return False

    return True


@curator_required
def checklist_item_archive_confirm(request, pk):
    item = get_object_or_404(
        ChecklistItem.objects.select_related("route"),
        pk=pk,
        is_archived=False,
        route__is_archived=False,
    )

    return render(
        request,
        "exchange/checklist_item_archive_confirm.html",
        {"item": item},
    )


@curator_required
def route_archive_confirm(request, pk):
    route = get_object_or_404(
        ExchangeRoute,
        pk=pk,
        is_archived=False,
    )

    has_active_participations = route.participations.filter(
        is_completed=False,
    ).exists()

    return render(
        request,
        "exchange/route_archive_confirm.html",
        {
            "route": route,
            "has_active_participations": has_active_participations,
        },
    )