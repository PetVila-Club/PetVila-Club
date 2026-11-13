"""
Dados de demonstração para homologação local. Idempotente.

Importante (COM-01): o preço do Essential continua pendente e o R$ 209,90 do Care é
referência de trabalho não oficial. Só com --demo-approve a oferta do Care é aprovada e
publicada, registrando que se trata de aprovação de ambiente local.
"""

from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Address, User
from apps.catalog.models import SKU, Category, Product, StoreCategory, Tag
from apps.catalog.store_tree import build_tree
from apps.core.services import Roles
from apps.inventory import services as stock
from apps.inventory.models import StockLevel
from apps.orders.models import ShippingZone
from apps.pets.models import Dog
from apps.plans import services as plan_services
from apps.plans.models import CompositionVersion, KitModel, OfferVersion, Plan

KIT_CATEGORIES = [
    ("brinquedo", "Brinquedo", 1),
    ("biobone", "BioBone mordedor natural", 2),
    ("snack-padrao", "Snacks", 3),
    ("snack-natural", "Snacks naturais", 4),
    ("refeicao-natural", "Refeição Natural", 5),
    ("higiene", "Higiene", 6),
    ("originals", "Surpresa PetVila Originals", 7),
]
STORE_ONLY = [("racao", "Ração", 8), ("passeio", "Passeio", 9), ("loja", "Só loja (fora dos kits)", 10)]

TAGS = [
    ("frango", "Frango", "ingredient"), ("carne-bovina", "Carne bovina", "ingredient"), ("peixe", "Peixe", "ingredient"),
    ("cordeiro", "Cordeiro", "ingredient"), ("cereais", "Cereais", "ingredient"), ("soja", "Soja", "ingredient"),
    ("corante", "Corante artificial", "ingredient"), ("batata-doce", "Batata-doce", "ingredient"),
    ("latex", "Látex", "material"), ("borracha-natural", "Borracha natural", "material"), ("algodao", "Algodão", "material"),
    ("nylon", "Nylon", "material"), ("pelucia", "Pelúcia", "material"),
    ("mastigacao-intensa", "Mastigação intensa", "feature"), ("sem-perfume", "Sem perfume", "feature"),
]

ALL = ["pequeno", "medio", "grande"]
PRODUCTS = [
    # (categoria, nome, slug, preço, assinante, custo, tags, portes, completo, recorrente)
    ("brinquedo", "Bolinha Vila de borracha natural", "bolinha-vila", 3990, 3590, 1400, ["borracha-natural"], ALL, True, False),
    ("brinquedo", "Corda de algodão trançada", "corda-algodao", 3490, 3190, 1100, ["algodao"], ["medio", "grande"], True, False),
    ("brinquedo", "Pelúcia Patinha", "pelucia-patinha", 4490, 3990, 1600, ["pelucia"], ["pequeno", "medio"], True, False),
    ("brinquedo", "Mordedor de látex Cenoura", "mordedor-latex", 2990, 2690, 900, ["latex"], ALL, True, False),
    ("biobone", "BioBone mordedor natural P", "biobone-p", 3290, 2990, 1300, ["mastigacao-intensa"], ["pequeno"], True, False),
    ("biobone", "BioBone mordedor natural G", "biobone-g", 4290, 3890, 1700, ["mastigacao-intensa"], ["medio", "grande"], True, False),
    ("snack-padrao", "Biscoito de frango", "biscoito-frango", 1990, 1790, 600, ["frango", "cereais"], ALL, True, False),
    ("snack-padrao", "Biscoito de carne", "biscoito-carne", 1990, 1790, 600, ["carne-bovina", "cereais"], ALL, True, False),
    ("snack-padrao", "Palitinho de cordeiro", "palitinho-cordeiro", 2290, 2090, 750, ["cordeiro"], ALL, True, False),
    ("snack-padrao", "Cookie de batata-doce", "cookie-batata-doce", 1890, 1690, 550, ["batata-doce"], ALL, True, False),
    ("snack-padrao", "Snack colorido (sem cadastro completo)", "snack-colorido", 1590, None, 400, ["corante"], [], False, False),
    ("snack-natural", "Chips de peixe desidratado", "chips-peixe", 2790, 2490, 1000, ["peixe"], ALL, True, False),
    ("snack-natural", "Fatias de batata-doce", "fatias-batata-doce", 2490, 2190, 800, ["batata-doce"], ALL, True, False),
    ("snack-natural", "Orelha bovina desidratada", "orelha-bovina", 2990, 2690, 1100, ["carne-bovina"], ["medio", "grande"], True, False),
    ("refeicao-natural", "Refeição Natural Frango e Legumes 300 g", "refeicao-frango", 2490, 2290, 900, ["frango"], ALL, True, False),
    ("refeicao-natural", "Refeição Natural Carne e Abóbora 300 g", "refeicao-carne", 2590, 2390, 950, ["carne-bovina"], ALL, True, False),
    ("refeicao-natural", "Refeição Natural Peixe e Batata-doce 300 g", "refeicao-peixe", 2790, 2490, 1050, ["peixe", "batata-doce"], ALL, True, False),
    ("higiene", "Lenço umedecido sem perfume", "lenco-umedecido", 1990, 1790, 600, ["sem-perfume"], ALL, True, False),
    ("higiene", "Shampoo neutro 250 ml", "shampoo-neutro", 3490, 3090, 1200, ["sem-perfume"], ALL, True, False),
    ("higiene", "Escova dental com dedeira", "escova-dental", 2290, 1990, 700, ["nylon"], ALL, True, False),
    ("higiene", "Saquinhos biodegradáveis (4 rolos)", "saquinhos", 1690, 1490, 450, [], ALL, True, False),
    ("originals", "Bandana PetVila Originals", "bandana-originals", 4990, 4490, 1500, ["algodao"], ALL, True, False),
    ("originals", "Pote de petiscos PetVila Originals", "pote-originals", 5990, 5390, 2100, [], ALL, True, False),
    ("racao", "Ração Natural Adulto Frango 2 kg", "racao-adulto-frango", 11990, 10990, 6500, ["frango", "cereais"], ALL, True, True),
    ("racao", "Ração Natural Adulto Cordeiro 2 kg", "racao-adulto-cordeiro", 12990, 11990, 7000, ["cordeiro"], ALL, True, True),
    ("passeio", "Guia de algodão 1,5 m", "guia-algodao", 6990, 6290, 2500, ["algodao"], ALL, True, False),
    # Só loja: completam as subcategorias do menu sem entrar nos kits.
    ("loja", "Mordedor de nylon Osso", "mordedor-nylon-osso", 3990, 3590, 1400, ["nylon", "mastigacao-intensa"], ["medio", "grande"], True, False),
    ("loja", "Mordedor recheável Vila", "mordedor-recheavel-vila", 5490, 4990, 2000, ["borracha-natural"], ALL, True, False),
    ("loja", "Tapete de farejar", "tapete-farejar", 6990, 6290, 2600, ["algodao"], ALL, True, False),
    ("loja", "Bola recheável de petiscos", "bola-recheavel", 4290, 3890, 1500, ["borracha-natural"], ALL, True, False),
    ("racao", "Ração úmida Natural Frango 400 g", "racao-umida-frango", 1490, 1290, 600, ["frango"], ALL, True, False),
    ("loja", "Escova de pelos macia", "escova-pelos", 3990, 3590, 1300, [], ALL, True, False),
    ("loja", "Hidratante de patas e focinho", "hidratante-patas", 3290, 2990, 1100, ["sem-perfume"], ALL, True, False),
    ("loja", "Comedouro de cerâmica", "comedouro-ceramica", 7990, 7190, 3000, [], ALL, True, False),
]

# Produto -> categoria da loja (menu). Ver apps/catalog/store_tree.py.
STORE_OF = {
    "bolinha-vila": "pegar-e-buscar", "corda-algodao": "mordedor-corda", "pelucia-patinha": "pelucia",
    "mordedor-latex": "mordedor-borracha", "biobone-p": "mordedor-natural", "biobone-g": "mordedor-natural",
    "biscoito-frango": "snacks", "biscoito-carne": "snacks", "palitinho-cordeiro": "snacks",
    "cookie-batata-doce": "snacks", "snack-colorido": "snacks", "chips-peixe": "snacks-naturais",
    "fatias-batata-doce": "snacks-naturais", "orelha-bovina": "snacks-naturais", "refeicao-frango": "refeicao-natural",
    "refeicao-carne": "refeicao-natural", "refeicao-peixe": "refeicao-natural", "lenco-umedecido": "patas-e-focinho",
    "shampoo-neutro": "banho", "escova-dental": "higiene-bucal", "saquinhos": "higiene-ambiente",
    "racao-adulto-frango": "racao-seca", "racao-adulto-cordeiro": "racao-seca", "guia-algodao": "passeio",
    "mordedor-nylon-osso": "mordedor-nylon", "mordedor-recheavel-vila": "mordedor-recheavel",
    "tapete-farejar": "brinquedo-interativo", "bola-recheavel": "brinquedo-recheavel",
    "racao-umida-frango": "racao-umida", "escova-pelos": "escovacao", "hidratante-patas": "patas-e-focinho",
    "comedouro-ceramica": "comedouros",
}

COMPOSITIONS = {
    "essential": {"brinquedo": 1, "biobone": 0, "snack-padrao": 3, "snack-natural": 0, "refeicao-natural": 1, "higiene": 2, "originals": 0},
    "care": {"brinquedo": 1, "biobone": 1, "snack-padrao": 2, "snack-natural": 2, "refeicao-natural": 1, "higiene": 2, "originals": 1},
}

DEMO_PASSWORD = "petvila123"


class Command(BaseCommand):
    help = "Popula dados de demonstração (catálogo, planos, composições, usuários de teste)."

    def add_arguments(self, parser):
        parser.add_argument("--demo-approve", action="store_true",
                            help="Aprova e publica a oferta do Care com o valor de referência (somente ambiente local).")
        parser.add_argument("--no-users", action="store_true", help="Não cria usuários de demonstração.")

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("bootstrap", verbosity=0)
        categories = self.seed_categories()
        tags = {code: Tag.objects.update_or_create(code=code, defaults={"name": name, "kind": kind})[0] for code, name, kind in TAGS}
        self.seed_products(categories, tags)
        admin = self.seed_users(options["no_users"])
        plans = self.seed_plans(admin, categories)
        self.seed_offers(plans, admin, options["demo_approve"])
        ShippingZone.objects.get_or_create(name="São Paulo capital", cep_start="01000000", cep_end="05999999",
                                           defaults={"price_cents": 1490, "eta_days": 2})
        ShippingZone.objects.get_or_create(name="Grande São Paulo", cep_start="06000000", cep_end="09999999",
                                           defaults={"price_cents": 2290, "eta_days": 3})
        if not options["no_users"]:
            self.seed_tutor(tags)
        self.stdout.write(self.style.SUCCESS("Dados de demonstração prontos."))

    def seed_categories(self):
        result = {}
        for slug, name, sort in KIT_CATEGORIES:
            result[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "is_kit_category": True, "sort": sort, "show_in_store": slug != "originals"})
        for slug, name, sort in STORE_ONLY:
            result[slug], _ = Category.objects.update_or_create(slug=slug, defaults={"name": name, "sort": sort})
        return result

    def seed_products(self, categories, tags):
        build_tree(StoreCategory)
        store = {c.slug: c for c in StoreCategory.objects.all()}
        for i, (cat, name, slug, price, member, cost, tag_codes, sizes, complete, recurring) in enumerate(PRODUCTS, start=1):
            product, _ = Product.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "category": categories[cat], "is_recurring_food": recurring,
                    "store_category": store.get(STORE_OF.get(slug, "")),
                    "is_originals": cat == "originals",
                    "short_description": f"{categories[cat].name} escolhido pela curadoria PetVila.",
                    "description": f"{name}. Selecionado pela curadoria PetVila para a rotina com o seu cão. "
                                   "Confira composição e indicações de porte antes de oferecer.",
                    "conservation": "Conservar em local seco e arejado, ao abrigo da luz." if cat in ("snack-padrao", "snack-natural", "racao")
                    else ("Manter refrigerado após aberto e consumir em até 3 dias." if cat == "refeicao-natural" else ""),
                },
            )
            sku, created = SKU.objects.update_or_create(
                code=f"PV-{i:03d}",
                defaults={
                    "product": product, "price_cents": price, "member_price_cents": member, "cost_cents": cost,
                    "weight_g": 400, "net_weight_g": 300, "length_cm": 20, "width_cm": 12, "height_cm": 8,
                    "suitable_sizes": sizes, "attributes_complete": complete,
                    "tracks_lots": cat in ("snack-padrao", "snack-natural", "refeicao-natural", "racao"),
                    "sellable_in_store": cat != "originals",
                    "variant_name": "2 kg" if slug.startswith("racao-adulto") else "",
                },
            )
            sku.contains.set([tags[c] for c in tag_codes])
            StockLevel.objects.get_or_create(sku=sku)
            if created:
                qty = 3 if slug == "pelucia-patinha" else 60
                lot = f"L{date.today():%y%m}-{i:03d}" if sku.tracks_lots else ""
                stock.receive(sku, qty, lot_code=lot, expires_on=date.today() + timedelta(days=240) if lot else None,
                              reason="Estoque inicial de demonstração", key=f"seed:{sku.code}")

    def seed_users(self, skip):
        admin = User.objects.filter(email="admin@petvila.local").first()
        if admin is None:
            admin = User.objects.create_superuser("admin@petvila.local", DEMO_PASSWORD, full_name="Gestão PetVila")
        if not skip:
            for role in Roles.ALL:
                email = f"{role}@petvila.local"
                user = User.objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(email, DEMO_PASSWORD, full_name=f"Equipe {role.title()}", is_staff=True)
                user.groups.add(Group.objects.get(name=role))
        return admin

    def seed_plans(self, admin, categories):
        data = {
            "essential": dict(name="Vila Essential", tagline="O essencial, bem escolhido.", base_item_count=7, sort=1,
                              description="Tudo o que o seu cão precisa no mês, escolhido com cuidado para a rotina de vocês. "
                                          "Sem excesso: só o que faz sentido, chegando todo mês."),
            "care": dict(name="Vila Care", tagline="A experiência completa PetVila.", base_item_count=10, sort=2, highlight=True,
                         description="Para quem quer viver a PetVila por inteiro. Mais cuidado, mais descobertas e mais surpresas a "
                                     "cada mês, para o seu cão fazer parte da comunidade PetVila de verdade.",
                         extras=[{"title": "PetVila Originals",
                                  "copy": "Acesso antecipado e prioridade em lançamentos de produtos originais PetVila, "
                                          "incluindo edições e disponibilidades limitadas."}]),
        }
        plans = {}
        for code, fields in data.items():
            plan, _ = Plan.objects.update_or_create(code=code, defaults=fields)
            plans[code] = plan
            if not plan.compositions.exists():
                comp = CompositionVersion.objects.create(plan=plan, version=1, created_by=admin, notes="Base inicial do PDR v1.1")
                for slug, qty in COMPOSITIONS[code].items():
                    comp.lines.create(category=categories[slug], quantity=qty)
                plan_services.approve_composition(comp, admin)
                plan_services.publish_composition(comp, admin)
            if not plan.kit_models.exists():
                KitModel.objects.create(plan=plan, name="Clássico", description="Seleção equilibrada da curadoria.")
                natural = KitModel.objects.create(plan=plan, name="Natural", description="Prioriza snacks e itens naturais.")
                natural.skus.set(SKU.objects.filter(product__slug__in=[
                    "chips-peixe", "fatias-batata-doce", "orelha-bovina", "cookie-batata-doce", "palitinho-cordeiro",
                    "refeicao-peixe", "refeicao-carne", "corda-algodao", "bolinha-vila"]))
        return plans

    def seed_offers(self, plans, admin, demo_approve):
        essential = plans["essential"]
        if not essential.offers.exists():
            OfferVersion.objects.create(plan=essential, version=1, price_cents=None, commitment_options=[3, 6, 12],
                                        internal_notes="P01: preço do Essential pendente. Não publicar sem valor aprovado.")
        care = plans["care"]
        offer = care.offers.order_by("version").first()
        if offer is None:
            offer = OfferVersion.objects.create(
                plan=care, version=1, price_cents=20990, commitment_options=[3, 6, 12], shipping_cents=0,
                benefits="Curadoria mensal com 10 itens, incluindo uma surpresa PetVila Originals.",
                terms="Assinatura mensal com cobrança recorrente. Ciclo mínimo de 3 meses (pendente de aprovação final).",
                internal_notes="R$ 209,90 é referência de trabalho não oficial (estimativa R$ 200–210).",
            )
        if demo_approve and offer.status == OfferVersion.Status.DRAFT:
            plan_services.approve_offer(offer, admin, "Aprovação de homologação LOCAL (dados de demonstração, valor não oficial).")
            plan_services.publish_offer(offer, admin)
            self.stdout.write(self.style.WARNING("Oferta do Care publicada apenas para homologação local."))

    def seed_tutor(self, tags):
        tutor = User.objects.filter(email="tutor@petvila.local").first()
        if tutor is None:
            tutor = User.objects.create_user("tutor@petvila.local", DEMO_PASSWORD, full_name="Ana Tutora", cpf="52998224725",
                                             phone="11999990000", terms_version="2026-11-01")
            Address.objects.create(user=tutor, label="Casa", recipient="Ana Tutora", cep="01310100",
                                   street="Avenida Paulista", number="1000", district="Bela Vista", city="São Paulo",
                                   state="SP", is_default=True)
        if not tutor.dogs.exists():
            pacoca = Dog.objects.create(tutor=tutor, name="Paçoca", size="pequeno", weight_kg=7.5, estimated_age_years=3,
                                        breed="SRD")
            pacoca.restrictions.set([tags["frango"]])
            pacoca.preferences.set([tags["batata-doce"]])
            pacoca.snapshot_version()
            thor = Dog.objects.create(tutor=tutor, name="Thor", size="grande", weight_kg=32, estimated_age_years=5,
                                      breed="Labrador")
            thor.restrictions.set([tags["latex"]])
            thor.preferences.set([tags["carne-bovina"], tags["mastigacao-intensa"]])
            thor.snapshot_version()
