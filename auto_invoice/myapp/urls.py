from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # Customers
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/edit/", views.customer_update, name="customer_update"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),

    # Invoices (header only for now; items come next)
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/new/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/edit/", views.invoice_update, name="invoice_update"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),

    # NEW actions
    path("invoices/<int:pk>/send/", views.invoice_send, name="invoice_send"),
    path("invoices/<int:pk>/mark-paid/", views.invoice_mark_paid, name="invoice_mark_paid"),
    path("invoices/<int:pk>/cancel/", views.invoice_cancel, name="invoice_cancel"),

    # Auth
    path("signup/", views.signup, name="signup"),
]
