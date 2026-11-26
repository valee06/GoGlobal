from django.urls import path

from . import views

app_name = "exchange"

urlpatterns = [
    # Вузы
    path("universities/", views.university_list, name="university_list"),
    path("universities/create/", views.university_create, name="university_create"),
    path("universities/<int:pk>/edit/", views.university_edit, name="university_edit"),
    path("universities/<int:pk>/archive/", views.university_archive, name="university_archive"),

    # Маршруты 
    path("routes/", views.route_list, name="route_list"),
    path("routes/create/", views.route_create, name="route_create"),
    path("routes/<int:pk>/edit/", views.route_edit, name="route_edit"),
    path("routes/<int:pk>/archive/", views.route_archive, name="route_archive"),

    # Пункты чек-листа 
    path("routes/<int:route_pk>/items/create/", views.checklist_item_create, name="item_create"),
    path("items/<int:pk>/edit/", views.checklist_item_edit, name="item_edit"),
    path("items/<int:pk>/archive/", views.checklist_item_archive, name="item_archive"),

    # Студенты куратора и участие 
    path("students/", views.student_list, name="student_list"),
    path("students/<int:student_id>/participation/create/", views.participation_create, name="participation_create"),
    path("participations/<int:pk>/edit/", views.participation_edit, name="participation_edit"),
    path("participations/<int:pk>/advance/", views.participation_advance_stage, name="participation_advance"),
    path("participations/<int:pk>/complete/", views.participation_complete, name="participation_complete"),

    # Назначение buddy 
    path("participations/<int:pk>/assign-buddy/", views.assign_buddy_view, name="assign_buddy"),
    path("assignments/<int:pk>/end/", views.end_assignment_view, name="end_assignment"),
]