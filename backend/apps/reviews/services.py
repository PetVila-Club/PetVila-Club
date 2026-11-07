from django.db import transaction

from apps.core.exceptions import DomainError
from apps.core.models import OperationalAlert
from apps.core.services import raise_alert
from apps.logistics.models import Shipment, ShipmentLine

from .models import Review, ReviewEdit

NEGATIVE_REACTIONS = {Review.Reaction.DISLIKED, Review.Reaction.ADVERSE}


@transaction.atomic
def upsert_review(user, *, shipment_line_id: int, rating: int, comment: str = "", dog_reaction: str = "",
                  allow_public: bool = False) -> tuple[Review, bool]:
    """Só avalia SKU realmente entregue ao próprio tutor. Reenvio do formulário edita em vez de duplicar."""
    line = (
        ShipmentLine.objects.select_related("shipment", "sku")
        .filter(pk=shipment_line_id, shipment__user=user, shipment__status=Shipment.Status.DELIVERED)
        .first()
    )
    if line is None:
        raise DomainError("Este item não foi entregue a você ou ainda não teve a entrega confirmada.", code="not_delivered",
                          status_code=403)
    if not 1 <= int(rating) <= 5:
        raise DomainError("A nota deve ser de 1 a 5.")
    if dog_reaction and dog_reaction not in Review.Reaction.values:
        raise DomainError("Reação inválida.")
    review = Review.objects.select_for_update().filter(shipment_line=line).first()
    created = review is None
    if review is not None:
        ReviewEdit.objects.create(review=review, data={"rating": review.rating, "comment": review.comment,
                                                       "dog_reaction": review.dog_reaction})
    else:
        review = Review(user=user, shipment_line=line, sku=line.sku, dog_id=line.dog_id)
    review.rating = int(rating)
    review.comment = comment
    review.dog_reaction = dog_reaction
    review.allow_public = allow_public
    if not allow_public:
        review.is_published = False
    negative = review.rating <= 2 or dog_reaction in NEGATIVE_REACTIONS
    review.flagged_for_curation = negative
    review.save()

    if negative:
        # AVL-02: feedback negativo vai para atendimento e para a próxima curadoria, sem virar bloqueio clínico automático.
        from apps.support.services import open_ticket

        open_ticket(user, kind="feedback", subject=f"Avaliação negativa: {line.product_name}",
                    description=f"Nota {review.rating}. Reação: {review.get_dog_reaction_display() or '—'}. {comment}",
                    reference=line.shipment.number, dedupe=f"review:{review.pk}")
        raise_alert(OperationalAlert.Kind.FEEDBACK, f"Feedback negativo em {line.sku_code}",
                    detail=comment, obj=review, dedupe_key=f"review-negative:{review.pk}:{review.rating}:{dog_reaction}")
    return review, created
