"""Signup KYC fields: full name, date of birth, and a national ID or
passport number. This is deliberately NOT identity verification -- no
document image, no liveness check, no third-party verification provider.
It's self-attested data collected at signup, stored, and nothing more.
Anyone can type anything here; don't build downstream logic that treats
a filled-in ID number as a verified identity.

The ID number specifically is real, sensitive government-ID data, so it's
encrypted at rest (Fernet, symmetric) rather than stored as plaintext next
to the password hash -- name/DOB stay plaintext since they're needed for
display and are far less sensitive on their own. If
GATEWAY_KYC_ENCRYPTION_KEY is ever lost, previously-stored ID numbers
become permanently unreadable (fine here: nothing downstream ever reads
them back programmatically, they're just retained records)."""
import os

from cryptography.fernet import Fernet, InvalidToken

_KEY = os.environ.get("GATEWAY_KYC_ENCRYPTION_KEY")
_fernet = Fernet(_KEY.encode()) if _KEY else None

VALID_ID_TYPES = {"nic", "passport"}


def configured():
    return _fernet is not None


def encrypt_id_number(id_number):
    if not _fernet:
        raise RuntimeError("GATEWAY_KYC_ENCRYPTION_KEY not set")
    return _fernet.encrypt(id_number.encode()).decode()


def decrypt_id_number(token):
    if not _fernet:
        raise RuntimeError("GATEWAY_KYC_ENCRYPTION_KEY not set")
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return None
