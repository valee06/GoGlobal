from django.shortcuts import redirect, render

from .forms import StaffRegistrationForm


def register_staff(request):
    if request.method == "POST":
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("auth:pending")  # без автоматического входа!
    else:
        form = StaffRegistrationForm()
    return render(request, "auth/register_staff.html", {"form": form})


def pending(request):
    return render(request, "auth/pending.html")