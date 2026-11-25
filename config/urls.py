from django.contrib import admin
from django.urls import include, path
from accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("accounts.urls")),
    path("", account_views.home, name="home"),
    path("profile/student/", account_views.profile_student, name="profile_student"),
]