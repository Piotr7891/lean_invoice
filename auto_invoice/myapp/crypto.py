# myapp/crypto.py
import base64
from cryptography.fernet import Fernet
from django.conf import settings

_fernet = Fernet(settings.FERNET_KEY)  # 32-byte base64 urlsafe key

def enc(s: str) -> bytes:
    return _fernet.encrypt(s.encode())

def dec(b: bytes) -> str:
    return _fernet.decrypt(b).decode()
