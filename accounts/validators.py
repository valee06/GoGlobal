import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordPolicyValidator:
    def validate(self, password, user=None):
        special = settings.PASSWORD_POLICY["special_chars"]
        errors = []

        if len(re.findall(r"[A-Za-z]", password)) < 8:
            errors.append(
                _("Добавьте не менее 8 латинских букв.")
            )

        if re.search(
            r"[^A-Za-z0-9" + re.escape(special) + r"]",
            password,
        ):
            errors.append(
                _(
                    "Разрешены только латинские буквы, цифры "
                    "и спецзнаки %(special)s."
                ) % {"special": special}
            )

        if not re.search(r"[0-9]", password):
            errors.append(
                _("Добавьте хотя бы одну цифру.")
            )

        if not re.search(
            r"[" + re.escape(special) + r"]",
            password,
        ):
            errors.append(
                _("Добавьте хотя бы один спецзнак: %(special)s.")
                % {"special": special}
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            _(
                "Не менее 8 латинских букв, хотя бы одна цифра "
                "и один спецзнак из %(special)s. "
                "Кириллица запрещена."
            )
            % {
                "special": settings.PASSWORD_POLICY["special_chars"],
            }
        )