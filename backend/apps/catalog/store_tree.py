"""Árvore de navegação da loja definida pelo Felipe em 13/11/2026 (departamento > subcategorias)."""

STORE_TREE = [
    ("alimentos", "Alimentos", [
        ("snacks", "Snacks"),
        ("snacks-naturais", "Snacks naturais"),
        ("racao-seca", "Ração seca"),
        ("racao-umida", "Ração úmida"),
        ("refeicao-natural", "Refeição Natural"),
    ]),
    ("higiene-e-cuidado", "Higiene e cuidado", [
        ("banho", "Banho"),
        ("escovacao", "Escovação"),
        ("higiene-ambiente", "Higiene de ambiente e acessórios"),
        ("higiene-bucal", "Higiene bucal"),
        ("patas-e-focinho", "Patas e focinho"),
    ]),
    ("mordedores", "Mordedores", [
        ("mordedor-natural", "Mordedor natural"),
        ("mordedor-borracha", "Mordedor de borracha"),
        ("mordedor-nylon", "Mordedor de nylon"),
        ("mordedor-corda", "Mordedor de corda"),
        ("mordedor-recheavel", "Recheáveis"),
    ]),
    ("brinquedos", "Brinquedos", [
        ("brinquedo-interativo", "Interativos"),
        ("brinquedo-recheavel", "Recheáveis"),
        ("pelucia", "Pelúcia"),
        ("pegar-e-buscar", "Pegar e buscar"),
    ]),
    ("acessorios", "Acessórios", [
        ("passeio", "Passeio"),
        ("comedouros", "Comedouros"),
        ("bolsas-e-organizadores", "Bolsas e organizadores"),
    ]),
]

# Produtos já cadastrados: categoria de kit -> categoria da loja, quando o encaixe é inequívoco.
DEFAULT_FROM_KIT_CATEGORY = {
    "snack-padrao": "snacks",
    "snack-natural": "snacks-naturais",
    "refeicao-natural": "refeicao-natural",
    "racao": "racao-seca",
    "biobone": "mordedor-natural",
    "passeio": "passeio",
}


def build_tree(StoreCategory):
    for i, (slug, name, children) in enumerate(STORE_TREE, start=1):
        parent, _ = StoreCategory.objects.update_or_create(slug=slug, defaults={"name": name, "sort": i * 10, "parent": None})
        for j, (child_slug, child_name) in enumerate(children, start=1):
            StoreCategory.objects.update_or_create(
                slug=child_slug, defaults={"name": child_name, "sort": i * 10 + j, "parent": parent})
