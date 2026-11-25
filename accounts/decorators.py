"""Декораторы контроля доступа, общие для всех приложений проекта."""

import functools

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import User


def curator_required(view):
    """Только одобренный куратор."""
    @login_required
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        u = request.user
        if u.role != User.Role.CURATOR or not u.is_approved:
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapper