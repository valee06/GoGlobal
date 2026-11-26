import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "config.middleware.RequestEventIdMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "goglobal"),
        "USER": os.getenv("POSTGRES_USER", "goglobal"),
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

AUTH_USER_MODEL = "accounts.User"



CONSENT_VERSION = "v0"  # текст согласия

PASSWORD_POLICY = {
    "min_length": 8,
    "require_digit": True,
    "require_special": True,
    "special_chars": "!@#$%^&*-_+",
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "accounts.validators.PasswordPolicyValidator"},
]

# Локально письма выводятся в консоль. Для SMTP используйте переменные окружения.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "noreply@goglobal.local",
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        "Выберите только один вариант: EMAIL_USE_TLS или EMAIL_USE_SSL."
    )

if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    if not EMAIL_HOST:
        raise ImproperlyConfigured("Для SMTP нужно задать EMAIL_HOST.")

    if not DEBUG and not (EMAIL_USE_TLS or EMAIL_USE_SSL):
        raise ImproperlyConfigured(
            "Вне режима отладки SMTP должен использовать TLS или SSL."
        )

if not 1 <= EMAIL_PORT <= 65535:
    raise ImproperlyConfigured("EMAIL_PORT должен быть от 1 до 65535.")

if EMAIL_TIMEOUT <= 0:
    raise ImproperlyConfigured("EMAIL_TIMEOUT должен быть больше нуля.")

try:
    validate_email(DEFAULT_FROM_EMAIL)
except ValidationError as exc:
    raise ImproperlyConfigured(
        "DEFAULT_FROM_EMAIL должен содержать корректный email."
    ) from exc

if (
    EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    and not DEBUG
    and (not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD)
):
    raise ImproperlyConfigured(
        "Для SMTP вне режима отладки нужны логин и пароль."
    )

# Параметры кодов и лимитов
EMAIL_CODE_TTL_MINUTES = 10        # код подтверждения
RESET_CODE_TTL_MINUTES = 12        # код восстановления
CODE_MAX_ATTEMPTS = 3
LOGIN_MAX_ATTEMPTS = 10            # подряд
LOGIN_LOCK_MINUTES = 3             # пауза после 10 подряд

LOGIN_URL = "/auth/login/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "safe": {
            "()": "config.logging_utils.SafeLogFilter",
        },
    },
    "formatters": {
        "safe": {
            "format": (
                "%(asctime)s %(levelname)s %(name)s "
                "event_id=%(event_id)s %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["safe"],
            "formatter": "safe",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

AUDIT_LOG_RETENTION_DAYS = int(
    os.getenv("AUDIT_LOG_RETENTION_DAYS", "365")
)

if not 1 <= AUDIT_LOG_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "AUDIT_LOG_RETENTION_DAYS должен быть от 1 до 3650."
    )