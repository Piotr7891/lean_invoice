from django import forms
from .models import Customer, Invoice

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address", "vat_id"]

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_type", "number", "customer", "issue_date", "due_date", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
