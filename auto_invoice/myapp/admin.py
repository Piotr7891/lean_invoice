from django.contrib import admin
from .models import Customer, Invoice, InvoiceItem
from .models import MailAccount

admin.site.register(Customer)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
# Register your models here.

# myapp/admin.py

@admin.register(MailAccount)
class MailAccountAdmin(admin.ModelAdmin):
    list_display = ("user","provider","email","expires_at","created_at")
    search_fields = ("email","user__username")
