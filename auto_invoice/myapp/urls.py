from django.urls import path
from . import views
from . import views_oauth, views_mailer_api

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


    # OAuth starts & callbacks
    path("oauth/google/start", views_oauth.google_start, name="oauth_google_start"),
    path("oauth/google/callback", views_oauth.google_callback, name="oauth_google_cb"),
    path("oauth/m365/start", views_oauth.m365_start, name="oauth_m365_start"),
    path("oauth/m365/callback", views_oauth.m365_callback, name="oauth_m365_cb"),

    # n8n <-> app API
    path("api/mailer/token", views_mailer_api.get_mail_token, name="mailer_get_token"),
    path("api/mailer/send", views_mailer_api.gmail_send, name="mailer_gmail_send"),  # only if using Gmail Option A
    path("api/mailer/events", views_mailer_api.mail_events, name="mailer_events"),   # optional for webhooks
]
