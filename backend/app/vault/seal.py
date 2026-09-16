"""
Encrypt-only side of the vault.

Scheme: libsodium sealed box (X25519 + XSalsa20-Poly1305, ephemeral sender key)
via PyNaCl. The API knows only the recipient *public* key (`VAULT_PUBLIC_KEY`),
so this module — and therefore this process — cannot reverse what it writes.
The matching private key is a GitHub Actions secret read by
`backend/runner/vault_decrypt.py` inside the job runner.

The plaintext is a small JSON envelope carrying the owning `user_id` and the
`provider`; the decrypt side refuses to open an envelope whose binding doesn't
match the row it was loaded from, so a ciphertext copied onto another user's
or provider's row is useless.
"""
import base64
import json
import os

from nacl.public import PublicKey, SealedBox

ENVELOPE_VERSION = 1
KEY_VERSION = 1  # bump when VAULT_PUBLIC_KEY is rotated

PUBLIC_KEY_ENV = "VAULT_PUBLIC_KEY"


class VaultPublicKeyMissing(RuntimeError):
    pass


def _public_key() -> PublicKey:
    raw = os.getenv(PUBLIC_KEY_ENV, "").strip()
    if not raw:
        raise VaultPublicKeyMissing(f"{PUBLIC_KEY_ENV} is not configured")
    try:
        return PublicKey(base64.b64decode(raw, validate=True))
    except Exception as exc:  # malformed base64 / wrong length
        raise VaultPublicKeyMissing(f"{PUBLIC_KEY_ENV} is not a valid base64 X25519 public key") from exc


def public_key_configured() -> bool:
    try:
        _public_key()
        return True
    except VaultPublicKeyMissing:
        return False


def seal_provider_secret(user_id: int, provider: str, secret: dict) -> str:
    """Return base64 ciphertext for `secret` bound to (user_id, provider)."""
    envelope = {
        "v": ENVELOPE_VERSION,
        "user_id": int(user_id),
        "provider": str(provider),
        "secret": {k: str(v) for k, v in secret.items()},
    }
    plaintext = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    ciphertext = SealedBox(_public_key()).encrypt(plaintext)
    return base64.b64encode(ciphertext).decode()
