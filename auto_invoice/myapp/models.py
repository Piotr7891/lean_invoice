from django.db import models
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    vat_id = models.CharField(max_length=50, blank=True, null=True, unique=True)  # tax ID
    created_at = models.DateTimeField(auto_now_add=True)
    iban = models.CharField(max_length=34, blank=True, null=True)  # International Bank Account Number
    bic = models.CharField(max_length=11, blank=True, null=True)   # Bank Identifier Code

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

    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='invoices')
    invoice_type = models.CharField(
        max_length=3,
        choices=InvoiceType.choices,
        default=InvoiceType.INVOICE,
    )
    number = models.CharField(max_length=50, unique=True)
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

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    @property
    def total_amount(self):
        """Sum of all invoice items (including VAT)."""
        return sum(item.total_price for item in self.items.all())

    # --- Convenience status setters ---
    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_paid(self):
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at'])

    def mark_cancelled(self):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancelled_at'])


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
