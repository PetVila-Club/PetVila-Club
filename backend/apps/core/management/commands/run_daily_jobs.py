"""Rotina diária: expira pedidos não pagos, aplica cancelamentos agendados e gera sugestões de curadoria."""

import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Executa as rotinas operacionais diárias (use --loop para rodar como serviço)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Repete a cada --interval segundos")
        parser.add_argument("--interval", type=int, default=3600)

    def handle(self, *args, **options):
        while True:
            self.run_once()
            if not options["loop"]:
                break
            time.sleep(options["interval"])

    def run_once(self):
        from apps.curation.services import generate_pending_kits
        from apps.orders.services import expire_unpaid_orders
        from apps.subscriptions.services import apply_scheduled_cancellations

        expired = expire_unpaid_orders()
        canceled = apply_scheduled_cancellations()
        kits = generate_pending_kits()
        self.stdout.write(
            f"pedidos expirados={expired} cancelamentos aplicados={canceled} "
            f"sugestões geradas={kits['created']} falhas={len(kits['failed'])}"
        )
