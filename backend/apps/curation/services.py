"""Curadoria do ciclo (CUR-02/04, KIT-04, PET-04)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import SKU, Category
from apps.core.exceptions import DomainError
from apps.core.models import OperationalAlert
from apps.core.services import Roles, audit, get_setting, raise_alert, require_role
from apps.inventory import services as stock
from apps.inventory.models import StockLevel
from apps.plans.models import KitModel
from apps.subscriptions.models import Cycle, Subscription

from . import engine
from .models import CycleKit, KitLine


def _history(cycle: Cycle) -> tuple[set[int], set[int]]:
    """SKUs entregues ao cão e à casa nos últimos N ciclos (janela configurável)."""
    window = int(get_setting("variety_window_cycles"))
    dog = cycle.subscription.dog
    previous = (
        CycleKit.objects.filter(dog=dog, status=CycleKit.Status.CLOSED).exclude(cycle=cycle).order_by("-closed_at")[:window]
    )
    dog_skus = set(KitLine.objects.filter(kit__in=list(previous), status=KitLine.Status.ACTIVE).values_list("sku_id", flat=True))
    house = (
        CycleKit.objects.filter(dog__tutor=dog.tutor, status=CycleKit.Status.CLOSED).exclude(dog=dog).order_by("-closed_at")[:window * 3]
    )
    house_skus = set(KitLine.objects.filter(kit__in=list(house), status=KitLine.Status.ACTIVE).values_list("sku_id", flat=True))
    return dog_skus, house_skus


def _stock_map() -> dict[int, int]:
    return {lvl.sku_id: lvl.available for lvl in StockLevel.objects.all()}


@transaction.atomic
def generate_kit(cycle: Cycle, *, actor=None, regenerate: bool = False) -> CycleKit:
    cycle = Cycle.objects.select_for_update(of=("self",)).select_related("subscription__plan", "subscription__dog").get(pk=cycle.pk)
    sub = cycle.subscription
    if sub.kind != Subscription.Kind.KIT:
        raise DomainError("Ciclos de ração não passam por curadoria de kit.")
    if cycle.paid_at is None:
        raise DomainError("Ciclo sem pagamento confirmado não entra em curadoria.", code="cycle_not_paid")
    existing = CycleKit.objects.filter(cycle=cycle).first()
    if existing and not regenerate:
        return existing
    if existing and existing.status in (CycleKit.Status.APPROVED, CycleKit.Status.CLOSED):
        raise DomainError("Kit já aprovado ou fechado não é reprocessado automaticamente.")

    dog = sub.dog
    profile_version = dog.snapshot_version()
    profile = profile_version.data
    composition = sub.plan.current_composition(at=timezone.now())
    if composition is None:
        raise_alert(OperationalAlert.Kind.CURATION, f"{sub.plan.name} sem composição publicada", obj=sub.plan,
                    dedupe_key=f"no-composition:{sub.plan_id}")
        raise DomainError(f"{sub.plan.name} não tem composição publicada.")
    models = list(KitModel.objects.filter(plan=sub.plan, status=KitModel.Status.ACTIVE))
    dog_hist, house_hist = _history(cycle)
    result = engine.suggest(profile=profile, composition=composition, kit_models=models, history_dog=dog_hist,
                            history_household=house_hist, stock=_stock_map())

    review = list(result["review"])
    missing = dog.missing_required_fields()
    if missing:
        review.insert(0, "Cadastro do cão incompleto: " + ", ".join(missing))

    if existing:
        before = [(line.sku.code, line.quantity) for line in existing.lines.all()]
        existing.lines.all().delete()
        kit = existing
        audit(actor, "kit_regenerated", kit, changes={"before": before})
    else:
        kit = CycleKit(cycle=cycle, dog=dog)
    kit.profile_version = profile_version
    kit.composition = composition
    kit.kit_model_id = result["chosen_model_id"]
    kit.engine_version = result["engine_version"]
    kit.trace = result
    kit.review_reasons = review
    kit.group_key = engine.group_key(sub.plan.code, profile)
    kit.status = CycleKit.Status.NEEDS_REVIEW if review else CycleKit.Status.SUGGESTED
    kit.save()

    categories = {c.slug: c for c in Category.objects.filter(slug__in=[c["category"] for c in result["categories"]])}
    for cat in result["categories"]:
        for sku_id, qty in cat["lines"]:
            sku = SKU.objects.get(pk=sku_id)
            KitLine.objects.create(kit=kit, category=categories[cat["category"]], sku=sku, quantity=qty,
                                   unit_cost_cents=sku.cost_cents)
    if cycle.status == Cycle.Status.PAID:
        cycle.status = Cycle.Status.CURATION
        cycle.save(update_fields=["status", "updated_at"])
    return kit


def generate_pending_kits(actor=None) -> dict:
    created, failed = 0, []
    for cycle in Cycle.objects.filter(status=Cycle.Status.PAID, subscription__kind=Subscription.Kind.KIT, kit__isnull=True):
        try:
            generate_kit(cycle, actor=actor)
            created += 1
        except DomainError as exc:
            failed.append(f"{cycle.code}: {exc.message}")
    return {"created": created, "failed": failed}


def validate_kit(kit: CycleKit) -> list[str]:
    errors = []
    missing = kit.dog.missing_required_fields()
    if missing:
        errors.append("Cadastro do cão incompleto: " + ", ".join(missing))
    profile = kit.profile_version.data
    by_category: dict[int, int] = {}
    for line in kit.active_lines.select_related("sku__product", "category"):
        compat = engine.check_compatibility(line.sku, profile)
        if compat.status == "blocked":
            errors.append(f"{line.sku.display_name}: incompatível ({compat.reason}).")
        elif compat.status == "unknown":
            errors.append(f"{line.sku.display_name}: {compat.reason}. Trate o cadastro antes de aprovar.")
        if line.sku.product.category_id != line.category_id:
            errors.append(f"{line.sku.display_name} não pertence à categoria {line.category.name}.")
        by_category[line.category_id] = by_category.get(line.category_id, 0) + line.quantity
    for comp_line in kit.composition.lines.select_related("category"):
        got = by_category.get(comp_line.category_id, 0)
        if got != comp_line.quantity:
            errors.append(f"{comp_line.category.name}: {got} de {comp_line.quantity} unidade(s). Nenhuma redução pode ser silenciosa.")
    return errors


@transaction.atomic
def approve_kit(kit: CycleKit, *, actor, note: str = "") -> CycleKit:
    require_role(actor, Roles.CURADOR, Roles.GESTOR)
    kit = CycleKit.objects.select_for_update().get(pk=kit.pk)
    if kit.status not in (CycleKit.Status.SUGGESTED, CycleKit.Status.NEEDS_REVIEW):
        raise DomainError("Este kit não está aguardando aprovação.")
    if kit.cycle.paid_at is None:
        raise DomainError("Ciclo sem pagamento confirmado.")
    errors = validate_kit(kit)
    if errors:
        raise DomainError("Aprovação bloqueada: " + " ".join(errors), code="kit_invalid")
    if kit.status == CycleKit.Status.NEEDS_REVIEW and not note.strip():
        raise DomainError("Kit com exceção exige justificativa na aprovação.")
    kit.status = CycleKit.Status.APPROVED
    kit.approved_by = actor
    kit.approved_at = timezone.now()
    kit.decision_note = note
    kit.save()
    Cycle.objects.filter(pk=kit.cycle_id).update(status=Cycle.Status.APPROVED)
    audit(actor, "kit_approved", kit, reason=note)
    return kit


@transaction.atomic
def reject_kit(kit: CycleKit, *, actor, note: str) -> CycleKit:
    require_role(actor, Roles.CURADOR, Roles.GESTOR)
    if not note.strip():
        raise DomainError("Rejeição exige justificativa.")
    if kit.status == CycleKit.Status.CLOSED:
        raise DomainError("Kit fechado não pode ser rejeitado; registre uma correção.")
    kit.status = CycleKit.Status.REJECTED
    kit.decision_note = note
    kit.save()
    audit(actor, "kit_rejected", kit, reason=note)
    return kit


@transaction.atomic
def substitute_line(line: KitLine, new_sku: SKU, *, actor, justification: str) -> KitLine:
    """CUR-04: troca com equivalência de categoria e unidade; troca incompatível é bloqueada."""
    require_role(actor, Roles.CURADOR, Roles.OPERACAO, Roles.GESTOR)
    if not justification.strip():
        raise DomainError("Substituição exige justificativa.")
    line = KitLine.objects.select_for_update().select_related("kit__cycle").get(pk=line.pk)
    kit = line.kit
    if line.status != KitLine.Status.ACTIVE:
        raise DomainError("Esta linha já foi substituída.")
    if kit.cycle.status in (Cycle.Status.SHIPPED, Cycle.Status.DELIVERED):
        raise DomainError("Kit já expedido. Registre uma ocorrência de reenvio em vez de alterar o conteúdo.")
    if new_sku.product.category_id != line.category_id:
        raise DomainError("O substituto precisa ser da mesma categoria.")
    if new_sku.pk == line.sku_id:
        raise DomainError("Escolha um SKU diferente.")
    compat = engine.check_compatibility(new_sku, kit.profile_version.data)
    if compat.status != "ok":
        raise DomainError(f"Substituição bloqueada: {new_sku.display_name} {compat.reason}.", code="incompatible")
    new_line = KitLine.objects.create(kit=kit, category=line.category, sku=new_sku, quantity=line.quantity,
                                      unit_cost_cents=new_sku.cost_cents, replaces=line, justification=justification,
                                      decided_by=actor)
    line.status = KitLine.Status.SUBSTITUTED
    line.save(update_fields=["status"])
    if kit.status == CycleKit.Status.CLOSED:
        stock.reserve(new_sku, new_line.quantity, key=new_line.reserve_key, reference=kit, actor=actor,
                      reason=f"Substituição no kit {kit.cycle.code}")
        stock.release(line.reserve_key, actor=actor, reason="Substituído")
        from apps.logistics.services import sync_kit_shipment_lines

        sync_kit_shipment_lines(kit)
        kit.snapshot = build_snapshot(kit)
        kit.save(update_fields=["snapshot", "updated_at"])
    audit(actor, "kit_line_substituted", kit, reason=justification,
          changes={"from": line.sku.code, "to": new_sku.code, "quantity": line.quantity})
    return new_line


def build_snapshot(kit: CycleKit) -> dict:
    sub = kit.cycle.subscription
    return {
        "frozen_at": timezone.now().isoformat(),
        "cycle": kit.cycle.code,
        "plan": sub.plan.code,
        "offer": kit.cycle.offer_snapshot,
        "composition": kit.composition.snapshot(),
        "kit_model": kit.kit_model.name if kit.kit_model else None,
        "profile": {"version": kit.profile_version.version, **kit.profile_version.data},
        "engine_version": kit.engine_version,
        "lines": [
            {**line.sku.snapshot(), "kit_line_id": line.pk, "quantity": line.quantity, "unit_cost_cents": line.unit_cost_cents,
             "replaces_sku": line.replaces.sku.code if line.replaces else None, "justification": line.justification}
            for line in kit.active_lines.select_related("sku__product__category", "replaces__sku")
        ],
        "price_cents": kit.cycle.price_cents,
        "shipping_cents": kit.cycle.shipping_cents,
    }


def close_kit(kit: CycleKit, *, actor) -> CycleKit:
    """Reserva o estoque e congela a composição. Ruptura bloqueia até decisão registrada."""
    require_role(actor, Roles.OPERACAO, Roles.CURADOR, Roles.GESTOR)
    with transaction.atomic():
        kit = CycleKit.objects.select_for_update().get(pk=kit.pk)
        if kit.status == CycleKit.Status.CLOSED:
            return kit
        if kit.status != CycleKit.Status.APPROVED:
            raise DomainError("Só kits aprovados pela curadoria podem ser fechados para separação.", code="kit_not_approved")
        try:
            for line in kit.active_lines.select_related("sku"):
                stock.reserve(line.sku, line.quantity, key=line.reserve_key, reference=kit, actor=actor,
                              reason=f"Kit {kit.cycle.code}")
        except stock.InsufficientStock as exc:
            transaction.set_rollback(True)
            failure = exc
        else:
            failure = None
            kit.status = CycleKit.Status.CLOSED
            kit.closed_at = timezone.now()
            kit.snapshot = build_snapshot(kit)
            kit.save()
            Cycle.objects.filter(pk=kit.cycle_id).update(status=Cycle.Status.RESERVED)
            from apps.logistics.services import create_shipment_for_kit

            create_shipment_for_kit(kit)
    if failure is not None:
        raise_alert(OperationalAlert.Kind.STOCKOUT, f"Ruptura no kit {kit.cycle.code}", detail=failure.message, obj=kit,
                    dedupe_key=f"stockout:{kit.pk}:{failure.data.get('sku')}")
        raise DomainError(f"Fechamento bloqueado por ruptura: {failure.message} Substitua o item ou aguarde reposição.",
                          code="stockout")
    audit(actor, "kit_closed", kit)
    return kit


def alert_profile_changed_after_close(dog, version) -> None:
    """PET-04: ciclo fechado conserva a versão anterior e gera alerta operacional."""
    affected = CycleKit.objects.filter(
        dog=dog, status__in=[CycleKit.Status.APPROVED, CycleKit.Status.CLOSED],
    ).exclude(cycle__status__in=[Cycle.Status.DELIVERED, Cycle.Status.CANCELED]).exclude(profile_version=version)
    for kit in affected:
        raise_alert(
            OperationalAlert.Kind.PROFILE_CHANGED,
            f"Perfil de {dog.name} mudou após o fechamento do kit {kit.cycle.code}",
            detail=f"Kit usa a versão {kit.profile_version.version}; nova versão {version.version}. Avalie se exige troca.",
            obj=kit, dedupe_key=f"profile-change:{kit.pk}:{version.version}",
        )
