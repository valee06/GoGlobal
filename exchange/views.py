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


def _forbidden(request, message="Это действие вам недоступно."):
    return render(request, "auth/form.html", {
        "heading": "Недостаточно прав", "message": message,
    }, status=403)


# Вузы 

@curator_required
def university_list(request):
    return render(request, "exchange/list.html", {
        "heading": "Вузы",
        "objects": University.objects.filter(is_archived=False),
        "create_url": "exchange:university_create",
    })


@curator_required
def university_create(request):
    if request.method == "POST":
        form = UniversityForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
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
    return redirect("exchange:university_list")


# ---------- Маршруты (FR-30) ----------

@curator_required
def route_list(request):
    return render(request, "exchange/list.html", {
        "heading": "Маршруты обмена",
        "objects": ExchangeRoute.objects.filter(is_archived=False),
        "create_url": "exchange:route_create",
    })


@curator_required
def route_create(request):
    if request.method == "POST":
        form = RouteForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
            return redirect("exchange:route_list")
    else:
        form = RouteForm(instance=route)
    return render(request, "auth/form.html", {
        "heading": "Редактировать маршрут", "form": form, "button": "Сохранить",
    })


@require_POST
@curator_required
def route_archive(request, pk):
    route = get_object_or_404(ExchangeRoute, pk=pk)
    route.is_archived = True
    route.save(update_fields=["is_archived"])
    return redirect("exchange:route_list")


# Пункты чек-листа

@curator_required
def checklist_item_create(request, route_pk):
    route = get_object_or_404(ExchangeRoute, pk=route_pk, is_archived=False)
    if request.method == "POST":
        form = ChecklistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.route = route  # закрытое поле назначает сервер
            item.save()
            return redirect("exchange:route_list")
    else:
        form = ChecklistItemForm()
    return render(request, "auth/form.html", {
        "heading": f"Новый пункт чек-листа — {route.name}",
        "form": form, "button": "Сохранить",
    })


@curator_required
def checklist_item_edit(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk, is_archived=False)
    if request.method == "POST":
        form = ChecklistItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("exchange:route_list")
    else:
        form = ChecklistItemForm(instance=item)
    return render(request, "auth/form.html", {
        "heading": "Редактировать пункт", "form": form, "button": "Сохранить",
    })


@require_POST
@curator_required
def checklist_item_archive(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk)
    item.is_archived = True
    item.save(update_fields=["is_archived"])
    return redirect("exchange:route_list")


# Студенты куратора и участие 

@curator_required
def student_list(request):
    """Мои студенты — те, кто зарегистрировался по моим кодам приглашений."""
    profiles = request.user.students.select_related("user")
    return render(request, "exchange/students.html", {
        "heading": "Мои студенты", "profiles": profiles,
    })


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