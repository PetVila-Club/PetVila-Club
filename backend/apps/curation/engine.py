"""
Motor de sugestão por regras (CUR-01/03). Determinístico: mesmas entradas e mesma
versão de regras produzem o mesmo resultado. A decisão final é sempre humana.

Ordem das regras:
  1. Bloqueios: SKU inativo, refrigeração não homologada, restrição declarada, porte inadequado.
  2. Informação desconhecida não equivale a compatível: o SKU vai para revisão e não é escolhido.
  3. Sem estoque disponível: rejeitado.
  4. Pontuação: preferências (+3 cada), repetição para o cão na janela (-6),
     repetição na casa na janela (-2). Desempate por menor custo e depois por código.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import SKU

ENGINE_VERSION = "regras-1.0"
WEIGHTS = {"preference": 3, "repeat_dog": -6, "repeat_household": -2}


@dataclass(frozen=True)
class Compat:
    status: str  # ok | blocked | unknown
    reason: str = ""


def check_compatibility(sku: SKU, profile: dict) -> Compat:
    if not sku.is_active or not sku.product.is_active:
        return Compat("blocked", "SKU inativo")
    if sku.requires_refrigeration:
        return Compat("blocked", "exige refrigeração (cadeia não homologada)")
    contains = {t.code for t in sku.contains.all()}
    hit = sorted(contains & set(profile.get("restrictions") or []))
    if hit:
        return Compat("blocked", "contém " + ", ".join(hit) + " (restrição declarada)")
    if not sku.attributes_complete:
        return Compat("unknown", "informação de compatibilidade incompleta: exige revisão")
    if not sku.suitable_sizes:
        return Compat("unknown", "porte adequado não informado: exige revisão")
    size = profile.get("size")
    if not size:
        return Compat("unknown", "porte do cão não informado")
    if size not in sku.suitable_sizes:
        return Compat("blocked", f"não indicado para porte {size}")
    return Compat("ok")


def group_key(plan_code: str, profile: dict) -> str:
    restrictions = "+".join(sorted(profile.get("restrictions") or [])) or "sem-restricao"
    return f"{plan_code}|{profile.get('size') or 'sem-porte'}|{restrictions}"


def _select_for_category(category, quantity: int, candidates: list[SKU], profile: dict, history_dog: set[int],
                         history_household: set[int], stock: dict[int, int]) -> dict:
    preferences = set(profile.get("preferences") or [])
    evaluated = []
    rejected = []
    for sku in sorted(candidates, key=lambda s: s.code):
        compat = check_compatibility(sku, profile)
        if compat.status != "ok":
            rejected.append({"sku": sku.code, "reason": compat.reason, "kind": compat.status})
            continue
        available = stock.get(sku.pk, 0)
        if available <= 0:
            rejected.append({"sku": sku.code, "reason": "sem estoque disponível", "kind": "stock"})
            continue
        matched = sorted({t.code for t in sku.contains.all()} & preferences)
        score = WEIGHTS["preference"] * len(matched)
        notes = [f"preferência: {', '.join(matched)}"] if matched else []
        if sku.pk in history_dog:
            score += WEIGHTS["repeat_dog"]
            notes.append("já entregue a este cão na janela de variedade")
        elif sku.pk in history_household:
            score += WEIGHTS["repeat_household"]
            notes.append("já entregue a outro cão da casa na janela")
        evaluated.append({"sku": sku, "score": score, "notes": notes, "available": available})

    evaluated.sort(key=lambda e: (-e["score"], e["sku"].cost_cents, e["sku"].code))
    allocation: dict[int, int] = {}
    remaining = quantity
    # Primeiro, SKUs distintos; depois completa com unidades extras dos melhores, respeitando o estoque.
    for entry in evaluated:
        if remaining == 0:
            break
        allocation[entry["sku"].pk] = 1
        remaining -= 1
    idx = 0
    while remaining > 0 and evaluated:
        entry = evaluated[idx % len(evaluated)]
        pk = entry["sku"].pk
        if allocation.get(pk, 0) < entry["available"]:
            allocation[pk] = allocation.get(pk, 0) + 1
            remaining -= 1
        idx += 1
        if idx > len(evaluated) * (quantity + 1):
            break

    review = []
    if remaining > 0:
        review.append(f"{category.name}: faltam {remaining} unidade(s) sem candidato compatível com estoque")
    chosen = [e for e in evaluated if e["sku"].pk in allocation]
    if chosen and all(e["sku"].pk in history_dog for e in chosen) and quantity > 0:
        review.append(f"{category.name}: só há SKU repetido para este cão; aprovar ou substituir")
    if any(r["kind"] == "unknown" for r in rejected) and remaining > 0:
        review.append(f"{category.name}: há SKU com informação incompleta; completar cadastro")
    return {
        "category": category.slug,
        "quantity": quantity,
        "lines": [(pk, qty) for pk, qty in allocation.items()],
        "score": sum(e["score"] * allocation[e["sku"].pk] for e in chosen),
        "candidates": [
            {"sku": e["sku"].code, "score": e["score"], "notes": e["notes"], "chosen_units": allocation.get(e["sku"].pk, 0)}
            for e in evaluated
        ],
        "rejected": rejected,
        "review": review,
    }


def suggest(*, profile: dict, composition, kit_models: list, history_dog: set[int], history_household: set[int],
            stock: dict[int, int]) -> dict:
    lines = [line for line in composition.lines.select_related("category").order_by("category__sort") if line.quantity > 0]
    options = kit_models or [None]
    results = []
    for model in sorted(options, key=lambda m: m.pk if m else 0):
        pool = set(model.skus.values_list("pk", flat=True)) if model else set()
        categories = []
        for line in lines:
            candidates = list(
                SKU.objects.filter(product__category=line.category, is_active=True)
                .select_related("product").prefetch_related("contains")
            )
            in_pool = [s for s in candidates if s.pk in pool]
            if in_pool:
                candidates = in_pool
            categories.append(_select_for_category(line.category, line.quantity, candidates, profile,
                                                   history_dog, history_household, stock))
        review = [r for c in categories for r in c["review"]]
        results.append({
            "kit_model_id": model.pk if model else None,
            "kit_model": model.name if model else None,
            "score": sum(c["score"] for c in categories),
            "review": review,
            "categories": categories,
        })
    results.sort(key=lambda r: (len(r["review"]) > 0, -r["score"], r["kit_model_id"] or 0))
    best = results[0]
    return {
        "engine_version": ENGINE_VERSION,
        "weights": WEIGHTS,
        "chosen_model_id": best["kit_model_id"],
        "options": [{"kit_model": r["kit_model"], "score": r["score"], "review": r["review"]} for r in results],
        "categories": best["categories"],
        "review": best["review"],
    }
