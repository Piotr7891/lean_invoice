from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q


# Reusable queryset: Model.objects.for_user(request.user)
class OwnedQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(owner=user)


class Customer(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customers",
        null=True,   # TEMP: allow null to backfill; make non-null after data migration
        blank=True,
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # per-owner uniqueness (was globally unique before)
    vat_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    iban = models.CharField(max_length=34, blank=True, null=True)
    bic = models.CharField(max_length=11, blank=True, null=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="uniq_customer_name_per_owner",
                condition=Q(owner__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["owner", "vat_id"],
                name="uniq_customer_vatid_per_owner",
                condition=Q(owner__isnull=False) & Q(vat_id__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "name"]),
            models.Index(fields=["owner", "vat_id"]),
        ]

    def __str__(self):
        return self.name


class Invoice(models.Model):
    class InvoiceType(models.TextChoices):
        INVOICE = "INV", "Invoice"
        PROFORMA = "PRO", "Proforma"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,   # TEMP: allow null to backfill; make non-null after data migration
        blank=True,
    )
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    invoice_type = models.CharField(
        max_length=3,
        choices=InvoiceType.choices,
        default=InvoiceType.INVOICE,
    )
    # per-owner uniqueness (was globally unique before)
    number = models.CharField(max_length=50)
    issue_date = models.DateField()
    due_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    sent_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "number"],
                name="uniq_invoice_number_per_owner",
                condition=Q(owner__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "number"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

    # Cross-tenant safety: the invoice customer must belong to the same owner
    def clean(self):
        if self.customer_id and self.owner_id and self.customer.owner_id != self.owner_id:
            raise ValidationError("Customer does not belong to the same owner.")

    # --- Convenience status setters ---
    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_paid(self):
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])

    def mark_cancelled(self):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at"])


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # e.g. 19.00 %

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"

    @property
    def total_price(self):
        base = self.quantity * self.unit_price
        return base + (base * self.vat_rate / 100)


class MailAccount(models.Model):
    PROVIDERS = [
        ("gmail", "Gmail"),
        ("m365", "Microsoft 365"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=10, choices=PROVIDERS)
    email = models.EmailField()
    access_token_enc = models.BinaryField(null=True, blank=True)
    refresh_token_enc = models.BinaryField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # UTC expiry time
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "provider", "email")]
