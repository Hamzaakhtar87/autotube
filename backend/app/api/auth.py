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
)


router = APIRouter(prefix="/auth")


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


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
    
    # TODO: Send verification email
    
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

