from django.utils import translation
from django.utils.cache import patch_vary_headers


class AuthLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.session.get("auth_ui_language", "ru")

        requested_language = request.GET.get("lang")
        if requested_language in ("ru", "en"):
            language = requested_language

        # При выборе buddy включаем английский.
        if request.GET.get("role") == "buddy":
            language = "en"

        # После входа используем фактическую роль аккаунта.
        if (
            request.user.is_authenticated
            and request.user.role == "buddy"
        ):
            language = "en"

        if language not in ("ru", "en"):
            language = "ru"

        if request.session.get("auth_ui_language") != language:
            request.session["auth_ui_language"] = language

        request.ui_language = language
        request.LANGUAGE_CODE = language

        with translation.override(language):
            response = self.get_response(request)

        response.headers["Content-Language"] = language
        patch_vary_headers(response, ("Cookie",))

        return response