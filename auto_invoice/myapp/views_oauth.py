# myapp/views_oauth.py
import requests
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import timezone
from .models import MailAccount
from .crypto import enc

# --- GOOGLE ---
@login_required
def google_start(request):
    base = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.send",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    q = "&".join(f"{k}={requests.utils.quote(v)}" for k,v in params.items())
    return redirect(f"{base}?{q}")

@login_required
def google_callback(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }, timeout=20).json()

    access_token = r["access_token"]
    refresh_token = r.get("refresh_token", "")
    expires_in = int(r.get("expires_in", 3500))
    expires_at = timezone.now() + timedelta(seconds=expires_in-60)

    prof = requests.get(
        "https://www.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    ).json()
    email = prof["emailAddress"]

    MailAccount.objects.update_or_create(
        user=request.user, provider="gmail", email=email,
        defaults={
            "access_token_enc": enc(access_token),
            "refresh_token_enc": enc(refresh_token),
            "expires_at": expires_at,
        }
    )
    return redirect("/settings/mailer?connected=gmail")

# --- MICROSOFT ---
@login_required
def m365_start(request):
    base = f"https://login.microsoftonline.com/{settings.MS_TENANT}/oauth2/v2.0/authorize"
    scope = " ".join(["Mail.Send","offline_access","openid","profile","User.Read"])
    params = {
        "client_id": settings.MS_OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.MS_REDIRECT_URI,
        "response_mode": "query",
        "scope": scope,
    }
    q = "&".join(f"{k}={requests.utils.quote(v)}" for k,v in params.items())
    return redirect(f"{base}?{q}")

@login_required
def m365_callback(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code")
    r = requests.post(
        f"https://login.microsoftonline.com/{settings.MS_TENANT}/oauth2/v2.0/token",
        data={
            "client_id": settings.MS_OAUTH_CLIENT_ID,
            "client_secret": settings.MS_OAUTH_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.MS_REDIRECT_URI,
        }, timeout=20
    ).json()

    access_token = r["access_token"]
    refresh_token = r.get("refresh_token","")
    expires_in = int(r.get("expires_in", 3500))
    expires_at = timezone.now() + timedelta(seconds=expires_in-60)

    me = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    ).json()
    email = me.get("mail") or me.get("userPrincipalName")

    MailAccount.objects.update_or_create(
        user=request.user, provider="m365", email=email,
        defaults={
            "access_token_enc": enc(access_token),
            "refresh_token_enc": enc(refresh_token),
            "expires_at": expires_at,
        }
    )
    return redirect("/settings/mailer?connected=m365")
