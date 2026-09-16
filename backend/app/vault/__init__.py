"""
BYOK key vault — the API-side half (Phase 2).

This package can *encrypt* provider keys and *test* them against the provider,
but it cannot decrypt anything: the API process only ever holds the vault's
public key. The decrypt half lives in `backend/runner/vault_decrypt.py` and is
imported by job execution only.
"""
