from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import upsert_review


@api_view(["POST"])
def submit_review(request):
    review, created = upsert_review(
        request.user,
        shipment_line_id=int(request.data.get("shipment_line") or 0),
        rating=int(request.data.get("rating") or 0),
        comment=(request.data.get("comment") or "")[:2000],
        dog_reaction=request.data.get("dog_reaction") or "",
        allow_public=bool(request.data.get("allow_public")),
    )
    return Response(
        {"id": review.pk, "rating": review.rating, "comment": review.comment, "dog_reaction": review.dog_reaction,
         "allow_public": review.allow_public, "created": created},
        status=201 if created else 200,
    )
