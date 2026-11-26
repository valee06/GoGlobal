def auth_ui(request):
    language = getattr(request, "ui_language", "ru")

    return {
        "ui_language": language,
        "english": language == "en",
    }