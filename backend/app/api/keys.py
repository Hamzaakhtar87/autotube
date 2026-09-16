"""
BYOK key vault routes (Phase 2).

  GET    /keys                    which providers have a key + last test result (never the key)
  POST   /keys/{provider}/test    fire the provider's minimal call; stores nothing
  PUT    /keys/{provider}         re-test server-side, then encrypt + upsert
  DELETE /keys/{provider}

The key itself only exists here as a pydantic `SecretStr` (repr/str is
'**********'), is handed to the tester and the sealer, and is gone. No route
returns the ciphertext either.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import ProviderKey, User
from app.services.auth_service import get_current_user
from app.vault.providers import (
    MAX_CREDENTIAL_LENGTH,
    PROVIDER_LABELS,
    Provider,
    credential_fields,
)
from app.vault.seal import KEY_VERSION, VaultPublicKeyMissing, seal_provider_secret
from app.vault.testers import TestResult, run_key_test

router = APIRouter(prefix="/keys", tags=["keys"])


class KeySubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr | None = None
    # Kling only
    access_key: SecretStr | None = None
    secret_key: SecretStr | None = None


class ProviderStatus(BaseModel):
    provider: Provider
    label: str
    fields: list[str]
    configured: bool
    last_tested_at: datetime | None
    last_test_status: str | None


class KeysListResponse(BaseModel):
    providers: list[ProviderStatus]


class TestResponse(BaseModel):
    provider: Provider
    status: str
    ok: bool
    message: str


class SaveResponse(TestResponse):
    saved: bool
    warning: bool


def _credentials(provider: Provider, body: KeySubmission) -> dict[str, str]:
    """Pull the fields this provider needs out of the submission; 422 on shape errors.

    Error text names the field, never its value.
    """
    wanted = credential_fields(provider)
    submitted = {k: v for k, v in body.model_dump().items() if v is not None}
    extra = set(submitted) - set(wanted)
    if extra:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{provider.value} does not take {', '.join(sorted(extra))}; expected {', '.join(wanted)}",
        )
    creds: dict[str, str] = {}
    for field in wanted:
        value = getattr(body, field)
        raw = value.get_secret_value().strip() if value is not None else ""
        if not raw:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} is required for {provider.value}")
        if len(raw) > MAX_CREDENTIAL_LENGTH:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} is longer than {MAX_CREDENTIAL_LENGTH} characters")
        creds[field] = raw
    return creds


def _row(db: Session, user_id: int, provider: Provider) -> ProviderKey | None:
    return (
        db.query(ProviderKey)
        .filter(ProviderKey.user_id == user_id, ProviderKey.provider == provider.value)
        .first()
    )


@router.get("", response_model=KeysListResponse)
def list_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = {r.provider: r for r in db.query(ProviderKey).filter(ProviderKey.user_id == current_user.id).all()}
    providers = []
    for p in Provider:
        row = rows.get(p.value)
        providers.append(
            ProviderStatus(
                provider=p,
                label=PROVIDER_LABELS[p],
                fields=list(credential_fields(p)),
                configured=row is not None,
                last_tested_at=row.last_tested_at if row is not None else None,
                last_test_status=row.last_test_status if row is not None else None,
            )
        )
    return KeysListResponse(providers=providers)


@router.post("/{provider}/test", response_model=TestResponse)
def test_key(
    provider: Provider,
    body: KeySubmission,
    current_user: User = Depends(get_current_user),
):
    result = run_key_test(provider, _credentials(provider, body))
    return TestResponse(provider=provider, status=result.status.value, ok=result.ok, message=result.message)


@router.put("/{provider}", response_model=SaveResponse)
def save_key(
    provider: Provider,
    body: KeySubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creds = _credentials(provider, body)
    # The browser's "test passed" is not trusted; test again here.
    result: TestResult = run_key_test(provider, creds)
    if not result.saveable:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"status": result.status.value, "message": result.message, "saved": False},
        )
    try:
        ciphertext = seal_provider_secret(current_user.id, provider.value, creds)
    except VaultPublicKeyMissing:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Key vault is not configured on this server.")
    finally:
        creds.clear()

    now = datetime.now(timezone.utc)
    row = _row(db, current_user.id, provider)
    if row is None:
        row = ProviderKey(user_id=current_user.id, provider=provider.value)
        db.add(row)
    row.ciphertext = ciphertext
    row.key_version = KEY_VERSION
    row.last_tested_at = now
    row.last_test_status = result.status.value
    db.commit()
    return SaveResponse(
        provider=provider,
        status=result.status.value,
        ok=result.ok,
        message=result.message,
        saved=True,
        warning=not result.ok,
    )


@router.delete("/{provider}")
def delete_key(
    provider: Provider,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _row(db, current_user.id, provider)
    if row is not None:
        db.delete(row)
        db.commit()
    return {"provider": provider.value, "deleted": row is not None}
