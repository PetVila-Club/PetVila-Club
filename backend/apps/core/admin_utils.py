"""Utilitários do painel: ações com formulário intermediário e tratamento uniforme de erros de regra."""

from __future__ import annotations

from typing import Callable

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.template.response import TemplateResponse

from .exceptions import DomainError
from .services import PermissionDeniedError


def run_each(modeladmin, request, queryset, handler: Callable, success: str) -> None:
    ok = 0
    for obj in queryset:
        try:
            handler(obj)
            ok += 1
        except (DomainError, PermissionDeniedError) as exc:
            modeladmin.message_user(request, f"{obj}: {getattr(exc, 'message', str(exc))}", messages.ERROR)
    if ok:
        modeladmin.message_user(request, f"{success} ({ok}).", messages.SUCCESS)


def form_action(*, form_class: type[forms.Form], title: str, description: str = "", success: str = "Concluído"):
    """
    Decorador para ações que pedem dados (justificativa, contagem, rastreio...).
    A função decorada recebe (modeladmin, request, obj, cleaned_data).
    """

    def decorator(func):
        def action(modeladmin, request, queryset):
            if "apply" in request.POST:
                form = form_class(request.POST)
                if form.is_valid():
                    run_each(modeladmin, request, queryset,
                             lambda obj: func(modeladmin, request, obj, form.cleaned_data), success)
                    return None
            else:
                form = form_class()
            context = {
                **modeladmin.admin_site.each_context(request),
                "title": title,
                "description": description,
                "form": form,
                "queryset": queryset,
                "action_name": request.POST.get("action"),
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "opts": modeladmin.model._meta,
            }
            return TemplateResponse(request, "admin/action_form.html", context)

        action.__name__ = func.__name__
        action.short_description = title
        return admin.action(description=title)(action)

    return decorator


class ReasonForm(forms.Form):
    note = forms.CharField(label="Justificativa / registro", widget=forms.Textarea(attrs={"rows": 3}))


class OptionalReasonForm(forms.Form):
    note = forms.CharField(label="Observação (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ReadOnlyAdminMixin:
    """Registros históricos: visíveis, nunca editáveis pelo painel."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
