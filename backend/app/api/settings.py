from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import os
import json
from google_auth_oauthlib.flow import Flow
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.core import config
from app.db import get_db
from app.models.models import User, YouTubeAccount
from app.services.auth_service import get_current_user, oauth2_scheme, decode_access_token, get_user_by_id

router = APIRouter()

# Auto-detect: Docker uses /app/core, local dev uses relative path
_DOCKER_CORE = "/app/core"
_LOCAL_CORE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "core"))
CORE_DIR = _DOCKER_CORE if os.path.isdir(_DOCKER_CORE) else _LOCAL_CORE
SECRETS_FILE = os.path.join(CORE_DIR, "client_secrets.json")
# CREDENTIALS_FILE is no longer used globally; credentials are stored in DB per user.

class ConfigStatus(BaseModel):
    has_client_secrets: bool
    has_credentials: bool
    gemini_key_configured: bool
    pexels_key_configured: bool
    is_admin: bool = False

from pydantic import BaseModel, Field

class APIKeys(BaseModel):
    pexels_key: str
    gemini_key: str

class UserPreferences(BaseModel):
    voice: str = Field("en-US-GuyNeural", pattern=r"^[a-zA-Z0-9_\-]+$")
    niche: str = Field("psychology", pattern=r"^[a-zA-Z0-9 _,.!\-?'\"]*$", max_length=150)
    default_video_count: int = Field(7, ge=1, le=10)
    bg_music: str = Field("random", pattern=r"^[a-zA-Z0-9_\-]+$")
    bg_music_volume: float = Field(0.15, ge=0.0, le=1.0)
    video_format: str = Field("short", pattern=r"^(short|long)$")
    custom_topic: str = Field("", pattern=r"^[a-zA-Z0-9 _,.!\-?'\"]*$", max_length=150)
    custom_niche: str = Field("", pattern=r"^[a-zA-Z0-9 _,.!\-?'\"]*$", max_length=150)
    channel_style: str = Field("narration", pattern=r"^[a-zA-Z0-9_\-]+$")
    tone: str = Field("serious", pattern=r"^[a-zA-Z0-9_\-]+$")
    output_action: str = Field("generate_only", pattern=r"^(generate_only|auto_publish|schedule)$")
    schedule_datetime: str = Field("", max_length=100)

@router.get("/config/status", response_model=ConfigStatus)
def get_config_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    has_secrets = os.path.exists(SECRETS_FILE)
    
    # Check if user has a connected YouTube account
    user_account = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == current_user.id).first()
    has_creds = bool(user_account and user_account.credentials_json)
    
    # Check env vars
    gemini = bool(os.getenv("GEMINI_API_KEY"))
    pexels = bool(os.getenv("PEXELS_API_KEY"))
    
    return {
        "has_client_secrets": has_secrets,
        "has_credentials": has_creds,
        "gemini_key_configured": gemini,
        "pexels_key_configured": pexels,
        "is_admin": bool(getattr(current_user, 'is_admin', False))
    }

@router.get("/config/preferences")
def get_preferences(current_user: User = Depends(get_current_user)):
    """Get user's video generation preferences."""
    prefs = current_user.preferences or {}
    return {
        "voice": prefs.get("voice", "en-US-GuyNeural"),
        "niche": prefs.get("niche", "psychology"),
        "default_video_count": prefs.get("default_video_count", 7),
        "bg_music": prefs.get("bg_music", "random"),
        "bg_music_volume": prefs.get("bg_music_volume", 0.15),
        "video_format": prefs.get("video_format", "short"),
        "custom_topic": prefs.get("custom_topic", ""),
        "custom_niche": prefs.get("custom_niche", ""),
        "channel_style": prefs.get("channel_style", "narration"),
        "tone": prefs.get("tone", "serious"),
        "output_action": prefs.get("output_action", "generate_only"),
        "schedule_datetime": prefs.get("schedule_datetime", ""),
    }

@router.post("/config/preferences")
def save_preferences(
    prefs: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save user's video generation preferences."""
    current_user.preferences = prefs.dict()
    db.commit()
    return {"status": "saved"}

@router.get("/config/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    """Get user profile info."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "subscription_tier": current_user.subscription_tier,
        "is_admin": bool(getattr(current_user, 'is_admin', False)),
        "videos_generated_this_month": current_user.videos_generated_this_month,
        "created_at": current_user.created_at,
    }

@router.post("/config/secrets")
async def upload_secrets(request: Request):
    # This is still global/admin level for now, as client_secrets is app-wide
    try:
        data = await request.json()
        # Validate format roughly
        if "web" not in data and "installed" not in data:
             raise ValueError("Invalid client_secrets.json format")

        with open(SECRETS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/config/keys")
def update_keys(keys: APIKeys):
    """Update API keys at runtime."""
    os.environ["PEXELS_API_KEY"] = keys.pexels_key
    os.environ["GEMINI_API_KEY"] = keys.gemini_key
    return {"status": "updated"}

# OAuth Flow

@router.get("/auth/youtube/url")
def get_google_auth_url(token: str = Depends(oauth2_scheme)):
    if not os.path.exists(SECRETS_FILE):
        raise HTTPException(status_code=400, detail="client_secrets.json missing. Admin must upload it first.")
        
    try:
        flow = Flow.from_client_secrets_file(
            SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly'],
            redirect_uri=f"{os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:8000')}/auth/youtube/callback"
        )
        
        # Use offline access to get refresh token, pass JWT token as state
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true',
            state=token
        )
        return {"url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/youtube/callback")
def google_auth_callback(
    code: str, 
    state: str = None,
    error: str = None, 
    db: Session = Depends(get_db)
):
    if error:
        raise HTTPException(status_code=400, detail=error)
        
    if not state:
        raise HTTPException(status_code=401, detail="Missing state token in callback")
        
    payload = decode_access_token(state)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid state token authentication")
        
    user_id_str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")
    current_user = get_user_by_id(db, user_id)
    if not current_user:
        raise HTTPException(status_code=401, detail="User not found")
        
    if not os.path.exists(SECRETS_FILE):
        raise HTTPException(status_code=400, detail="client_secrets.json missing")
    
    try:
        flow = Flow.from_client_secrets_file(
            SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly'],
            redirect_uri=f"{os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:8000')}/auth/youtube/callback",
            state=state
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save or Update YouTubeAccount for User
        account = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == current_user.id).first()
        if not account:
            account = YouTubeAccount(user_id=current_user.id)
            db.add(account)
        
        from app.core.security import encrypt_dict
        account.credentials_json = encrypt_dict(json.loads(creds.to_json()))
        account.updated_at = datetime.utcnow()
        
        # Try to fetch channel info immediately if possible? 
        # For now just save credentials.
        
        db.commit()
            
        frontend_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
        return RedirectResponse(f"{frontend_url}/settings?success=true")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/youtube/disconnect")
def disconnect_youtube(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect the user's YouTube account."""
    account = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == current_user.id).first()
    if account:
        db.delete(account)
        db.commit()
    return {"status": "disconnected"}


