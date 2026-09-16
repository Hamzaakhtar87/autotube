"""
Phase 2 test (1): encryption round-trip.

seal (app side, public key only) -> open (runner side, private key) returns the
original credentials; and every way the open can go wrong, does.
"""
import base64
import json

import pytest
from nacl.public import PrivateKey

from app.vault.seal import seal_provider_secret
from runner.vault_decrypt import (
    VaultBindingMismatch,
    VaultCiphertextInvalid,
    VaultPrivateKeyUnavailable,
    open_provider_secret,
)
from tests.planted import PLANTED_API_KEY, PLANTED_KLING_ACCESS_KEY, PLANTED_KLING_SECRET_KEY


@pytest.mark.parametrize(
    "provider, secret",
    [
        ("openai", {"api_key": PLANTED_API_KEY}),
        ("kling", {"access_key": PLANTED_KLING_ACCESS_KEY, "secret_key": PLANTED_KLING_SECRET_KEY}),
    ],
)
def test_round_trip_returns_original(vault_private_key, provider, secret):
    ct = seal_provider_secret(42, provider, secret)
    out = open_provider_secret(ct, expected_user_id=42, expected_provider=provider, private_key=vault_private_key)
    assert out == secret


def test_ciphertext_does_not_contain_plaintext_and_is_randomised():
    a = seal_provider_secret(1, "groq", {"api_key": PLANTED_API_KEY})
    b = seal_provider_secret(1, "groq", {"api_key": PLANTED_API_KEY})
    assert PLANTED_API_KEY not in a
    assert PLANTED_API_KEY not in base64.b64decode(a).decode("latin-1")
    assert a != b, "sealed boxes use a fresh ephemeral key each time"


def test_wrong_private_key_fails(vault_private_key):
    ct = seal_provider_secret(7, "anthropic", {"api_key": PLANTED_API_KEY})
    other = base64.b64encode(bytes(PrivateKey.generate())).decode()
    with pytest.raises(VaultCiphertextInvalid):
        open_provider_secret(ct, expected_user_id=7, expected_provider="anthropic", private_key=other)


def test_binding_mismatch_fails(vault_private_key):
    ct = seal_provider_secret(7, "anthropic", {"api_key": PLANTED_API_KEY})
    with pytest.raises(VaultBindingMismatch):
        open_provider_secret(ct, expected_user_id=8, expected_provider="anthropic", private_key=vault_private_key)
    with pytest.raises(VaultBindingMismatch):
        open_provider_secret(ct, expected_user_id=7, expected_provider="openai", private_key=vault_private_key)


def test_tampered_ciphertext_fails(vault_private_key):
    ct = seal_provider_secret(7, "seedance", {"api_key": PLANTED_API_KEY})
    raw = bytearray(base64.b64decode(ct))
    raw[-1] ^= 0x01
    with pytest.raises(VaultCiphertextInvalid):
        open_provider_secret(base64.b64encode(bytes(raw)).decode(), expected_user_id=7, expected_provider="seedance", private_key=vault_private_key)
    with pytest.raises(VaultCiphertextInvalid):
        open_provider_secret("not base64!", expected_user_id=7, expected_provider="seedance", private_key=vault_private_key)


def test_no_private_key_in_this_process():
    """The API process has no VAULT_PRIVATE_KEY; decrypt must refuse, not fall back."""
    import os
    assert "VAULT_PRIVATE_KEY" not in os.environ
    ct = seal_provider_secret(7, "veo", {"api_key": PLANTED_API_KEY})
    with pytest.raises(VaultPrivateKeyUnavailable):
        open_provider_secret(ct, expected_user_id=7, expected_provider="veo")


def test_error_messages_never_carry_key_material(vault_private_key):
    ct = seal_provider_secret(7, "gemini", {"api_key": PLANTED_API_KEY})
    for exc_type, kwargs in [
        (VaultBindingMismatch, dict(expected_user_id=9, expected_provider="gemini", private_key=vault_private_key)),
        (VaultPrivateKeyUnavailable, dict(expected_user_id=7, expected_provider="gemini")),
    ]:
        with pytest.raises(exc_type) as ei:
            open_provider_secret(ct, **kwargs)
        assert PLANTED_API_KEY not in str(ei.value)
        assert vault_private_key not in str(ei.value)


def test_envelope_shape(vault_private_key):
    """What the runner actually decrypts: a versioned JSON envelope bound to user+provider."""
    from nacl.public import PrivateKey as _PK, SealedBox
    ct = seal_provider_secret(3, "kling", {"access_key": "a", "secret_key": "b"})
    sk = _PK(base64.b64decode(vault_private_key))
    env = json.loads(SealedBox(sk).decrypt(base64.b64decode(ct)))
    assert env == {"v": 1, "user_id": 3, "provider": "kling", "secret": {"access_key": "a", "secret_key": "b"}}
