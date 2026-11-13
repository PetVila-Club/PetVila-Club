"""Ciclo de vida de ofertas, composições e modelos (COM-01/02, KIT-01/02/03)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.catalog.models import SKU
from apps.core.exceptions import DomainError
from apps.core.services import Roles, audit, get_setting, require_role

from .models import CompositionVersion, KitModel, OfferVersion, Plan

# ---------------- Ofertas ----------------


def next_offer_version(plan: Plan) -> int:
    return (plan.offers.aggregate(m=Max("version"))["m"] or 0) + 1


@transaction.atomic
def approve_offer(offer: OfferVersion, actor, note: str) -> OfferVersion:
    require_role(actor, Roles.GESTOR)
    if offer.status != OfferVersion.Status.DRAFT:
        raise DomainError("Só ofertas em rascunho podem ser aprovadas.")
    if not offer.price_cents:
        raise DomainError("Oferta sem preço não pode ser aprovada. O preço deste plano continua pendente.", code="price_pending")
    if not note.strip():
        raise DomainError("Registre a aprovação (quem decidiu e em qual instância).")
    offer.status = OfferVersion.Status.APPROVED
    offer.approved_by = actor
    offer.approved_at = timezone.now()
    offer.approval_note = note
    offer.save()
    audit(actor, "offer_approved", offer, reason=note, changes={"price_cents": offer.price_cents})
    return offer


@transaction.atomic
def publish_offer(offer: OfferVersion, actor, valid_from=None) -> OfferVersion:
    """COM-01: bloqueia publicação sem preço aprovado. COM-02: vigência futura não altera contratos fechados."""
    require_role(actor, Roles.GESTOR)
    if not offer.price_cents or offer.status != OfferVersion.Status.APPROVED or not offer.approved_at:
        raise DomainError(
            "Publicação bloqueada: a oferta precisa de preço e aprovação registrados.", code="offer_not_approved"
        )
    valid_from = valid_from or offer.valid_from or timezone.now()
    current = offer.plan.current_offer(at=valid_from)
    if current and current.pk != offer.pk:
        current.valid_until = valid_from
        current.save(update_fields=["valid_until", "updated_at"])
    offer.status = OfferVersion.Status.PUBLISHED
    offer.valid_from = valid_from
    offer.published_by = actor
    offer.published_at = timezone.now()
    offer.save()
    audit(actor, "offer_published", offer, changes={"valid_from": valid_from.isoformat(),
                                                    "previous_offer": current.pk if current else None})
    return offer


@transaction.atomic
def archive_offer(offer: OfferVersion, actor, reason: str) -> OfferVersion:
    require_role(actor, Roles.GESTOR)
    offer.status = OfferVersion.Status.ARCHIVED
    if not offer.valid_until:
        offer.valid_until = timezone.now()
    offer.save()
    audit(actor, "offer_archived", offer, reason=reason)
    return offer


# ---------------- Composições ----------------


def validate_composition(composition: CompositionVersion) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Erros impedem aprovação (KIT-03)."""
    errors: list[str] = []
    warnings: list[str] = []
    lines = list(composition.lines.select_related("category"))
    if not lines:
        errors.append("A composição não tem nenhuma categoria.")
    seen = set()
    for line in lines:
        if line.quantity < 0:
            errors.append(f"Quantidade negativa em {line.category.name}.")
        if line.category_id in seen:
            errors.append(f"{line.category.name} aparece mais de uma vez (item contado duas vezes).")
        seen.add(line.category_id)
        if not line.category.is_kit_category:
            errors.append(f"{line.category.name} não é uma categoria de kit.")
        if line.quantity > 0:
            candidates = SKU.objects.filter(product__category=line.category, is_active=True, product__is_active=True)
            if not candidates.exists():
                errors.append(f"{line.category.name} não tem nenhum SKU candidato ativo.")
    total = sum(line.quantity for line in lines if line.counts_toward_total)
    if total != composition.plan.base_item_count:
        msg = (
            f"Total de {total} itens difere da base pública de {composition.plan.base_item_count} itens do "
            f"{composition.plan.name}. Exige confirmação de nova versão e revisão da oferta."
        )
        if composition.total_change_confirmed:
            warnings.append(msg)
        else:
            errors.append(msg)
    return errors, warnings


def diff_compositions(new: CompositionVersion, old: CompositionVersion | None) -> list[dict]:
    old_map = {line.category.slug: line.quantity for line in old.lines.select_related("category")} if old else {}
    new_map = {line.category.slug: line.quantity for line in new.lines.select_related("category")}
    rows = []
    for slug in sorted(set(old_map) | set(new_map)):
        before, after = old_map.get(slug, 0), new_map.get(slug, 0)
        if before != after:
            rows.append({"category": slug, "before": before, "after": after})
    return rows


@transaction.atomic
def submit_composition(composition: CompositionVersion, actor) -> CompositionVersion:
    require_role(actor, Roles.OPERACAO, Roles.CURADOR, Roles.GESTOR)
    if composition.status != CompositionVersion.Status.DRAFT:
        raise DomainError("Só rascunhos podem ir para revisão.")
    composition.status = CompositionVersion.Status.IN_REVIEW
    composition.save()
    audit(actor, "composition_submitted", composition)
    return composition


@transaction.atomic
def approve_composition(composition: CompositionVersion, actor) -> CompositionVersion:
    require_role(actor, Roles.CURADOR, Roles.GESTOR)
    if composition.status not in (CompositionVersion.Status.DRAFT, CompositionVersion.Status.IN_REVIEW):
        raise DomainError("Esta versão não está em rascunho ou revisão.")
    errors, warnings = validate_composition(composition)
    if errors:
        raise DomainError("Composição inválida: " + " ".join(errors), code="invalid_composition")
    composition.status = CompositionVersion.Status.APPROVED
    composition.approved_by = actor
    composition.approved_at = timezone.now()
    composition.save()
    audit(actor, "composition_approved", composition, changes={"warnings": warnings})
    return composition


@transaction.atomic
def publish_composition(composition: CompositionVersion, actor, valid_from=None) -> CompositionVersion:
    require_role(actor, Roles.GESTOR)
    if composition.status != CompositionVersion.Status.APPROVED:
        raise DomainError("Só composições aprovadas podem ser publicadas.")
    errors, _ = validate_composition(composition)
    if errors:
        raise DomainError("Composição inválida: " + " ".join(errors), code="invalid_composition")
    previous = composition.plan.current_composition()
    composition.previous = previous
    composition.status = CompositionVersion.Status.PUBLISHED
    composition.valid_from = valid_from or composition.valid_from or timezone.now()
    composition.published_by = actor
    composition.published_at = timezone.now()
    composition.save()
    audit(actor, "composition_published", composition,
          changes={"diff": diff_compositions(composition, previous), "previous": previous.pk if previous else None})
    return composition


@transaction.atomic
def clone_composition(composition: CompositionVersion, actor) -> CompositionVersion:
    """Cria um novo rascunho a partir de uma versão (para editar sem tocar na publicada)."""
    plan = composition.plan
    version = (plan.compositions.aggregate(m=Max("version"))["m"] or 0) + 1
    draft = CompositionVersion.objects.create(plan=plan, version=version, created_by=actor,
                                              notes=f"Criada a partir da v{composition.version}")
    for line in composition.lines.all():
        draft.lines.create(category=line.category, quantity=line.quantity, counts_toward_total=line.counts_toward_total)
    audit(actor, "composition_cloned", draft, changes={"from": composition.pk})
    return draft


# ---------------- Modelos de kit ----------------


def check_kit_model_limit(plan: Plan, exclude_pk: int | None = None) -> None:
    limit = int(get_setting("kit_models_max_active_per_plan"))
    qs = KitModel.objects.filter(plan=plan, status=KitModel.Status.ACTIVE)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.count() >= limit:
        raise DomainError(
            f"Limite de {limit} modelos ativos para o {plan.name} atingido. Arquive um modelo antes de ativar outro.",
            code="kit_model_limit",
        )


# ---------------- Oferta do Club no checkout da loja ----------------


def recommend_plan_for_cart(lines) -> dict | None:
    """Escolhe o plano mais ligado ao que está no carrinho e devolve o contexto para a chamada.

    Pontua cada plano disponível pelas unidades do carrinho cujas categorias de kit aparecem na
    composição publicada do plano; empate vai para o plano em destaque. Só oferece plano com preço publicado.
    """
    candidates = []
    for plan in Plan.objects.filter(is_active=True).order_by("sort"):
        offer = plan.current_offer()
        if offer is None or not offer.price_cents:
            continue
        composition = plan.current_composition()
        covered = set()
        if composition:
            covered = {line.category.slug for line in composition.lines.select_related("category") if line.quantity > 0}
        score = sum(line.quantity for line in lines if line.sku.product.category.slug in covered)
        candidates.append((score, plan.highlight, -plan.sort, plan, offer))
    if not candidates:
        return None
    score, _, _, plan, offer = max(candidates, key=lambda c: (c[0], c[1], c[2]))

    top = max(lines, key=lambda line: line.total_cents)
    departments: dict[str, list] = {}
    for line in lines:
        sc = line.sku.product.store_category
        if sc is None:
            continue
        dept = sc.parent or sc
        entry = departments.setdefault(dept.slug, [dept.name, 0])
        entry[1] += line.quantity
    dept_slug, (dept_name, _) = max(departments.items(), key=lambda kv: kv[1][1]) if departments else (None, (None, 0))
    return {
        "plan_code": plan.code,
        "plan_name": plan.name,
        "tagline": plan.tagline,
        "highlight": plan.highlight,
        "price_cents": offer.price_cents,
        "matches_cart": score > 0,
        "top_item": top.sku.product.name,
        "department_slug": dept_slug,
        "department_name": dept_name,
    }
