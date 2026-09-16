"""
`load_provider_key(user_id, provider, db)` — the one function job execution
calls to get a user's plaintext credentials. Phase 6 wires it into the pipeline.
This is the only permitted importer of `runner.vault_decrypt`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import ProviderKey
from runner.vault_decrypt import VaultDecryptError, open_provider_secret


class ProviderKeyNotConfigured(VaultDecryptError):
    pass


def load_provider_key(user_id: int, provider: str, db: Session) -> dict[str, str]:
    row = (
        db.query(ProviderKey)
        .filter(ProviderKey.user_id == user_id, ProviderKey.provider == str(provider))
        .first()
    )
    if row is None:
        raise ProviderKeyNotConfigured(f"user {user_id} has no {provider} key configured")
    return open_provider_secret(
        row.ciphertext, expected_user_id=row.user_id, expected_provider=row.provider
    )
