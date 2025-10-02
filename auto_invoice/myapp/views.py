from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import Customer, Invoice
from .forms import CustomerForm, InvoiceForm

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

# --- Invoices (header only for now) ---
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
        invoice.delete()  # will cascade delete items due to FK(on_delete=CASCADE)
        messages.success(request, "Invoice removed.")
        return redirect("invoice_list")
    return render(request, "invoices/confirm_delete.html", {"invoice": invoice})

## NEW views for invoice actions
@login_required
def invoice_send(request, pk):
    if request.method != "POST":
        messages.error(request, "Invalid method.")
        return redirect("invoice_list")
    inv = get_object_or_404(Invoice, pk=pk)
    inv.mark_sent()  # for now: only change status (no n8n call yet)
    messages.success(request, f"Invoice {inv.number} marked as Sent.")
    return redirect("invoice_list")

@login_required
def invoice_mark_paid(request, pk):
    if request.method != "POST":
        messages.error(request, "Invalid method.")
        return redirect("invoice_list")
    inv = get_object_or_404(Invoice, pk=pk)
    inv.mark_paid()
    messages.success(request, f"Invoice {inv.number} marked as Paid.")
    return redirect("invoice_list")

@login_required
def invoice_cancel(request, pk):
    if request.method != "POST":
        messages.error(request, "Invalid method.")
        return redirect("invoice_list")
    inv = get_object_or_404(Invoice, pk=pk)
    inv.mark_cancelled()
    messages.success(request, f"Invoice {inv.number} cancelled.")
    return redirect("invoice_list")

