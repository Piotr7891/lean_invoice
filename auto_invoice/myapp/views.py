import json
import hmac
import hashlib
import requests

from django.conf import settings
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404

from .models import Customer, Invoice
from .forms import CustomerForm, InvoiceForm


# ------------------------------
# Helpers for n8n webhook calling
# ------------------------------
def _hmac_signature(raw: bytes) -> str | None:
    secret = (settings.HMAC_SHARED_SECRET or "").encode()
    if not secret:
        return None
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()

def _invoice_payload(inv: Invoice) -> dict:
    """Build the payload expected by your n8n workflow. Adjust as needed."""
    payload = {
        "invoice_id": inv.number,
        "issue_date": str(inv.issue_date),
        "due_date": str(inv.due_date),
        "currency": inv.currency,
        "customer": {
            "name": getattr(inv, "customer_name", "") or (inv.customer.name if getattr(inv, "customer", None) else ""),
            "email": getattr(inv, "customer_email", "") or (getattr(inv.customer, "email", "") if getattr(inv, "customer", None) else ""),
        },
        "items": [],
    }
    # If you have related items, map them here:
    # payload["items"] = [
    #     {"name": it.name, "qty": it.quantity, "price": float(it.unit_price)}
    #     for it in inv.items.all()
    # ]
    return payload

def _post_to_n8n(payload: dict, timeout=12) -> tuple[int | None, str | None]:
    """
    Returns (status_code, error_message).
    On success -> (2xx, None). On failure -> (code or None, error text).
    """
    raw = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json"}
    sig = _hmac_signature(raw)
    if sig:
        headers["x-signature"] = sig

    try:
        r = requests.post(settings.N8N_WEBHOOK_URL, data=raw, headers=headers, timeout=timeout)
        return r.status_code, None if r.ok else (r.text[:2000] or f"HTTP {r.status_code}")
    except requests.RequestException as e:
        return None, str(e)


# ------------------------------
# Core pages
# ------------------------------
def home(request):
    return render(request, "home.html")

@login_required
def dashboard(request):
    stats = {
        "customers": Customer.objects.count(),
        "invoices": Invoice.objects.count(),
    }
    return render(request, "dashboard.html", {"stats": stats})

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)           # auto-login after signup
            return redirect("dashboard")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


# ------------------------------
# Customers CRUD
# ------------------------------
@login_required
def customer_list(request):
    customers = Customer.objects.order_by("name")
    return render(request, "customers/list.html", {"customers": customers})

@login_required
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer created.")
            return redirect("customer_list")
    else:
        form = CustomerForm()
    return render(request, "customers/form.html", {"form": form, "title": "New Customer"})

@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer updated.")
            return redirect("customer_list")
    else:
        form = CustomerForm(instance=customer)
    return render(request, "customers/form.html", {"form": form, "title": "Edit Customer"})

@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.delete()
        messages.success(request, "Customer removed.")
        return redirect("customer_list")
    return render(request, "customers/confirm_delete.html", {"customer": customer})


# ------------------------------
# Invoices CRUD
# ------------------------------
@login_required
def invoice_list(request):
    invoices = Invoice.objects.select_related("customer").order_by("-issue_date")
    return render(request, "invoices/list.html", {"invoices": invoices})

@login_required
def invoice_create(request):
    if request.method == "POST":
        form = InvoiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice created.")
            return redirect("invoice_list")
    else:
        form = InvoiceForm()
    return render(request, "invoices/form.html", {"form": form, "title": "New Invoice"})

@login_required
def invoice_update(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice updated.")
            return redirect("invoice_list")
    else:
        form = InvoiceForm(instance=invoice)
    return render(request, "invoices/form.html", {"form": form, "title": "Edit Invoice"})

@login_required
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        invoice.delete()  # cascades if FK(on_delete=CASCADE)
        messages.success(request, "Invoice removed.")
        return redirect("invoice_list")
    return render(request, "invoices/confirm_delete.html", {"invoice": invoice})


# ------------------------------
# Invoice actions (POST-only)
# ------------------------------
@login_required
@require_POST
def invoice_send(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)

    # Only DRAFT can be sent
    if inv.status != Invoice.Status.DRAFT:
        messages.error(request, "Only draft invoices can be sent.")
        return redirect("invoice_list")

    payload = _invoice_payload(inv)
    code, err = _post_to_n8n(payload)

    # Persist debug info if model has those fields (optional)
    if hasattr(inv, "last_webhook_code"):
        inv.last_webhook_code = code or 0
    if hasattr(inv, "last_webhook_error"):
        inv.last_webhook_error = err or ""

    if code and 200 <= code < 300:
        # mark as sent (prefer model helper if present)
        if hasattr(inv, "mark_sent"):
            inv.mark_sent()
        else:
            inv.status = Invoice.Status.SENT
        inv.save()
        messages.success(request, f"Invoice {inv.number} sent to n8n.")
    else:
        inv.save(update_fields=["last_webhook_code", "last_webhook_error"] if hasattr(inv, "last_webhook_code") else None)
        messages.error(request, f"Failed to send invoice {inv.number}: {err or f'HTTP {code}'}")

    return redirect("invoice_list")


@login_required
@require_POST
def invoice_mark_paid(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)

    # Only SENT can be marked as paid
    if inv.status != Invoice.Status.SENT:
        messages.error(request, "Only sent invoices can be marked as paid.")
        return redirect("invoice_list")

    if hasattr(inv, "mark_paid"):
        inv.mark_paid()
    else:
        inv.status = Invoice.Status.PAID
    inv.save()
    messages.success(request, f"Invoice {inv.number} marked as Paid.")
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_cancel(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)

    # Optional: you may restrict cancel to DRAFT only
    # if inv.status != Invoice.Status.DRAFT:
    #     messages.error(request, "Only draft invoices can be cancelled.")
    #     return redirect("invoice_list")

    if hasattr(inv, "mark_cancelled"):
        inv.mark_cancelled()
    else:
        inv.status = Invoice.Status.CANCELED
    inv.save()
    messages.success(request, f"Invoice {inv.number} cancelled.")
    return redirect("invoice_list")
