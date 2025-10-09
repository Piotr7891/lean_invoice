import json, hmac, hashlib, requests
from django.conf import settings

def _hmac_signature(raw: bytes) -> str | None:
    secret = (settings.HMAC_SHARED_SECRET or "").encode()
    if not secret:
        return None
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()

def post_to_n8n(payload: dict, timeout=12) -> tuple[int | None, str | None]:
    """
    Returns (status_code, error_message). On success -> (2xx, None).
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
