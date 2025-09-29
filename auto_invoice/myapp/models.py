from django.db import models

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
    INVOICE_TYPES = [
        ('INV', 'Invoice'),
        ('PRO', 'Proforma Invoice'),
        ('CN', 'Credit Note'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="invoices")
    invoice_type = models.CharField(max_length=3, choices=INVOICE_TYPES, default='INV')
    number = models.CharField(max_length=50, unique=True)  # e.g. INV-2025-001
    issue_date = models.DateField()
    due_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())


class InvoiceItem(models.Model):
    TAX_RATES = [
        (0.00, '0%'),
        (5.00, '5%'),
        (8.00, '8%'),
        (23.00, '23%'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, choices=TAX_RATES, default=0.00)


    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"

    @property
    def total_price(self):
        base = self.quantity * self.unit_price
        return base + (base * self.vat_rate / 100)
