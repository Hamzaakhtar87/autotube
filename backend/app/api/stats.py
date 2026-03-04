"""
YouTube Stats API
Endpoints for retrieving and syncing YouTube analytics.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.models import User, YouTubeAccount, ChannelStats, Video, VideoStats
from app.services.auth_service import get_current_user
from app.services.youtube_service import sync_channel_stats

router = APIRouter()


class ChannelStatsResponse(BaseModel):
    channel_name: Optional[str]
    subscribers: int
    total_views: int
    video_count: int
    last_updated: Optional[datetime]
    
    class Config:
        from_attributes = True


class VideoStatsResponse(BaseModel):
    title: Optional[str]
    youtube_id: Optional[str]
    views: int
    likes: int
    comments: int
    published_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@router.post("/sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger a background sync of YouTube statistics."""
    # We run this in background to not block the request
    # Note: We need a new DB session for the background task usually, 
    # but here we pass the user ID and re-fetch in task?
    # Or just run it synchronously for simple MVP if it's fast enough.
    # For now, let's run it synchronously to catch auth errors immediately 
    # since we don't have a complex worker setup for this specific task yet.
    # If it's slow, we'll move to Celery.
    
    try:
        sync_channel_stats(db, current_user)
        return {"status": "success", "message": "Stats synced successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overview", response_model=List[ChannelStatsResponse])
def get_channel_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overview stats for all connected channels."""
    accounts = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == current_user.id).all()
    
    return [
        ChannelStatsResponse(
            channel_name=acc.channel_name,
            subscribers=acc.subscribers or 0,
            total_views=acc.views or 0,
            video_count=0, # access from latest stats history if needed
            last_updated=acc.updated_at
        )
        for acc in accounts
    ]


@router.get("/videos", response_model=List[VideoStatsResponse])
def get_video_performance(
    skip: int = 0, 
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get performance stats for generated videos."""
    # Join with Job to filter by user
    videos = db.query(Video).join(Video.job).filter(
        Video.job.has(user_id=current_user.id),
        Video.youtube_id.isnot(None)
    ).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for vid in videos:
        # Get latest stats
        latest_stat = db.query(VideoStats).filter(
            VideoStats.video_id == vid.id
        ).order_by(VideoStats.recorded_at.desc()).first()
        
        results.append(VideoStatsResponse(
            title=vid.title or "Untitled",
            youtube_id=vid.youtube_id,
            views=latest_stat.views if latest_stat else 0,
            likes=latest_stat.likes if latest_stat else 0,
            comments=latest_stat.comments if latest_stat else 0,
            published_at=vid.created_at
        ))
        
    return results

