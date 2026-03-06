"""
Admin API Endpoints
Platform management, user admin, system health, and analytics.
Only accessible to users with is_admin=True.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import User, Job, JobStatus, Video, SubscriptionTier
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/admin")


# ============================================================================
# ADMIN DEPENDENCY
# ============================================================================

def require_admin(current_user: User = Depends(get_current_user)):
    """Reject non-admin users."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class PlatformStatsResponse(BaseModel):
    total_users: int
    active_users_30d: int
    total_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_videos: int
    users_by_tier: dict


class UserAdminResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    subscription_tier: str
    videos_generated_this_month: int
    created_at: datetime
    total_jobs: int
    total_videos: int

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    subscription_tier: Optional[str] = None


class RecentJobAdmin(BaseModel):
    id: int
    user_email: str
    status: str
    video_count: Optional[int]
    created_at: datetime


# ============================================================================
# PLATFORM STATS
# ============================================================================

@router.get("/stats", response_model=PlatformStatsResponse)
def get_platform_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Platform-wide statistics for the admin dashboard."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(
        User.created_at >= thirty_days_ago
    ).scalar()

    total_jobs = db.query(func.count(Job.id)).scalar()
    running_jobs = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
    ).scalar()
    completed_jobs = db.query(func.count(Job.id)).filter(
        Job.status == JobStatus.COMPLETED
    ).scalar()
    failed_jobs = db.query(func.count(Job.id)).filter(
        Job.status == JobStatus.FAILED
    ).scalar()

    total_videos = db.query(func.count(Video.id)).scalar()

    # Users grouped by subscription tier
    tier_counts = db.query(
        User.subscription_tier, func.count(User.id)
    ).group_by(User.subscription_tier).all()
    
    users_by_tier = {tier: count for tier, count in tier_counts}

    return PlatformStatsResponse(
        total_users=total_users,
        active_users_30d=active_users,
        total_jobs=total_jobs,
        running_jobs=running_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        total_videos=total_videos,
        users_by_tier=users_by_tier
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=List[UserAdminResponse])
def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    tier: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users with filtering and search."""
    query = db.query(User)

    if search:
        query = query.filter(
            User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        )

    if tier:
        query = query.filter(User.subscription_tier == tier)

    users = query.order_by(User.id.desc()).offset(skip).limit(limit).all()

    result = []
    for user in users:
        job_count = db.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar()
        video_count = db.query(func.count(Video.id)).join(Job).filter(Job.user_id == user.id).scalar()
        result.append(UserAdminResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_admin=user.is_admin,
            subscription_tier=user.subscription_tier,
            videos_generated_this_month=user.videos_generated_this_month,
            created_at=user.created_at,
            total_jobs=job_count,
            total_videos=video_count
        ))

    return result


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    updates: UserUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a user's admin status, active status, or subscription tier."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if updates.is_active is not None:
        user.is_active = updates.is_active
    if updates.is_admin is not None:
        user.is_admin = updates.is_admin
    if updates.subscription_tier is not None:
        try:
            SubscriptionTier(updates.subscription_tier)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
        user.subscription_tier = updates.subscription_tier

    db.commit()
    return {"message": f"User {user.email} updated"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user and all their data."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} and all associated data deleted"}


# ============================================================================
# RECENT JOBS (platform-wide)
# ============================================================================

@router.get("/jobs", response_model=List[RecentJobAdmin])
def list_all_jobs(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all jobs across all users (admin view)."""
    query = db.query(Job).join(User)

    if status_filter:
        query = query.filter(Job.status == status_filter)

    jobs = query.order_by(Job.id.desc()).offset(skip).limit(limit).all()

    return [
        RecentJobAdmin(
            id=job.id,
            user_email=job.user.email if job.user else "unknown",
            status=job.status,
            video_count=job.config.get("video_count") if job.config else None,
            created_at=job.created_at
        )
        for job in jobs
    ]


# ============================================================================
# SYSTEM HEALTH
# ============================================================================

@router.get("/health")
def admin_health(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Detailed system health check."""
    import psutil

    # DB check
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Redis check
    redis_ok = False
    try:
        from app.worker import celery
        celery.control.ping(timeout=2)
        redis_ok = True
    except Exception:
        pass

    # System resources
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()

    return {
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "cpu_percent": cpu,
        "memory_used_percent": memory.percent,
        "memory_available_gb": round(memory.available / (1024 ** 3), 2),
        "disk_percent": psutil.disk_usage("/").percent,
    }
