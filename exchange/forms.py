from django import forms

from .models import ChecklistItem, ExchangeParticipation, ExchangeRoute, University

from accounts.models import User


class UniversityForm(forms.ModelForm):
    class Meta:
        model = University
        fields = ["name", "city", "country", "timezone"]

        labels = {
            "name": "Название вуза",
            "city": "Город",
            "country": "Страна",
            "timezone": "Часовой пояс",
        }

        help_texts = {
            "timezone": (
                "Укажите часовой пояс в формате Europe/Moscow "
                "или Asia/Shanghai."
            ),
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Например, Учебный университет А",
            }),
            "city": forms.TextInput(attrs={
                "placeholder": "Например, Москва",
            }),
            "country": forms.TextInput(attrs={
                "placeholder": "Например, Россия",
            }),
            "timezone": forms.TextInput(attrs={
                "placeholder": "Europe/Moscow",
            }),
        }

        error_messages = {
            "name": {
                "required": "Введите название вуза.",
                "unique": "Вуз с таким названием уже существует.",
            },
            "timezone": {
                "required": "Укажите часовой пояс.",
            },
        }

    def clean_timezone(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        value = self.cleaned_data["timezone"].strip()

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError(
                "Неизвестный часовой пояс. "
                "Например: Europe/Moscow или Asia/Shanghai."
            )

        return value


class RouteForm(forms.ModelForm):
    class Meta:
        model = ExchangeRoute
        fields = ["name", "from_university", "to_university"]

        labels = {
            "name": "Название маршрута",
            "from_university": "Отправляющий вуз",
            "to_university": "Принимающий вуз",
        }

        help_texts = {
            "from_university": "Вуз, из которого отправляется студент.",
            "to_university": "Вуз, в котором студент будет учиться по обмену.",
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Например, Москва — Касабланка",
            }),
        }

        error_messages = {
            "name": {
                "required": "Введите название маршрута.",
            },
            "from_university": {
                "required": "Выберите отправляющий вуз.",
                "invalid_choice": "Этот вуз недоступен. Выберите другой.",
            },
            "to_university": {
                "required": "Выберите принимающий вуз.",
                "invalid_choice": "Этот вуз недоступен. Выберите другой.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        universities = University.objects.filter(
            is_archived=False,
        ).order_by("name", "pk")

        for field_name in ("from_university", "to_university"):
            self.fields[field_name].queryset = universities
            self.fields[field_name].empty_label = "Выберите вуз"

    def clean(self):
        cleaned = super().clean()

        from_university = cleaned.get("from_university")
        to_university = cleaned.get("to_university")

        if (
            from_university is not None
            and to_university is not None
            and from_university == to_university
        ):
            self.add_error(
                "to_university",
                "Отправляющий и принимающий вузы должны различаться.",
            )

        return cleaned


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["title", "stage", "display_order"]

        labels = {
            "title": "Название пункта",
            "stage": "Этап обмена",
            "display_order": "Порядковый номер",
        }

        help_texts = {
            "title": "Например, проверить срок действия паспорта.",
            "stage": "Выберите этап, к которому относится пункт.",
            "display_order": (
                "Число от 0. Меньший номер отображается раньше. "
                "Внутри одного этапа номера не должны повторяться."
            ),
        }

        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Что необходимо сделать студенту?",
            }),
            "display_order": forms.NumberInput(attrs={
                "min": 0,
                "step": 1,
            }),
        }

        error_messages = {
            "title": {
                "required": "Введите название пункта.",
            },
            "stage": {
                "required": "Выберите этап обмена.",
                "invalid_choice": "Выберите этап из списка.",
            },
            "display_order": {
                "required": "Укажите порядковый номер.",
                "invalid": "Введите целое число.",
                "min_value": "Номер не может быть отрицательным.",
            },
        }

    def clean(self):
        cleaned = super().clean()

        stage = cleaned.get("stage")
        display_order = cleaned.get("display_order")
        route_id = self.instance.route_id

        if (
            route_id is not None
            and stage is not None
            and display_order is not None
        ):
            duplicates = ChecklistItem.objects.filter(
                route_id=route_id,
                stage=stage,
                display_order=display_order,
            )

            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)

            if duplicates.exists():
                self.add_error(
                    "display_order",
                    "Этот номер уже занят на выбранном этапе. "
                    "Укажите другой.",
                )

        return cleaned


class ParticipationForm(forms.ModelForm):
    """Маршрут и этап участия; студент и куратор задаются сервером."""

    class Meta:
        model = ExchangeParticipation
        fields = ["route", "current_stage"]

        labels = {
            "route": "Маршрут обмена",
            "current_stage": "Этап обмена",
        }

        help_texts = {
            "route": (
                "Выберите маршрут между отправляющим "
                "и принимающим вузами."
            ),
            "current_stage": (
                "Подготовка — до поездки; пребывание — во время "
                "обмена; возвращение — после поездки."
            ),
        }

        error_messages = {
            "route": {
                "required": "Выберите маршрут обмена.",
                "invalid_choice": (
                    "Этот маршрут недоступен. Выберите другой."
                ),
            },
            "current_stage": {
                "required": "Выберите этап обмена.",
                "invalid_choice": "Выберите этап из списка.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["route"].queryset = (
            ExchangeRoute.objects
            .filter(
                is_archived=False,
                from_university__is_archived=False,
                to_university__is_archived=False,
            )
            .order_by("name", "pk")
        )

        self.fields["route"].empty_label = "Выберите маршрут"
        if self.instance.pk:
            self.fields["current_stage"].disabled = True
            self.fields["current_stage"].help_text = (
                "Для перехода используйте кнопку "
                "«На следующий этап» в карточке студента."
            )


class AssignBuddyForm(forms.Form):
    buddy = forms.ModelChoiceField(
        queryset=User.objects.filter(
            role=User.Role.BUDDY, is_approved=True, is_active=True),
        label="Buddy",
        empty_label="— выберите buddy —",
    )