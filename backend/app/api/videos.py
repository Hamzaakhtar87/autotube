"""
Videos API Endpoints
Serves generated local video files securely.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import os
import logging

from app.db import get_db
from app.models.models import User, Video, Job
from app.services.auth_service import get_current_user
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/{video_id}/download")
def download_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Securely download a video, ensuring the user owns the video or shares a workspace."""
    
    # Authenticate and retrieve video record
    video = db.query(Video).join(Job).join(User, Job.user_id == User.id).filter(
        Video.id == video_id,
        or_(
            Job.user_id == current_user.id,
            (User.workspace_id == current_user.workspace_id) & (current_user.workspace_id != None)
        )
    ).first()

    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found or access denied")

    if not video.path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file path not registered")

    # SECURE: Prevent Unauthenticated File Traversal (Exploit 11)
    # Ensure the requested video path actually resides inside our configured OUTPUT_DIR
    target_path = os.path.abspath(video.path)
    safe_dir = os.path.abspath(OUTPUT_DIR)
    
    if not target_path.startswith(safe_dir):
        logger.warning(f"SECURITY ALERT: User {current_user.id} attempted directory traversal on video {video_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid file path detected.")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File no longer exists on disk")

    file_name = os.path.basename(target_path)
    return FileResponse(
        path=target_path,
        filename=f"autotube_{file_name}",
        media_type="video/mp4"
    )
