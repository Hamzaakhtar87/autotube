"""
Decrypt side of the BYOK vault. Isolated on purpose — audit this file, not the app.

Reads the vault private key from `VAULT_PRIVATE_KEY` (base64 X25519 secret key),
which exists only as a GitHub Actions secret. The API process never has it, so
even code that imports this module can't open a ciphertext there.

Only `runner.provider_keys.load_provider_key` should import this.
"""
from __future__ import annotations

import base64
import json
import os

from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox

PRIVATE_KEY_ENV = "VAULT_PRIVATE_KEY"
ENVELOPE_VERSION = 1


class VaultDecryptError(Exception):
    """Base class; message never contains key material."""


class VaultPrivateKeyUnavailable(VaultDecryptError):
    pass


class VaultCiphertextInvalid(VaultDecryptError):
    pass


class VaultBindingMismatch(VaultDecryptError):
    pass


def _private_key(explicit: str | bytes | None) -> PrivateKey:
    source = explicit if explicit is not None else os.getenv(PRIVATE_KEY_ENV, "")
    if isinstance(source, bytes):
        raw = source
    else:
        encoded = source.strip()
        if not encoded:
            raise VaultPrivateKeyUnavailable(f"{PRIVATE_KEY_ENV} is not available in this process")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise VaultPrivateKeyUnavailable(f"{PRIVATE_KEY_ENV} is not valid base64") from exc
    try:
        return PrivateKey(raw)
    except Exception as exc:
        raise VaultPrivateKeyUnavailable(f"{PRIVATE_KEY_ENV} is not a valid X25519 secret key") from exc


def open_provider_secret(
    ciphertext_b64: str,
    *,
    expected_user_id: int,
    expected_provider: str,
    private_key: str | bytes | None = None,
) -> dict[str, str]:
    """Return the credential dict sealed by `app.vault.seal.seal_provider_secret`.

    Fails if the private key is missing, the ciphertext was tampered with or
    sealed to another key, or the envelope's (user_id, provider) binding does
    not match the row it was read from.
    """
    sk = _private_key(private_key)
    try:
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
    except Exception as exc:
        raise VaultCiphertextInvalid("ciphertext is not valid base64") from exc
    try:
        plaintext = SealedBox(sk).decrypt(ciphertext)
    except CryptoError as exc:
        raise VaultCiphertextInvalid("ciphertext could not be opened with this key") from exc
    try:
        envelope = json.loads(plaintext)
    except ValueError as exc:
        raise VaultCiphertextInvalid("envelope is not JSON") from exc
    if not isinstance(envelope, dict) or envelope.get("v") != ENVELOPE_VERSION:
        raise VaultCiphertextInvalid("unsupported envelope version")
    if envelope.get("user_id") != int(expected_user_id) or envelope.get("provider") != str(expected_provider):
        raise VaultBindingMismatch("envelope is bound to a different user or provider")
    secret = envelope.get("secret")
    if not isinstance(secret, dict) or not secret:
        raise VaultCiphertextInvalid("envelope has no secret")
    return {str(k): str(v) for k, v in secret.items()}
