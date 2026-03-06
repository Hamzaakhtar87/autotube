from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db import Base


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("User", back_populates="workspace", foreign_keys="User.workspace_id")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security
    tokens_revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Subscription fields
    subscription_tier = Column(String, default=SubscriptionTier.FREE)
    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_ends_at = Column(DateTime(timezone=True), nullable=True)
    
    # Usage tracking
    videos_generated_this_month = Column(Integer, default=0)
    usage_reset_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # User preferences for video generation
    preferences = Column(JSON, default={})
    
    # Admin flag
    is_admin = Column(Boolean, default=False)
    
    # Workspace/Tenant
    workspace_id = Column(Integer, ForeignKey("workspaces.id", use_alter=True, name="fk_user_workspace"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    youtube_accounts = relationship("YouTubeAccount", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    workspace = relationship("Workspace", back_populates="members", foreign_keys=[workspace_id])


class RefreshToken(Base):
    """Store refresh tokens for JWT authentication"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="refresh_tokens")


class YouTubeAccount(Base):
    __tablename__ = "youtube_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(String, unique=True, index=True)
    channel_name = Column(String)
    subscribers = Column(Integer, default=0)
    views = Column(Integer, default=0)
    credentials_json = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="youtube_accounts")
    stats = relationship("ChannelStats", back_populates="youtube_account", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for legacy jobs
    status = Column(String, default=JobStatus.PENDING)
    config = Column(JSON, default={})
    celery_task_id = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="jobs")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="job", cascade="all, delete-orphan")


class JobLog(Base):
    __tablename__ = "job_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    message = Column(Text)
    level = Column(String, default="INFO")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    job = relationship("Job", back_populates="logs")


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    path = Column(String)
    youtube_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    status = Column(String)  # generated, uploaded, scheduled
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    job = relationship("Job", back_populates="videos")
    stats = relationship("VideoStats", back_populates="video", cascade="all, delete-orphan")


# ============================================================================
# YOUTUBE STATS MODELS (Phase 3)
# ============================================================================

class ChannelStats(Base):
    """Historical channel statistics for analytics"""
    __tablename__ = "channel_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    youtube_account_id = Column(Integer, ForeignKey("youtube_accounts.id"), nullable=False)
    subscribers = Column(Integer, default=0)
    total_views = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    youtube_account = relationship("YouTubeAccount", back_populates="stats")


class VideoStats(Base):
    """Historical video statistics for analytics"""
    __tablename__ = "video_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    watch_time_hours = Column(Float, default=0.0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video", back_populates="stats")


class CompetitorChannel(Base):
    """Tracking competitor metrics"""
    __tablename__ = "competitor_channels"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_url = Column(String, nullable=False)
    custom_name = Column(String, nullable=True)
    
    # Snapshot data
    subscribers = Column(Integer, default=0)
    total_views = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    recent_videos_data = Column(JSON, default=[])
    
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")
