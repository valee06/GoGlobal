from django import forms

from .models import ChecklistItem, ExchangeParticipation, ExchangeRoute, University

from accounts.models import User


class UniversityForm(forms.ModelForm):
    class Meta:
        model = University
        fields = ["name", "city", "country", "timezone"]  # is_archived закрыт


class RouteForm(forms.ModelForm):
    class Meta:
        model = ExchangeRoute
        fields = ["name", "from_university", "to_university"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("from_university") and \
           cleaned.get("from_university") == cleaned.get("to_university"):
            self.add_error("to_university", "Вузы маршрута должны различаться")
        return cleaned


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["title", "stage", "display_order"]  # route и is_archived закрыты


class ParticipationForm(forms.ModelForm):
    """FR-29. В полях НЕТ buddy — прямое назначение запрещено."""

    class Meta:
        model = ExchangeParticipation
        fields = ["route", "current_stage"]  # student, curator закрыты


class AssignBuddyForm(forms.Form):
    buddy = forms.ModelChoiceField(
        queryset=User.objects.filter(
            role=User.Role.BUDDY, is_approved=True, is_active=True),
        label="Buddy",
        empty_label="— выберите buddy —",
    )