"""Cria papéis com permissões mínimas (ADM-02) e parâmetros operacionais padrão. Idempotente."""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.core.services import Roles, ensure_default_settings

# app_label -> ações permitidas por papel. "view" = só leitura.
ROLE_MATRIX = {
    Roles.GESTOR: {"*": ["add", "change", "delete", "view"]},
    Roles.CURADOR: {
        "curation": ["change", "view"], "pets": ["view", "change"], "catalog": ["view", "change"],
        "plans": ["add", "change", "view"], "subscriptions": ["view"], "reviews": ["view"], "inventory": ["view"],
        "core": ["view", "change"],
    },
    Roles.OPERACAO: {
        "inventory": ["add", "change", "view"], "logistics": ["change", "view"], "catalog": ["add", "change", "view"],
        "curation": ["view", "change"], "plans": ["add", "change", "view"], "orders": ["view", "change"],
        "subscriptions": ["view"], "fiscal": ["view"], "core": ["view", "change"],
    },
    Roles.ATENDIMENTO: {
        "support": ["change", "view"], "orders": ["view"], "subscriptions": ["view", "change"], "pets": ["view"],
        "accounts": ["view"], "logistics": ["view", "change"], "reviews": ["view", "change"], "payments": ["view"],
        "core": ["view"],
    },
    Roles.FINANCEIRO: {
        "payments": ["change", "view"], "fiscal": ["change", "view"], "orders": ["view", "change"],
        "subscriptions": ["view"], "plans": ["view"], "core": ["view", "change"], "logistics": ["view"],
    },
}
EXCLUDED_FOR_NON_MANAGERS = {"accounts.change_user", "accounts.delete_user", "accounts.add_user", "auth.change_group",
                             "core.change_operationalsetting", "core.change_auditlog"}


class Command(BaseCommand):
    help = "Cria papéis, permissões e parâmetros operacionais padrão."

    def handle(self, *args, **options):
        ensure_default_settings()
        for role, matrix in ROLE_MATRIX.items():
            group, _ = Group.objects.get_or_create(name=role)
            perms = []
            if "*" in matrix:
                perms = list(Permission.objects.filter(content_type__app_label__in=self._project_apps() + ["auth"]))
            else:
                for app_label, actions in matrix.items():
                    for action in actions:
                        perms += list(Permission.objects.filter(content_type__app_label=app_label, codename__startswith=f"{action}_"))
                perms = [p for p in perms if f"{p.content_type.app_label}.{p.codename}" not in EXCLUDED_FOR_NON_MANAGERS]
            group.permissions.set(perms)
            self.stdout.write(f"Papel {role}: {len(perms)} permissões")
        self.stdout.write(self.style.SUCCESS("Bootstrap concluído."))

    @staticmethod
    def _project_apps():
        return ["core", "accounts", "catalog", "pets", "inventory", "plans", "subscriptions", "curation", "orders",
                "payments", "logistics", "fiscal", "reviews", "support"]
