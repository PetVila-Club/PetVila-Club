from datetime import date

from django.conf import settings
from django.db import models, transaction

from apps.catalog.models import DogSize, Tag
from apps.core.models import TimeStampedModel


class Dog(TimeStampedModel):
    """Perfil de cão. Cada alteração gera uma nova versão imutável (PET-04)."""

    tutor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dogs", verbose_name="tutor")
    name = models.CharField("nome", max_length=80)
    birth_date = models.DateField("data de nascimento", null=True, blank=True)
    estimated_age_years = models.PositiveSmallIntegerField("idade estimada (anos)", null=True, blank=True)
    size = models.CharField("porte", max_length=20, choices=DogSize.choices, blank=True)
    weight_kg = models.DecimalField("peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True)
    breed = models.CharField("raça", max_length=80, blank=True)
    preferences = models.ManyToManyField(Tag, blank=True, related_name="preferred_by", verbose_name="preferências")
    restrictions = models.ManyToManyField(Tag, blank=True, related_name="restricted_for", verbose_name="restrições declaradas")
    notes = models.TextField("observações", blank=True)
    is_active = models.BooleanField("ativo", default=True)
    profile_version = models.PositiveIntegerField("versão do perfil", default=0)

    class Meta:
        verbose_name = "cão"
        verbose_name_plural = "cães"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.tutor.full_name})"

    @property
    def age_years(self) -> int | None:
        if self.birth_date:
            today = date.today()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return self.estimated_age_years

    def missing_required_fields(self) -> list[str]:
        from apps.core.services import get_setting

        required = get_setting("dog_required_fields")
        labels = {"name": "nome", "size": "porte", "weight_kg": "peso", "age": "data de nascimento ou idade estimada"}
        missing = []
        for field in required:
            if field == "age":
                if self.birth_date is None and self.estimated_age_years is None:
                    missing.append(labels["age"])
            elif not getattr(self, field, None):
                missing.append(labels.get(field, field))
        return missing

    def profile_data(self) -> dict:
        return {
            "dog_id": self.pk,
            "name": self.name,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "estimated_age_years": self.estimated_age_years,
            "size": self.size,
            "weight_kg": str(self.weight_kg) if self.weight_kg is not None else None,
            "breed": self.breed,
            "preferences": sorted(self.preferences.values_list("code", flat=True)),
            "restrictions": sorted(self.restrictions.values_list("code", flat=True)),
            "notes": self.notes,
        }

    @transaction.atomic
    def snapshot_version(self) -> "DogProfileVersion":
        """Grava a versão atual do perfil se mudou desde a última."""
        data = self.profile_data()
        last = self.versions.order_by("-version").first()
        if last and last.data == data:
            return last
        locked = Dog.objects.select_for_update().get(pk=self.pk)
        locked.profile_version += 1
        Dog.objects.filter(pk=self.pk).update(profile_version=locked.profile_version)
        self.profile_version = locked.profile_version
        version = DogProfileVersion.objects.create(dog=self, version=locked.profile_version, data=data)
        if last:
            from apps.curation.services import alert_profile_changed_after_close

            alert_profile_changed_after_close(self, version)
        return version


class DogProfileVersion(models.Model):
    dog = models.ForeignKey(Dog, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "versão de perfil"
        verbose_name_plural = "versões de perfil"
        unique_together = [("dog", "version")]
        ordering = ["dog", "-version"]

    def __str__(self):
        return f"{self.dog.name} v{self.version}"
