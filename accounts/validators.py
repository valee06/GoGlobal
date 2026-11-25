import re

from django.core.exceptions import ValidationError
from django.conf import settings


class PasswordPolicyValidator:
    """>=8 символов, только латиница/цифры/спецзнаки,
    минимум 1 цифра и 1 спецзнак из согласованного набора."""

    def validate(self, password, user=None):
        policy = settings.PASSWORD_POLICY
        special = policy["special_chars"]
        errors = []

        if len(password) < policy["min_length"]:
            errors.append(f"Пароль должен быть не короче {policy['min_length']} символов.")
        if re.search(r"[^A-Za-z0-9" + re.escape(special) + "]", password):
            errors.append("Разрешены только латинские буквы, цифры и спецзнаки " + special)
        if policy["require_digit"] and not re.search(r"\d", password):
            errors.append("Добавьте хотя бы одну цифру.")
        if policy["require_special"] and not re.search("[" + re.escape(special) + "]", password):
            errors.append("Добавьте хотя бы один спецзнак: " + special)

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        p = settings.PASSWORD_POLICY
        return (f"Минимум {p['min_length']} символов: латинские буквы, "
                f"хотя бы одна цифра и спецзнак из {p['special_chars']}.")