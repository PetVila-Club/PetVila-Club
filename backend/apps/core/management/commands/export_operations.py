import json

from django.core.management.base import BaseCommand

from apps.core.ops import build_export


class Command(BaseCommand):
    help = "ADM-03: exporta a operação em JSON aberto, com IDs e versão do esquema."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="-", help="Arquivo de saída (padrão: stdout)")

    def handle(self, *args, **options):
        data = json.dumps(build_export(), ensure_ascii=False, indent=2, default=str)
        if options["out"] == "-":
            self.stdout.write(data)
        else:
            with open(options["out"], "w", encoding="utf-8") as fh:
                fh.write(data)
            self.stdout.write(self.style.SUCCESS(f"Exportado para {options['out']}"))
