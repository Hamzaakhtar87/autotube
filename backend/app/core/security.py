import json
import base64
from cryptography.fernet import Fernet
from app.core import config

# We need a 32 url-safe base64-encoded byte string for Fernet.
# We'll derive it from the SECRET_KEY to keep things stateless.
def get_fernet() -> Fernet:
    # Hash the SECRET_KEY to a consistent 32 bytes and b64 encode it
    import hashlib
    key_bytes = hashlib.sha256(config.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)

def encrypt_dict(data: dict) -> dict:
    """Take a raw dictionary, encrypt it, and return a dictionary wrapping the ciphertext."""
    if not data:
        return data
    # Already encrypted?
    if "encrypted_data" in data:
        return data
    f = get_fernet()
    raw_json = json.dumps(data)
    ciphertext = f.encrypt(raw_json.encode()).decode()
    return {"encrypted_data": ciphertext}

def decrypt_dict(data: dict) -> dict:
    """Take an encrypted wrapper dict and return the raw dictionary."""
    if not data or "encrypted_data" not in data:
        return data
    f = get_fernet()
    ciphertext = data["encrypted_data"].encode()
    try:
        raw_json = f.decrypt(ciphertext).decode()
        return json.loads(raw_json)
    except Exception:
        # In case of corruption or key rotation
        return {}
