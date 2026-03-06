"""
Authentication API Endpoints
Handles user registration, login, token refresh, and profile management.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import User
from app.services.auth_service import (
    create_user,
    authenticate_user,
    create_access_token,
    create_user_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    get_current_user,
    get_tier_limit,
    get_user_by_email,
    verify_password,
    get_password_hash,
    create_verification_token,
    decode_verification_token,
)
from app.services.email_service import email_service


router = APIRouter(prefix="/auth")


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_verified: bool
    subscription_tier: str
    videos_generated_this_month: int
    videos_limit: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Validate password strength
    if len(user_in.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    user = create_user(
        db=db,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name
    )
    
    # Send verification email
    token = create_verification_token(user.id)
    email_service.send_verification_email(user.email, token)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_verified=user.is_verified,
        subscription_tier=user.subscription_tier,
        videos_generated_this_month=user.videos_generated_this_month,
        videos_limit=get_tier_limit(user.subscription_tier),
        created_at=user.created_at
    )


@router.post("/login", response_model=TokenResponse)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    Returns access token in response body and sets refresh token as httpOnly cookie.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_user_refresh_token(db, user.id)
    
    # Set refresh token as httpOnly cookie (more secure than localStorage)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token.token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )
    
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Refresh the access token using the refresh token cookie.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )
    
    token_obj = validate_refresh_token(db, refresh_token)
    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user = token_obj.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    # Create new access token
    access_token = create_access_token(data={"sub": user.id})
    
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Logout the current session by revoking the refresh token.
    """
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    
    # Clear the cookie
    response.delete_cookie("refresh_token")
    
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout from all devices by revoking all refresh tokens.
    """
    revoke_all_user_tokens(db, current_user.id)
    response.delete_cookie("refresh_token")
    
    return MessageResponse(message="Successfully logged out from all devices")


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_verified=current_user.is_verified,
        subscription_tier=current_user.subscription_tier,
        videos_generated_this_month=current_user.videos_generated_this_month,
        videos_limit=get_tier_limit(current_user.subscription_tier),
        created_at=current_user.created_at
    )


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None


@router.patch("/me", response_model=UserResponse)
def update_profile(
    updates: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the current user's profile."""
    if updates.full_name is not None:
        current_user.full_name = updates.full_name
    
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_verified=current_user.is_verified,
        subscription_tier=current_user.subscription_tier,
        videos_generated_this_month=current_user.videos_generated_this_month,
        videos_limit=get_tier_limit(current_user.subscription_tier),
        created_at=current_user.created_at
    )


# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


import secrets as _secrets
import time as _time
from threading import Lock as _Lock

# In-memory password reset tokens (production would use Redis or DB)
_reset_tokens: dict = {}
_reset_lock = _Lock()
RESET_TOKEN_EXPIRY = 3600  # 1 hour


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for the currently logged-in user."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = get_password_hash(req.new_password)
    db.commit()

    # Revoke all refresh tokens (force re-login everywhere)
    revoke_all_user_tokens(db, current_user.id)

    return MessageResponse(message="Password changed successfully. Please log in again.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    req: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Request a password reset token. In production, this would send an email."""
    # Always return success to prevent email enumeration
    user = get_user_by_email(db, req.email)
    if user:
        token = _secrets.token_urlsafe(32)
        with _reset_lock:
            # Clean expired tokens
            now = _time.time()
            _reset_tokens.update({
                k: v for k, v in _reset_tokens.items()
                if v["expires"] > now
            })
            _reset_tokens[token] = {
                "user_id": user.id,
                "expires": now + RESET_TOKEN_EXPIRY
            }
        # In production: send email with reset link
        # For now: log it (visible in Docker logs)
        import logging
        logging.getLogger(__name__).info(f"Password reset token for {user.email}: {token}")

    return MessageResponse(message="If an account with that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    req: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reset password using a valid reset token."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    with _reset_lock:
        token_data = _reset_tokens.pop(req.token, None)

    if not token_data or token_data["expires"] < _time.time():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = get_password_hash(req.new_password)
    db.commit()

    # Revoke all sessions
    revoke_all_user_tokens(db, user.id)

    return MessageResponse(message="Password has been reset. You can now log in.")


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """Verify user's email address using a token."""
    user_id = decode_verification_token(request.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    from app.services.auth_service import get_user_by_id
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    if user.is_verified:
        return MessageResponse(message="Email is already verified")
        
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    db.commit()
    
    return MessageResponse(message="Email successfully verified")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """Resend the verification email to the user."""
    user = get_user_by_email(db, request.email)
    if not user:
        # Silently succeed to prevent email enumeration
        return MessageResponse(message="If the email exists, a verification link has been sent.")
        
    if user.is_verified:
        return MessageResponse(message="Email is already verified.")
        
    # Send verification email
    token = create_verification_token(user.id)
    email_service.send_verification_email(user.email, token)
    
    return MessageResponse(message="If the email exists, a verification link has been sent.")


# ============================================================================
# LEGACY: Token endpoint for OAuth2PasswordRequestForm compatibility
# This is used by the frontend's current login flow
# ============================================================================

@router.post("/token", response_model=TokenResponse)
def token_login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Legacy token endpoint for backward compatibility.
    Same as /login but mirrors OAuth2 standard path.
    """
    return login(response, form_data, db)

