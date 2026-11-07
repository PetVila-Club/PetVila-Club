from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Review(TimeStampedModel):
    """AVL-01/02: uma avaliação editável por linha entregue (e portanto por cão)."""

    class Reaction(models.TextChoices):
        LOVED = "loved", "Amou"
        LIKED = "liked", "Gostou"
        INDIFFERENT = "indifferent", "Indiferente"
        DISLIKED = "disliked", "Não gostou"
        ADVERSE = "adverse", "Teve reação adversa"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    shipment_line = models.OneToOneField("logistics.ShipmentLine", on_delete=models.PROTECT, related_name="review")
    sku = models.ForeignKey("catalog.SKU", on_delete=models.PROTECT, related_name="reviews")
    dog = models.ForeignKey("pets.Dog", null=True, blank=True, on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField("nota", validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField("comentário", blank=True)
    dog_reaction = models.CharField("reação do cão", max_length=20, choices=Reaction.choices, blank=True)
    allow_public = models.BooleanField("autoriza publicação", default=False)
    is_published = models.BooleanField("publicada (moderação)", default=False)
    flagged_for_curation = models.BooleanField("sinalizada para curadoria", default=False)

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ {self.sku.code}" + (f" · {self.dog.name}" if self.dog_id else "")


class ReviewEdit(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="edits")
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "histórico de edição"
        verbose_name_plural = "históricos de edição"
        ordering = ["-created_at"]
