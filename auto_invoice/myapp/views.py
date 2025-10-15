import json
import hmac
import hashlib
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Customer, Invoice
from .forms import CustomerForm, InvoiceForm


# ------------------------------
# Helpers for n8n webhook calling
# ------------------------------
def _hmac_signature(raw: bytes) -> str | None:
    secret = (getattr(settings, "HMAC_SHARED_SECRET", "") or "").encode()
    if not secret:
        return None
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()


def _invoice_payload(inv: Invoice) -> dict:
    """
    Build the payload expected by your n8n workflow.
    """
    currency = getattr(inv, "currency", "RON")  # default until you add a real field

    payload = {
        "invoice_pk": inv.pk,                 # DB id for safe lookups
        "invoice_id": inv.number,             # kept for backward-compat
        "issue_date": str(inv.issue_date),
        "due_date": str(inv.due_date),
        "currency": currency,
        "customer": {
            "name": inv.customer.name if getattr(inv, "customer", None) else "",
            "email": getattr(inv.customer, "email", "") if getattr(inv, "customer", None) else "",
        },
        "items": [
            {
                "description": it.description,
                "qty": float(it.quantity),
                "unit_price": float(it.unit_price),
                "vat_rate": float(it.vat_rate),
                "total_price": float(it.total_price),
            }
            for it in inv.items.all()
        ],
        "totals": {
            "grand_total": float(inv.total_amount),
        },
        "meta": {
            "status": inv.status,
            "type": inv.invoice_type,
            "number": inv.number,
        },
        "owner": {"user_id": inv.owner_id},
    }
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
        "customers": Customer.objects.filter(owner=request.user).count(),
        "invoices":   Invoice.objects.filter(owner=request.user).count(),
    }
    return render(request, "dashboard.html", {"stats": stats})


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)  # auto-login after signup
            return redirect("dashboard")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


# ------------------------------
# Customers CRUD
# ------------------------------
@login_required
def customer_list(request):
    customers = Customer.objects.filter(owner=request.user).order_by("name")
    return render(request, "customers/list.html", {"customers": customers})


@login_required
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save(owner=request.user)
            messages.success(request, "Customer created.")
            return redirect("customer_list")
    else:
        form = CustomerForm()
    return render(request, "customers/form.html", {"form": form, "title": "New Customer"})


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk, owner=request.user)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save(owner=request.user)
            messages.success(request, "Customer updated.")
            return redirect("customer_list")
    else:
        form = CustomerForm(instance=customer)
    return render(request, "customers/form.html", {"form": form, "title": "Edit Customer"})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk, owner=request.user)
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
    invoices = (
        Invoice.objects
        .filter(owner=request.user)
        .select_related("customer")
        .order_by("-issue_date", "-id")
    )
    return render(request, "invoices/list.html", {"invoices": invoices})


@login_required
def invoice_create(request):
    if request.method == "POST":
        form = InvoiceForm(request.POST, owner=request.user)
        if form.is_valid():
            form.save(owner=request.user)
            messages.success(request, "Invoice created.")
            return redirect("invoice_list")
    else:
        form = InvoiceForm(owner=request.user)
    return render(request, "invoices/form.html", {"form": form, "title": "New Invoice"})


@login_required
def invoice_update(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, owner=request.user)
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, owner=request.user)
        if form.is_valid():
            form.save(owner=request.user)
            messages.success(request, "Invoice updated.")
            return redirect("invoice_list")
    else:
        form = InvoiceForm(instance=invoice, owner=request.user)
    return render(request, "invoices/form.html", {"form": form, "title": "Edit Invoice"})


@login_required
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, owner=request.user)
    if request.method == "POST":
        invoice.delete()
        messages.success(request, "Invoice removed.")
        return redirect("invoice_list")
    return render(request, "invoices/confirm_delete.html", {"invoice": invoice})


# ------------------------------
# Invoice actions (POST-only)
# ------------------------------
@login_required
@require_POST
def invoice_send(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, owner=request.user)

    if inv.status != Invoice.Status.DRAFT:
        messages.error(request, "Only draft invoices can be sent.")
        return redirect("invoice_list")

    payload = _invoice_payload(inv)
    code, err = _post_to_n8n(payload)

    if hasattr(inv, "last_webhook_code"):
        inv.last_webhook_code = code or 0
    if hasattr(inv, "last_webhook_error"):
        inv.last_webhook_error = err or ""

    if code and 200 <= code < 300:
        inv.mark_sent()
        messages.success(request, f"Invoice {inv.number} sent to n8n.")
    else:
        if hasattr(inv, "last_webhook_code") or hasattr(inv, "last_webhook_error"):
            inv.save(update_fields=[f for f in ["last_webhook_code", "last_webhook_error"] if hasattr(inv, f)])
        messages.error(request, f"Failed to send invoice {inv.number}: {err or f'HTTP {code}'}")

    return redirect("invoice_list")


@login_required
@require_POST
def invoice_mark_paid(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, owner=request.user)

    if inv.status != Invoice.Status.SENT:
        messages.error(request, "Only sent invoices can be marked as paid.")
        return redirect("invoice_list")

    inv.mark_paid()
    messages.success(request, f"Invoice {inv.number} marked as Paid.")
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_cancel(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, owner=request.user)

    if inv.status == Invoice.Status.PAID:
        messages.error(request, "Paid invoices cannot be cancelled.")
        return redirect("invoice_list")

    inv.mark_cancelled()
    messages.success(request, f"Invoice {inv.number} cancelled.")
    return redirect("invoice_list")
