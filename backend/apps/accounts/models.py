from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("E-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Tutor ou membro da equipe. Login por e-mail."""

    username = None
    first_name = None
    last_name = None
    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField("nome completo", max_length=160)
    cpf = models.CharField("CPF", max_length=14, blank=True, help_text="Necessário para cobrança no provedor de pagamento.")
    phone = models.CharField("celular", max_length=20, blank=True)

    # PRV-01: marketing separado dos avisos necessários à execução do contrato.
    marketing_opt_in = models.BooleanField("aceita comunicações de marketing", default=False)
    marketing_opt_in_updated_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField("versão dos termos aceitos", max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    asaas_customer_id = models.CharField("ID do cliente no Asaas", max_length=40, blank=True, db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email

    def set_marketing(self, value: bool):
        if self.marketing_opt_in != value:
            self.marketing_opt_in = value
            self.marketing_opt_in_updated_at = timezone.now()


class Address(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField("identificação", max_length=40, default="Casa")
    recipient = models.CharField("destinatário", max_length=160)
    cep = models.CharField("CEP", max_length=9)
    street = models.CharField("logradouro", max_length=200)
    number = models.CharField("número", max_length=20)
    complement = models.CharField("complemento", max_length=100, blank=True)
    district = models.CharField("bairro", max_length=100)
    city = models.CharField("cidade", max_length=100)
    state = models.CharField("UF", max_length=2)
    is_default = models.BooleanField("principal", default=False)

    class Meta:
        verbose_name = "endereço"
        verbose_name_plural = "endereços"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.street}, {self.number} · {self.city}/{self.state}"

    @property
    def cep_digits(self) -> str:
        return "".join(ch for ch in self.cep if ch.isdigit())

    def snapshot(self) -> dict:
        return {
            "address_id": self.pk,
            "recipient": self.recipient,
            "cep": self.cep_digits,
            "street": self.street,
            "number": self.number,
            "complement": self.complement,
            "district": self.district,
            "city": self.city,
            "state": self.state,
        }
