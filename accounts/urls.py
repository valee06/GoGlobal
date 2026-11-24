from django.urls import path

from . import views

app_name = "auth"

urlpatterns = [
    path("register/staff/", views.register_staff, name="register_staff"),
    path("pending/", views.pending, name="pending"),
]