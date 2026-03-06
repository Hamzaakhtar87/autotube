"""
Jobs API Endpoints
Handles video generation job creation, monitoring, and management.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.models import Job, JobStatus, JobLog, User
from app.worker import run_batch_task
from app.services.auth_service import (
    get_current_user,
    get_current_user_optional,
    can_create_video,
    increment_video_usage,
    reset_monthly_usage_if_needed,
    get_tier_limit,
)


router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

from pydantic import BaseModel, Field

class JobCreate(BaseModel):
    test_mode: bool = False  # Legacy/simple toggle
    videos_count: int = Field(7, ge=1, le=10)
    output_action: str = Field("generate_only", pattern=r"^(generate_only|auto_publish|schedule)$")
    video_format: str = Field("short", pattern=r"^(short|long)$")
    schedule_datetime: str = Field("", max_length=100)


class JobLogResponse(BaseModel):
    timestamp: datetime
    level: str
    message: str
    
    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    videos_count: Optional[int] = None
    test_mode: Optional[bool] = None
    
    class Config:
        from_attributes = True


class JobDetailResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    config: dict
    logs: List[JobLogResponse]


class UsageResponse(BaseModel):
    videos_generated_this_month: int
    videos_limit: int
    can_create_video: bool
    subscription_tier: str


# ============================================================================
# JOB ENDPOINTS
# ============================================================================

@router.post("/jobs", response_model=JobResponse)
def create_job(
    job_in: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new video generation job."""
    # Check and reset monthly usage if needed
    reset_monthly_usage_if_needed(db, current_user)
    
    # Check quota
    if not can_create_video(current_user):
        tier_limit = get_tier_limit(current_user.subscription_tier)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly video limit reached ({tier_limit} videos). Upgrade your plan to generate more videos."
        )

    # SECURE: Prevent Celery Queue Exhaustion (Exploit 10)
    # Ensure users cannot spam the broker with thousands of background tasks
    active_jobs = db.query(Job).filter(
        Job.user_id == current_user.id,
        Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
    ).count()
    
    max_concurrent_jobs = 1 if current_user.subscription_tier == "free" else (3 if current_user.subscription_tier == "pro" else 10)
    if active_jobs >= max_concurrent_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You already have {active_jobs} active job(s) in the queue. Please wait for them to finish before submitting more."
        )
    
    # Enforce video count limits based on tier
    max_videos_per_job = min(job_in.videos_count, 7)  # Cap at 7 per job
    remaining_quota = get_tier_limit(current_user.subscription_tier) - current_user.videos_generated_this_month
    videos_to_generate = min(max_videos_per_job, remaining_quota) if remaining_quota < 999999 else max_videos_per_job
    
    # Derive test_mode from output_action (generate_only = no upload)
    effective_test_mode = job_in.output_action == "generate_only"
    
    # Create job
    new_job = Job(
        user_id=current_user.id,
        status=JobStatus.PENDING,
        config={
            "test_mode": effective_test_mode,
            "video_count": videos_to_generate,
            "schedule_batch": videos_to_generate >= 7,
            "start_date": datetime.utcnow().isoformat(),
            "output_action": job_in.output_action,
            "video_format": job_in.video_format,
            "schedule_datetime": job_in.schedule_datetime,
        }
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Trigger Celery task
    try:
        task = run_batch_task.delay(new_job.id, effective_test_mode)
        new_job.celery_task_id = task.id
        db.commit()
    except Exception as e:
        # Redis/Celery not available — job is created but can't be dispatched
        from app.models.models import JobLog
        log = JobLog(job_id=new_job.id, level="ERROR", message=f"⚠️ Worker dispatch failed: {str(e)[:200]}. Is Redis/Celery running?")
        db.add(log)
        new_job.status = JobStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video worker is not available. Please ensure Redis and Celery are running."
        )
    
    # Increment usage (reserve quota)
    for _ in range(videos_to_generate):
        increment_video_usage(db, current_user)
    
    return JobResponse(
        id=new_job.id,
        status=new_job.status,
        created_at=new_job.created_at,
        updated_at=new_job.updated_at,
        videos_count=videos_to_generate,
        test_mode=job_in.test_mode
    )


@router.post("/jobs/{job_id}/stop")
def stop_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop a running job."""
    from sqlalchemy import or_
    job = db.query(Job).join(User, Job.user_id == User.id).filter(
        Job.id == job_id,
        or_(
            Job.user_id == current_user.id,
            (User.workspace_id == current_user.workspace_id) & (current_user.workspace_id != None)
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.RUNNING, JobStatus.PENDING]:
        return {"message": "Job is not running"}

    # Revoke Celery task
    if job.celery_task_id:
        from app.worker import celery
        celery.control.revoke(job.celery_task_id, terminate=True, signal='SIGKILL')
        
    # Update status
    job.status = JobStatus.FAILED
    new_log = JobLog(job_id=job.id, level="ERROR", message="🚫 Job stopped by user")
    db.add(new_log)
    db.commit()
    
    return {"message": "Job stopped successfully"}


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all jobs for the current user."""
    from sqlalchemy import or_
    jobs = db.query(Job).join(User, Job.user_id == User.id).filter(
        or_(
            Job.user_id == current_user.id,
            (User.workspace_id == current_user.workspace_id) & (current_user.workspace_id != None)
        )
    ).order_by(Job.id.desc()).offset(skip).limit(limit).all()
    
    return [
        JobResponse(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            videos_count=job.config.get("video_count") if job.config else None,
            test_mode=job.config.get("test_mode") if job.config else None
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}")
def get_job_details(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific job."""
    from sqlalchemy import or_
    job = db.query(Job).join(User, Job.user_id == User.id).options(
        joinedload(Job.logs)
    ).filter(
        Job.id == job_id,
        or_(
            Job.user_id == current_user.id,
            (User.workspace_id == current_user.workspace_id) & (current_user.workspace_id != None)
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "config": job.config,
        "logs": [
            {
                "timestamp": log.timestamp,
                "level": log.level,
                "message": log.message
            }
            for log in sorted(job.logs, key=lambda x: x.id)
        ]
    }


# ============================================================================
# USAGE ENDPOINTS
# ============================================================================

@router.get("/usage", response_model=UsageResponse)
def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current usage statistics for the user."""
    reset_monthly_usage_if_needed(db, current_user)
    
    return UsageResponse(
        videos_generated_this_month=current_user.videos_generated_this_month,
        videos_limit=get_tier_limit(current_user.subscription_tier),
        can_create_video=can_create_video(current_user),
        subscription_tier=current_user.subscription_tier
    )

