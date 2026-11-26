from django.urls import path

from . import views

app_name = "auth"

urlpatterns = [
        path(
        "choose/<str:mode>/",
        views.entry_page,
        name="choose_role",
    ),
    path("register/staff/", views.register_staff, name="register_staff"),
    path("register/student/", views.register_student, name="register_student"),
    path("email/verify/", views.verify_email, name="verify_email"),
    path("email/resend/", views.resend_code, name="resend_code"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password/reset/request/", views.reset_request, name="reset_request"),
    path("password/reset/verify/", views.reset_verify, name="reset_verify",),
    path("password/reset/confirm/", views.reset_confirm, name="reset_confirm"),
    path("pending/", views.pending, name="pending"),
    path("invitations/", views.invitations, name="invitations"),
    path( "personal-data-consent/", views.personal_data_consent, name="personal_data_consent",),
]