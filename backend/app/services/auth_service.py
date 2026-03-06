"""
Authentication Service
Handles user registration, login, JWT tokens, and password management.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import User, RefreshToken, SubscriptionTier
from app.core import config


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for extracting token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# Token configuration
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    # python-jose requires 'sub' to be a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def create_refresh_token() -> str:
    """Generate a secure random refresh token."""
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate an access token."""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def create_verification_token(user_id: int) -> str:
    """Create a secure email verification token."""
    expire = datetime.utcnow() + timedelta(hours=24) # Valid for 24h
    to_encode = {"sub": str(user_id), "type": "verify_email", "exp": expire}
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_verification_token(token: str) -> Optional[int]:
    """Decode a verification token to get the user ID."""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("type") != "verify_email":
            return None
        return int(payload.get("sub"))
    except Exception:
        return None


# ============================================================================
# USER CRUD OPERATIONS
# ============================================================================

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email address."""
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, email: str, password: str, full_name: Optional[str] = None) -> User:
    """Create a new user."""
    # Check if email already exists
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=email.lower(),
        password_hash=get_password_hash(password),
        full_name=full_name,
        subscription_tier=SubscriptionTier.FREE,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ============================================================================
# REFRESH TOKEN OPERATIONS
# ============================================================================

def create_user_refresh_token(db: Session, user_id: int) -> RefreshToken:
    """Create and store a new refresh token for a user."""
    token = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    refresh_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(refresh_token)
    db.commit()
    db.refresh(refresh_token)
    return refresh_token


def validate_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """Validate a refresh token and return it if valid."""
    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    return refresh_token


def revoke_refresh_token(db: Session, token: str) -> bool:
    """Revoke a refresh token."""
    refresh_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if refresh_token:
        refresh_token.revoked = True
        db.commit()
        return True
    return False


def revoke_all_user_tokens(db: Session, user_id: int):
    """Revoke all refresh tokens for a user (logout everywhere)."""
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()


# ============================================================================
# DEPENDENCY: GET CURRENT USER
# ============================================================================

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Optional user dependency - returns None if not authenticated."""
    if not token:
        return None
    
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


# ============================================================================
# SUBSCRIPTION TIER UTILITIES
# ============================================================================

TIER_LIMITS = {
    SubscriptionTier.FREE: {"videos_per_month": 3},
    SubscriptionTier.PRO: {"videos_per_month": 30},
    SubscriptionTier.ENTERPRISE: {"videos_per_month": 999999},  # Effectively unlimited
}


def get_tier_limit(tier: str) -> int:
    """Get the video limit for a subscription tier."""
    try:
        tier_enum = SubscriptionTier(tier)
        return TIER_LIMITS.get(tier_enum, {}).get("videos_per_month", 3)
    except ValueError:
        return 3  # Default to free tier limit


def can_create_video(user: User) -> bool:
    """Check if user can create another video based on their tier and usage."""
    limit = get_tier_limit(user.subscription_tier)
    if limit >= 999999:
        return True
    return user.videos_generated_this_month < limit


def increment_video_usage(db: Session, user: User):
    """Increment the user's monthly video count."""
    user.videos_generated_this_month += 1
    db.commit()


def reset_monthly_usage_if_needed(db: Session, user: User):
    """Reset usage if it's a new month."""
    if user.usage_reset_at:
        now = datetime.utcnow()
        if now.month != user.usage_reset_at.month or now.year != user.usage_reset_at.year:
            user.videos_generated_this_month = 0
            user.usage_reset_at = now
            db.commit()
