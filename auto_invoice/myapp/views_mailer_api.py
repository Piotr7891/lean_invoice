# myapp/views_mailer_api.py
import base64, hashlib, hmac, json, requests
from datetime import timedelta
from email.message import EmailMessage
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from .models import MailAccount
from .crypto import enc, dec

def _hmac_ok(raw: bytes, header_sig: str|None) -> bool:
    secret = (settings.HMAC_SHARED_SECRET or "").encode()
    if not secret or not header_sig:
        return False
    calc = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    return header_sig == calc

def _refresh_gmail(ma: MailAccount):
    rt = dec(ma.refresh_token_enc) if ma.refresh_token_enc else ""
    if not rt:
        return
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": rt,
        "grant_type": "refresh_token",
    }, timeout=20).json()
    if "access_token" in r:
        ma.access_token_enc = enc(r["access_token"])
        ma.expires_at = timezone.now() + timedelta(seconds=int(r.get("expires_in", 3500))-60)
        if r.get("refresh_token"):
            ma.refresh_token_enc = enc(r["refresh_token"])
        ma.save(update_fields=["access_token_enc","expires_at","refresh_token_enc"])

def _refresh_m365(ma: MailAccount):
    rt = dec(ma.refresh_token_enc) if ma.refresh_token_enc else ""
    if not rt:
        return
    r = requests.post(
        f"https://login.microsoftonline.com/{settings.MS_TENANT}/oauth2/v2.0/token",
        data={
            "client_id": settings.MS_OAUTH_CLIENT_ID,
            "client_secret": settings.MS_OAUTH_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": rt,
        }, timeout=20
    ).json()
    if "access_token" in r:
        ma.access_token_enc = enc(r["access_token"])
        ma.expires_at = timezone.now() + timedelta(seconds=int(r.get("expires_in", 3500))-60)
        if r.get("refresh_token"):
            ma.refresh_token_enc = enc(r["refresh_token"])
        ma.save(update_fields=["access_token_enc","expires_at","refresh_token_enc"])

@require_GET
def get_mail_token(request):
    # HMAC over the raw query string
    header_sig = request.headers.get("X-Signature")
    raw = (request.META.get("QUERY_STRING") or "").encode()
    if not _hmac_ok(raw, header_sig):
        return HttpResponseForbidden("Bad signature")

    user_id = request.GET.get("user_id")
    provider = request.GET.get("provider")  # optional
    if not user_id:
        return HttpResponseBadRequest("Missing user_id")

    qs = MailAccount.objects.filter(user_id=user_id)
    if provider:
        qs = qs.filter(provider=provider)
    ma = qs.order_by("provider").first()
    if not ma:
        return JsonResponse({"error":"no_mail_account"}, status=404)

    if not ma.expires_at or ma.expires_at <= timezone.now():
        (_refresh_gmail if ma.provider=="gmail" else _refresh_m365)(ma)

    return JsonResponse({
        "provider": ma.provider,
        "from": ma.email,
        "access_token": dec(ma.access_token_enc),
        "expires_at": int(ma.expires_at.timestamp()) if ma.expires_at else None,
    })

# Gmail Option A: backend sends
@csrf_exempt
@require_POST
def gmail_send(request):
    header_sig = request.headers.get("X-Signature")
    raw = request.body
    if not _hmac_ok(raw, header_sig):
        return HttpResponseForbidden("Bad signature")

    data = json.loads(raw.decode())
    user_id = data.get("user_id")
    if not user_id:
        return HttpResponseBadRequest("Missing user_id")
    to = data["to"]; subj = data["subject"]; html = data["html"]
    from_addr = data["from"]; pdf_name = data["pdf_name"]; pdf_b64 = data["pdf_base64"]

    ma = MailAccount.objects.filter(user_id=user_id, provider="gmail").first()
    if not ma:
        return JsonResponse({"error":"no_gmail_account"}, status=404)
    if not ma.expires_at or ma.expires_at <= timezone.now():
        _refresh_gmail(ma)
    token = dec(ma.access_token_enc)

    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = from_addr
    msg["Subject"] = subj
    msg["Reply-To"] = from_addr
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    pdf_bytes = base64.b64decode(pdf_b64)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_name)

    raw_urlsafe = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")

    r = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"raw": raw_urlsafe},
        timeout=25,
    )
    if r.status_code >= 300:
        return JsonResponse({"error":"gmail_send_failed","detail":r.text}, status=502)
    return JsonResponse({"ok": True})

# Optional: provider webhooks
@csrf_exempt
@require_POST
def mail_events(request):
    # TODO: validate provider signature or re-use HMAC, parse payload and persist events
    return JsonResponse({"ok": True})
