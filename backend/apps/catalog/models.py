from django.db import models

from apps.core.models import TimeStampedModel


class DogSize(models.TextChoices):
    PEQUENO = "pequeno", "Pequeno"
    MEDIO = "medio", "Médio"
    GRANDE = "grande", "Grande"


class Category(TimeStampedModel):
    """Categoria de produto. As categorias de kit formam a composição dos planos."""

    slug = models.SlugField(unique=True)
    name = models.CharField("nome", max_length=80)
    description = models.CharField("descrição", max_length=255, blank=True)
    is_kit_category = models.BooleanField("usada na composição de kits", default=False)
    show_in_store = models.BooleanField("exibir na loja", default=True)
    sort = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["sort", "name"]

    def __str__(self):
        return self.name


class StoreCategory(TimeStampedModel):
    """Navegação da loja (menu, vitrine): departamento > subcategoria.

    Independente de Category, que define a composição dos kits e a curadoria.
    """

    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children",
                               verbose_name="departamento (vazio = é um departamento)")
    slug = models.SlugField(unique=True)
    name = models.CharField("nome", max_length=80)
    sort = models.PositiveIntegerField("ordem", default=0)
    is_active = models.BooleanField("exibir na loja", default=True)

    class Meta:
        verbose_name = "categoria da loja"
        verbose_name_plural = "categorias da loja (menu)"
        ordering = ["sort", "name"]

    def __str__(self):
        return f"{self.parent.name} › {self.name}" if self.parent_id else self.name


class Tag(models.Model):
    """Vocabulário de ingredientes, materiais e características usado em SKUs e cães (PET-02)."""

    class Kind(models.TextChoices):
        INGREDIENT = "ingredient", "Ingrediente"
        MATERIAL = "material", "Material"
        FEATURE = "feature", "Característica"

    code = models.SlugField("código", unique=True)
    name = models.CharField("nome", max_length=80)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)

    class Meta:
        verbose_name = "atributo"
        verbose_name_plural = "atributos (ingredientes, materiais, características)"
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display().lower()})"


class Product(TimeStampedModel):
    name = models.CharField("nome", max_length=160)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name="categoria")
    store_category = models.ForeignKey(StoreCategory, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="products", verbose_name="categoria na loja")
    short_description = models.CharField("resumo", max_length=200, blank=True)
    description = models.TextField("descrição", blank=True)
    conservation = models.TextField("instruções de conservação", blank=True)
    image = models.ImageField("foto", upload_to="products/", blank=True)
    image_url = models.CharField("URL da foto (alternativa)", max_length=400, blank=True)
    is_active = models.BooleanField("ativo", default=True)
    is_recurring_food = models.BooleanField("disponível como ração recorrente", default=False)
    is_originals = models.BooleanField("PetVila Originals", default=False)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["category__sort", "name"]

    def __str__(self):
        return self.name

    @property
    def picture(self) -> str:
        if self.image:
            return self.image.url
        return self.image_url


class SKU(TimeStampedModel):
    """Unidade vendável/entregue. Inativos permanecem no histórico (LOJ-01)."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="skus", verbose_name="produto")
    code = models.CharField("SKU", max_length=40, unique=True)
    variant_name = models.CharField("variante", max_length=80, blank=True, help_text="Ex.: 300 g, tamanho M")
    unit_description = models.CharField("unidade comercial", max_length=80, default="1 unidade")

    price_cents = models.PositiveIntegerField("preço (centavos)", null=True, blank=True)
    member_price_cents = models.PositiveIntegerField("preço de assinante (centavos)", null=True, blank=True)
    cost_cents = models.PositiveIntegerField("custo atual (centavos)", default=0)

    weight_g = models.PositiveIntegerField("peso com embalagem (g)", null=True, blank=True)
    net_weight_g = models.PositiveIntegerField("peso líquido (g)", null=True, blank=True)
    length_cm = models.DecimalField("comprimento (cm)", max_digits=6, decimal_places=1, null=True, blank=True)
    width_cm = models.DecimalField("largura (cm)", max_digits=6, decimal_places=1, null=True, blank=True)
    height_cm = models.DecimalField("altura (cm)", max_digits=6, decimal_places=1, null=True, blank=True)

    # PET-02: compatibilidade. Lista vazia de portes = informação desconhecida (exige revisão).
    contains = models.ManyToManyField(Tag, blank=True, related_name="skus", verbose_name="contém (ingredientes/materiais)")
    suitable_sizes = models.JSONField("portes adequados", default=list, blank=True)
    attributes_complete = models.BooleanField(
        "informação de compatibilidade completa", default=False,
        help_text="Marque só depois de conferir ingredientes, materiais e porte. Sem isso o SKU vai para revisão humana.",
    )
    requires_refrigeration = models.BooleanField("exige refrigeração", default=False)
    tracks_lots = models.BooleanField("controla lote e validade", default=False)

    ncm = models.CharField("NCM", max_length=10, blank=True)
    fiscal_notes = models.CharField("observações fiscais", max_length=200, blank=True)

    is_active = models.BooleanField("ativo", default=True)
    sellable_in_store = models.BooleanField("vendável na loja avulsa", default=True)

    class Meta:
        verbose_name = "SKU"
        verbose_name_plural = "SKUs"
        ordering = ["product__name", "code"]

    def __str__(self):
        return f"{self.code} · {self.product.name}{' ' + self.variant_name if self.variant_name else ''}"

    @property
    def display_name(self) -> str:
        return f"{self.product.name}{' · ' + self.variant_name if self.variant_name else ''}"

    def missing_sale_data(self) -> list[str]:
        missing = []
        if self.price_cents is None or self.price_cents <= 0:
            missing.append("preço")
        if not self.weight_g:
            missing.append("peso")
        if not (self.length_cm and self.width_cm and self.height_cm):
            missing.append("dimensões")
        if not self.product.description:
            missing.append("descrição")
        if self.requires_refrigeration:
            missing.append("cadeia de refrigeração não homologada")
        return missing

    def available_quantity(self) -> int:
        level = getattr(self, "stock", None)
        return level.available if level else 0

    def is_sellable(self) -> bool:
        return (
            self.is_active
            and self.product.is_active
            and self.sellable_in_store
            and not self.missing_sale_data()
            and self.available_quantity() > 0
        )

    def snapshot(self) -> dict:
        return {
            "sku_id": self.pk,
            "sku_code": self.code,
            "product_name": self.product.name,
            "variant_name": self.variant_name,
            "unit_description": self.unit_description,
            "category": self.product.category.slug,
        }
