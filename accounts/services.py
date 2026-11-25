from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.conf import settings


def kill_user_sessions(user):
    """Отзыв всех серверных сессий пользователя."""
    for s in Session.objects.all():
        if str(s.get_decoded().get("_auth_user_id")) == str(user.pk):
            s.delete()


def _key(email):
    return f"loginfail:{email.strip().lower()}"


def login_locked(email):
    return bool(cache.get(f"loginlock:{email.strip().lower()}"))


def register_login_failure(email):
    """10 неудач подряд -> пауза LOGIN_LOCK_MINUTES."""
    fails = (cache.get(_key(email)) or 0) + 1
    if fails >= settings.LOGIN_MAX_ATTEMPTS:
        cache.set(f"loginlock:{email.strip().lower()}", True,
                  timeout=settings.LOGIN_LOCK_MINUTES * 60)
        cache.delete(_key(email))
    else:
        cache.set(_key(email), fails, timeout=3600)


def reset_login_failures(email):
    cache.delete(_key(email))