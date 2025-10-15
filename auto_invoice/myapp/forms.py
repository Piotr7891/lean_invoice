from django import forms
from .models import Customer, Invoice


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address", "vat_id", "iban", "bic"]

    def save(self, owner, commit=True):
        """
        Force ownership on create/update.
        Usage: form.save(owner=request.user)
        """
        obj = super().save(commit=False)
        obj.owner = owner
        if commit:
            obj.save()
        return obj


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_type", "number", "customer", "issue_date", "due_date", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Restrict customer choices to the current user's customers.
        Usage: InvoiceForm(..., owner=request.user)
        """
        self._owner = kwargs.pop("owner", None)
        super().__init__(*args, **kwargs)
        if self._owner is not None:
            self.fields["customer"].queryset = (
                Customer.objects.for_user(self._owner).order_by("name")
            )

    def clean_customer(self):
        """
        Ensure selected customer belongs to the owner (defense in depth).
        """
        cust = self.cleaned_data["customer"]
        if self._owner is not None and cust.owner_id != getattr(self._owner, "id", None):
            raise forms.ValidationError("Selected customer does not belong to you.")
        return cust

    def save(self, owner, commit=True):
        """
        Force ownership on create/update and re-validate cross-tenant constraints.
        Usage: form.save(owner=request.user)
        """
        obj = super().save(commit=False)
        obj.owner = owner
        # Cross-check again in case instance was changed
        if obj.customer_id and obj.customer.owner_id != owner.id:
            raise forms.ValidationError("Selected customer does not belong to you.")
        if commit:
            obj.full_clean()  # triggers model.clean() too
            obj.save()
        return obj
