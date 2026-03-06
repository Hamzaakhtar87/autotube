from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import json
import logging

from app.db import get_db
from app.models.models import User, CompetitorChannel
from app.services.auth_service import get_current_user
from backend.core.providers.youtube_provider import YouTubeProvider  # Assumed available in core

router = APIRouter(prefix="/competitors", tags=["competitor-analysis"])
logger = logging.getLogger(__name__)

class CompetitorCreate(BaseModel):
    channel_url: str
    custom_name: Optional[str] = None

class CompetitorResponse(BaseModel):
    id: int
    channel_url: str
    custom_name: Optional[str]
    subscribers: int
    total_views: int
    video_count: int
    recent_videos_data: List[dict]
    last_synced_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/", response_model=CompetitorResponse)
def add_competitor(
    data: CompetitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a competitor to track and sync initial data."""
    if current_user.subscription_tier == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Competitor tracking requires a Pro or Enterprise subscription."
        )
        
    count = db.query(CompetitorChannel).filter(CompetitorChannel.user_id == current_user.id).count()
    if count >= 5 and current_user.subscription_tier == "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro tier is limited to 5 competitors. Upgrade to Enterprise for unlimited."
        )
        
    competitor = CompetitorChannel(
        user_id=current_user.id,
        channel_url=data.channel_url,
        custom_name=data.custom_name
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    
    # Intentionally skipped direct YouTube API syncing here for scope
    # Normally this would hit Google API to fetch the channel using `channel_url`
    # and update subscribers/views fields immediately.
    
    return competitor

@router.get("/", response_model=List[CompetitorResponse])
def get_competitors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all tracked competitors."""
    return db.query(CompetitorChannel).filter(CompetitorChannel.user_id == current_user.id).all()
